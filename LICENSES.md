# Licences

This repository mixes code, our own content, and data from other organisations. Each has its own terms.

| What | Where | Licence |
|---|---|---|
| **Code** | `build.py`, `src/`, `tools/`, `tests/`, `.github/` | [MIT](LICENSE) |
| **Our own content**: menus, profiles, route mappings, documentation and the explanatory text in the built pages | `data/trusts/*/menu.csv`, `profiles.csv`, `profiles/`, `trust.csv`, `data/legal/routes.csv`, `data/frozen_ids.csv`, `*.md` | [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/) |
| **Legislation**: the Misuse of Drugs Regulations 2001 and the named lists transcribed from it | `data/legal/cd_named.csv`, `data/legal/professions.csv`, `data/legal/sources.csv` | Crown copyright, [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/) |
| **dm+d**: medicine codes and names, controlled-drug schedules and BNF codes, from the NHS Dictionary of Medicines and Devices | dm+d columns of `data/medicines.csv`, `data/dmd/` | NHSBSA via NHS TRUD, under the [Open Government Licence for TRUD](https://isd.digital.nhs.uk/trud/users/guest/filters/0/licence/1) |
| **Formulary statuses** | `data/formularies/*/formulary.csv` | Belong to each formulary's owner. See below. |

## Attribution

If you reuse the data, keep this statement:

> Contains public sector information licensed under the Open Government Licence v3.0. Medicine data from the NHS Dictionary of Medicines and Devices (dm+d), NHS Business Services Authority, via NHS TRUD. Legislation: Misuse of Drugs Regulations 2001, legislation.gov.uk.

CC BY 4.0 content should be credited to "Prescribing Scope Builder contributors", with a link to this repository.

## Not included

ATC codes are deliberately not imported from the dm+d supplementary file. The builder doesn't need them, and they carry the WHO Collaborating Centre's own copyright terms.

## Formulary data

Formulary statuses come from reports that a person saved from the formulary's public website. The import script never fetches anything itself.

**What we use is deliberately small.** For each medicine on a Trust's menu, about 150 in all, we keep:

- whether it is on the formulary, restricted, or not listed (Y, R or N);
- its BNF chapter;
- a link to its section on the formulary's own website, so people check the live entry there.

We do not copy restriction wording, guidance, traffic-light ratings or any other content. The import also produces a full list of every item in the saved reports, so matches can be checked. That list stays on the importer's own computer (`.cache/`, which git ignores) and is never committed or published.

Each formulary records its licence and permission status in its `about.csv`, and the About page of every Trust using it shows them.

| Formulary | Used by | Licence | Permission |
|---|---|---|---|
| South West London Joint Medicines Formulary (`swl`) | KRFT | Not established: a publicly available website with no licence information found | Not yet requested: modest use of a public website, described above |

Whoever adds a formulary should confirm that the formulary's owner is happy for the statuses to be republished before the repository or site is public.

## No warranty

None of this is clinical advice or prescribing authority. The [MIT licence](LICENSE) and CC BY 4.0 both exclude warranties, and the disclaimer in the built pages applies.
