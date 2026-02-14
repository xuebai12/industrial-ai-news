#!/usr/bin/env python3
"""Build weekly-style feedback report from Notion feedback JSON."""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
from collections import defaultdict
from datetime import datetime


def latest_feedback_file(output_dir: str) -> str | None:
    files = sorted(glob.glob(os.path.join(output_dir, "feedback-*.json")))
    return files[-1] if files else None


def _to_score(v) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except Exception:
        return None


def _split_tags(v) -> list[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    text = str(v)
    parts = re.split(r"[,;，；、/|]", text)
    return [p.strip() for p in parts if p.strip()]


def _bucket(scores: list[float]) -> dict:
    if not scores:
        return {"count": 0, "avg": 0.0, "high_rate": 0.0, "low_rate": 0.0}
    n = len(scores)
    high = sum(1 for s in scores if s >= 4)
    low = sum(1 for s in scores if s <= 2)
    return {
        "count": n,
        "avg": round(sum(scores) / n, 3),
        "high_rate": round(high / n, 3),
        "low_rate": round(low / n, 3),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build feedback report from feedback JSON")
    parser.add_argument("--input", default="", help="Path to feedback-YYYY-MM-DD.json")
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--min-samples", type=int, default=3)
    args = parser.parse_args()

    input_path = args.input or latest_feedback_file(args.output_dir)
    if not input_path:
        raise SystemExit("No feedback file found. Run fetch_notion_feedback.py first.")

    with open(input_path, encoding="utf-8") as f:
        payload = json.load(f)

    records = payload.get("records", [])
    scored_records = []
    for r in records:
        s = _to_score(r.get("score"))
        if s is None:
            continue
        row = dict(r)
        row["_score"] = s
        scored_records.append(row)

    by_source: dict[str, list[float]] = defaultdict(list)
    by_category: dict[str, list[float]] = defaultdict(list)
    by_keyword: dict[str, list[float]] = defaultdict(list)

    for r in scored_records:
        score = r["_score"]
        source = str(r.get("source") or "Unknown").strip()
        category = str(r.get("category") or "Unknown").strip()
        by_source[source].append(score)
        by_category[category].append(score)
        for tag in _split_tags(r.get("core_tech")):
            by_keyword[tag].append(score)

    source_stats = [
        {"name": name, **_bucket(vals)}
        for name, vals in by_source.items()
        if len(vals) >= args.min_samples
    ]
    source_stats.sort(key=lambda x: (x["avg"], x["high_rate"], x["count"]), reverse=True)

    category_stats = [
        {"name": name, **_bucket(vals)}
        for name, vals in by_category.items()
        if len(vals) >= args.min_samples
    ]
    category_stats.sort(key=lambda x: (x["avg"], x["high_rate"], x["count"]), reverse=True)

    keyword_stats = [
        {"name": name, **_bucket(vals)}
        for name, vals in by_keyword.items()
        if len(vals) >= args.min_samples
    ]
    keyword_stats.sort(key=lambda x: (x["avg"], x["high_rate"], x["count"]), reverse=True)

    total = len(records)
    rated = len(scored_records)
    coverage = round((rated / total), 3) if total else 0.0

    ts = datetime.now().strftime("%Y-%m-%d")
    os.makedirs(args.output_dir, exist_ok=True)
    out_json = os.path.join(args.output_dir, f"feedback-report-{ts}.json")
    out_md = os.path.join(args.output_dir, f"feedback-report-{ts}.md")

    report = {
        "generated_at": datetime.now().isoformat(),
        "input": input_path,
        "total_records": total,
        "rated_records": rated,
        "rating_coverage": coverage,
        "source_stats": source_stats,
        "category_stats": category_stats,
        "keyword_stats": keyword_stats,
    }

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    lines: list[str] = []
    lines.append(f"# Feedback Report ({ts})")
    lines.append("")
    lines.append(f"- Input: `{input_path}`")
    lines.append(f"- Total records: **{total}**")
    lines.append(f"- Rated records: **{rated}**")
    lines.append(f"- Rating coverage: **{coverage:.1%}**")
    lines.append("")

    lines.append("## Source Performance")
    if source_stats:
        lines.append("| Source | Count | Avg | High(>=4) | Low(<=2) |")
        lines.append("|---|---:|---:|---:|---:|")
        for x in source_stats:
            lines.append(
                f"| {x['name']} | {x['count']} | {x['avg']:.2f} | {x['high_rate']:.1%} | {x['low_rate']:.1%} |"
            )
    else:
        lines.append("No source has enough samples.")
    lines.append("")

    lines.append("## Category Performance")
    if category_stats:
        lines.append("| Category | Count | Avg | High(>=4) | Low(<=2) |")
        lines.append("|---|---:|---:|---:|---:|")
        for x in category_stats:
            lines.append(
                f"| {x['name']} | {x['count']} | {x['avg']:.2f} | {x['high_rate']:.1%} | {x['low_rate']:.1%} |"
            )
    else:
        lines.append("No category has enough samples.")
    lines.append("")

    lines.append("## Keyword Signals")
    if keyword_stats:
        lines.append("| Keyword | Count | Avg | High(>=4) | Low(<=2) |")
        lines.append("|---|---:|---:|---:|---:|")
        for x in keyword_stats[:30]:
            lines.append(
                f"| {x['name']} | {x['count']} | {x['avg']:.2f} | {x['high_rate']:.1%} | {x['low_rate']:.1%} |"
            )
    else:
        lines.append("No keyword has enough samples.")
    lines.append("")

    lines.append("## Suggested Next Adjustments")
    lines.append("- Promote sources with high avg + high-rate and enough samples.")
    lines.append("- Demote sources with low avg + high low-rate.")
    lines.append("- Add high-performing keywords to HIGH_PRIORITY_KEYWORDS.")
    lines.append("- Remove/downgrade consistently low-performing keywords.")

    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"report_json={out_json}")
    print(f"report_md={out_md}")
    print(f"rated={rated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
