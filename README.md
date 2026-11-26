# Prescribing Scope Builder (proof of concept)

> [!WARNING]
> **A proof of concept for demonstration, not for live use.** The menu and profiles are rough drafts made for the demo (AI-drafted and not yet clinically reviewed), the strict reading of the Schedule 5 rules is still to be confirmed, and no Trust has adopted this tool. Do not use a scope made with it to prescribe.

This tool helps a non-medical prescriber build a **prescribing scope of practice**:

1. Choose your profession.
2. Tick the profiles that fit your role (Core is ticked for everyone).
3. Decide on each medicine by route.

The page then produces a consolidated scope document to print and sign.

It is a **mapping tool, not a prescribing guide**. It contains no doses and makes no clinical risk judgements. Nothing is sent anywhere. The page runs entirely in the browser; your draft and details are kept in that browser's storage as you go, and can be saved to a file. A finished scope can be kept on your own phone too, if you choose to.

**Demo:** https://transilluminate.org/scope-builder/ (published from `main` by `.github/workflows/pages.yml`).

## Using it

Run `python3 build.py`, then open `dist/index.html` and choose a Trust, or open `dist/krft/index.html` directly.

The build makes a small static site, ready for GitHub Pages:

| File | What it is |
|---|---|
| `dist/index.html` | Trust picker, with search |
| `dist/trusts.json` | Machine-readable list of the Trusts |
| `dist/<trust>/index.html` | The builder: one self-contained file that also works offline, emailed or on a shared drive |
| `dist/<trust>/about.html` | Disclaimer, privacy, data sources and dates |
| `dist/<trust>/legal.html` | Full legal basis: every profession, the named CD lists, route wording, open questions |

Every page has the same header: **Build · Check · Document**, plus a **Menu** with the information pages, *Open a saved file*, *Save to a file* and *Start over*. On a phone the three modes sit in a bar at the bottom of the screen.

The usual journeys:

- **Starting fresh:** Build (profession, profiles, then the medicines) → Check, to try it → Document, to add your details and print, share or keep it.
- **Shared a link:** it opens in Check as a shared scope, with a banner, and your own draft stays untouched. Document prints it; **Edit a copy** makes it your draft, asking first if that would replace one.
- **Coming back:** your draft is where you left it. It is saved in the browser as you go, so a refresh or a visit to the About page loses nothing. **Menu → Start over** discards it.

What each hand-off keeps: a scope link carries the decisions, profession, profiles, Trust and data versions, but never your name or details. Your details stay on the device, for the printed document. A saved file keeps everything.

### Build

- **One card per medicine, one line per route.** You decide on each route separately (IV morphine, oral morphine and so on). The presentations each medicine is used for are listed as context on the card.
- **Route pills are colour-coded by family:** oral, injection, inhaled, buccal/SL/intranasal, topical, and rectal.
- **Profile chips** show which of your ticked profiles offer each route. The filled chip is **Core**.
- **Decisions are colour-coded:**
  - green: Include, Include with restriction, Continuation only, On specialist advice only, Emergency use only
  - purple: Developmental
  - grey: Exclude
- **A note box appears only where it is needed:** for *Include with restriction* (the restriction) and *Developmental* (the plan).
- **Legal blocks are automatic.** Routes your profession cannot legally prescribe are shown in red, with the regulation that applies.
- **Shortcuts:**
  - **Include all Core** includes the Core profile's unreviewed routes.
  - *All routes…* sets a whole medicine at once.
  - *Set all unreviewed here to…* sets a whole group at once.
- **Grouping:** by clinical system, profile, BNF chapter, or A–Z.

### Check

**Can I prescribe…?** for whichever scope is open: your draft, or a shared one. See *Scope links and fingerprints* below.

### Document

Your details (optional, kept on this device only), then the document itself. 
This shows what's in scope, a development plan with a sign-off column, what you excluded, what's not legally permitted, and signature boxes. Print it or save it as PDF or CSV.

### Profiles

The menu is one master list of presentation, medicine and route. A **profile** is a named, agreed subset of it: ED Resus, ED majors & minors, UTC, SDEC, AMU, and later ITU, frailty and so on.

- **Profiles are additive.** Tick ED Resus and UTC and you work from the union of both. *Also show the whole menu* adds everything else.
- **Core** (any prescriber, any area) is ticked for everyone. It holds pan-hospital emergency and life-saving drugs and basic analgesia: adrenaline IM for anaphylaxis, oxygen, bronchodilators, glucose and glucagon, naloxone, aspirin and GTN, buccal midazolam and IV lorazepam, hydrocortisone, IV fluids, paracetamol, ibuprofen, co-codamol and two antiemetics. ALS drugs are deliberately left out, because not every prescriber is an ALS provider.
- **Profiles carry no profession.** One profile serves a nurse, pharmacist or paramedic; the legal gate decides what applies.
- **Anything you decide counts**, even outside your profiles: the document lists it.
- **Save as profile** downloads the routes you have included as a profile file. Put it in `data/trusts/<trust>/profiles/` and add a row to `profiles.csv` to share it. A profile file can also be dropped into the page (*Use your own Trust's data*) to try it without a build.

### Scope links and fingerprints

In Document, **Get scope link** makes a link (about 500 characters for a full ED scope) that opens the scope in Check, as a shared scope.

- **What the link holds:** the scope travels after the `#`, so browsers never send it to a server, GitHub Pages included. It carries the decisions, profession and profiles, but no name, dates or other personal details.
- **What Check does:** it shows the fingerprint, a profession picker (the legal rules apply when the link is opened), and a **Can I prescribe…?** search. Each route gets a clear answer: in scope (with any restriction), developmental, excluded, not legally permitted, or not in your scope. It also warns about drift, such as routes now restricted or off the formulary, or no longer on the menu.
- **The fingerprint** is a SHA-256 Merkle Tree Hash (RFC 6962) over one leaf per permission: `dmd:<VTM code>|<route>=<type>[:restriction]`. It is shown as a 64-digit value plus a 16-character check code for reading by eye.
  - **Record the full value:** a shortened hash can be forged by someone who prepares two scopes in advance.
  - **What it leaves out:** names, dates, profession, the Trust, developmental items, exclusions and data versions. So a team with the same permissions shares a fingerprint, and the same scope matches across Trusts.
  - **What it proves:** it is tamper-evident against the Trust's record. It is not a signature.
  - **Selective proof:** the Merkle structure allows a single permission to be proved later without revealing the whole scope.
- **The specification** is [SPEC.md](SPEC.md), an open format anyone can implement: identifiers, link encoding, leaves, the Merkle tree, the check code, a worked example and the versioning rules. `tools/verify_scope.py` is its reference implementation, Python standard library only. Run `python3 tools/verify_scope.py --leaves '<link>'` to check any link without the page.
- **Assurance:**
  - **On every load,** the page tests its SHA-256 and Merkle code against the NIST "abc" value, the RFC 6962 test tree and the browser's own SHA-256. It withholds fingerprints if anything disagrees.
  - **On every change,** CI runs `verify_scope.py --self-test` and `node tests/check_crypto.js`. The latter checks the page's code against Node's SHA-256, the RFC 6962 vectors and `tests/vectors.json`, which the reference generated, and has the reference re-read links the page made.
- **Stable identifiers:**
  - **Medicines** use dm+d VTM codes. `dmd_vtm_prev` keeps links made before a dm+d re-coding resolvable.
  - **Routes and the few local medicine ids** are listed in `data/frozen_ids.csv`, and the build refuses to rename or remove them.
  - **The data context** (dm+d release, build date, git commit, marked `-dirty` for uncommitted builds) travels in the link beside the fingerprint, not inside it.
- **The printed document** shows the fingerprint too.
- **On a phone:** Check puts the fingerprint on one line and the **Can I prescribe…?** search next. **Keep on this device** (in Document) saves the link in that browser's storage only, and the builder installs to the home screen with its own icon. It then opens straight to the kept scope and works offline: a small service worker (`src/sw.js`) keeps the last version it fetched. Nothing is sent anywhere. The icons are drawn by `tools/make_icons.py`, which writes the SVGs and renders the PNG sizes.
- **Open a copy in the builder** turns a link back into editable decisions.

### Saving

The draft and your details save themselves in the browser as you go. **Menu → Save to a file** downloads your own `.json` file, including your profession, profiles and details, to keep or move to another device; **Open a saved file** loads it back, at your annual review for example.

## How the data is organised

All data is plain CSV, so it opens in Excel.

```
data/
  legal/                 national: changes only when the law does
    professions.csv      prescriber types: CD rule, regulation, unlicensed Y/N, scope note
    cd_named.csv         the named CD + route lists from MDR 2001 regs 6C and 6D, verbatim
    routes.csv           route -> short label, colour family, legal class, dm+d route codes
  medicines.csv          medicine id, name, CD schedule, dm+d VTM code(s) and previous code(s), BNF section
  frozen_ids.csv         route ids and local medicine ids used in scope links: permanent
  dmd/                   generated by tools/import_dmd.py; do not edit by hand
    medicine_routes.csv  per medicine and route: number of dm+d products and their CD schedules
    dmd_release.csv      which dm+d release the codes came from
  legal/sources.csv      the legal sources and the date each was checked (shown on the About page)
  formularies/           one folder per formulary, shared by every Trust that uses it
    swl/
      about.csv          name, owner's full name, region, system, URL, import date, licence, permission
      formulary.csv      medicine -> Y / R(estricted) / N / blank, BNF chapter, matched entries, link
  trusts/
    krft/                everything local to one Trust; tools/new_trust.py makes another
      trust.csv          name, short name, region, formulary (an id from formularies/), status line
      menu.csv           the master list: system, presentation, medicine, route, source, reviewed
      profiles.csv       profile index: id, name, short name, group, description, default (Y = ticked
                         for everyone, i.e. Core), source, reviewed
      profiles/*.csv     one file per profile: medicine_id, route
```

### Review status

`menu.csv` rows and `profiles.csv` entries each carry:

- **`source`:** where they came from, e.g. "v0.4 draft" or "AI-drafted".
- **`reviewed`:** the reviewer's initials and date. Leave it blank until someone has reviewed it. The page says how much is unreviewed, and so does the printed document.

### Formulary import

Formularies are usually regional: the SWL formulary covers several Trusts. So each formulary has its own folder in `data/formularies/`, imported once, and each Trust's `trust.csv` names the one it uses (`formulary,swl`). The Trust picker groups Trusts by formulary.

The statuses come from netFormulary's **A-Z of formulary items** and **A-Z of Non Formulary items** reports. Many regional formularies use netFormulary, including SWL, SEL and NWL London, so any area on [netFormulary's customer list](https://www.netformulary.co.uk/Customers) can be added with the same importer: no new code, just an `about.csv` and its saved report pages. Ask the formulary's owners for permission first (see [LICENSES.md](LICENSES.md)).

1. For a new formulary, create `data/formularies/<id>/about.csv` by copying `swl/about.csv` and editing it.
2. A person saves each chapter's report page from their browser.
3. Run the importer on the folder of saved pages:

   ```
   python3 tools/import_netformulary.py ~/Downloads/swl swl
   ```

It covers every medicine in `medicines.csv`, so the formulary serves every Trust that uses it. The full list of report entries, used for checking matches, is written to `.cache/formulary/<id>/` and never committed.

The script fetches nothing itself, so it respects the formulary site's `robots.txt`.

- **Matching:** medicines are matched by name and brand. Edit `ALIASES` in the script when a medicine is listed under another name.
- **BNF chapters:** where a medicine's entries are mostly eye, skin or ENT preparations, `CHAPTER` in the script pins the chapter for its systemic use.
- **Links:** each matched medicine stores a link to its section on the live formulary (`url` in the formulary's `about.csv`), so the page can send people to the current entry.
- **Ideal source:** a formulary export from the ICB's formulary team would replace this step.

### dm+d codes (NHS TRUD)

Medicines are coded against **dm+d**, the NHS dictionary of medicines and devices. Each medicine is linked to its **VTM**, the drug itself (e.g. "Morphine"); a medicine sold as different salts can have several VTMs. From dm+d's product data the import also records:

- the **BNF section** (ATC codes are deliberately not imported: the builder doesn't need them, and they carry the WHO's own copyright terms);
- for every route, **how many products exist** and **which CD schedules they carry**. For example, oral morphine products are Schedule 2 or 5 depending on strength.

To refresh the codes you need a TRUD account subscribed to items 24 (NHSBSA dm+d) and 25 (NHSBSA dm+d supplementary):

```
TRUD_API_KEY=... python3 tools/fetch_dmd.py    # or --key-file path; checks SHA-256, caches in .cache/
python3 tools/import_dmd.py                    # updates medicines.csv and data/dmd/
```

A `dmd_vtm` value already in `medicines.csv` is kept, so a mapping corrected by hand stays corrected. VTMs that dm+d has retired are moved to their successors. Name differences are handled by `VTM_NAMES`, and classes such as "Laxatives" are listed in `NO_VTM`.

`build.py` uses the dm+d data in two ways:

- **It fails** if a medicine's `cd_schedule` is not dm+d's most restrictive schedule for that drug, so the legal gate cannot silently miss a controlled drug.
- **It notes** menu routes with no dm+d product, which usually means off-label use (e.g. SC midazolam). The page shows the same note.

#### Automatic monthly refresh

`.github/workflows/refresh-dmd.yml` runs on the 3rd of each month, or by hand from the Actions tab. It downloads and imports the latest release, then builds and runs every check:

- **If anything changed**, it opens a pull request listing the changes medicine by medicine, with schedule changes flagged, and the check results. Review it and merge.
- **If the build fails**, usually because dm+d now gives a medicine a different controlled-drug schedule, it opens an issue instead, so the change can't go unnoticed.
- **If nothing changed**, it does nothing.

It needs your TRUD API key as a repository secret. Run this in a terminal and paste the key when asked, so it never appears in your shell history:

```
gh secret set TRUD_API_KEY --repo <owner>/scope-builder
```

**If a refresh is missed**, nothing breaks, but the data ages. The build warns when the dm+d data is more than 90 days old, or a legal source in `data/legal/sources.csv` was last checked more than a year ago. The builder page shows its own warning once its dm+d data is more than 3 months old.

### Adding a profile or a Trust

See [CONTRIBUTING.md](CONTRIBUTING.md). `python3 tools/new_trust.py <id> "<name>" <SHORT>` scaffolds a new Trust from an existing one. A GitHub Action runs the build's checks on every pull request, and `CODEOWNERS` routes changes to shared data (legal rules, medicines, dm+d) to a maintainer.


- **New profile** (e.g. ITU): add any missing medicines and routes to `menu.csv`, create `profiles/itu.csv` listing `medicine_id,route`, and add a row to `profiles.csv`. Or build it in the page and use **Save as profile**.
- **New Trust:** `python3 tools/new_trust.py`, then edit and review (see CONTRIBUTING.md).
- **Without a build:** anyone can try their own CSVs by dropping them into the page under *Use your own Trust's data*.

### Building and checks

`python3 build.py` uses Python 3 only, with no extra packages. It refuses to build if there are problems, such as:

- an unknown medicine or route
- a profile that lists something not on the menu, or a profile file not listed in `profiles.csv` (and the reverse)
- a route family the page can't colour
- a duplicate row

### Excel tips

- Save as **CSV UTF-8**. The build tolerates Excel's byte-order mark.
- IDs are text slugs (`morphine_sulfate`), so Excel won't mangle them.

## How the legal rules work

The legal gate covers **controlled drugs by profession**. This is the part that is black and white in law.

| Prescriber | CD rule | Source |
|---|---|---|
| Nurse IP, pharmacist IP | Any Schedule 2–5 drug, except cocaine, diamorphine or dipipanone for treating addiction | MDR 2001 reg 6B |
| Physiotherapist IP, podiatrist IP | Named drugs and routes only; organic disease or injury | reg 6C(1), 6C(2) |
| Therapeutic radiographer IP, paramedic IP | Named drugs and routes only; organic disease or injury | reg 6D(1), 6D(2) |
| Supplementary prescriber | Per clinical management plan, with the same addiction exclusion | CPE summary; statutory reference still to be added |

How a route is matched against these rules:

- **CD schedules come from dm+d per route.** If every product by a route is a controlled drug, the gate applies, and the reason shown names the schedule(s).
- **Schedule 5** (e.g. co-codamol, oral codeine tablets, Entonox): whether a profession with a named list needs a Schedule 5 drug to be on that list is set per profession in the `schedule5` column of `professions.csv`. `named` is the strict reading and the current default; `any` lets Schedule 5 preparations through. This is a policy decision to confirm. Under `named`, a paramedic IP cannot prescribe Entonox.

- **Combination products** have a `cd_ingredient` column. Co-codamol is checked as codeine phosphate.
- **Routes** are matched through `legal_class`. IV, IM, SC and IO count as "by injection", and buccal counts as "oromucosal".
- **Conservative reading:** sublingual and NG tube are **not** treated as "oral administration".

**Verification status:** the CD lists were transcribed from legislation.gov.uk (text current to Nov 2026) and cross-checked against the Community Pharmacy England "who can prescribe what" page. They still need an independent human check before anyone relies on them. Open questions:

- Whether Schedule 5 preparations need to be on the named lists in regs 6C and 6D (the `schedule5` setting above). dm+d settles which products *are* Schedule 5, e.g. nitrous oxide with oxygen, codeine tablets and some oral morphine.
- Amendments from SI 2025/1249 not yet applied to the MDR text on legislation.gov.uk.

## Status and next steps

- **Menu content:** 272 rows, adults only. Seeded from an earlier draft (v0.4), then expanded with an AI-drafted top-of-licence pass for ED, Resus, UTC and SDEC, including named antimicrobials. The profiles are AI-drafted too. **None of it is clinically reviewed yet.** Paediatrics is out of scope for now.
- **Formulary:** statuses come from the SWL A-Z reports saved on 26 Nov 2026. Each formulary badge links to that medicine's section on the live formulary site.
- **dm+d:** release 11.3.0 (23 Nov 2026). 142 of 152 medicines are coded; the other 10 are classes or have no VTM.
- **Next:** keying scopes on dm+d codes makes it possible to audit EPMA prescribing data against them.

## Licence

Code is [MIT](LICENSE). Our own content, such as menus, profiles and documentation, is [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Legislation and dm+d data are used under the Open Government Licence, and formulary statuses belong to their owners. See [LICENSES.md](LICENSES.md) for the details and the attribution to keep.
