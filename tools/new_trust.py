#!/usr/bin/env python3
"""Start a new Trust by copying another Trust's menu and profiles.

    python3 tools/new_trust.py <id> "<Trust name>" <SHORT> [--formulary swl] [--from krft]

Creates data/trusts/<id>/ with:
  trust.csv       your Trust's name, short name and region (edit the rest)
  menu.csv        copied, with every row marked unreviewed for your Trust
  profiles.csv    copied, unreviewed
  profiles/*.csv  copied

The formulary is not copied: it lives in data/formularies/<id>/ and is shared by every Trust that
uses it. Name an existing one with --formulary, or import a new one (see README).
"""
import argparse, csv, re, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRUSTS = ROOT / 'data' / 'trusts'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('id', help='folder name: lower-case letters, digits and hyphens, e.g. kch')
    ap.add_argument('name', help='full Trust name')
    ap.add_argument('short', help='short name, e.g. KCH')
    ap.add_argument('--region', default='')
    ap.add_argument('--formulary', default='', help='formulary id from data/formularies/, e.g. swl')
    ap.add_argument('--from', dest='src', default='krft', help='Trust to copy the menu and profiles from')
    a = ap.parse_args()
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', a.id):
        sys.exit('id must be lower-case letters, digits and hyphens')
    src, dst = TRUSTS / a.src, TRUSTS / a.id
    if dst.exists():
        sys.exit(f'{dst.relative_to(ROOT)} already exists')
    if not src.exists():
        sys.exit(f'no Trust called {a.src!r} to copy from')
    if a.formulary and not (ROOT / 'data' / 'formularies' / a.formulary / 'about.csv').exists():
        sys.exit(f'no formulary called {a.formulary!r} in data/formularies/')

    dst.mkdir(parents=True)
    shutil.copytree(src / 'profiles', dst / 'profiles')
    for name in ('menu.csv', 'profiles.csv'):
        rows = list(csv.DictReader(open(src / name, encoding='utf-8-sig')))
        for r in rows:
            r['source'] = f'copied from {a.src}'
            r['reviewed'] = ''
        with open(dst / name, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    with open(dst / 'trust.csv', 'w', newline='', encoding='utf-8') as f:
        csv.writer(f).writerows([
            ['key', 'value'], ['trust_name', a.name], ['trust_short', a.short], ['region', a.region], ['formulary', a.formulary],
            ['menu_status', f'Copied from {a.src}; not yet reviewed for {a.short}'], ['contact', ''],
        ])
    print(f'Created {dst.relative_to(ROOT)}/. Next: edit trust.csv, review the menu and profiles, '
          f'{"" if a.formulary else "import or choose a formulary, "}then run python3 build.py {a.id}')


if __name__ == '__main__':
    main()
