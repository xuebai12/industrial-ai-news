#!/usr/bin/env python3
"""Resend email digest from an existing markdown file."""

import argparse
import os
import re
from dataclasses import dataclass
from pathlib import Path
from datetime import date

from dotenv import load_dotenv

from src.delivery.email_sender import send_email
from src.models import AnalyzedArticle, Article
from config import RECIPIENT_PROFILES

@dataclass
class DigestEntry:
    category: str
    title_zh: str
    title_en: str
    summary_zh: str
    summary_en: str
    core_tech: str
    german_context: str
    source_name: str
    source_url: str

def _extract(pattern: str, text: str) -> str:
    match = re.search(pattern, text, flags=re.S)
    if not match:
        return ""
    return match.group(1).strip()

def parse_digest(content: str) -> list[DigestEntry]:
    parts = re.split(r"\n---\n\n### ", content)
    entries: list[DigestEntry] = []
    for part in parts[1:]:
        block = "### " + part
        heading_match = re.search(r"^### \[(.*?)\]\s*(.+)$", block, flags=re.M)
        if not heading_match:
            continue
        category = heading_match.group(1).strip()
        title_zh = heading_match.group(2).strip()

        title_en = _extract(r"^\*(.*?)\*$", block)
        summary_zh = _extract(r"\*\*🇨🇳 摘要：\*\*\s*(.+?)(?:\n\n|\n🔬)", block)
        summary_en = _extract(r"\*\*🇬🇧 Summary:\*\*\s*(.+?)(?:\n\n|\n🔬)", block)
        core_tech = _extract(r"🔬 \*\*核心技术：\*\*\s*(.+?)(?:\n\n|\n🏭)", block)
        german_context = _extract(r"🏭 \*\*应用背景：\*\*\s*(.+?)(?:\n\n|\n>)", block)

        source_match = re.search(
            r"📎 来源：\s*(.+?)\s*\|\s*\[点击查看原文\]\((https?://[^)]+)\)",
            block,
            flags=re.S,
        )
        source_name = source_match.group(1).strip() if source_match else "Unknown"
        source_url = source_match.group(2).strip() if source_match else ""

        entries.append(
            DigestEntry(
                category=category or "Other",
                title_zh=title_zh or "Untitled",
                title_en=title_en or title_zh or "Untitled",
                summary_zh=summary_zh,
                summary_en=summary_en,
                core_tech=core_tech,
                german_context=german_context,
                source_name=source_name,
                source_url=source_url,
            )
        )
    return entries

def to_analyzed(entry: DigestEntry) -> AnalyzedArticle:
    original = Article(
        title=entry.title_en or entry.title_zh,
        url=entry.source_url,
        source=entry.source_name,
        content_snippet=entry.summary_en or entry.summary_zh,
        language="en",
        category=entry.category,
    )
    # Note: Target personas are lost in markdown round-trip. 
    # We will assume these are general articles or re-apply based on keywords if needed.
    # For now, we tag them for ALL profiles to ensure delivery, or let send_email filter?
    # Actually logic in main.py filters by persona. If we assume this digest was ALREADY filtered
    # or creates a "master" list, we might miss persona tags. 
    # Let's add all personas to be safe so they get sent to all profiles if main.py logic was strict.
    # But wait, send_email takes a specific set of articles. 
    # If we call send_email with ALL articles for ALL profiles, it might be spammy if we loop profiles.
    # Let's just restore "student" and "technician" to cover bases.
    personas = ["student", "technician"]
    
    return AnalyzedArticle(
        category_tag=entry.category,
        title_zh=entry.title_zh,
        title_en=entry.title_en,
        title_de=entry.title_en,
        core_tech_points=entry.core_tech,
        german_context=entry.german_context,
        source_name=entry.source_name,
        source_url=entry.source_url,
        summary_zh=entry.summary_zh,
        summary_en=entry.summary_en,
        summary_de=entry.summary_en,
        tool_stack="",
        simple_explanation="",
        technician_analysis_de="",
        target_personas=personas,
        original=original,
    )

def main() -> int:
    parser = argparse.ArgumentParser(description="Resend email digest from markdown")
    parser.add_argument("digest_path", help="Path to digest markdown file")
    args = parser.parse_args()

    load_dotenv()
    
    digest_path = Path(args.digest_path)
    if not digest_path.exists():
        print(f"Error: File not found: {digest_path}")
        return 1
        
    content = digest_path.read_text(encoding="utf-8")
    entries = parse_digest(content)
    if not entries:
        print(f"No entries parsed from {digest_path}")
        return 1

    articles = [to_analyzed(item) for item in entries]
    print(f"Parsed {len(articles)} articles from {digest_path.name}")
    
    today = date.today().strftime("%Y-%m-%d")
    
    # Send to all configured profiles
    for profile in RECIPIENT_PROFILES:
        if profile.delivery_channel not in ("email", "both"):
            continue
            
        print(f"Sending to profile: {profile.name} ({profile.email})")
        # filter if needed, but since we lost persona data, we send all? 
        # Or blindly send all parsed articles as they were in the daily digest.
        # Yes, resending the "Daily Digest" usually implies the whole thing.
        try:
            success = send_email(articles, today, profile=profile)
            if success:
                print(f"✅ Email sent to {profile.name}")
            else:
                print(f"❌ Failed to send to {profile.name}")
        except Exception as e:
             print(f"❌ Error sending to {profile.name}: {e}")

    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
