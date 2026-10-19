# Cochise Defensive Pistol Match web site

The site at <https://cochisedefensivepistolmatch.com>, built with
[Hugo](https://gohugo.io/) and edited through [Decap CMS](https://decapcms.org/).
Hosted on Cloudflare; every push to `main` rebuilds the site.

## Editing the site (match directors)

1. Go to <https://cochisedefensivepistolmatch.com/admin/> and choose **Login with GitHub**.
   Your GitHub account needs write access to this repository.
2. **Match results → New Match** after each match:
   - Match date and title (e.g. "November 7, 2026")
   - PractiScore results link
   - Stage designs PDF (upload)
   - Optional notes, like "Zombie Match" or "Thanks to Scott for designing Stage 2"
3. **Save** as often as you like. Saved changes are drafts and don't touch
   the live site.
4. When it looks right, open **Workflow** (top menu), drag the card to
   **Ready**, then click **Publish** (or use **Publish → Publish now** in the
   entry). The live site updates in about a minute.

Drafts are kept as pull requests on GitHub until they're published, so
nothing half-finished goes live.

Other things you can change there:

| Section | What it controls |
|---|---|
| Site settings → Schedule and announcements | Home-page "Next match" box, sign-in times, cost, announcements, cancelled dates |
| Site settings → Year notices | A note at the top of one year's results page |
| Pages | Home, Qualifier, Workshop, FAQ, Contact |
| Photo albums | Photo galleries |

The "Next match" and "Workshop" dates are worked out automatically (first and
fourth Saturday). To cancel one, add it under **Cancelled dates**.

## How it's organised

```
content/results/YYYY-MM-DD.md   one file per match (flat; year pages are generated)
content/results/_content.gotmpl  makes /results/2015/ … /results/<this year>/
data/settings.yaml              schedule, announcements, cancellations
data/years.yaml                 per-year notices
static/admin/                   Decap CMS
static/documents/legacy/        stage-design PDFs from the old site
static/documents/stage-designs/ PDFs uploaded through the CMS
static/vendor/pdfjs/            PDF.js 6.4.299 (shows stage designs inline on match pages)
static/_redirects               old .php and /documents URLs → new pages
static/_headers                 response headers
wrangler.jsonc                  Cloudflare deploy settings for the site
tools/decap-oauth/              "Login with GitHub" helper (separate Worker)
tools/*.py                      one-off migration scripts (see below)
```

## Running it locally

```bash
hugo server
```

Then open <http://localhost:1313/>. To try the editor without logging in,
also run `npx decap-server` and open <http://localhost:1313/admin/>; changes
are written straight to your local files.

## Hosting and accounts

Everything runs on free plans. Handover note for whoever looks after the site:

| What | Where | Notes |
|---|---|---|
| Site files | GitHub repo `DaveGirgis/cdpm-website` | Editors need write access (repo **Settings → Collaborators**) |
| Website | Cloudflare Worker **cdpm-website** (Dave Girgis's Cloudflare account) | Builds `main`: `hugo --gc --minify`, then `npx wrangler deploy`; build variable `HUGO_VERSION=0.167.0`; custom domains `cochisedefensivepistolmatch.com` and `www` |
| Editor login | Cloudflare Worker **cdpm-decap-oauth** (code in `tools/decap-oauth/`) | Runtime secrets `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` from the GitHub OAuth app **cdpm cloudflare** (redirect URI `https://cdpm-decap-oauth.dave-girgis.workers.dev/callback`) |
| DNS | Cloudflare (same account) | Website records point at the Worker; `www` redirects to the bare domain (Rules → Redirect Rules); Always Use HTTPS is on |
| Email | HostMetro (`metro705.hostmetro.com`) | MX, `mail`, `pop`, `smtp`, SPF and DKIM records in Cloudflare DNS must keep pointing there |
| Domain registration | HostMetro (registrar eNom) | Renews **Feb 17, 2027**; plan to transfer to Cloudflare Registrar before then |

The HTTPS certificate is issued and renewed by Cloudflare automatically.

## Migration from the old site

The old RVSiteBuilder site was scraped on 2026-10-06. To repeat it, scrape
into `_scrape/` (ignored by git) and run:

```bash
pip install beautifulsoup4
python tools/legacy_files.py   # download PDFs/images with case-safe names
python tools/migrate.py        # results pages -> content/results/*.md
python tools/redirects.py      # static/_redirects
```

Problems found and fixed in the old content:

- All 2023 and 2024 matches linked to `december.pdf`; each now links to its own
  month's PDF (the files were on the server, just not linked). August 2024 has
  no PDF on the server, so its link was removed.
- Four matches were hidden inside their neighbours because of unusual
  headings: November and December 2024 ("CORES FOR"), January 2016 and
  July 2015 (month names). All four are now separate matches.
- Several dates were typos (`12/52022`, `11//2022`, `2/42023`, `1/72023`,
  `8/672024`); they now use the first Saturday of that month.
- PDF names that differ only by case (`May.pdf` / `may.pdf`) are different
  files on the old server; they're kept as `may.pdf` and `may-2.pdf`.
- Old stage-design links re-use names like `July.pdf` across several years, so
  some older matches show a later year's PDF. That was already true on the old
  site and can't be recovered from it.
