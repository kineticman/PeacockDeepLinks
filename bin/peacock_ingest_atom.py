#!/usr/bin/env python3
"""peacock_ingest_atom.py - Fetch schedule from Peacock API into SQLite"""
import os, argparse, json, sqlite3, requests
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ATOM_BASE = "https://atom.peacocktv.com/adapter-calypso/v3/query/node"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json", "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.peacocktv.com", "Referer": "https://www.peacocktv.com/",
    "X-SkyOTT-Proposition": "NBCUOTT", "X-SkyOTT-Platform": "PC",
    "X-SkyOTT-Device": "005", "X-SkyOTT-Territory": "US",
    "X-SkyOTT-Language": "en", "X-SkyOTT-Provider": "NBCU",
}

def ts_ms_to_iso(ts_ms: Optional[int]) -> Optional[str]:
    return datetime.fromtimestamp(ts_ms/1000, tz=timezone.utc).isoformat(timespec="seconds") if ts_ms else None

def ensure_schema(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS events (
        id TEXT PRIMARY KEY, pvid TEXT, slug TEXT, title TEXT, title_brief TEXT,
        synopsis TEXT, synopsis_brief TEXT, channel_name TEXT, channel_provider_id TEXT,
        airing_type TEXT, classification_json TEXT, genres_json TEXT, content_segments_json TEXT,
        is_free INTEGER, is_premium INTEGER, runtime_secs INTEGER, start_ms INTEGER, end_ms INTEGER,
        start_utc TEXT, end_utc TEXT, created_ms INTEGER, created_utc TEXT,
        last_seen_utc TEXT, raw_attributes_json TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS event_images (
        event_id TEXT, img_type TEXT, url TEXT, PRIMARY KEY (event_id, img_type, url))""")
    conn.commit()

def derive_times(attrs: Dict[str, Any]) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    start_ms, end_ms, runtime_secs = attrs.get("displayStartTime"), attrs.get("displayEndTime"), attrs.get("runtime")
    runtime_seconds = None
    if isinstance(runtime_secs, (int, float)):
        runtime_seconds = int(runtime_secs)
    elif isinstance(runtime_secs, str):
        try:
            parts = runtime_secs.split(":")
            if len(parts) == 3:
                h, m, s = map(int, parts)
                runtime_seconds = h*3600 + m*60 + s
        except:
            pass
    if start_ms and not end_ms and runtime_seconds:
        end_ms = start_ms + runtime_seconds*1000
    formats = attrs.get("formats") or {}
    if isinstance(formats, dict):
        for fmt_data in formats.values():
            avail = (fmt_data or {}).get("availability") or {}
            if not start_ms:
                start_ms = avail.get("offerStartTs")
            if not end_ms and not runtime_seconds:
                end_ms = avail.get("offerEndTs")
    return start_ms, end_ms, runtime_seconds

def upsert_event(conn: sqlite3.Connection, item: Dict[str, Any]):
    cur = conn.cursor()
    attrs = item.get("attributes") or {}
    node_id = item.get("id")

    pvid = attrs.get("providerVariantId")
    slug = attrs.get("slug")
    title = attrs.get("title") or ""
    title_brief = attrs.get("titleBrief") or title
    synopsis = attrs.get("synopsis")
    synopsis_brief = attrs.get("synopsisBrief")
    
    channel = attrs.get("channel") or {}
    channel_name = channel.get("name")
    channel_provider_id = channel.get("providerId")

    start_ms, end_ms, runtime_secs = derive_times(attrs)
    start_utc = ts_ms_to_iso(start_ms)
    end_utc = ts_ms_to_iso(end_ms)
    created_ms = attrs.get("createdDate")
    created_utc = ts_ms_to_iso(created_ms)
    last_seen_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")

    classification_json = json.dumps(attrs.get("classification") or [])
    genres_json = json.dumps(attrs.get("genres") or [])
    content_segments_json = json.dumps(attrs.get("contentSegments") or [])
    is_free = int(bool(attrs.get("isFree")))
    is_premium = int(bool(attrs.get("isPremium")))

    cur.execute(
        """INSERT INTO events (
            id, pvid, slug, title, title_brief, synopsis, synopsis_brief,
            channel_name, channel_provider_id,
            airing_type, classification_json, genres_json, content_segments_json,
            is_free, is_premium, runtime_secs,
            start_ms, end_ms, start_utc, end_utc,
            created_ms, created_utc, last_seen_utc, raw_attributes_json
        ) VALUES (
            :id, :pvid, :slug, :title, :title_brief, :synopsis, :synopsis_brief,
            :channel_name, :channel_provider_id,
            :airing_type, :classification_json, :genres_json, :content_segments_json,
            :is_free, :is_premium, :runtime_secs,
            :start_ms, :end_ms, :start_utc, :end_utc,
            :created_ms, :created_utc, :last_seen_utc, :raw_attributes_json
        )
        ON CONFLICT(id) DO UPDATE SET
            pvid=excluded.pvid, slug=excluded.slug, title=excluded.title,
            title_brief=excluded.title_brief, synopsis=excluded.synopsis, synopsis_brief=excluded.synopsis_brief,
            channel_name=excluded.channel_name, channel_provider_id=excluded.channel_provider_id,
            airing_type=excluded.airing_type, classification_json=excluded.classification_json,
            genres_json=excluded.genres_json, content_segments_json=excluded.content_segments_json,
            is_free=excluded.is_free, is_premium=excluded.is_premium, runtime_secs=excluded.runtime_secs,
            start_ms=excluded.start_ms, end_ms=excluded.end_ms, start_utc=excluded.start_utc, end_utc=excluded.end_utc,
            last_seen_utc=excluded.last_seen_utc, raw_attributes_json=excluded.raw_attributes_json
        """,
        {
            "id": node_id, "pvid": pvid, "slug": slug, "title": title, "title_brief": title_brief,
            "synopsis": synopsis, "synopsis_brief": synopsis_brief,
            "channel_name": channel_name, "channel_provider_id": channel_provider_id,
            "airing_type": attrs.get("airingType"),
            "classification_json": classification_json, "genres_json": genres_json,
            "content_segments_json": content_segments_json,
            "is_free": is_free, "is_premium": is_premium, "runtime_secs": runtime_secs,
            "start_ms": start_ms, "end_ms": end_ms, "start_utc": start_utc, "end_utc": end_utc,
            "created_ms": created_ms, "created_utc": created_utc,
            "last_seen_utc": last_seen_utc, "raw_attributes_json": json.dumps(attrs),
        },
    )

    for img in (attrs.get("images") or []):
        url = img.get("url") or img.get("template")
        if node_id and img.get("type") and url:
            cur.execute("INSERT OR IGNORE INTO event_images VALUES (?, ?, ?)", (node_id, img["type"], url))
    conn.commit()

def main():
    script_dir = Path(__file__).resolve().parent
    default_db = str(script_dir.parent / 'data' / 'peacock_events.db') if script_dir.name == 'bin' else "peacock_events.db"
    
    env_db = os.getenv("PEACOCK_DB_PATH")
    env_slug = os.getenv("PEACOCK_SLUG")
    
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=env_db or default_db)
    ap.add_argument("--slug", default=env_slug or "/sports/live-and-upcoming")
    args = ap.parse_args()
    
    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(args.db)
    ensure_schema(conn)
    
    headers = dict(HEADERS)
    headers["Referer"] = f"https://www.peacocktv.com{args.slug}"
    print(f"Fetching {args.slug}...")
    resp = requests.get(ATOM_BASE, params={"slug": args.slug, "represent": "(items(items))"}, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    
    rel = data.get("relationships") or {}
    items = (rel.get("items") or {}).get("data") or []
    print(f"Found {len(items)} items")
    
    count = 0
    for item in items:
        try:
            upsert_event(conn, item)
            count += 1
        except Exception as e:
            print(f"Error: {e}")
    
    print(f"Upserted {count} events into {args.db}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
