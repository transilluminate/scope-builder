#!/usr/bin/env python3
"""Add dm+d codes to the medicines list, using a release fetched by tools/fetch_dmd.py.

    python3 tools/import_dmd.py

For each medicine in data/medicines.csv it:
  - finds the dm+d VTM (virtual therapeutic moiety: the drug itself, e.g. "Morphine").
    An existing dmd_vtm value is kept, so a human can fix a mapping once and it sticks.
    A VTM that dm+d has since replaced is updated to its successor.
  - records the most common BNF section across that VTM's products (VMPs). ATC codes are not
    imported: the builder does not need them, and they carry the WHO's own copyright terms.
  - writes data/dmd/medicine_routes.csv: for each medicine and route, how many dm+d
    products exist and which controlled-drug schedules they carry (e.g. morphine oral: 2 and 5).
  - writes data/dmd/dmd_release.csv with the release used.

Medicines that are classes (e.g. "Laxatives") or not in dm+d (some blood products) keep a
blank dmd_vtm; list them in NO_VTM so they are not reported as missing.
"""
import collections, csv, glob, json, re, sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'

# our medicine name differs from the dm+d VTM name; a list maps one medicine to several VTMs (e.g. salts)
VTM_NAMES = {
    'diclofenac': ['Diclofenac sodium', 'Diclofenac potassium'],
    'phenytoin': ['Phenytoin', 'Phenytoin sodium'],
    'phenobarbital': ['Phenobarbital', 'Phenobarbital sodium'],
    'codeine_phosphate': 'Codeine',
    'morphine_sulfate': 'Morphine',
    'entonox': 'Nitrous oxide + Oxygen',
    'fondaparinux': 'Fondaparinux sodium',
    'glycopyrronium': 'Glycopyrronium bromide',
    'human_tetanus_immunoglobulin': 'Tetanus immunoglobulin human',
    'insulin_soluble': 'Insulin soluble human',
    'ipratropium_bromide': 'Ipratropium',
    'naseptin': 'Neomycin + Chlorhexidine',
    'tetanus_diphtheria_polio_vaccine': 'Diphtheria + Tetanus + Poliomyelitis vaccine',
    'lipid_emulsion': 'Soya oil',
    'promethazine': 'Promethazine hydrochloride',
    'digoxin_antibody': 'Digoxin specific antibody',
    'sodium_chloride_hypertonic': 'Sodium chloride',
}
# classes, regimens, or products dm+d holds without a VTM
NO_VTM = {'alginate_preparation', 'crystalloid_fluids', 'oral_rehydration_salts', 'ear_drops_antimicrobial_steroid',
          'hiv_post_exposure_prophylaxis', 'laxatives', 'oxygen', 'pabrinex', 'phosphate_replacement',
          'prothrombin_complex_concentrate'}
# dm+d controlled drug category -> our schedule code
CD_CATEGORY = {'0001': '1', '0002': '2', '0003': '2', '0004': '3', '0005': '3', '0006': '3', '0007': '3',
               '0008': '4-2', '0009': '4-1', '0010': '5'}
SCHEDULE_ORDER = ['1', '2', '3', '4-1', '4-2', '5']


def release_dir(prefix):
    dirs = sorted(glob.glob(str(ROOT / '.cache' / 'dmd' / f'{prefix}_*')))
    if not dirs:
        sys.exit('No dm+d release in .cache/dmd; run tools/fetch_dmd.py first.')
    return Path(dirs[-1])


def one(folder, pattern):
    return ET.parse(next(folder.rglob(pattern))).getroot()


def main():
    dmd, bonus = release_dir('nhsbsa_dmd'), release_dir('nhsbsa_dmdbonus')
    rel = json.loads((dmd / '.complete').read_text())

    vtms, successor, previous = {}, {}, {}
    for v in one(dmd, 'f_vtm2_*.xml'):
        vid = v.findtext('VTMID')
        if v.findtext('VTMIDPREV'):
            successor[v.findtext('VTMIDPREV')] = vid
            previous[vid] = v.findtext('VTMIDPREV')
        if v.findtext('INVALID') != '1':
            vtms[vid] = v.findtext('NM')
    by_name = {n.lower(): i for i, n in vtms.items()}

    root = one(dmd, 'f_vmp2_*.xml')
    vmp_vtm = {}
    for v in root.find('VMPS'):
        if v.findtext('INVALID') != '1' and v.findtext('VTMID'):
            vmp_vtm[v.findtext('VPID')] = v.findtext('VTMID')
    vmp_routes = collections.defaultdict(set)
    for r in root.find('DRUG_ROUTE'):
        vmp_routes[r.findtext('VPID')].add(r.findtext('ROUTECD'))
    vmp_cd = {c.findtext('VPID'): CD_CATEGORY.get(c.findtext('CATCD'), '') for c in root.find('CONTROL_DRUG_INFO')}
    vmp_codes = {}
    for v in one(bonus, 'f_bnf1_*.xml').find('VMPS'):
        vmp_codes[v.findtext('VPID')] = v.findtext('BNF') or ''

    by_vtm = collections.defaultdict(list)
    for vpid, vid in vmp_vtm.items():
        by_vtm[vid].append(vpid)

    routes = list(csv.DictReader(open(DATA / 'legal' / 'routes.csv', encoding='utf-8-sig')))
    meds_path = DATA / 'medicines.csv'
    meds = list(csv.DictReader(open(meds_path, encoding='utf-8-sig')))
    fields = ['medicine_id', 'name', 'cd_schedule', 'cd_ingredient', 'dmd_vtm', 'dmd_vtm_prev', 'dmd_name', 'bnf', 'note']

    out_routes, missing, moved = [], [], []
    for m in meds:
        mid = m['medicine_id']
        vids = m.get('dmd_vtm', '').split()
        for i, vid in enumerate(vids):
            while vid in successor and vid not in vtms:
                moved.append(f'{mid}: VTM {vid} -> {successor[vid]}'); vid = successor[vid]
            vids[i] = vid
        if not vids and mid not in NO_VTM:
            names = VTM_NAMES.get(mid) or re.sub(r'\s*\(.*?\)', '', m['name'])
            for name in ([names] if isinstance(names, str) else names):
                if name.lower() in by_name:
                    vids.append(by_name[name.lower()])
                else:
                    missing.append(f'{mid} ("{name}")')
        m['dmd_vtm'], m['dmd_name'] = ' '.join(vids), ' / '.join(vtms.get(v, '?') for v in vids)
        # earlier codes for the same drug, so scope links made before a dm+d re-coding still resolve
        m['dmd_vtm_prev'] = ' '.join(sorted({previous[v] for v in vids if v in previous} | set(m.get('dmd_vtm_prev', '').split())))
        vpids = [p for v in vids for p in by_vtm.get(v, [])]
        bnfs = collections.Counter(vmp_codes[p][:6] for p in vpids if vmp_codes.get(p))
        m['bnf'] = '.'.join(re.findall('..', bnfs.most_common(1)[0][0])) if bnfs else ''
        for r in routes:
            codes = set(r['dmd_routes'].split())
            hits = [p for p in vpids if vmp_routes[p] & codes]
            if hits:
                cds = sorted({vmp_cd.get(p, '') for p in hits} - {''}, key=SCHEDULE_ORDER.index)
                out_routes.append({'medicine_id': mid, 'route': r['route_id'], 'products': len(hits), 'cd_schedules': ' '.join(cds)})

    with open(meds_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore'); w.writeheader(); w.writerows(meds)
    (DATA / 'dmd').mkdir(exist_ok=True)
    with open(DATA / 'dmd' / 'medicine_routes.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['medicine_id', 'route', 'products', 'cd_schedules']); w.writeheader(); w.writerows(out_routes)
    with open(DATA / 'dmd' / 'dmd_release.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['key', 'value'])
        w.writerows([['dmd_release', rel['name']], ['release_date', rel['releaseDate']], ['archive', rel['archiveFileName']]])

    coded = sum(1 for m in meds if m['dmd_vtm'])
    print(f'dm+d {rel["name"]} ({rel["releaseDate"]}): {coded} of {len(meds)} medicines coded, {len(NO_VTM)} classes/no VTM by design')
    for x in moved: print('  updated:', x)
    for x in missing: print('  NOT FOUND:', x)


if __name__ == '__main__':
    main()
