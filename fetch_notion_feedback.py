#!/usr/bin/env python3
"""Fetch rated article feedback from Notion database into local JSON."""

from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, timedelta

from dotenv import load_dotenv
from notion_client import Client

PREFERRED_NAMES = {
    "score": ["评分", "Score", "score"],
    "source": ["来源/机构", "来源", "Source", "source"],
    "category": ["类别", "Category", "category"],
    "title": ["标题", "Title", "title"],
    "url": ["原文链接", "URL", "url", "Link", "Source URL"],
    "date": ["日期", "Date", "date"],
}


def _lower_map(schema: dict) -> dict[str, str]:
    return {k.lower(): k for k in schema}


def find_property(schema: dict, prop_type: str, preferred: list[str]) -> str | None:
    by_lower = _lower_map(schema)
    for name in preferred:
        actual = by_lower.get(name.lower())
        if actual and schema.get(actual, {}).get("type") == prop_type:
            return actual
    for name, meta in schema.items():
        if meta.get("type") == prop_type:
            return name
    return None


def parse_property_value(prop: dict, prop_type: str):
    if not prop:
        return None
    if prop_type == "number":
        return prop.get("number")
    if prop_type == "select":
        val = prop.get("select") or {}
        return val.get("name")
    if prop_type == "multi_select":
        return [x.get("name", "") for x in (prop.get("multi_select") or []) if x.get("name")]
    if prop_type == "title":
        parts = prop.get("title") or []
        return "".join(p.get("plain_text", "") for p in parts).strip()
    if prop_type == "rich_text":
        parts = prop.get("rich_text") or []
        return "".join(p.get("plain_text", "") for p in parts).strip()
    if prop_type == "url":
        return prop.get("url")
    if prop_type == "date":
        d = prop.get("date") or {}
        return d.get("start")
    return None


def _notion_request(method: str, path: str, api_key: str, body: dict | None = None) -> dict:
    url = f"https://api.notion.com/v1/{path}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }
    timeout = httpx.Timeout(30.0)
    try:
        if method.upper() == "GET":
            resp = httpx.get(url, headers=headers, params=body, timeout=timeout)
        else:
            resp = httpx.post(url, headers=headers, json=body, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        print(f"DEBUG: HTTP Error {e.response.status_code}: {e.response.text}")
        raise

def fetch_all_pages(api_key: str, database_id: str, date_prop: str | None, since: str | None) -> list[dict]:
    rows: list[dict] = []
    start_cursor = None
    while True:
        body: dict = {"page_size": 100}
        if start_cursor:
            body["start_cursor"] = start_cursor
        if date_prop and since:
            body["filter"] = {
                "property": date_prop,
                "date": {"on_or_after": since},
            }

        resp = _notion_request("POST", f"databases/{database_id}/query", api_key, body)
        rows.extend(resp.get("results", []))
        if not resp.get("has_more"):
            break
        start_cursor = resp.get("next_cursor")
    return rows


import uuid
import traceback
import httpx

def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch Notion ratings to local JSON")
    parser.add_argument("--days", type=int, default=30, help="Lookback days for date filter")
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--include-unrated", action="store_true", help="Keep rows without score")
    args = parser.parse_args()

    # Check for proxy vars (debug)
    for k, v in os.environ.items():
        if "proxy" in k.lower():
            print(f"DEBUG: Proxy Var: {k}='{v}'")

    load_dotenv()
    api_key = os.getenv("NOTION_API_KEY", "").strip()
    database_id_raw = os.getenv("NOTION_DATABASE_ID", "").strip()
    if not api_key or not database_id_raw:
        raise SystemExit("Missing NOTION_API_KEY or NOTION_DATABASE_ID")

    try:
        database_id = str(uuid.UUID(database_id_raw))
    except ValueError:
        database_id = database_id_raw

    print(f"DEBUG: Using Database ID: {database_id} (len={len(database_id)})")

    # 1. Fetch Database to gets properties (Schema)
    # Replaced notion-client with direct httpx
    schema = {}
    try:
        db = _notion_request("GET", f"databases/{database_id}", api_key)
        schema = db.get("properties", {})
    except Exception as e:
        print(f"DEBUG: Retrieve database failed: {e}")

    # Fallback: if properties missing, fetch one page
    if not schema:
        print("DEBUG: Schema missing in retrieve() response. Attempting fallback via query...")
        try:
            resp = _notion_request("POST", f"databases/{database_id}/query", api_key, {"page_size": 1})
            results = resp.get("results", [])
            schema = results[0].get("properties", {}) if results else {}
        except Exception as e:
            traceback.print_exc()
            print("DEBUG: Fallback query failed.")

    if schema:
        print(f"DEBUG: Schema found (keys={list(schema.keys())})")
    
    score_prop = find_property(schema, "number", PREFERRED_NAMES["score"])
    source_prop = find_property(schema, "select", PREFERRED_NAMES["source"]) or find_property(
        schema, "rich_text", PREFERRED_NAMES["source"]
    )
    category_prop = find_property(schema, "select", PREFERRED_NAMES["category"]) or find_property(
        schema, "rich_text", PREFERRED_NAMES["category"]
    )
    title_prop = find_property(schema, "title", PREFERRED_NAMES["title"])
    url_prop = find_property(schema, "url", PREFERRED_NAMES["url"])
    date_prop = find_property(schema, "date", PREFERRED_NAMES["date"])

    if not score_prop:
        print(f"DEBUG: Available properties in schema: {list(schema.keys())}")
        for k, v in schema.items():
            print(f"  - {k}: type={v.get('type')}")
        raise SystemExit("No score property found (expected number property like '评分').")

    since = (date.today() - timedelta(days=max(0, args.days))).isoformat() if date_prop else None
    
    # Use direct httpx fetch
    pages = fetch_all_pages(api_key, database_id, date_prop, since)

    records: list[dict] = []
    for page in pages:
        props = page.get("properties", {})

        score_val = parse_property_value(props.get(score_prop, {}), "number")
        if score_val is None and not args.include_unrated:
            continue

        def _get(prop_name: str | None):
            if not prop_name:
                return None
            prop = props.get(prop_name, {})
            ptype = (schema.get(prop_name) or {}).get("type")
            return parse_property_value(prop, ptype)

        records.append(
            {
                "page_id": page.get("id"),
                "score": score_val,
                "source": _get(source_prop),
                "category": _get(category_prop),
                "title": _get(title_prop),
                "url": _get(url_prop),
                "date": _get(date_prop),
                "created_time": page.get("created_time"),
                "last_edited_time": page.get("last_edited_time"),
            }
        )

    os.makedirs(args.output_dir, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    out_path = os.path.join(args.output_dir, f"feedback-{today}.json")
    payload = {
        "generated_at": datetime.now().isoformat(),
        "days": args.days,
        "database_id": database_id,
        "schema_map": {
            "score": score_prop,
            "source": source_prop,
            "category": category_prop,
            "title": title_prop,
            "url": url_prop,
            "date": date_prop,
        },
        "total_pages_queried": len(pages),
        "records": records,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"wrote={out_path}")
    print(f"queried_pages={len(pages)}")
    print(f"records={len(records)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
