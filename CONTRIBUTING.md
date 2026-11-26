# Contributing

Thank you for helping. The aim is one shared tool, with each Trust keeping its own menu, profiles and formulary, and everyone sharing the legal rules and medicine codes.

## What lives where

| Folder | Owned by | Changes when |
|---|---|---|
| `data/legal/` | Shared: maintainers review every change | The law changes |
| `data/medicines.csv`, `data/dmd/` | Shared: maintainers review every change | A medicine is added, or a new dm+d release |
| `data/formularies/<id>/` | Shared by the Trusts that use that formulary | The formulary is re-imported |
| `data/trusts/<your-trust>/` | Your Trust | Your menu or profiles change |

## Adding your Trust

1. **Fork the repository** and create a branch.
2. **Scaffold your folder** from an existing Trust:

   ```
   python3 tools/new_trust.py kch "King's College Hospital NHS Foundation Trust" KCH --region "London (South East)"
   ```

   This copies the menu and profiles from KRFT and marks every row as unreviewed for your Trust.
   If your formulary is already in `data/formularies/` (for example `swl`), add `--formulary swl`.
3. **Edit `trust.csv`:** the name, region, formulary id and a contact.
4. **Review the menu and profiles.** Remove what your Trust doesn't use and add what it does. Fill in the `reviewed` column (initials and date) as rows are clinically checked. Profiles are plain lists of `medicine_id,route`.
5. **Your formulary**, if it isn't there yet. Formularies are shared, so check `data/formularies/` first: one import serves every Trust that uses it. For a new one on netFormulary:
   - create `data/formularies/<id>/about.csv`, copying `swl/about.csv`;
   - save each chapter's *A-Z of formulary items* and *A-Z of Non Formulary items* report from your browser;
   - run:

   ```
   python3 tools/import_netformulary.py <folder of saved pages> <id>
   ```

   - then set `formulary,<id>` in your `trust.csv`.

   Other formulary systems: fill in `formulary.csv` by hand, or leave `formulary` blank in `trust.csv` (the page then shows "not checked").
6. **Build and check:** `python3 build.py <your-trust>`, then open `dist/<your-trust>/index.html`.
7. **Open a pull request.** The automatic check runs the same build. It must pass before merging.

## Adding a medicine

1. Add a row to `data/medicines.csv` with a `medicine_id` (lower case with underscores, e.g. `co_amoxiclav`) and a name.
2. A maintainer with a TRUD account runs `tools/fetch_dmd.py` and `tools/import_dmd.py` to add its dm+d codes and CD schedule. If you have TRUD access you can run them yourself.
3. The build refuses a medicine whose CD schedule doesn't match dm+d. That's deliberate: it stops a controlled drug from slipping past the legal check.

## Identifiers are permanent

Scope links and fingerprints name medicines by dm+d code and routes by the builder's route id. A route id, or the id of a medicine with no dm+d code, must never be renamed or removed once it has been used. `data/frozen_ids.csv` lists them, and the build fails if one disappears. A new route or local medicine has to be added to that file deliberately, and a new route also to the route table in [SPEC.md](SPEC.md), the published format. Anything that would change an existing fingerprint needs a new format version: see SPEC.md, section 9.

## Changing the legal data

Every change to `data/legal/` needs a **source**: the regulation, with a link and the date it was checked. Put the source in `data/legal/sources.csv` and in the `source` column of the row you change. Say in the pull request what changed in the law, and when.

## Ground rules

- **No doses, no clinical guidance.** This is a mapping tool.
- **No personal or patient data** anywhere in the repository.
- **Mark drafts honestly.** Content generated with AI help, or copied from another Trust, keeps a blank `reviewed` column until a clinician has checked it.
- **Formulary content:** check that your formulary's owner is happy for its statuses to be republished before the repository is public.
