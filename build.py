#!/usr/bin/env python3
"""Check the CSV data and bake it into one self-contained HTML file.

    python3 build.py              # builds every trust in data/trusts/
    python3 build.py krft         # builds one trust

Output: dist/<trust>-scope-builder.html  (no dependencies, opens from file:// or email)
Standard library only.
"""
import csv, datetime, html, io, json, os, re, shutil, subprocess, sys, urllib.parse
from pathlib import Path

ROOT = Path(__file__).parent
SHARED = ['legal/professions.csv', 'legal/cd_named.csv', 'legal/routes.csv', 'legal/sources.csv', 'medicines.csv',
          'dmd/medicine_routes.csv', 'dmd/dmd_release.csv', 'frozen_ids.csv']
TRUST = ['trust.csv', 'profiles.csv', 'menu.csv']
FORMULARY_HEADER = 'medicine_id,route,status,bnf_chapter,note,url\n'
# formulary details from data/formularies/<id>/about.csv, shown to the page as these trust.csv keys
FORMULARY_KEYS = {'name': 'formulary_name', 'full_name': 'formulary_source', 'url': 'formulary_url', 'imported': 'formulary_imported',
                  'licence': 'formulary_licence', 'permission': 'formulary_permission'}
FAMILIES = {'oral', 'mucosal', 'injection', 'inhaled', 'topical', 'rectal'}
SCHEDULE_ORDER = ['1', '2', '3', '4-1', '4-2', '5']
SCHEDULES = {''} | set(SCHEDULE_ORDER)


def read(path):
    text = path.read_text(encoding='utf-8-sig')  # tolerate Excel's BOM
    return text, list(csv.DictReader(io.StringIO(text)))


def check(t, trust):
    errs, warns = [], []
    def need(cond, msg):
        if not cond: errs.append(f'[{trust}] {msg}')
    def warn(cond, msg):
        if not cond: warns.append(f'[{trust}] note: {msg}')

    profs = {r['profession_id'] for r in t['professions.csv']}
    routes = {r['route_id']: r for r in t['routes.csv']}
    classes = {r['legal_class'] for r in routes.values()}
    meds = {r['medicine_id']: r for r in t['medicines.csv']}

    for r in t['professions.csv']:
        need(r['cd_rule'] in {'any', 'named', 'none'}, f"professions.csv {r['profession_id']}: cd_rule must be any/named/none")
        need(r['schedule5'] in {'any', 'named'}, f"professions.csv {r['profession_id']}: schedule5 must be any/named")
    for i, r in enumerate(t['cd_named.csv'], 2):
        need(r['profession_id'] in profs, f"cd_named.csv line {i}: unknown profession {r['profession_id']!r}")
        need(r['medicine_id'] in meds, f"cd_named.csv line {i}: unknown medicine {r['medicine_id']!r}")
        need(r['legal_class'] in classes, f"cd_named.csv line {i}: legal_class {r['legal_class']!r} not used by any route")
    for k, r in routes.items():
        need(r['family'] in FAMILIES, f"routes.csv {k}: family {r['family']!r} not one of {sorted(FAMILIES)}")
    for k, m in meds.items():
        need(m['cd_schedule'] in SCHEDULES, f"medicines.csv {k}: cd_schedule {m['cd_schedule']!r} not one of {sorted(SCHEDULES)}")
        need(not m['cd_ingredient'] or m['cd_ingredient'] in meds, f"medicines.csv {k}: cd_ingredient {m['cd_ingredient']!r} unknown")
    # the legal gate must never miss a controlled drug: our schedule must match dm+d's most restrictive one
    dmd = {}
    for r in t['medicine_routes.csv']:
        dmd.setdefault(r['medicine_id'], {})[r['route']] = r['cd_schedules'].split()
    for k, m in meds.items():
        seen_sch = sorted({s for v in dmd.get(k, {}).values() for s in v}, key=SCHEDULE_ORDER.index)
        if m.get('dmd_vtm'):
            need((seen_sch[0] if seen_sch else '') == m['cd_schedule'],
                 f"medicines.csv {k}: cd_schedule {m['cd_schedule']!r} but dm+d products are {' '.join(seen_sch) or 'not controlled'}")
    seen = set()
    for i, r in enumerate(t['menu.csv'], 2):
        need(r['medicine_id'] in meds, f"menu.csv line {i}: unknown medicine {r['medicine_id']!r} (add it to medicines.csv)")
        need(r['route'] in routes, f"menu.csv line {i}: unknown route {r['route']!r} (see legal/routes.csv)")
        if meds.get(r['medicine_id'], {}).get('dmd_vtm'):
            warn(r['route'] in dmd.get(r['medicine_id'], {}), f"menu.csv line {i}: no dm+d product for {r['medicine_id']} by {r['route']} (off-label route?)")
        k = (r['system'], r['presentation'], r['medicine_id'], r['route'])
        need(k not in seen, f'menu.csv line {i}: duplicate row'); seen.add(k)
    # profiles: named subsets of the menu, one CSV each, listed in profiles.csv
    items = {f"{r['medicine_id']}|{r['route']}" for r in t['menu.csv']}
    in_any = set()
    ids = [r['profile_id'] for r in t['profiles.csv']]
    need(len(set(ids)) == len(ids), 'profiles.csv: duplicate profile_id')
    for r in t['profiles.csv']:
        need(r['default'].strip().upper() in {'', 'Y'}, f"profiles.csv {r['profile_id']}: default must be Y (ticked for everyone) or blank")
    for pid, rows in t['__profiles'].items():
        need(pid in ids, f'profiles/{pid}.csv is not listed in profiles.csv')
        pseen = set()
        for i, r in enumerate(rows, 2):
            k = f"{r['medicine_id']}|{r['route']}"
            need(k in items, f'profiles/{pid}.csv line {i}: {k} is not on the menu')
            need(k not in pseen, f'profiles/{pid}.csv line {i}: duplicate'); pseen.add(k); in_any.add(k)
    for pid in ids:
        need(pid in t['__profiles'], f'profiles.csv lists {pid!r} but profiles/{pid}.csv is missing')
    for k in sorted(items - in_any):
        warn(False, f'{k} is on the menu but in no profile (shown only with "whole menu")')
    # ids that appear in scope links and fingerprints are permanent: route ids, and medicine ids with no dm+d code
    frozen = {(r['kind'], r['id']) for r in t['frozen_ids.csv']}
    current = {('route', k) for k in routes} | {('local_medicine', k) for k, m in meds.items() if not m.get('dmd_vtm')}
    for kind, k in sorted(frozen):
        if kind == 'route':
            need(k in routes, f'route id {k!r} is frozen (scope links use it) and cannot be removed or renamed')
        elif kind == 'local_medicine':
            need(k in meds, f'medicine id {k!r} is frozen (scope links use it) and cannot be removed or renamed')
    for kind, k in sorted(current - frozen):
        need(False, f'new {kind.replace("_", " ")} id {k!r}: ids are permanent once used in scope links, so add it to data/frozen_ids.csv deliberately')
    spec = (ROOT / 'SPEC.md').read_text(encoding='utf-8')  # the open format document lists every route id
    for k in sorted(routes):
        need(f'| `{k}` |' in spec, f'route id {k!r} is not in the route table in SPEC.md, section 2.2')
    for i, r in enumerate(t['formulary.csv'], 2):
        need(r['medicine_id'] in meds, f"formulary.csv line {i}: unknown medicine {r['medicine_id']!r}")
        need(not r['route'] or r['route'] in routes, f"formulary.csv line {i}: unknown route {r['route']!r}")
        need(r['status'].upper() in {'', 'Y', 'N', 'R'}, f"formulary.csv line {i}: status must be Y, N, R or blank")
    fid = {r['key']: r['value'] for r in t['trust.csv']}.get('formulary', '')
    if fid:
        listed = {r['medicine_id'] for r in t['formulary.csv']}
        unlisted = sorted({r['medicine_id'] for r in t['menu.csv']} - listed)
        if unlisted:
            warns.append(f'[{trust}] note: {len(unlisted)} menu medicine(s) have no row in formulary {fid!r} '
                         f'(shown as "not checked"; re-run the import): {", ".join(unlisted[:8])}{" ..." if len(unlisted) > 8 else ""}')
    return errs, warns


DMD_MAX_AGE, LEGAL_MAX_AGE = 90, 365  # days


def staleness(t, today=None):
    """Old data never stops the build, but it should not go unnoticed: a drug can be rescheduled."""
    today, out = today or datetime.date.today(), []
    D = {r['key']: r['value'] for r in t['dmd_release.csv']}
    try:
        age = (today - datetime.date.fromisoformat(D.get('release_date', ''))).days
        if age > DMD_MAX_AGE:
            out.append(f'dm+d data is {age} days old ({D.get("dmd_release")}): refresh it (see README, "dm+d codes")')
    except ValueError:
        out.append('dm+d release date missing from data/dmd/dmd_release.csv')
    for r in t['sources.csv']:
        try:
            age = (today - datetime.date.fromisoformat(r['checked'])).days
        except ValueError:
            age = None
        if age is None or age > LEGAL_MAX_AGE:
            out.append(f'legal source "{r["source"]}" last checked {r["checked"] or "never"}: re-check it and update data/legal/sources.csv')
    return out


def esc(x):
    return html.escape(str(x or ''), quote=True)


def fmt_date(d):
    try:
        return datetime.date.fromisoformat(d).strftime('%-d %b %Y')
    except (TypeError, ValueError):
        return d or ''


NAV = [('about.html', 'About'), ('legal.html', 'Legal basis'), ('fingerprint.html', 'Fingerprints'), ('../index.html', 'All Trusts')]
MODES = [('build', 'Build'), ('check', 'Check'), ('document', 'Document')]
CLOSE_MENU = "document.addEventListener('click',e=>{const m=document.getElementById('more');if(m&&!e.target.closest('#more'))m.open=false});"


THEME = '#005eb8'


def head_links(icons, manifest=''):
    """Favicon (inline, so it works from file:// too), home-screen icon, manifest and colours."""
    svg = (ROOT / 'src' / 'icons' / 'icon.svg').read_text(encoding='utf-8')
    data = 'data:image/svg+xml,' + urllib.parse.quote(' '.join(svg.split()), safe=' =:/.-,()')
    return (f'<link rel="icon" type="image/png" sizes="32x32" href="{icons}favicon-32.png">'
            f'<link rel="icon" type="image/svg+xml" href="{data}">'
            f'<link rel="apple-touch-icon" href="{icons}apple-touch-icon.png">'
            + (f'<link rel="manifest" href="{manifest}">' if manifest else '')
            + f'<meta name="theme-color" content="{THEME}">')


def page(title, body, css, current, trust_short, script=''):
    """An information page, with the builder's header: the three modes take you back to your scope, as you left it."""
    menu = ''.join(f'<a href="{h}"{' aria-current="page"' if h == current else ''}>{t}</a>' for h, t in NAV)
    modes = ''.join(f'<a href="index.html#{m}">{t}</a>' for m, t in MODES)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} · Prescribing Scope Builder</title>{head_links('../icons/', 'manifest.webmanifest')}<style>{css}</style></head>
<body><header class="appbar"><div class="in"><a class="brand" href="index.html">Prescribing Scope Builder<span>{esc(trust_short)}</span></a>
<nav class="modes" aria-label="Your scope">{modes}</nav><details class="more" id="more"><summary>Menu</summary><div class="menu">{menu}</div></details></div></header>
<main class="wrap prose">{body}</main><script>{CLOSE_MENU}{script}</script></body></html>
"""


def git_commit():
    try:
        sha = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(['git', '-C', str(ROOT), 'status', '--porcelain', '--', 'data', 'src', 'build.py'], capture_output=True, text=True, check=True).stdout.strip()
        return sha + ('-dirty' if dirty else '')  # a build from uncommitted changes must not claim a commit
    except (OSError, subprocess.CalledProcessError):
        return ''


def about_body(t, built):
    T = {r['key']: r['value'] for r in t['trust.csv']}
    D = {r['key']: r['value'] for r in t['dmd_release.csv']}
    menu = t['menu.csv']
    unrev = sum(1 for r in menu if not r['reviewed'])
    profs = t['profiles.csv']
    legal_rows = ''.join(f'<tr><td><a href="{esc(r["url"])}">{esc(r["source"])}</a></td><td>{esc(r["covers"])}</td><td>{esc(fmt_date(r["checked"]))}</td></tr>'
                         for r in t['sources.csv'])
    prof_rows = ''.join(f'<li><b>{esc(p["name"])}</b>: {esc(p["description"])} <span class="muted">({esc(p["source"])}; '
                        f'{"reviewed " + esc(p["reviewed"]) if p["reviewed"] else "not yet reviewed"})</span></li>' for p in profs)
    commit = git_commit()
    return f"""
<h1>About &amp; disclaimer</h1>
<p class="muted">{esc(T.get('trust_name'))}</p>

<div class="card notice"><h3>This is a mapping tool, not a prescribing guide</h3>
<ul>
<li><b>This is a proof of concept, for demonstration only.</b> The menu and profiles are rough drafts made for the demo and have not been clinically reviewed, and no Trust has adopted it. Do not use a scope made with it to prescribe.</li>
<li>It shows <b>no doses</b> and gives <b>no clinical guidance</b>. Always use the BNF, the SPC and local guidelines.</li>
<li>It <b>does not grant prescribing authority</b>. A scope of practice is agreed with your clinical supervisor or designated prescribing practitioner and your non-medical prescribing lead, under Trust policy.</li>
<li>The legal check covers <b>controlled drugs by profession</b> (Misuse of Drugs Regulations 2001). Other legal points, such as unlicensed medicines and profession-specific scope, are shown as information. See <a href="legal.html">Legal basis</a>.</li>
<li>Your own competence, local governance and the formulary remain your responsibility.</li>
<li>The menu and profiles are <b>drafts</b>. {unrev} of {len(menu)} menu rows have not yet been clinically reviewed.</li>
</ul></div>

<h2>Privacy</h2>
<p>The builder runs entirely in your browser. Nothing you enter is sent anywhere. Your draft and your details are kept in this browser's storage on your device as you go, so a refresh or a visit to another page loses nothing; <b>Menu → Start over</b> discards the draft and <b>Forget my details</b> clears your details. <b>Menu → Save to a file</b> downloads everything to your own device, to open later or elsewhere. If you choose <b>Keep on this device</b> for a finished scope, its link is kept too, so the page can open straight to it from your home screen; <b>Remove from this device</b> deletes it. Formulary badges link to the formulary's own website.</p>

<h2>How it works</h2>
<ol>
<li><b>Professional background</b> sets the legal rules. Anything your profession cannot legally prescribe is greyed out, with the regulation.</li>
<li><b>Profiles</b> are agreed sets of medicines for a role or area, such as Core, ED Resus, UTC or SDEC. Pick any combination.</li>
<li><b>Decide on each medicine by route</b>: include, include with restriction, continuation only, specialist advice only, emergency use only, developmental, or exclude.</li>
<li><b>Scope document</b> gathers your decisions into a document to print and sign, with a development plan.</li>
<li><b>Scope link and fingerprint.</b> <i>Get scope link</i> makes a link that opens a read-only "my scope" view with a <i>Can I prescribe…?</i> search. The scope travels in the part of the link after <code>#</code>, which browsers never send to a server. The link also records the Trust and data versions it was made with, for context.</li>
</ol>

<h2>Scope fingerprint</h2>
<p>Every scope has a <b>fingerprint</b>: a 64-character code worked out from exactly what the scope permits. The same permissions always give the same fingerprint, and any change to them gives a different one. Record it with the signed scope, and anyone can later check that a scope link is the one that was agreed. See <a href="fingerprint.html">Fingerprints</a> for a plain-English explanation and a playground to try it.</p>

<h2 id="sources">Data sources and dates</h2>
<div class="tbl"><table><thead><tr><th>Source</th><th>Used for</th><th>Version / checked</th></tr></thead><tbody>
{legal_rows}
<tr><td><a href="https://isd.digital.nhs.uk/trud">NHS dm+d</a> (NHSBSA, via TRUD)</td><td>Medicine codes, BNF codes, controlled-drug schedule of every product by route</td><td>{esc(D.get('dmd_release'))} ({esc(fmt_date(D.get('release_date')))})</td></tr>
<tr><td><a href="{esc(T.get('formulary_url'))}">{esc(T.get('formulary_source'))}</a></td><td>Formulary status (formulary, restricted, not found) and links. Licence: {esc(T.get('formulary_licence') or 'not recorded')}. Permission to republish: {esc(T.get('formulary_permission') or 'not recorded')}.</td><td>Imported {esc(fmt_date(T.get('formulary_imported')))}</td></tr>
<tr><td>Menu and profiles</td><td>Presentations, medicines and routes offered, and the profiles</td><td>{len(menu)} rows, {unrev} unreviewed; {len(profs)} profiles</td></tr>
</tbody></table></div>
<p class="small">Contains public sector information licensed under the <a href="https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/">Open Government Licence v3.0</a>: medicine data from the NHS Dictionary of Medicines and Devices (NHS Business Services Authority, via NHS TRUD) and legislation from legislation.gov.uk. Formulary statuses belong to the formulary's owner. The builder's code is MIT licensed and its own content is <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>.</p>
<p class="small muted">{esc(T.get('menu_status'))}. Page built {esc(fmt_date(built))}{f', version {esc(commit)}' if commit else ''}.</p>

<h2>Profiles</h2>
<ul>{prof_rows}</ul>
{f'<h2>Contact</h2><p>{esc(T["contact"])}</p>' if T.get('contact') else ''}
"""


# Sample scope for the fingerprint playground: real dm+d codes, illustrative decisions only.
SAMPLE = [('paracetamol', 'PO', 'include', ''), ('ibuprofen', 'PO', 'include', ''), ('morphine_sulfate', 'IV', 'include', ''),
          ('adrenaline', 'IM', 'emergency', ''), ('co_amoxiclav', 'PO', 'restricted', 'In line with the Trust antimicrobial guideline'),
          ('salbutamol', 'nebulised', 'include', ''), ('ondansetron', 'IV', 'developmental', 'Five supervised cases')]


def fingerprint_sample(t):
    meds = {m['medicine_id']: m for m in t['medicines.csv']}
    routes = {r['route_id']: r for r in t['routes.csv']}
    out = []
    for mid, rid, d, note in SAMPLE:
        m, r = meds.get(mid), routes.get(rid)
        if not m or not r:
            continue
        key = 'dmd:' + '+'.join(sorted(m['dmd_vtm'].split())) if m['dmd_vtm'] else 'local:' + mid
        out.append({'name': m['name'], 'med': key, 'route': rid, 'short': r['short'] or r['name'], 'route_name': r['name'],
                    'family': r['family'], 'd': d, 'note': note})
    return out


def fingerprint_body():
    return """
<h1>Scope fingerprints</h1>
<p class="lead">A fingerprint is a 64-character code worked out from exactly what a scope lets you prescribe. <b>The same permissions always give the same fingerprint. Change anything that matters, even one letter of a restriction, and you get a completely different one.</b> The Trust records the fingerprint when the scope is signed. Later, anyone can open the scope link and see whether it still matches.</p>

<h2>Try it</h2>
<p>This is a small made-up scope. Change a decision, edit the restriction, or shuffle the order, and watch the fingerprint.</p>
<div class="card pg" id="pgBox">
  <div class="pg-left">
  <div class="pg-fp">
    <div class="fp-row"><span class="muted small">Fingerprint</span><code class="fp" id="pgCode"></code></div>
    <code class="fphex pg-hex" id="pgHex"></code>
    <p class="small pg-msg" id="pgMsg" aria-live="polite"></p>
    <div class="pg-status"><span id="pgStatus"></span></div>
    <p class="small muted">Recorded fingerprint: <code id="pgRecorded"></code></p>
    <div class="pg-btns"><button class="btn" type="button" id="pgShuffle">Shuffle the order</button><button class="btn" type="button" id="pgRecord">Record this fingerprint</button><button class="btn primary" type="button" id="pgUndo" hidden>Undo my changes</button></div>
  </div>
  <div id="pgRows"></div>
  <p class="small muted" id="pgLeft"></p>
  </div>
  <div class="pg-right">
    <h3>Inside the fingerprint</h3>
    <p class="small muted">Each permission is a leaf on the bottom row. Pairs are combined, level by level, up to the root at the top, which is the fingerprint. <span class="key same">Green</span> boxes are the same as in the recorded fingerprint; <span class="key diff">red</span> boxes differ.</p>
    <div class="pg-tree" id="pgTree"></div>
    <p class="small pg-gone" id="pgGone"></p>
    <p class="small muted pg-tip">Hover over a box, or tap it, to see what it is made of.</p>
    <div class="pg-inspect" id="pgInspect" aria-live="polite"></div>
  </div>
</div>

<h2>What goes in</h2>
<p>Each permission becomes one line of text, called a <b>leaf</b>. The medicine is written as its national dm+d code, so it means the same in every Trust. The lines are sorted by code, so the order you choose things in never matters. In the playground, hover over or tap a box on the bottom row to see its exact line.</p>
<p class="small muted">Only permissions go in. Names, dates, your profession, the Trust, developmental items, exclusions and development plans are all left out, so everyone in a team with the same permissions shares one fingerprint.</p>

<h2>How the lines become one code: the tree</h2>
<p>Each leaf is put through a <b>hash</b> (below). Then pairs of results are joined and hashed again, and again, until one value is left at the top: the <b>root</b>, which is the fingerprint. Each box shows the first four characters of its value. Change one leaf and only the boxes on its path to the top change, but the top always does. Add or remove a permission and the tree reshapes.</p>
<p class="small muted">Each box on the bottom row is labelled with its medicine. The first leaf is a fixed format label, so a fingerprint can never be mistaken for anything else.</p>

<h2>What a hash does</h2>
<p>A hash turns any text into a 64-character code. The same text always gives the same code. Type something, then change one letter:</p>
<div class="card">
  <label class="f" for="hIn">Any text</label>
  <input type="text" id="hIn" value="Morphine IV">
  <p style="margin:10px 0 0"><code class="fphex pg-hex" id="hOut"></code></p>
  <p class="small pg-msg" id="hMsg" aria-live="polite"></p>
  <p class="small muted" id="hRef"></p>
</div>
<p>You cannot work backwards from the code to the text, and nobody has ever found two different texts with the same code.</p>

<h2>The words, in plain English</h2>
<dl class="gloss">
<dt>Fingerprint</dt><dd>The 64-character code for a scope. Same permissions, same fingerprint; different permissions, different fingerprint.</dd>
<dt>Check code</dt><dd>The first 16 characters, written in four groups (like <code>5PFK-T6ER-AKGQ-9QC3</code>), so people can compare fingerprints at a glance. Good for reading out; record the full fingerprint.</dd>
<dt>Hash (SHA-256)</dt><dd>A fixed recipe that turns any text into a 64-character code. SHA-256 is the recipe behind website security certificates and software updates. It is a published standard, not something this project made up.</dd>
<dt>Leaf</dt><dd>One line of text for one permission, such as IV morphine, include.</dd>
<dt>Merkle tree</dt><dd>The way the leaves are combined: hash each leaf, then join and hash in pairs up to a single value at the top. Named after Ralph Merkle, who invented it in 1979. We use the exact version published as RFC 6962, the standard behind the public logs of website security certificates.</dd>
<dt>Root</dt><dd>The single value at the top of the tree. It is the fingerprint.</dd>
<dt>Collision</dt><dd>Two different scopes giving the same fingerprint. With SHA-256 this has never been seen. Making a billion billion scopes every second, you would expect to wait hundreds of times the age of the universe before finding one.</dd>
<dt>dm+d code</dt><dd>The NHS Dictionary of Medicines and Devices number for a medicine, the same everywhere in the NHS. Using it means the fingerprint does not depend on how a medicine is spelt.</dd>
<dt>Scope link</dt><dd>A web link that carries the whole scope inside it, after the <code>#</code>. Browsers never send that part to any server, so nothing is stored online.</dd>
<dt>Tamper-evident</dt><dd>Changes can be seen, but not prevented. Anyone can make a scope link; an edited one simply will not match the fingerprint the Trust recorded.</dd>
</dl>

<h2>Questions governance teams ask</h2>
<h3>Could someone edit their scope and keep the same fingerprint?</h3>
<p>No. Finding a different scope with the same 64-character fingerprint is beyond any computer that exists. That is why the full fingerprint is what gets recorded.</p>
<h3>Why record all 64 characters, not just the check code?</h3>
<p>The check code is short enough that someone with a lot of computing power could, in principle, prepare two different scopes that share one. Nobody can do that with the full fingerprint.</p>
<h3>What does a matching fingerprint prove?</h3>
<p>That the scope link permits exactly what was recorded, nothing more and nothing less. It does not prove who approved it, or when. Sign-off, review dates and the register of fingerprints stay with the Trust's own governance.</p>
<h3>What if a medicine's code changes?</h3>
<p>dm+d sometimes re-codes a medicine. The builder keeps the previous codes, so older links still open correctly. A scope made again after a re-coding gets a new fingerprint, so record it at the next review.</p>
<h3>Does the fingerprint change when the builder is updated?</h3>
<p>No. Data versions and dates travel with the link for context but are not part of the fingerprint. It only changes if the permissions change.</p>

<details class="card working tech">
<summary>For technical reviewers</summary>
<ul class="small">
<li><b>Algorithm:</b> the Merkle Tree Hash of <a href="https://www.rfc-editor.org/rfc/rfc6962#section-2.1">RFC 6962 section 2.1</a> (SHA-256, leaf prefix 0x00, node prefix 0x01). Leaf 0 is <code>scope-builder scope v1</code>; the other leaves are the granting item lines, <code>&lt;medicine&gt;|&lt;route&gt;=&lt;code&gt;[:&lt;restriction&gt;]</code>, sorted by their UTF-8 bytes. Restrictions are NFC-normalised with runs of whitespace collapsed.</li>
<li><b>Reference specification:</b> <code>tools/verify_scope.py</code> in the repository, using the Python standard library only. It decodes any scope link and recomputes its fingerprint without this website: <code>python3 tools/verify_scope.py --leaves '&lt;link&gt;'</code>.</li>
<li><b>Testing:</b> the pages test their SHA-256 and Merkle code on every load against published answers (NIST and RFC 6962) and the browser's own SHA-256, and withhold fingerprints if any check fails. Every change to the project is checked against the Python reference, Node's SHA-256 and the RFC 6962 test vectors. This playground runs the same code as the builder.</li>
<li><b>Identifiers:</b> medicines use dm+d VTM codes, with previous codes followed for older links. Route identifiers and the few local medicine identifiers are frozen; the build refuses to rename or remove them.</li>
<li><b>No third-party code:</b> SHA-256 is implemented in the page, with no external libraries.</li>
</ul>
</details>
"""


def legal_body(t):
    routes = t['routes.csv']
    classes = {}
    for r in routes:
        classes.setdefault(r['legal_class'], []).append(r['name'])
    toc = ''.join(f'<a href="#{esc(p["profession_id"])}">{esc(p["name"].replace(" independent prescriber", " IP"))}</a>' for p in t['professions.csv'])
    cards = []
    for p in t['professions.csv']:
        named = [c for c in t['cd_named.csv'] if c['profession_id'] == p['profession_id']]
        rows = {}
        for c in named:
            rows.setdefault((c['statute_name'], c['regulation']), []).append(c['legal_class'])
        table = ''
        if rows:
            table = '<div class="tbl"><table><thead><tr><th>Controlled drug (as in the regulation)</th><th>Permitted route</th><th>Regulation</th></tr></thead><tbody>' + ''.join(
                f'<tr><td>{esc(n)}</td><td>{esc(" or ".join(dict.fromkeys(v)))}</td><td>{esc(r)}</td></tr>' for (n, r), v in rows.items()) + '</tbody></table></div>'
        sch5 = ''
        if p['cd_rule'] == 'named':
            sch5 = f'<dt>Schedule 5</dt><dd>{"Must be on the named list (strict reading, still to be confirmed)" if p["schedule5"] == "named" else "Allowed without being on the named list"}</dd>'
        cards.append(f"""<section class="card" id="{esc(p['profession_id'])}"><h3>{esc(p['name'])}</h3><dl>
<dt>Medicines</dt><dd>{esc(p['scope_note'])}</dd>
<dt>Controlled drugs</dt><dd>{esc(p['cd_note'])} <span class="muted">({esc(p['cd_regulation'])})</span></dd>{sch5}
<dt>Unlicensed</dt><dd>{'Permitted' if p['unlicensed'].upper() == 'Y' else 'Not permitted'}</dd>
<dt>Source</dt><dd class="small">{esc(p['source'])}</dd></dl>{table}</section>""")
    route_rows = ''.join(f'<tr><td>{esc(k)}</td><td>{esc(", ".join(v))}</td></tr>' for k, v in classes.items())
    return f"""
<h1>Legal basis</h1>
<p>Controlled-drug prescribing by non-medical prescribers is set by the <a href="https://www.legislation.gov.uk/uksi/2001/3998/contents">Misuse of Drugs Regulations 2001</a>: <b>reg 6B</b> for nurse and pharmacist independent prescribers, <b>reg 6C</b> for physiotherapists and podiatrists, and <b>reg 6D</b> for therapeutic radiographers and paramedics. The builder enforces these rules route by route. The other points below are shown as information.</p>
<div class="toc">{toc}</div>
{''.join(cards)}

<h2>How routes are read against the regulations</h2>
<p>The regulations name routes such as "by oral administration" or "by injection". Each route in the menu is mapped to one of these. The reading is conservative: sublingual and nasogastric are <b>not</b> treated as oral administration.</p>
<div class="tbl"><table><thead><tr><th>Legal wording</th><th>Menu routes</th></tr></thead><tbody>{route_rows}</tbody></table></div>

<h2>Controlled-drug schedules</h2>
<p>Schedules come from NHS dm+d, product by product and route by route. Some medicines are Schedule 2 or 5 depending on strength (oral morphine, codeine), and the builder shows that. Nitrous oxide with oxygen (Entonox) is Schedule 5 in dm+d.</p>

<h2>Open questions</h2>
<ul>
<li><b>Schedule 5 and the named lists.</b> Whether a Schedule 5 preparation (co-codamol, codeine tablets, Entonox) must appear on a profession's named list in reg 6C or 6D. The builder currently takes the strict reading, set per profession in <code>professions.csv</code>.</li>
<li><b>Supplementary prescribers.</b> The statutory reference still needs adding.</li>
<li><b>Pending amendments.</b> legislation.gov.uk lists amendments from SI 2025/1249 that are not yet applied to the text.</li>
</ul>
"""


MANIFEST = []


def landing(css):
    def card(m):
        return f"""<a class="card trust" href="{esc(m['path'])}" data-q="{esc(' '.join([m['name'], m['short'], m['region'], m['formulary'], m['formulary_full']]).lower())}">
<h3>{esc(m['name'])}</h3><div class="meta">{esc(' · '.join(x for x in [m['short'], m['region']] if x))}</div>
<div class="meta">{len(m['profiles'])} profiles · {m['menu_rows']} menu rows{f", {m['unreviewed_rows']} unreviewed" if m['unreviewed_rows'] else ''}</div></a>"""
    groups = {}
    for m in sorted(MANIFEST, key=lambda m: m['name']):
        groups.setdefault(m['formulary_full'] or m['formulary'] or 'No formulary imported yet', []).append(m)
    cards = ''.join(f'<section class="tgroup"><h2>{esc(g)}</h2><div class="trusts">{"".join(card(m) for m in ms)}</div></section>'
                    for g, ms in sorted(groups.items(), key=lambda x: (x[0].startswith('No formulary'), x[0])))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Prescribing Scope Builder</title>{head_links('icons/')}<style>{css}</style></head>
<body><header class="appbar"><div class="in"><a class="brand" href="index.html">Prescribing Scope Builder</a></div></header>
<main class="wrap prose" style="max-width:1160px">
<h1>Choose your Trust</h1>
<p class="muted">Build a non-medical prescribing scope of practice from the law, your Trust's formulary and agreed profiles. Each Trust keeps its own menu and profiles; the legal rules and medicine codes are shared.</p>
<input type="search" id="tq" placeholder="Search by Trust, region or formulary" aria-label="Search Trusts" style="max-width:520px">
<div id="tlist">{cards}</div>
<p class="small muted" id="tnone" hidden>No Trust matches. Want to add yours? See CONTRIBUTING.md in the repository.</p>
</main>
<script>
const q = document.getElementById('tq'), cards = [...document.querySelectorAll('.trust')];
q.oninput = () => {{ const v = q.value.trim().toLowerCase(); let n = 0;
  cards.forEach(c => {{ const ok = !v || c.dataset.q.includes(v); c.hidden = !ok; n += ok; }});
  document.querySelectorAll('.tgroup').forEach(g => {{ g.hidden = !g.querySelector('.trust:not([hidden])'); }});
  document.getElementById('tnone').hidden = n > 0; }};
</script></body></html>
"""


def build(trust):
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', trust):
        print(f'[{trust}] trust folder names must be lower-case letters, digits and hyphens', file=sys.stderr)
        return False
    raw, tables = {}, {}
    for rel in SHARED:
        raw[Path(rel).name], tables[Path(rel).name] = read(ROOT / 'data' / rel)
    for name in TRUST:
        raw[name], tables[name] = read(ROOT / 'data' / 'trusts' / trust / name)
    # the formulary is shared by every Trust that uses it: data/formularies/<id>/
    fid = {r['key']: r['value'] for r in tables['trust.csv']}.get('formulary', '')
    info = {}
    raw['formulary.csv'], tables['formulary.csv'] = FORMULARY_HEADER, []
    if fid:
        fdir = ROOT / 'data' / 'formularies' / fid
        if not (fdir / 'formulary.csv').exists() or not (fdir / 'about.csv').exists():
            print(f'[{trust}] trust.csv names formulary {fid!r}, but data/formularies/{fid}/ has no formulary.csv and about.csv', file=sys.stderr)
            return False
        raw['formulary.csv'], tables['formulary.csv'] = read(fdir / 'formulary.csv')
        info = {r['key']: r['value'] for r in read(fdir / 'about.csv')[1]}
    trust_rows = [r for r in tables['trust.csv'] if not r['key'].startswith('formulary_')]
    trust_rows += [{'key': k, 'value': info.get(f, '')} for f, k in FORMULARY_KEYS.items()]
    out_csv = io.StringIO(); w = csv.DictWriter(out_csv, fieldnames=['key', 'value'], lineterminator='\n'); w.writeheader(); w.writerows(trust_rows)
    raw['trust.csv'], tables['trust.csv'] = out_csv.getvalue(), trust_rows
    raw['__profiles'], tables['__profiles'] = {}, {}
    for p in sorted((ROOT / 'data' / 'trusts' / trust / 'profiles').glob('*.csv')):
        raw['__profiles'][p.stem], tables['__profiles'][p.stem] = read(p)
    errs, warns = check(tables, trust)
    warns += [f'[{trust}] {w}' for w in staleness(tables)]
    gh = os.environ.get('GITHUB_ACTIONS')  # in Actions, show each as an annotation on the run
    tag = lambda w: ('::notice::' if '] note:' in w else '::warning::') if gh else ''
    print('\n'.join(tag(w) + w for w in sorted(set(warns))), file=sys.stderr) if warns else None
    if errs:
        print('\n'.join(errs), file=sys.stderr)
        return False
    raw['__trust'] = trust
    raw['__commit'] = git_commit()
    built = raw['__built'] = datetime.date.today().isoformat()
    css = (ROOT / 'src' / 'style.css').read_text(encoding='utf-8')
    short = {r['key']: r['value'] for r in tables['trust.csv']}.get('trust_short', '')
    payload = json.dumps(raw, ensure_ascii=False).replace('</', '<\\/')
    out = ROOT / 'dist' / trust
    out.mkdir(parents=True, exist_ok=True)
    (out / 'index.html').write_text((ROOT / 'src' / 'template.html').read_text(encoding='utf-8')
                                    .replace('<!--__HEAD__-->', head_links('../icons/', 'manifest.webmanifest'))
                                    .replace('/*__CSS__*/', css).replace('/*__DATA__*/', payload), encoding='utf-8')
    # installable: "Add to Home Screen" opens this Trust's builder full screen, with its own icon
    icon = lambda name, n, purpose: {'src': f'../icons/{name}-{n}.png', 'sizes': f'{n}x{n}', 'type': 'image/png', 'purpose': purpose}
    (out / 'manifest.webmanifest').write_text(json.dumps({
        'name': f'Prescribing scope ({short or trust})', 'short_name': f'{short} scope'.strip() if len(f'{short} scope') <= 12 else 'Scope',
        'description': 'Build, carry and check a non-medical prescribing scope of practice.',
        'id': './', 'start_url': './', 'scope': './', 'display': 'standalone',
        'background_color': '#f2f4f7', 'theme_color': THEME,
        'icons': [icon('icon', 192, 'any'), icon('icon', 512, 'any'), icon('maskable', 192, 'maskable'), icon('maskable', 512, 'maskable')]}, indent=1), encoding='utf-8')
    (out / 'about.html').write_text(page('About & disclaimer', about_body(tables, built), css, 'about.html', short), encoding='utf-8')
    (out / 'legal.html').write_text(page('Legal basis', legal_body(tables), css, 'legal.html', short), encoding='utf-8')
    template = (ROOT / 'src' / 'template.html').read_text(encoding='utf-8')
    crypto = template[template.index('// crypto:begin'):template.index('// crypto:end') + len('// crypto:end')]
    script = ('const SAMPLE = ' + json.dumps(fingerprint_sample(tables), ensure_ascii=False).replace('</', '<\\/') + ';\n'
              + crypto + '\n' + (ROOT / 'src' / 'fingerprint.js').read_text(encoding='utf-8'))
    (out / 'fingerprint.html').write_text(page('Scope fingerprints', fingerprint_body(), css, 'fingerprint.html', short, script), encoding='utf-8')
    T = {r['key']: r['value'] for r in tables['trust.csv']}
    MANIFEST.append({'id': trust, 'name': T.get('trust_name', trust), 'short': short, 'region': T.get('region', ''),
                     'formulary': T.get('formulary_name', ''), 'formulary_id': T.get('formulary', ''), 'formulary_full': T.get('formulary_source', ''), 'formulary_imported': T.get('formulary_imported', ''),
                     'menu_rows': len(tables['menu.csv']), 'unreviewed_rows': sum(1 for r in tables['menu.csv'] if not r['reviewed']),
                     'profiles': [r['name'] for r in tables['profiles.csv']], 'built': built, 'path': f'{trust}/'})
    print(f'{trust}: {len(tables["menu.csv"])} menu rows, {len(tables["medicines.csv"])} medicines, {len(raw["__profiles"])} profiles -> {out.relative_to(ROOT)}/')
    return True


if __name__ == '__main__':
    trusts = sys.argv[1:] or sorted(p.name for p in (ROOT / 'data' / 'trusts').iterdir() if p.is_dir())
    ok = all([build(t) for t in trusts])
    # site root for GitHub Pages: a searchable Trust picker plus a machine-readable manifest
    css = (ROOT / 'src' / 'style.css').read_text(encoding='utf-8')
    (ROOT / 'dist' / 'index.html').write_text(landing(css), encoding='utf-8')
    icons = ROOT / 'dist' / 'icons'
    icons.mkdir(parents=True, exist_ok=True)
    for f in (ROOT / 'src' / 'icons').iterdir():
        shutil.copyfile(f, icons / f.name)
    shutil.copyfile(ROOT / 'src' / 'sw.js', ROOT / 'dist' / 'sw.js')
    (ROOT / 'dist' / 'trusts.json').write_text(json.dumps(sorted(MANIFEST, key=lambda m: m['id']), indent=2), encoding='utf-8')
    sys.exit(0 if ok else 1)
