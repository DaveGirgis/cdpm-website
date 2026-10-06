"""Download the old site's PDFs and images into static/ under case-safe names.

The old server is case-sensitive (May.pdf and may.pdf are different files), but
Windows checkouts are not, so every file is stored lowercased under
static/documents/legacy/ with a numeric suffix when two names collide.
Writes tools/legacy_map.json: {old path: new path}.

    python tools/legacy_files.py
"""
import hashlib
import json
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://cochisedefensivepistolmatch.com/"
LIST = ROOT / "_scrape" / "dl.txt"
STATIC = ROOT / "static"


def fetch(rel):
    url = BASE + urllib.parse.quote(urllib.parse.unquote(rel))
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (cdpm-archive)"})
    return urllib.request.urlopen(req, timeout=120).read()


def main():
    mapping, by_hash, used = {}, {}, set()
    for rel in LIST.read_text().split():
        folder = "documents/legacy" if rel.lower().startswith("documents/") else "images/legacy"
        if rel.lower().endswith("spacer.gif") or rel.startswith("images/img_"):
            continue  # layout slices from the old template
        data = fetch(rel)
        h = hashlib.sha256(data).hexdigest()
        if h in by_hash:
            mapping["/" + rel] = by_hash[h]
            continue
        name = Path(urllib.parse.unquote(rel)).name.lower()
        stem, ext = name.rsplit(".", 1)
        new, n = f"{folder}/{name}", 2
        while new in used:
            new, n = f"{folder}/{stem}-{n}.{ext}", n + 1
        used.add(new)
        out = STATIC / new
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        by_hash[h] = mapping["/" + rel] = "/" + new
    (ROOT / "tools" / "legacy_map.json").write_text(json.dumps(mapping, indent=1, sort_keys=True))
    print(len(mapping), "paths ->", len(used), "files")


if __name__ == "__main__":
    main()
