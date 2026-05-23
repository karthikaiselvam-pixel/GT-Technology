# GT Technology — staged publishing

A drip-release system for 981 static HTML pages: 20 new pages go live each
Monday, internal links are auto-pruned so nothing points to an unpublished
page, sitemap is rebuilt, and the new URLs are pushed to omegaindexer.com.

## How it works

```
source/        # the full library of 981 pages — never served
publish/
  strategy.yml # category order and batch size
  published.txt# manifest of currently-live pages (one path per line)
  last_batch.txt # paths added in the most recent run
scripts/
  select_next.py   # pick the next batch from strategy
  build.py         # build docs/ from source/ + published.txt
  submit_indexer.py# POST new URLs to omegaindexer
docs/          # built site (gitignored, deployed to GH Pages)
.github/workflows/weekly-publish.yml
```

Each weekly run does:

1. `select_next.py` walks `strategy.yml` top-to-bottom, picks the first 20
   files not yet in `published.txt`, appends them, writes `last_batch.txt`.
2. `build.py` wipes `docs/`, copies every published file from `source/` to
   `docs/`, and for every `<a href="…">` in the copies, if the target is a
   relative `.html` link to a page that is **not** yet published, unwraps the
   anchor — the visible text stays, the broken link disappears. Then it
   regenerates `docs/sitemap.xml` from the published set and copies
   `robots.txt`.
3. The workflow commits the updated `published.txt`, deploys `docs/` to GitHub
   Pages, and POSTs the 20 new URLs to omegaindexer.

## One-time GitHub setup

1. **Pages**: repo Settings → Pages → Source = "GitHub Actions".
2. **Secrets** (Settings → Secrets and variables → Actions → New secret):
   - `OMEGA_API_KEY` — your omegaindexer API key
   - `OMEGA_ENDPOINT` — full URL of the indexer's submit endpoint (e.g.
     `https://api.omegaindexer.com/v1/submit`)
3. If omegaindexer expects a payload shape different from `{"urls": [...]}`
   with `Authorization: Bearer …`, edit `build_payload` and the request
   headers in [scripts/submit_indexer.py](scripts/submit_indexer.py).
4. **Custom domain** (optional): repo Settings → Pages → set
   `thetitaniumtech.com`. GitHub will write a `CNAME` file into the deployment
   automatically.

## Triggering a release

- **Automatic**: every Monday 09:00 UTC.
- **Manual**: GitHub → Actions → "Weekly publish" → Run workflow. You can
  override `batch_size` for that run (e.g. `0` to only rebuild, or `40` to
  catch up).

## Editing the schedule / order

- Change cadence: edit the `cron:` line in
  [.github/workflows/weekly-publish.yml](.github/workflows/weekly-publish.yml).
- Re-order categories or hand-curate the queue: edit
  [publish/strategy.yml](publish/strategy.yml). Files already in
  `published.txt` are never re-released, so you can safely re-shuffle the
  unreleased portion of the strategy at any time.

## Running locally

```bash
pip install -r requirements.txt

# Preview which 20 would be picked next, without writing anything
python scripts/select_next.py --dry-run

# Commit the next batch and rebuild docs/
python scripts/select_next.py
python scripts/build.py

# See the would-be indexer payload
python scripts/submit_indexer.py --dry-run

# Serve locally
python -m http.server -d docs 8000
```

## Rolling back a release

Pages are added in order. To un-publish the most recent batch, delete the
trailing lines of `publish/published.txt` (or restore the file from a prior
commit) and re-run `build.py`. The Action will deploy the smaller set on the
next run, or you can trigger it manually with `batch_size: 0`.
