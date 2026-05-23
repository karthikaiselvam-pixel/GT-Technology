#!/usr/bin/env python3
"""
Select the next batch of pages to publish, by category strategy.

Reads:
  publish/strategy.yml
  publish/published.txt   (one path per line, relative to source/)
  source/                  (the file library)

Writes:
  publish/published.txt    (appends newly selected paths)
  publish/last_batch.txt   (just the newly selected paths, one per line)

Usage:
  python scripts/select_next.py [--dry-run] [--batch-size N]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source"
STRATEGY = ROOT / "publish" / "strategy.yml"
PUBLISHED = ROOT / "publish" / "published.txt"
LAST_BATCH = ROOT / "publish" / "last_batch.txt"


def load_published() -> list[str]:
    if not PUBLISHED.exists():
        return []
    return [line.strip() for line in PUBLISHED.read_text().splitlines() if line.strip()]


def expand_category(cat: dict) -> list[str]:
    """Return list of source-relative paths for one category, in release order."""
    if "files" in cat:
        return list(cat["files"])
    if "glob" in cat:
        matches = sorted(p.relative_to(SOURCE).as_posix() for p in SOURCE.glob(cat["glob"]))
        return matches
    return []


def select_next(batch_size: int) -> tuple[list[str], list[dict]]:
    cfg = yaml.safe_load(STRATEGY.read_text())
    already = set(load_published())
    selected: list[str] = []
    breakdown: list[dict] = []

    for cat in cfg["categories"]:
        if len(selected) >= batch_size:
            break
        cat_files = expand_category(cat)
        picked_here = []
        for f in cat_files:
            if f in already or f in selected:
                continue
            if not (SOURCE / f).exists():
                print(f"warn: {f} listed in strategy but missing from source/", file=sys.stderr)
                continue
            selected.append(f)
            picked_here.append(f)
            if len(selected) >= batch_size:
                break
        if picked_here:
            breakdown.append({"category": cat["name"], "count": len(picked_here), "files": picked_here})

    return selected, breakdown


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print selection without writing")
    parser.add_argument("--batch-size", type=int, help="Override batch size from strategy.yml")
    args = parser.parse_args()

    cfg = yaml.safe_load(STRATEGY.read_text())
    batch_size = args.batch_size or cfg.get("batch_size", 20)

    selected, breakdown = select_next(batch_size)

    print(f"Selected {len(selected)} pages:")
    for b in breakdown:
        print(f"  [{b['category']}] {b['count']} pages")
        for f in b["files"]:
            print(f"    - {f}")

    if not selected:
        print("\nNothing left to publish.")
        return 0

    if args.dry_run:
        print("\n(dry-run; not writing)")
        return 0

    with PUBLISHED.open("a") as fh:
        for f in selected:
            fh.write(f + "\n")
    LAST_BATCH.write_text("\n".join(selected) + "\n")
    print(f"\nAppended to {PUBLISHED.relative_to(ROOT)}")
    print(f"Wrote {LAST_BATCH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
