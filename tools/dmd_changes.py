#!/usr/bin/env python3
"""Summarise what a dm+d refresh changed, compared with the last commit.

    python3 tools/dmd_changes.py [summary.md]

Prints a Markdown summary (or writes it to the file given) and exits with status 0 if medicine
codes, names, BNF sections, controlled-drug schedules or route coverage changed, or 1 if only the
release details did. Used by .github/workflows/refresh-dmd.yml. Standard library only.
"""
import csv, io, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = {'data/medicines.csv': ('medicine_id',), 'data/dmd/medicine_routes.csv': ('medicine_id', 'route')}


def rows(text, key):
    return {tuple(r[k] for k in key): r for r in csv.DictReader(io.StringIO(text))}


def committed(path):
    out = subprocess.run(['git', '-C', str(ROOT), 'show', f'HEAD:{path}'], capture_output=True, text=True)
    return out.stdout if out.returncode == 0 else ''


def main(argv):
    lines, meaningful = [], False
    release = {r['key']: r['value'] for r in csv.DictReader(open(ROOT / 'data/dmd/dmd_release.csv', encoding='utf-8-sig'))}
    lines.append(f"dm+d {release.get('dmd_release', '?')}, released {release.get('release_date', '?')}.\n")
    for path, key in FILES.items():
        old, new = rows(committed(path), key), rows((ROOT / path).read_text(encoding='utf-8-sig'), key)
        changes = []
        for k in sorted(set(old) | set(new)):
            a, b = old.get(k), new.get(k)
            name = ' '.join(k)
            if a is None:
                changes.append(f'- **{name}**: added')
            elif b is None:
                changes.append(f'- **{name}**: removed')
            else:
                diff = [f'{f}: `{a.get(f, "")}` → `{b.get(f, "")}`' for f in b if a.get(f, '') != b.get(f, '')]
                if diff:
                    flag = ' ⚠️ **controlled-drug schedule**' if any(f.startswith('cd_') for f in b if a.get(f, '') != b.get(f, '')) else ''
                    changes.append(f'- **{name}**{flag}: ' + '; '.join(diff))
        if changes:
            meaningful = True
            lines.append(f'### `{path}`\n')
            lines += changes
            lines.append('')
    if not meaningful:
        lines.append('No changes to medicine codes, names, BNF sections, schedules or routes.')
    text = '\n'.join(lines) + '\n'
    if argv:
        Path(argv[0]).write_text(text, encoding='utf-8')
    else:
        print(text)
    return 0 if meaningful else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
