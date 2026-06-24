#!/usr/bin/env python3
"""
reddit_demand_census.py — quantify forum demand for POS migration help.

Counts Reddit threads + engagement (score, comments) per migration theme, to
put hard numbers behind the rankings in pos-migration-demand-research.md.

WHY THIS EXISTS: Reddit blocks anonymous scraping, so the deep-research pass
could not get thread-level counts. This uses the official Reddit API (OAuth
"script" app) which is allowed and reliable.

SETUP
  1. Create a "script" app at https://www.reddit.com/prefs/apps
  2. export REDDIT_CLIENT_ID=...      REDDIT_CLIENT_SECRET=...
     export REDDIT_USER_AGENT="pos-census by u/yourname"
  3. pip install requests
  4. python reddit_demand_census.py            # all themes
     python reddit_demand_census.py --csv out.csv --min-score 1 --limit 100

Output: per-theme totals (threads, total score, total comments, top thread)
and a per-thread CSV for manual review. No login/password needed — read-only
app-only OAuth.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field

import requests

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
SEARCH_URL = "https://oauth.reddit.com/search"

# Migration themes -> the queries that surface them. Edit freely.
# Keep queries quoted/specific enough to avoid generic POS noise.
THEMES: dict[str, list[str]] = {
    "QuickBooks POS exit": [
        "quickbooks point of sale discontinued",
        "quickbooks pos alternative migrate",
        "quickbooks pos sales history export",
    ],
    "Aloha -> cloud": [
        "Aloha POS switch Toast",
        "replacing Aloha pos restaurant",
    ],
    "MICROS -> cloud": [
        "Micros pos replacement restaurant",
        "Oracle Micros switch Toast Square",
    ],
    "Clover <-> Square": [
        "Clover to Square import inventory",
        "switching Clover Square data",
    ],
    "Lightspeed/Vend -> Shopify": [
        "Lightspeed Shopify sales history migrate",
        "Vend Lightspeed export sales history",
    ],
    "Generic: stuck / lost data": [
        "switching POS lost sales history",
        "stuck old POS system can't switch data",
        "POS migration lost reporting history regret",
    ],
}


@dataclass
class ThemeStats:
    threads: int = 0
    score: int = 0
    comments: int = 0
    top_title: str = ""
    top_score: int = -1
    top_url: str = ""
    seen_ids: set[str] = field(default_factory=set)  # dedupe across queries


def get_token(client_id: str, client_secret: str, user_agent: str) -> str:
    resp = requests.post(
        TOKEN_URL,
        auth=(client_id, client_secret),
        data={"grant_type": "client_credentials"},
        headers={"User-Agent": user_agent},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def search(token: str, user_agent: str, query: str, limit: int) -> list[dict]:
    """Paginate Reddit search up to `limit` results (100/page max)."""
    out: list[dict] = []
    after = None
    headers = {"Authorization": f"bearer {token}", "User-Agent": user_agent}
    while len(out) < limit:
        page = min(100, limit - len(out))
        params = {
            "q": query,
            "limit": page,
            "sort": "relevance",
            "type": "link",
            "t": "all",
            "raw_json": 1,
        }
        if after:
            params["after"] = after
        r = requests.get(SEARCH_URL, headers=headers, params=params, timeout=30)
        if r.status_code == 429:  # rate limited — back off and retry
            time.sleep(5)
            continue
        r.raise_for_status()
        data = r.json().get("data", {})
        children = data.get("children", [])
        if not children:
            break
        out.extend(c["data"] for c in children)
        after = data.get("after")
        if not after:
            break
        time.sleep(1)  # be polite; stay well under 60 req/min
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Reddit POS-migration demand census")
    ap.add_argument("--limit", type=int, default=100, help="max results per query")
    ap.add_argument("--min-score", type=int, default=0, help="ignore threads below this score")
    ap.add_argument("--csv", default="reddit_demand_threads.csv", help="per-thread CSV output")
    args = ap.parse_args()

    cid = os.environ.get("REDDIT_CLIENT_ID")
    secret = os.environ.get("REDDIT_CLIENT_SECRET")
    ua = os.environ.get("REDDIT_USER_AGENT", "pos-demand-census/1.0")
    if not cid or not secret:
        sys.exit("Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET (see header docstring).")

    token = get_token(cid, secret, ua)
    stats: dict[str, ThemeStats] = {t: ThemeStats() for t in THEMES}
    rows: list[dict] = []

    for theme, queries in THEMES.items():
        st = stats[theme]
        for q in queries:
            for p in search(token, ua, q, args.limit):
                pid = p.get("id")
                if not pid or pid in st.seen_ids:
                    continue
                score = int(p.get("score", 0))
                if score < args.min_score:
                    continue
                st.seen_ids.add(pid)
                ncomments = int(p.get("num_comments", 0))
                st.threads += 1
                st.score += score
                st.comments += ncomments
                if score > st.top_score:
                    st.top_score = score
                    st.top_title = p.get("title", "")
                    st.top_url = "https://reddit.com" + p.get("permalink", "")
                rows.append(
                    {
                        "theme": theme,
                        "query": q,
                        "subreddit": p.get("subreddit", ""),
                        "score": score,
                        "num_comments": ncomments,
                        "created_utc": int(p.get("created_utc", 0)),
                        "title": p.get("title", ""),
                        "url": "https://reddit.com" + p.get("permalink", ""),
                    }
                )

    # Per-theme summary, ranked by total engagement (score + comments).
    print(f"\n{'THEME':<32}{'THREADS':>9}{'SCORE':>9}{'COMMENTS':>10}   TOP THREAD")
    print("-" * 100)
    for theme, st in sorted(
        stats.items(), key=lambda kv: kv[1].score + kv[1].comments, reverse=True
    ):
        print(
            f"{theme:<32}{st.threads:>9}{st.score:>9}{st.comments:>10}   "
            f"{st.top_title[:50]}"
        )

    with open(args.csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "theme", "query", "subreddit", "score",
                "num_comments", "created_utc", "title", "url",
            ],
        )
        w.writeheader()
        w.writerows(rows)
    print(f"\nWrote {len(rows)} threads to {args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
