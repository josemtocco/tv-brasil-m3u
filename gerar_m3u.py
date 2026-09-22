import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
SOURCES = ROOT / "fontes.json"
FILTERS = ROOT / "filtros.json"
OUTPUT = ROOT / "tv-brasil.m3u"
STATUS = ROOT / "status.json"

UA = "Mozilla/5.0 (compatible; TVBrasil-M3U-Generator/1.0)"

def clean(v):
    return str(v or "").replace('"', "'").replace("\r", " ").replace("\n", " ").strip()

def valid_url(url):
    try:
        p = urlparse(clean(url))
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False

def fetch(url, timeout=25):
    req = Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urlopen(req, timeout=timeout) as r:
        data = r.read()
        charset = r.headers.get_content_charset() or "utf-8"
        return data.decode(charset, errors="replace")

def parse_extinf(line):
    if "#EXTINF:" not in line:
        return None
    body = line.split("#EXTINF:", 1)[1]
    attrs = {}
    for m in re.finditer(r'([\w-]+)="([^"]*)"', body):
        attrs[m.group(1)] = m.group(2)
    title = body.rsplit(",", 1)[-1].strip() if "," in body else attrs.get("tvg-name", "")
    return {
        "name": clean(title),
        "tvg_id": clean(attrs.get("tvg-id")),
        "logo": clean(attrs.get("tvg-logo")),
        "group": clean(attrs.get("group-title"))
    }

def parse_m3u(text):
    result = []
    current = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF:"):
            current = parse_extinf(line)
        elif not line.startswith("#") and valid_url(line):
            if current:
                current["url"] = line
                current["enabled"] = True
                result.append(current)
            current = None
    return result

def parse_json(text):
    obj = json.loads(text)
    if isinstance(obj, dict):
        obj = obj.get("channels", obj.get("items", []))
    result = []
    for item in obj if isinstance(obj, list) else []:
        if not isinstance(item, dict):
            continue
        result.append({
            "name": clean(item.get("name") or item.get("title")),
            "url": clean(item.get("url") or item.get("stream") or item.get("stream_url")),
            "logo": clean(item.get("logo") or item.get("tvg-logo")),
            "group": clean(item.get("group") or item.get("category")),
            "tvg_id": clean(item.get("tvg_id") or item.get("tvg-id")),
            "country": clean(item.get("country")),
            "enabled": item.get("enabled", True)
        })
    return result

def normalize(ch, source):
    ch = dict(ch)
    ch["source"] = source
    ch["name"] = clean(ch.get("name"))
    ch["url"] = clean(ch.get("url"))
    ch["group"] = clean(ch.get("group")) or "TV Brasil"
    ch["logo"] = clean(ch.get("logo"))
    ch["tvg_id"] = clean(ch.get("tvg_id"))
    return ch

def looks_brazilian(ch, cfg):
    text = " ".join([
        ch.get("name", ""), ch.get("group", ""),
        ch.get("tvg_id", ""), ch.get("country", "")
    ]).lower()

    country = ch.get("country", "").lower()
    if country in {x.lower() for x in cfg["allowed_countries"]}:
        return True

    return any(k.lower() in text for k in cfg["brazil_keywords"])

def blocked(ch, cfg):
    text = " ".join([ch.get("name", ""), ch.get("group", "")]).lower()
    return any(k.lower() in text for k in cfg["blocked_keywords"])

def check_url(item, timeout=10):
    url = item["url"]
    try:
        req = Request(url, method="HEAD", headers={"User-Agent": UA})
        with urlopen(req, timeout=timeout) as r:
            return item, True, r.status
    except Exception:
        try:
            req = Request(url, headers={"User-Agent": UA, "Range": "bytes=0-64"})
            with urlopen(req, timeout=timeout) as r:
                return item, True, r.status
        except Exception:
            return item, False, None

def build_m3u(items):
    lines = ['#EXTM3U']
    for ch in items:
        attrs = [
            f'tvg-name="{clean(ch["name"])}"',
            f'group-title="{clean(ch["group"])}"'
        ]
        if ch.get("tvg_id"):
            attrs.append(f'tvg-id="{clean(ch["tvg_id"])}"')
        if ch.get("logo"):
            attrs.append(f'tvg-logo="{clean(ch["logo"])}"')
        lines.append(f'#EXTINF:-1 {" ".join(attrs)},{clean(ch["name"])}')
        lines.append(ch["url"])
    return "\n".join(lines) + "\n"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-streams", action="store_true")
    ap.add_argument("--workers", type=int, default=10)
    args = ap.parse_args()

    sources = json.loads(SOURCES.read_text(encoding="utf-8"))
    cfg = json.loads(FILTERS.read_text(encoding="utf-8"))

    channels = []
    source_stats = []

    for src in sources:
        if not src.get("enabled", True):
            continue
        try:
            raw = fetch(src["url"])
            parsed = parse_json(raw) if src.get("format") == "json" else parse_m3u(raw)
            parsed = [normalize(x, src["name"]) for x in parsed]
            if src.get("brazil_only", True):
                parsed = [x for x in parsed if looks_brazilian(x, cfg)]
            parsed = [x for x in parsed if x.get("enabled", True) and valid_url(x.get("url")) and not blocked(x, cfg)]
            channels.extend(parsed)
            source_stats.append({"source": src["name"], "downloaded": len(parsed), "error": None})
        except Exception as e:
            source_stats.append({"source": src["name"], "downloaded": 0, "error": str(e)})

    # Duplicidade: URL primeiro; depois nome + URL.
    unique = {}
    for ch in channels:
        key = ch["url"].strip().lower()
        if key not in unique:
            unique[key] = ch
    channels = list(unique.values())
    channels.sort(key=lambda x: (x["group"].lower(), x["name"].lower()))

    checked = 0
    online = 0

    if args.check_streams and channels:
        good = []
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
            futures = [ex.submit(check_url, ch) for ch in channels]
            for f in as_completed(futures):
                ch, ok, _ = f.result()
                checked += 1
                if ok:
                    online += 1
                    good.append(ch)
        channels = sorted(good, key=lambda x: (x["group"].lower(), x["name"].lower()))

    OUTPUT.write_text(build_m3u(channels), encoding="utf-8")

    report = {
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sources": source_stats,
        "channels_before_deduplication": len(channels),
        "channels_output": len(channels),
        "streams_checked": checked,
        "streams_online": online
    }
    STATUS.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Canais na playlist: {len(channels)}")
    print(f"Streams verificados: {checked}")
    print(f"Streams respondendo: {online}")

if __name__ == "__main__":
    main()
