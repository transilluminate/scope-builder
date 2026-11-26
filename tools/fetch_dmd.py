#!/usr/bin/env python3
"""Download the latest dm+d release (and its supplementary file, used for BNF codes) from NHS TRUD.

Needs a TRUD account subscribed to items 24 (NHSBSA dm+d) and 25 (NHSBSA dm+d supplementary).
Give the API key in an environment variable or a file; it is never written anywhere:

    TRUD_API_KEY=... python3 tools/fetch_dmd.py
    python3 tools/fetch_dmd.py --key-file ~/path/to/key

Files are checked against TRUD's published SHA-256 and unpacked into .cache/dmd/<release>/.
Re-running skips anything already downloaded. Standard library only.
"""
import argparse, hashlib, io, json, os, sys, urllib.error, urllib.request, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / '.cache' / 'dmd'
ITEMS = {24: 'dmd', 25: 'dmdbonus'}
UA = {'User-Agent': 'scope-builder/0.1 (dm+d download)'}


def get(url, key):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', 'replace').replace(key, '<key>')
        sys.exit(f'TRUD returned {e.code}: {body[:300]}')


def unzip_all(data, dest):
    """Unpack a zip, including zips nested inside it (the bonus file has these)."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for name in z.namelist():
            if name.endswith('/'):
                continue
            inner = z.read(name)
            if name.lower().endswith('.zip'):
                unzip_all(inner, dest / Path(name).stem)
            else:
                out = dest / Path(name).name
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(inner)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--key-file', help='file containing the TRUD API key')
    args = ap.parse_args()
    key = (Path(args.key_file).expanduser().read_text() if args.key_file else os.environ.get('TRUD_API_KEY', '')).strip()
    if not key:
        sys.exit('No TRUD API key: set TRUD_API_KEY or pass --key-file.')
    for item, label in ITEMS.items():
        meta = json.loads(get(f'https://isd.digital.nhs.uk/trud/api/v1/keys/{key}/items/{item}/releases?latest', key))
        rel = meta['releases'][0]
        dest = CACHE / rel['id'].removesuffix('.zip')
        if (dest / '.complete').exists():
            print(f'{label}: {rel["name"]} ({rel["releaseDate"]}) already in {dest.relative_to(ROOT)}')
            continue
        print(f'{label}: downloading {rel["archiveFileName"]} ({rel["archiveFileSizeBytes"] / 1e6:.1f} MB)')
        data = get(rel['archiveFileUrl'], key)
        digest = hashlib.sha256(data).hexdigest().upper()
        if digest != rel['archiveFileSha256'].upper():
            sys.exit(f'{label}: checksum mismatch ({digest} != {rel["archiveFileSha256"]}); not unpacking.')
        dest.mkdir(parents=True, exist_ok=True)
        unzip_all(data, dest)
        (dest / '.complete').write_text(json.dumps({k: v for k, v in rel.items() if 'Url' not in k}, indent=2))
        print(f'{label}: {rel["name"]} ({rel["releaseDate"]}) checksum OK -> {dest.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
