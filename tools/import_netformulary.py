#!/usr/bin/env python3
"""Import a netFormulary "A-Z" report that someone has saved from their browser.

This script never fetches anything. A person opens the report pages
(Reports -> A-Z of formulary items / A-Z of Non Formulary items, one page per
chapter), saves each one as HTML, and points this script at the folder:

    python3 tools/import_netformulary.py ~/Downloads/swl swl

The second argument is the formulary's folder, data/formularies/<id>/. Create it first with an
about.csv (copy data/formularies/swl/about.csv and edit it). Every Trust whose trust.csv says
formulary,<id> then uses it. Links to each medicine's formulary section use the url in about.csv.

It writes into data/formularies/<id>/:
  formulary.csv        one row per menu medicine: Y / R / N / blank, its BNF chapter, and the matched items as a note

Status: a row on a formulary report is Y, or R if it shows the "Restricted" icon.
A row on a non-formulary report is N. A medicine with no match keeps a blank status.
Edit ALIASES below when a medicine is listed under another name.
"""
import csv, html, re, sys, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# medicine_id -> extra search terms (lower case, matched at the start of an item name)
ALIASES = {
    'alginate_preparation': ['alginate', 'gaviscon', 'peptac'],
    'laxatives': ['lactulose', 'macrogol', 'senna', 'bisacodyl', 'docusate', 'glycerol', 'ispaghula', 'phosphate enema', 'micralax'],
    'crystalloid_fluids': ['compound sodium lactate', 'hartmann', 'plasma-lyte', 'sodium chloride 0.9% infusion'],
    'insulin_soluble': ['insulin soluble', 'soluble insulin', 'insulin human', 'actrapid', 'humulin s'],
    'pabrinex': ['pabrinex', 'vitamins b and c'],
    'phosphate_replacement': ['phosphate', 'sandoz phosphate', 'phosphate-sandoz', 'phosphate polyfusor'],
    'ear_drops_antimicrobial_steroid': ['otomize', 'sofradex', 'betnesol-n', 'locorten', 'ciprofloxacin/dexamethasone', 'cilodex'],
    'entonox': ['nitrous oxide', 'entonox'],
    'glucose': ['glucose', 'dextrose', 'glucogel'],
    'co_codamol': ['co-codamol', 'paracetamol and codeine'],
    'morphine_sulfate': ['morphine'],
    'codeine_phosphate': ['codeine'],
    'glyceryl_trinitrate': ['glyceryl trinitrate', 'gtn'],
    'tetanus_diphtheria_polio_vaccine': ['revaxis', 'diphtheria, tetanus', 'tetanus, diphtheria'],
    'human_tetanus_immunoglobulin': ['tetanus immunoglobulin'],
    'hepatitis_b_vaccine': ['hepatitis b vaccine', 'engerix', 'hbvaxpro'],
    'hiv_post_exposure_prophylaxis': ['emtricitabine/tenofovir', 'truvada', 'raltegravir'],
    'lipid_emulsion': ['lipid emulsion', 'intralipid'],
    'prothrombin_complex_concentrate': ['prothrombin complex', 'octaplex', 'beriplex'],
    'magnesium_sulfate': ['magnesium sulfate', 'magnesium sulphate'],
    'phytomenadione': ['phytomenadione', 'vitamin k'],
    'activated_charcoal': ['activated charcoal', 'charcoal'],
    'oxygen': ['oxygen'],
    'piperacillin_tazobactam': ['piperacillin', 'tazocin'],
    'sodium_chloride_hypertonic': ['sodium chloride 2.7%', 'sodium chloride 3%', 'sodium chloride 30%'],
    'oral_rehydration_salts': ['oral rehydration', 'dioralyte'],
    'digoxin_antibody': ['digoxin specific antibody', 'digifab'],
    'nicotine': ['nicotine'],
}
SKIP = set()  # classes that cannot match a single formulary entry
# Where most matching entries sit in a topical chapter (eye, skin, ENT), name the chapter for the systemic use.
CHAPTER = {
    'prednisolone': '6', 'hydrocortisone': '6', 'diclofenac': '10', 'magnesium_sulfate': '9',
    'sodium_bicarbonate': '9', 'alteplase': '2', 'atropine': '15',
    'glycopyrronium': '15', 'ipratropium_bromide': '3', 'chloramphenicol': '11', 'aciclovir': '5',
    'clotrimazole': '13', 'fusidic_acid': '13', 'doxycycline': '5', 'metronidazole': '5', 'mannitol': '2', 'ulipristal': '7',
    'adrenaline': '3', 'aspirin': '2', 'codeine_phosphate': '4', 'lorazepam': '4', 'midazolam': '4', 'tetracaine': '11', 'naloxone': '18',
}


def parse(path):
    s = path.read_text(encoding='utf-8', errors='replace')
    nonform = bool(re.search(r'A-Z of Non Formulary items', s, re.I))
    if not nonform and not re.search(r'A-Z of formulary items', s, re.I):
        return None
    m = re.search(r'Chapter\s+(\d+)\s*:\s*([^<:]+)', s)
    chapter = f'{int(m.group(1))} {m.group(2).strip()}' if m else ''
    items = []
    for tr in re.findall(r'<tr class="TblMain(?:Alternative)?">([\s\S]*?)</tr>', s):
        tds = re.findall(r'<td[^>]*>([\s\S]*?)</td>', tr)
        if len(tds) < 3:
            continue
        text = lambda t: re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', html.unescape(re.sub(r'<[^>]+>', ' ', t)))).strip()
        status = 'N' if nonform else ('R' if 'alt="Restricted"' in tds[1] else 'Y')
        name = text(re.search(r'<span class="boldDrug">([\s\S]*?)</span>', tds[1]).group(1)) if 'boldDrug' in tds[1] else text(tds[1])
        link = re.search(r'href="([^"]+)"', tds[0])
        url = html.unescape(link.group(1)).lstrip('./') if link else ''
        items.append({'chapter': chapter, 'bnf_section': text(tds[0]), 'name': name, 'brand': text(tds[2]).replace('®', ''), 'status': status, 'url': url})
    return items


def norm(s):
    return re.sub(r'\s+', ' ', s.lower().replace('sulphate', 'sulfate').replace('®', '')).strip()


def main(folder, fid):
    folder, out_dir = Path(folder).expanduser(), ROOT / 'data' / 'formularies' / fid
    if not (out_dir / 'about.csv').exists():
        sys.exit(f'No data/formularies/{fid}/about.csv: create it first (copy data/formularies/swl/about.csv and edit it).')
    items, used = [], 0
    for p in sorted(folder.glob('*.htm*')):
        got = parse(p)
        if got is None:
            print(f'skip (not a netFormulary A-Z report): {p.name}')
            continue
        used += 1
        items += got
    if not items:
        sys.exit('No report rows found.')
    items = [dict(t) for t in {tuple(sorted(i.items())) for i in items}]
    items.sort(key=lambda i: (i['chapter'], i['bnf_section'], i['name'], i['status'], i['brand'], i['url']))  # a total order: runs agree
    # every item in the saved pages, for checking matches: kept out of git, since it copies the whole formulary
    local = ROOT / '.cache' / 'formulary' / fid
    local.mkdir(parents=True, exist_ok=True)
    print(f'all items -> {local.relative_to(ROOT)}/formulary_items.csv (local only, not committed)')
    with open(local / 'formulary_items.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['chapter', 'bnf_section', 'name', 'brand', 'status', 'url'])
        w.writeheader(); w.writerows(items)

    chapters = sorted({i['chapter'] for i in items}, key=lambda c: int(c.split()[0]))
    about = {r['key']: r['value'] for r in csv.DictReader(open(out_dir / 'about.csv', encoding='utf-8-sig'))}
    base = about.get('url', '').rstrip('/') + '/' if about.get('url') else ''
    label = about.get('short') or fid.upper()
    meds = {r['medicine_id']: r for r in csv.DictReader(open(ROOT / 'data' / 'medicines.csv', encoding='utf-8-sig'))}
    menu_ids = sorted(meds)  # every shared medicine, so the formulary serves every Trust that uses it
    rows, counts = [], {'Y': 0, 'R': 0, 'N': 0, '': 0}
    for mid in menu_ids:
        status, note, chapter, url = '', '', '', ''
        if mid not in SKIP:
            terms = ALIASES.get(mid) or [norm(re.sub(r'\(.*?\)', '', meds[mid]['name']))]
            hits = [i for i in items if any(re.match(re.escape(t) + r'\b', norm(i['name'])) or re.match(re.escape(t) + r'\b', norm(i['brand'])) for t in terms)]
            if hits:
                ss = {h['status'] for h in hits}
                status = 'Y' if 'Y' in ss else 'R' if 'R' in ss else 'N'
                url = next((base + h['url'] for h in hits if h['status'] == status and h['url']), '')
                names = sorted({h['name'] + (' [restricted]' if h['status'] == 'R' else ' [non-formulary]' if h['status'] == 'N' else '') for h in hits})
                note = f'{label}: ' + '; '.join(names[:4]) + (f' (+{len(names) - 4} more)' if len(names) > 4 else '')
                chs = [h['chapter'] for h in hits]
                want = [c for c in chs if c.split()[0] == CHAPTER.get(mid)]
                exact = [h['chapter'] for h in hits if norm(h['name']) in terms]
                pool = exact or chs  # most common chapter; a tie goes to the lower chapter number, so every run agrees
                chapter = (want or sorted(set(pool), key=lambda c: (-pool.count(c), int(c.split()[0]))))[0]
            else:
                note = f'Not found in the imported formulary reports ({len(chapters)} chapters)'
        counts[status] += 1
        rows.append({'medicine_id': mid, 'route': '', 'status': status, 'bnf_chapter': chapter, 'note': note, 'url': url})
    with open(out_dir / 'formulary.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['medicine_id', 'route', 'status', 'bnf_chapter', 'note', 'url'])
        w.writeheader(); w.writerows(rows)

    # record the import date so pages can show how current the formulary is
    about_rows = list(csv.reader(open(out_dir / 'about.csv', encoding='utf-8-sig')))
    today = datetime.date.today().isoformat()
    if any(r[:1] == ['imported'] for r in about_rows):
        about_rows = [['imported', today] if r[:1] == ['imported'] else r for r in about_rows]
    else:
        about_rows.append(['imported', today])
    with open(out_dir / 'about.csv', 'w', newline='', encoding='utf-8') as f:
        csv.writer(f).writerows(about_rows)

    print(f'{used} report page(s), {len(items)} items, chapters: {", ".join(c.split()[0] for c in chapters)}')
    print(f'medicines: {counts["Y"]} formulary, {counts["R"]} restricted, {counts["N"]} non-formulary, {counts[""]} not found')
    print(f'imported {datetime.date.today().isoformat()} -> {out_dir.relative_to(ROOT)}/formulary.csv')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
