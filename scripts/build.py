#!/usr/bin/env python3
"""
Build the deployable site under docs/ from source/ + publish/published.txt.

For each published page:
  - Copy source/X -> docs/X
  - Rewrite <a href="..."> in the copy:
      * If href is a relative .html path resolving to a NON-published source file,
        unwrap the anchor (drop <a>, keep visible inner text/markup).
      * External links, mailto:, tel:, javascript:, and pure #anchors are left alone.
  - Also normalize self-links to the file itself (left as-is).

Regenerates docs/sitemap.xml from published.txt and copies robots.txt to docs/.

Usage:
  python scripts/build.py
"""
from __future__ import annotations

import datetime
import os.path
import shutil
import sys
import xml.sax.saxutils as sx
from pathlib import Path
from urllib.parse import urldefrag

import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source"
DOCS = ROOT / "docs"
PUBLISHED = ROOT / "publish" / "published.txt"
STRATEGY = ROOT / "publish" / "strategy.yml"
ROBOTS = ROOT / "robots.txt"


def load_published() -> set[str]:
    if not PUBLISHED.exists():
        return set()
    return {line.strip() for line in PUBLISHED.read_text().splitlines() if line.strip()}


def is_external(href: str) -> bool:
    if not href:
        return True
    if href.startswith(("http://", "https://", "//", "mailto:", "tel:", "javascript:", "data:")):
        return True
    if href.startswith("#"):
        return True
    return False


def resolve_link(current_file: str, href: str) -> str | None:
    """Resolve href against current_file (both source-relative POSIX paths).
    Pure string math — does not touch the filesystem.
    Returns the target as a source-relative POSIX path, or None if it
    isn't a relative .html link we should rewrite."""
    href_path, _ = urldefrag(href)
    if not href_path:
        return None
    href_path = href_path.split("?", 1)[0]
    if not href_path.endswith(".html"):
        return None
    base_dir = os.path.dirname(current_file)
    joined = os.path.join(base_dir, href_path) if base_dir else href_path
    normalized = os.path.normpath(joined).replace(os.sep, "/")
    # If the link escapes the source tree, ignore it.
    if normalized.startswith("../") or normalized == "..":
        return None
    return normalized


def rewrite_html(html: str, current_file: str, published: set[str]) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for a in list(soup.find_all("a", href=True)):
        href = a["href"].strip()
        if is_external(href):
            continue
        target = resolve_link(current_file, href)
        if target is None:
            continue
        if target in published:
            continue
        # Unwrap: replace <a>children</a> with children.
        a.unwrap()
    return str(soup)


def copy_and_rewrite(published: set[str]) -> None:
    if DOCS.exists():
        shutil.rmtree(DOCS)
    DOCS.mkdir()

    for rel in sorted(published):
        src = SOURCE / rel
        dst = DOCS / rel
        if not src.exists():
            print(f"warn: published path missing in source: {rel}", file=sys.stderr)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix.lower() == ".html":
            rewritten = rewrite_html(src.read_text(encoding="utf-8"), rel, published)
            dst.write_text(rewritten, encoding="utf-8")
        else:
            shutil.copy2(src, dst)

    if ROBOTS.exists():
        shutil.copy2(ROBOTS, DOCS / "robots.txt")


SITEMAP_PRIORITY = {
    "index.html": ("1.0", "weekly"),
    "about.html": ("0.9", "monthly"),
    "contact.html": ("0.9", "monthly"),
    "services.html": ("0.9", "monthly"),
    "industries.html": ("0.9", "monthly"),
    "locations.html": ("0.9", "monthly"),
    "portfolio.html": ("0.8", "monthly"),
    "pricing.html": ("0.8", "monthly"),
    "offer.html": ("1.0", "weekly"),
    "404.html": ("0.1", "yearly"),
}


def page_meta(rel: str) -> tuple[str, str]:
    if rel in SITEMAP_PRIORITY:
        return SITEMAP_PRIORITY[rel]
    if rel.startswith("services/"):
        return ("0.8", "monthly")
    if rel.startswith("industries/"):
        return ("0.8", "monthly")
    if rel.startswith("locations/") and rel.count("/") == 1:
        return ("0.7", "monthly")
    if rel.startswith("locations/"):
        return ("0.6", "monthly")
    return ("0.5", "monthly")


def url_for(rel: str, site_url: str) -> str:
    site_url = site_url.rstrip("/")
    if rel == "index.html":
        return site_url + "/"
    return f"{site_url}/{rel}"


def write_sitemap(published: set[str], site_url: str) -> None:
    today = datetime.date.today().isoformat()
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    # Stable order: core first by SITEMAP_PRIORITY insertion, then alpha.
    core = [p for p in SITEMAP_PRIORITY if p in published]
    rest = sorted(p for p in published if p not in SITEMAP_PRIORITY)
    for rel in core + rest:
        priority, changefreq = page_meta(rel)
        loc = sx.escape(url_for(rel, site_url))
        lines.append("  <url>")
        lines.append(f"    <loc>{loc}</loc>")
        lines.append(f"    <lastmod>{today}</lastmod>")
        lines.append(f"    <changefreq>{changefreq}</changefreq>")
        lines.append(f"    <priority>{priority}</priority>")
        lines.append("  </url>")
    lines.append("</urlset>")
    (DOCS / "sitemap.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    published = load_published()
    cfg = yaml.safe_load(STRATEGY.read_text())
    site_url = cfg.get("site_url", "").rstrip("/")

    if not published:
        print("published.txt is empty; nothing to build.")
        DOCS.mkdir(exist_ok=True)
        return 0

    print(f"Building {len(published)} pages -> {DOCS.relative_to(ROOT)}/")
    copy_and_rewrite(published)
    write_sitemap(published, site_url)
    print(f"Built {len(published)} pages and sitemap.xml")
    return 0


if __name__ == "__main__":
    sys.exit(main())
