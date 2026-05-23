#!/usr/bin/env python3
"""
Submit the most-recently-published URLs to omegaindexer.com.

Reads:
  publish/last_batch.txt   (paths added in this run, written by select_next.py)
  publish/strategy.yml     (for site_url)

Env vars (set as GitHub secrets):
  OMEGA_API_KEY     required — sent as `Authorization: Bearer ...`
  OMEGA_ENDPOINT    required — e.g. https://api.omegaindexer.com/v1/index

Adjust the request body in `build_payload` if the API expects a different
schema (e.g. {"links": [...]} vs {"urls": [...]}).

Usage:
  python scripts/submit_indexer.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
LAST_BATCH = ROOT / "publish" / "last_batch.txt"
STRATEGY = ROOT / "publish" / "strategy.yml"


def url_for(rel: str, site_url: str) -> str:
    site_url = site_url.rstrip("/")
    if rel == "index.html":
        return site_url + "/"
    return f"{site_url}/{rel}"


def build_payload(urls: list[str]) -> dict:
    # Generic shape — adjust to match omegaindexer's actual API contract.
    return {"urls": urls}


def submit(endpoint: str, api_key: str, payload: dict) -> tuple[int, str]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as e:
        return 0, f"URLError: {e.reason}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print payload but don't POST")
    args = parser.parse_args()

    if not LAST_BATCH.exists():
        print("No last_batch.txt; nothing to submit.")
        return 0
    paths = [p for p in LAST_BATCH.read_text().splitlines() if p.strip()]
    if not paths:
        print("last_batch.txt is empty; nothing to submit.")
        return 0

    cfg = yaml.safe_load(STRATEGY.read_text())
    site_url = cfg.get("site_url")
    if not site_url:
        print("error: site_url missing from strategy.yml", file=sys.stderr)
        return 2

    urls = [url_for(p, site_url) for p in paths]
    payload = build_payload(urls)
    print(f"Submitting {len(urls)} URLs to omegaindexer:")
    for u in urls:
        print(f"  - {u}")

    if args.dry_run:
        print("\nPayload (dry-run):")
        print(json.dumps(payload, indent=2))
        return 0

    endpoint = os.environ.get("OMEGA_ENDPOINT")
    api_key = os.environ.get("OMEGA_API_KEY")
    if not endpoint or not api_key:
        print("error: OMEGA_ENDPOINT and OMEGA_API_KEY env vars are required", file=sys.stderr)
        return 2

    status, body = submit(endpoint, api_key, payload)
    print(f"\nResponse: HTTP {status}")
    print(body[:2000])
    return 0 if 200 <= status < 300 else 1


if __name__ == "__main__":
    sys.exit(main())
