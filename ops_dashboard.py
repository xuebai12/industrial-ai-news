#!/usr/bin/env python3
"""Build run-summary dashboard and emit alert emails on threshold breaches."""

from __future__ import annotations

import argparse
import glob
import json
import os
import smtplib
from datetime import date
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv


def load_summaries(output_dir: str, days: int) -> list[dict]:
    paths = sorted(glob.glob(os.path.join(output_dir, "run-summary-*.json")))
    selected = paths[-days:] if days > 0 else paths
    summaries: list[dict] = []
    for path in selected:
        try:
            with open(path, encoding="utf-8") as f:
                summaries.append(json.load(f))
        except Exception:
            continue
    return summaries


def evaluate_alerts(latest: dict) -> list[str]:
    alerts: list[str] = []
    if not latest:
        return ["No run summary found for evaluation."]

    if not latest.get("success", False):
        alerts.append(f"Run not successful: {latest.get('exit_reason', 'unknown reason')}")
    if int(latest.get("scraped_count", 0) or 0) == 0:
        alerts.append("scraped_count is 0")
    if int(latest.get("relevant_count", 0) or 0) == 0:
        alerts.append("relevant_count is 0")
    if int(latest.get("analyzed_count", 0) or 0) == 0:
        alerts.append("analyzed_count is 0")

    output_mode = str(latest.get("output", ""))
    if output_mode in ("email", "both") and not bool(latest.get("email_sent", False)):
        alerts.append("email_sent is false for email/both mode")

    analyzed = int(latest.get("analyzed_count", 0) or 0)
    notion_pushed = int(latest.get("notion_pushed", 0) or 0)
    if output_mode in ("notion", "both") and analyzed > 0 and notion_pushed == 0:
        alerts.append("notion_pushed is 0 while analyzed_count > 0")

    return alerts


def write_dashboard(output_dir: str, summaries: list[dict], alerts: list[str]) -> tuple[str, str]:
    today = date.today().strftime("%Y-%m-%d")
    latest = summaries[-1] if summaries else {}

    payload = {
        "generated_at": today,
        "window_days": len(summaries),
        "latest": latest,
        "alerts": alerts,
        "history": summaries,
    }

    json_path = os.path.join(output_dir, "ops-dashboard.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    lines = [
        f"# Ops Dashboard ({today})",
        "",
        f"- Window: {len(summaries)} run(s)",
        f"- Alerts: {len(alerts)}",
        "",
        "## Latest Run",
    ]
    if latest:
        lines.extend(
            [
                f"- run_id: {latest.get('run_id', '')}",
                f"- date: {latest.get('date', '')}",
                f"- output: {latest.get('output', '')}",
                f"- success: {latest.get('success', False)}",
                f"- exit_reason: {latest.get('exit_reason', '')}",
                f"- scraped: {latest.get('scraped_count', 0)}",
                f"- relevant: {latest.get('relevant_count', 0)}",
                f"- analyzed: {latest.get('analyzed_count', 0)}",
                f"- email_sent: {latest.get('email_sent', False)}",
                f"- notion_pushed: {latest.get('notion_pushed', 0)}",
            ]
        )
    else:
        lines.append("- No run summaries found.")

    lines.append("")
    lines.append("## Alerts")
    if alerts:
        for item in alerts:
            lines.append(f"- {item}")
    else:
        lines.append("- None")

    lines.append("")
    lines.append("## Recent Runs")
    for item in reversed(summaries):
        lines.append(
            "- "
            f"{item.get('date', '')} | {item.get('run_id', '')} | "
            f"success={item.get('success', False)} | scraped={item.get('scraped_count', 0)} "
            f"relevant={item.get('relevant_count', 0)} analyzed={item.get('analyzed_count', 0)} "
            f"notion={item.get('notion_pushed', 0)} email={item.get('email_sent', False)} "
            f"reason={item.get('exit_reason', '')}"
        )

    md_path = os.path.join(output_dir, "ops-dashboard.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return json_path, md_path


def maybe_send_alert_email(alerts: list[str], latest: dict) -> bool:
    if not alerts:
        return False

    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", "587") or "587")
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")
    email_from = os.getenv("EMAIL_FROM", "") or smtp_user
    email_to = os.getenv("ALERT_EMAIL_TO", "") or os.getenv("EMAIL_TO", "")
    if not all([smtp_host, smtp_user, smtp_pass, email_to]):
        return False

    subject = f"[ALERT] Industrial AI pipeline {latest.get('date', '')}"
    body = "\n".join(
        [
            "Pipeline alert triggered by threshold checks:",
            "",
            *[f"- {item}" for item in alerts],
            "",
            "Latest run summary:",
            json.dumps(latest, ensure_ascii=False, indent=2),
        ]
    )
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = email_from
    msg["To"] = email_to

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(email_from, email_to.split(","), msg.as_string())
        return True
    except Exception:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Build run dashboard and emit alerts.")
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--send-alert-email", action="store_true")
    args = parser.parse_args()

    load_dotenv()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    summaries = load_summaries(str(output_dir), args.days)
    latest = summaries[-1] if summaries else {}
    alerts = evaluate_alerts(latest)
    json_path, md_path = write_dashboard(str(output_dir), summaries, alerts)

    sent = False
    if args.send_alert_email:
        sent = maybe_send_alert_email(alerts, latest)

    print(f"dashboard_json={json_path}")
    print(f"dashboard_md={md_path}")
    print(f"alerts={len(alerts)}")
    print(f"alert_email_sent={sent}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
