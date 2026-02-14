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
    "core_tech": ["核心技术", "Core Tech", "core_tech_points"],
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


def fetch_all_pages(client: Client, database_id: str, date_prop: str | None, since: str | None) -> list[dict]:
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

        resp = client.request(
            path=f"databases/{database_id}/query",
            method="POST",
            body=body,
        )
        rows.extend(resp.get("results", []))
        if not resp.get("has_more"):
            break
        start_cursor = resp.get("next_cursor")
    return rows


import uuid
import traceback

def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch Notion ratings to local JSON")
    parser.add_argument("--days", type=int, default=30, help="Lookback days for date filter")
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--include-unrated", action="store_true", help="Keep rows without score")
    args = parser.parse_args()

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

    client = Client(auth=api_key)
    # Note: retrieve likely works but returns partial object?
    try:
        db = client.databases.retrieve(database_id=database_id)
        schema = db.get("properties", {})
    except Exception as e:
        print(f"DEBUG: Retrieve failed: {e}")
        schema = {}

    # Fallback: if retrieve() returns no properties (e.g. permission/version issue),
    # try to fetch one page and use its properties as schema.
    if not schema:
        print("DEBUG: Schema missing in retrieve() response. Attempting fallback via query...")
        try:
            # check if client.databases has query method, else use raw request
            if hasattr(client.databases, "query"):
                print("DEBUG: Using client.databases.query")
                resp = client.databases.query(database_id=database_id, page_size=1)
            else:
                path = f"databases/{database_id}/query"
                print(f"DEBUG: Using client.request(path='{path}')")
                resp = client.request(
                    path=path,
                    method="POST",
                    body={"page_size": 1},
                )
            results = resp.get("results", [])
            if results:
                schema = results[0].get("properties", {})
                print(f"DEBUG: Inferred schema from page query. Keys: {list(schema.keys())}")
            else:
                print("DEBUG: Query returned no pages, cannot infer schema.")
        except Exception:
            traceback.print_exc()
            print("DEBUG: Fallback query failed.")

    score_prop = find_property(schema, "number", PREFERRED_NAMES["score"])
    source_prop = find_property(schema, "select", PREFERRED_NAMES["source"]) or find_property(
        schema, "rich_text", PREFERRED_NAMES["source"]
    )
    category_prop = find_property(schema, "select", PREFERRED_NAMES["category"]) or find_property(
        schema, "rich_text", PREFERRED_NAMES["category"]
    )
    title_prop = find_property(schema, "title", PREFERRED_NAMES["title"])
    url_prop = find_property(schema, "url", PREFERRED_NAMES["url"])
    core_tech_prop = find_property(schema, "multi_select", PREFERRED_NAMES["core_tech"]) or find_property(
        schema, "rich_text", PREFERRED_NAMES["core_tech"]
    )
    date_prop = find_property(schema, "date", PREFERRED_NAMES["date"])

    if not score_prop:
        print(f"DEBUG: Available properties in schema: {list(schema.keys())}")
        for k, v in schema.items():
            print(f"  - {k}: type={v.get('type')}")
        raise SystemExit("No score property found (expected number property like '评分').")

    since = (date.today() - timedelta(days=max(0, args.days))).isoformat() if date_prop else None
    pages = fetch_all_pages(client, database_id, date_prop, since)

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
                "core_tech": _get(core_tech_prop),
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
            "core_tech": core_tech_prop,
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
