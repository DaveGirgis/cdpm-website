"""One-off migration of the old RVSiteBuilder results pages into Hugo content.

Reads the content zones saved by the scrape (_scrape/zones/*.html) and writes
one file per match to content/results/<date>.md, plus data/years.yaml for
notices that applied to a whole year.

    python tools/migrate.py
"""
import datetime as dt
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag

ROOT = Path(__file__).resolve().parent.parent
ZONES = ROOT / "_scrape" / "zones"
OUT = ROOT / "content" / "results"
SITE = "https://cochisedefensivepistolmatch.com/"

# The old site named each year's page after the previous year's copy.
PAGES = {2015: "2015-Match-results.php"}
PAGES.update({y: f"Copied-{y - 1}-Match-results.php" for y in range(2016, 2027)})

# "SCORES FOR 12/4", "SCORES FOR 3 / 4/17", "SCORES FOR Jan 2, 2016"
HEADING = r"S?CORES FOR\s*(\d[\d/ ]*|[A-Za-z]{3,9}\.?\s*\d{1,2}(?:,\s*\d{4})?)"
FIXED_DATES = []  # (year, raw heading, date used) for headings that weren't valid dates

BOILER = [
    r"COCHISE DEFENSIVE PISTOL\s*(ZOMBIE\s*)?MATCH",
    r"S?CORES FOR\s*\S*",
    r"Scores are on( the)?",
    r"PractiScore Web Site",
    r"Stage designs are( found)?",
    r"Stage Designs are",
    r"^here$",
    r"Scores that are blue are \"clean\" or perfect stages\.\s*No points lost\.",
    r"Yellow Highlight indicates Stage Winner",
]
YELLOW = {"#ffff99", "#ffff00", "#ffffcc"}
BLUE = {"#0000ff", "#5a10ef"}


def clean(s):
    s = s.replace("\xa0", " ").replace("�", " ")
    return re.sub(r"[ \t\r\f\v]+", " ", s).strip()


def is_header_row(cells):
    return bool(cells) and cells[0].lower().startswith("rank")


def is_data_row(cells):
    return len(cells) >= 6 and cells[0].isdigit() and bool(cells[1])


def has_rank_row(t):
    rows = [[clean(td.get_text(" ")) for td in tr.find_all(["td", "th"], recursive=False)]
            for tr in t.find_all("tr")]
    return any(is_header_row(r) for r in rows) or sum(map(is_data_row, rows)) >= 3


def is_scores_table(t):
    return has_rank_row(t) and not any(has_rank_row(i) for i in t.find_all("table"))


BLOCK = {"br", "p", "div", "h1", "h2", "h3", "h4", "tr", "li", "ul", "table"}


def walk(node):
    for ch in node.children:
        if isinstance(ch, NavigableString):
            if ch.__class__.__name__ in ("Comment",):
                continue
            yield ("text", str(ch))
        elif isinstance(ch, Tag):
            if ch.name in ("script", "style"):
                continue
            if ch.name == "table" and is_scores_table(ch):
                yield ("br",)
                yield ("table", ch)
                yield ("br",)
                continue
            if ch.name == "a" and ch.get("href"):
                yield ("link", ch["href"], clean(ch.get_text(" ")))
                yield ("text", ch.get_text(" "))
                continue
            if ch.name in BLOCK:
                yield ("br",)
            yield from walk(ch)
            if ch.name in BLOCK:
                yield ("br",)


def parse_table(t):
    """Return (heading lines, links, scores) for an old inline score table."""
    heads, links, scores = [], [], []
    header_seen = False
    for tr in t.find_all("tr"):
        tds = tr.find_all(["td", "th"], recursive=False)
        cells = [clean(td.get_text(" ")) for td in tds]
        for a in tr.find_all("a"):
            if a.get("href"):
                links.append(a["href"])
        if not any(cells):
            continue
        if is_header_row(cells):
            header_seen = True
            continue
        if is_data_row(cells):
            header_seen = True
        if not header_seen or not is_data_row(cells):
            heads.extend(c for c in cells if c)
            continue
        stages, winner, clean_ = [], [], []
        for i, td in enumerate(tds[3:-1]):
            stages.append(cells[3 + i])
            bg = (td.get("bgcolor") or "").lower()
            m = re.search(r"background(?:-color)?:\s*([^;]+)", td.get("style", ""))
            if m:
                bg = m.group(1).strip().lower()
            if bg in YELLOW:
                winner.append(i + 1)
            fonts = [f.get("color", "").lower() for f in td.find_all("font")]
            if any(c in BLUE for c in fonts):
                clean_.append(i + 1)
        row = {
            "rank": cells[0],
            "shooter": cells[1],
            "class": cells[2],
            "stages": stages,
            "total": cells[-1] if len(cells) > 3 else "",
        }
        if winner:
            row["stage_wins"] = winner
        if clean_:
            row["clean"] = clean_
        scores.append(row)
    return heads, links, scores


def first_saturday(year, month):
    d = dt.date(year, month, 1)
    return d + dt.timedelta(days=(5 - d.weekday()) % 7)


def to_date(raw, year):
    named = re.match(r"([A-Za-z]{3})[A-Za-z]*\.?\s*(\d{1,2})", raw)
    if named:
        month = dt.datetime.strptime(named.group(1).title(), "%b").month
        return dt.date(year, month, int(named.group(2)))
    raw = raw.replace(" ", "")
    parts = raw.split("/")
    try:
        m, d = int(parts[0]), int(parts[1])
        y = parts[2] if len(parts) > 2 else ""
        if y and int(y) % 100 != year % 100:
            raise ValueError
        return dt.date(year, m, d)
    except (ValueError, IndexError):
        date = first_saturday(year, int(parts[0]))
        FIXED_DATES.append((year, raw, date))
        return date


class Match:
    def __init__(self, raw):
        self.raw = raw
        self.lines = []
        self.links = []
        self.scores = []
        self.title_extra = ""


def segment(year):
    html = (ZONES / f"{PAGES[year]}.html").read_text(encoding="utf-8")
    zone = BeautifulSoup(html, "html.parser")
    intro, matches, cur, buf = [], [], None, []

    def flush():
        line = clean("".join(buf))
        buf.clear()
        if not line:
            return
        for piece in re.split(r"(?=SCORES FOR)|(?<!S)(?=CORES FOR)", line):
            piece = clean(piece)
            if not piece:
                continue
            m = re.match(HEADING, piece)
            nonlocal cur
            if m:
                cur = Match(m.group(1))
                matches.append(cur)
                piece = piece[m.end():]
            (cur.lines if cur else intro).append(piece)

    for tok in walk(zone):
        if tok[0] == "text":
            buf.append(tok[1])
        elif tok[0] == "br":
            flush()
        elif tok[0] == "link":
            flush()
            if cur:
                cur.links.append(tok[1])
            else:
                intro.append(("link", tok[1], tok[2]))
        elif tok[0] == "table":
            heads, links, scores = parse_table(tok[1])
            head_txt = " ".join(heads)
            m = re.search(HEADING, head_txt)
            if m and not (cur and cur.raw == m.group(1) and not cur.scores):
                cur = Match(m.group(1))
                matches.append(cur)
            if cur is None:
                cur = Match("?")
                matches.append(cur)
            cur.lines.extend(heads)
            cur.links.extend(links)
            cur.scores = scores
    flush()
    return intro, matches


def strip_boiler(line):
    if isinstance(line, tuple):
        return ""
    for b in BOILER:
        line = re.sub(b, " ", line, flags=re.I)
    return clean(line)


JUNK = re.compile(
    r"^(.|here\s*:?|aqui|[\d/., ]+|\d{1,2},\s*\d{4})$|@|was found after the", re.I)

YEAR_NOTES = []

LEGACY = json.loads((ROOT / "tools" / "legacy_map.json").read_text())
FIXED_PDFS = []


def month_pdf(date):
    """Find /documents/<month><yy>.pdf (any case, full or 3-letter month)."""
    yy = f"{date.year % 100:02d}"
    names = {date.strftime("%B").lower() + yy, date.strftime("%b").lower() + yy}
    for old in LEGACY:
        stem = old.rsplit("/", 1)[-1].rsplit(".", 1)[0].lower()
        if old.startswith("/documents/") and stem in names:
            return old
    return ""


def yaml_str(s):
    return json.dumps(s, ensure_ascii=False)


def write_year(year):
    intro, matches = segment(year)
    d = OUT
    d.mkdir(parents=True, exist_ok=True)

    # Year intro: keep only notices that aren't the standard thank-you boilerplate.
    standard = re.compile(
        r"Thank you to all|your assistance in setup|We could not do it|Welcome to all the New|"
        r"We are using the PractiScore|The links below|Please check the|range web site|"
        r"Sierra Vista range|for the current|NOTE Due to security|If you want a copy|"
        r"Important Notice", re.I)
    notices = [l for l in (strip_boiler(x) for x in intro) if l and not standard.search(l) and not JUNK.search(l)]
    if notices:
        YEAR_NOTES.append({"year": year, "notice": " ".join(notices)})

    seen = {}
    report = []
    for m in matches:
        date = to_date(m.raw, year)
        ps = next((l for l in m.links if "practiscore.com" in l), "")
        ps = re.sub(r"\?__cf_chl.*$", "", ps)
        pdf = next((l for l in m.links if l.lower().endswith(".pdf")), "")
        if pdf.startswith(SITE):
            pdf = "/" + pdf[len(SITE):]
        if year in (2023, 2024) and pdf == "/documents/december.pdf":
            # The old 2023/2024 pages linked every match to december.pdf; the
            # month's own PDF is on the server, just unlinked.
            fixed = month_pdf(date)
            FIXED_PDFS.append((date, pdf, fixed or "(removed: no PDF for that month)"))
            pdf = fixed
        pdf = LEGACY.get(pdf, pdf)
        notes = []
        for l in m.lines:
            s = strip_boiler(l)
            if s and s not in notes and not JUNK.search(s):
                notes.append(s)
        key = (date, ps, pdf)
        if key in seen:
            report.append(f"  dup dropped {m.raw}")
            continue
        slug = date.isoformat()
        n = sum(1 for k in seen if k[0] == date)
        if n:
            slug += f"-{n + 1}"
        seen[key] = slug
        fm = [
            "---",
            "record: match",
            f"title: {yaml_str(f'{date:%B} {date.day}, {date.year}')}",
            f"date: {date.isoformat()}",
        ]
        if ps:
            fm.append(f"practiscore: {yaml_str(ps)}")
        if pdf:
            fm.append(f"stage_designs: {yaml_str(pdf)}")
        if m.scores:
            fm.append("scores:")
            for r in m.scores:
                fm.append(f"  - {json.dumps(r, ensure_ascii=False)}")
        fm.append("---")
        text = "\n".join(fm) + "\n\n" + "\n\n".join(notes) + "\n"
        (d / f"{slug}.md").write_text(text.rstrip() + "\n", encoding="utf-8")
        report.append(f"  {slug} ps={'Y' if ps else '-'} pdf={pdf or '-'} rows={len(m.scores)} notes={len(notes)}")
    return report


if __name__ == "__main__":
    for y in sorted(PAGES):
        print(y)
        print("\n".join(write_year(y)))
    with open(ROOT / "data" / "years.yaml", "w", encoding="utf-8") as f:
        f.write("# Notices shown at the top of a year's results page.\nnotices:\n")
        for n in YEAR_NOTES:
            f.write(f"  - year: {n['year']}\n    notice: {yaml_str(n['notice'])}\n")
    print("Headings that weren't valid dates (used first Saturday of the month):")
    for y, raw, d in FIXED_DATES:
        print(f"  {y}: {raw!r} -> {d}")
    print("Stage-design links corrected:")
    for d, old, new in FIXED_PDFS:
        print(f"  {d}: {old} -> {new}")
