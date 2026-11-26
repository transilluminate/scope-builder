# Scope link and fingerprint format, version 1

This document defines how Prescribing Scope Builder writes a scope of practice into a link, and how it calculates the scope's **fingerprint**. Anyone can write a compatible tool from this document alone: a Trust's own system, a governance spreadsheet macro, or an independent checker.

- **Status:** version 1, stable. Anything that would change a fingerprint needs a new version number (see [Versioning](#9-versioning-and-change-control)).
- **Reference implementation:** [`tools/verify_scope.py`](tools/verify_scope.py), Python standard library only. Where this document and that file disagree, it is a bug; please report it.
- **Test vectors:** [`tests/vectors.json`](tests/vectors.json). A conforming implementation reproduces every root, check code and decoded link in it. CI checks both the reference implementation and the web page against them on every change.
- **Licence:** this document is CC BY 4.0, like the rest of the project's own content.

The key words MUST, MUST NOT, SHOULD and MAY are used as in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

## 1. What a fingerprint covers

A fingerprint identifies **what a scope permits**, and nothing else. Two scopes that permit exactly the same medicine and route combinations, with the same restrictions, have the same fingerprint, wherever and whenever they were made.

| Part of the scope | In the fingerprint? |
|---|---|
| Each medicine and route marked include, restricted, continuation only, specialist advice only, or emergency use only | Yes |
| The wording of a restriction | Yes |
| Developmental and excluded entries, and their notes | No |
| The Trust, profession, person's name, dates, signatures | No |
| Data versions (dm+d release, formulary date, build) | No |
| The order decisions were made in, or listed in | No |

So a fingerprint does not change when the builder's data is refreshed, and the same scope moved to another Trust keeps its fingerprint. The Trust's record of *who* was signed off for *which* fingerprint, and when, is kept by the Trust, not by this format.

## 2. Identifiers

Every entry names a medicine, a route and a decision.

### 2.1 Medicines

- **dm+d medicines:** `dmd:` followed by the medicine's dm+d **VTM** (Virtual Therapeutic Moiety) code, for example `dmd:777067000` (paracetamol). VTM codes are issued by NHS England in the [NHS Dictionary of Medicines and Devices](https://www.nhsbsa.nhs.uk/pharmacies-gp-practices-and-appliance-contractors/dictionary-medicines-and-devices-dmd).
- **Several VTMs:** where one entry deliberately covers more than one VTM, the codes are joined with `+` and **MUST** be sorted as strings (character by character, not numerically), for example `dmd:111+222`. An implementation **MUST** re-sort them before use, so the same medicine always has exactly one identifier.
- **Medicines with no VTM:** `local:` followed by the builder's own id, for example `local:oxygen`. These are used only where dm+d has no VTM, such as oxygen or a class like "laxatives". The registry of local ids is [`data/frozen_ids.csv`](data/frozen_ids.csv).

**Re-coding.** dm+d occasionally retires a VTM code and issues a new one. The builder records each medicine's previous codes in the `dmd_vtm_prev` column of [`data/medicines.csv`](data/medicines.csv), so links made before a re-coding still open. A link keeps the code it was made with, and so keeps its fingerprint: re-coding never changes an existing fingerprint. A scope rebuilt after a re-coding has a new fingerprint and needs signing off again, as any changed scope does.

### 2.2 Routes

Routes use the builder's own ids. They are permanent: once used in a link, an id **MUST NOT** be renamed, removed or given a different meaning. The build refuses to run if one disappears from the data, and a new id has to be added to [`data/frozen_ids.csv`](data/frozen_ids.csv) deliberately.

| Route id | Meaning |
|---|---|
| `PO` | Oral |
| `NG` | Nasogastric tube |
| `SL` | Sublingual |
| `buccal` | Buccal / oromucosal |
| `intranasal` | Intranasal |
| `IV` | Intravenous |
| `IO` | Intraosseous |
| `IM` | Intramuscular |
| `SC` | Subcutaneous |
| `infiltration` | Local infiltration |
| `regional` | Regional nerve block |
| `inhaled` | Inhaled |
| `nebulised` | Nebulised |
| `topical` | Topical |
| `nasal_topical` | Topical (nasal) |
| `eye` | Eye |
| `PR` | Rectal |
| `transdermal` | Transdermal |

The build checks that every route id in use is listed in this table.

### 2.3 Decisions

| Code | Decision | Grants permission? | Note kept? |
|---|---|---|---|
| `i` | Include | Yes | No |
| `r` | Include, with a restriction | Yes | Yes, and it is part of the fingerprint |
| `c` | Continuation only | Yes | No |
| `s` | On specialist advice only | Yes | No |
| `e` | Emergency use only | Yes | No |
| `d` | Developmental: not yet in scope | No | Yes, in the link only |
| `x` | Exclude | No | No |

A medicine and route with no entry is not in scope.

## 3. Entry lines

Each decision is one line of UTF-8 text:

```
<medicine>|<route>=<code>[:<note>]
```

For example `dmd:777067000|PO=i` or `dmd:773372004|PO=r:Short course only`.

- A note is written only for `r` and `d`. Any note on another code **MUST** be dropped.
- An empty note (after normalising) is written as no note: no `:`.
- **Note normalisation**, applied in this order:
  1. Unicode normalisation form NFC.
  2. Each run of one or more of these characters is replaced by one space: space U+0020, tab U+0009, line feed U+000A, carriage return U+000D, form feed U+000C, vertical tab U+000B, no-break space U+00A0. The set is explicit, not "whitespace", so every programming language agrees.
  3. Leading and trailing spaces are removed.

## 4. Scope links

A scope link carries the whole scope in the URL fragment, after `#s=`. Browsers do not send the fragment to the server, so the scope is never stored online.

```
<builder page URL>#s=<payload>
```

The **text** of the payload is UTF-8, with lines separated by a single line feed (U+000A) and no line feed at the end:

```
scope-builder/1
t=<trust id>
p=<profession id>
c=<data context>
f=<profiles>
<entry line>
<entry line>
...
```

- **Line 1** is exactly `scope-builder/1`. A reader **MUST** reject anything else.
- **Context lines** `t=`, `p=`, `c=` and `f=` are optional, appear at most once each, and come before the entries. They say which Trust's builder made the link, the profession chosen, the data versions (dm+d release, build date, commit), and the Trust profiles the scope was built from, so a reader can show them and an editor can reopen the scope as it was made. `f=` is a comma-separated list of the Trust's profile ids, with `*` meaning "the whole menu"; ids a reader does not know are ignored. Context lines are **not** part of the fingerprint. A writer omits a context line that has no value.
- **Entry lines** follow, as in section 3. Writers **SHOULD** sort them; readers **MUST NOT** depend on their order.

The **payload** is one of:

- `z` followed by the text compressed with raw DEFLATE ([RFC 1951](https://www.rfc-editor.org/rfc/rfc1951), no zlib or gzip header), then base64url-encoded ([RFC 4648 section 5](https://www.rfc-editor.org/rfc/rfc4648#section-5)) without `=` padding.
- `t` followed by the uncompressed text, base64url-encoded without padding. Writers use this only where compression is unavailable.

Readers **MUST** accept both.

## 5. Leaves

The fingerprint is calculated over a list of **leaves**, each a string encoded as UTF-8:

1. **Leaf 0** is exactly `scope-builder scope v1`. It labels the format, so a fingerprint from any other format or version can never collide with a version 1 fingerprint.
2. **The other leaves** are the entry lines whose code grants permission (`i`, `r`, `c`, `s`, `e`), each rewritten as in section 3. The note is kept only for `r`; the medicine identifier has its VTM codes re-sorted; restriction notes are normalised.
3. Duplicates are removed.
4. These leaves are sorted by their UTF-8 bytes, compared byte by byte as unsigned values, where a shorter string that is a prefix of a longer one comes first.

Developmental (`d`) and excluded (`x`) entries, and lines that are not entries, produce no leaves.

## 6. The Merkle tree

The fingerprint is the **Merkle Tree Hash** (MTH) of [RFC 6962 section 2.1](https://www.rfc-editor.org/rfc/rfc6962#section-2.1), with SHA-256 ([FIPS 180-4](https://csrc.nist.gov/pubs/fips/180-4/upd1/final)), over the leaves in order:

- For one leaf *d*: MTH = SHA-256(`0x00` ‖ *d*).
- For *n* > 1 leaves: let *k* be the largest power of two smaller than *n*. MTH = SHA-256(`0x01` ‖ MTH(first *k* leaves) ‖ MTH(remaining *n* − *k* leaves)).

Here ‖ means joining bytes, and hashes are joined as their 32 raw bytes, not as hex text. The `0x00` and `0x01` prefixes keep leaves and joining nodes apart, so one can never be passed off as the other.

There is always at least leaf 0, so the empty-tree case of RFC 6962 never arises.

The **fingerprint** is the root hash written as 64 lowercase hexadecimal digits. It is the value to record and compare.

## 7. Check code

The check code is a short form for reading aloud or by eye. It **MUST NOT** be used in place of the fingerprint as a record.

1. Take the first 10 bytes (80 bits) of the root hash.
2. Split the 80 bits, most significant first, into sixteen groups of 5 bits.
3. Write each group as one character of Crockford's base32 alphabet, `0123456789ABCDEFGHJKMNPQRSTVWXYZ` (no I, L, O or U).
4. Put a hyphen after every 4 characters: `XXXX-XXXX-XXXX-XXXX`.

## 8. Worked example

A scope with four decisions, in any order:

```
dmd:777067000|PO=i
dmd:773372004|PO=r:Short  course only 
dmd:776993002|IV=d:Five supervised cases
local:oxygen|inhaled=e
```

The developmental ondansetron entry produces no leaf. The morphine restriction loses its double space and trailing space. Sorted by bytes, the leaves are:

| # | Leaf | SHA-256(`0x00` ‖ leaf) |
|---|---|---|
| 0 | `scope-builder scope v1` | `54581f997a6cdb40cbb636c1ddac440c5eb0338c5308814b38ee35a00471257b` |
| 1 | `dmd:773372004\|PO=r:Short course only` | `d0b299c106ea30b71e4cb6ae8de70ab503fa37207cb58d8b0e95e02fef946f49` |
| 2 | `dmd:777067000\|PO=i` | `eae799a2530d6361536d4b35d6f2eba5f854ad24bfb5fdd3223e911793933d17` |
| 3 | `local:oxygen\|inhaled=e` | `e4dfca37757af6d6383f5e0ed9c783937afce804272c17864f04691594d47c14` |

With four leaves, *k* = 2:

- Node for leaves 0–1: `fb12468167da4fd5a2b04d0a25899b56736252860ab8cb54e92395177b8e61ac`
- Node for leaves 2–3: `0ee1e1936bd36ca9ff48ca7d02fdaff20f2c9f658e03ab14cfe38ae6943d8221`
- **Fingerprint:** `878a946cfe112b20470819b72eea740bf6d128055c01aaabd9cfb279fe135216`
- **Check code:** `GY59-8V7Y-24NJ-0HR8`

A scope with nothing in it has only leaf 0, so its fingerprint is that leaf's hash, `54581f99…471257b`, check code `AHC1-Z6BT-DKDM-1JXP`.

This example is the vector named "SPEC.md worked example" in `tests/vectors.json`, so CI fails if this section and the code drift apart.

To check any link yourself:

```
python3 tools/verify_scope.py --leaves '<scope link>'
```

## 9. Versioning and change control

- **Anything that would change the fingerprint of an existing scope** needs a new format version: a new line 1 (`scope-builder/2`), a new leaf 0 (`scope-builder scope v2`), and a new version of this document. Examples: a new decision code that grants permission, a change to note normalisation, a different hash.
- **Version 1 readers** reject other versions rather than guess. Future builders **SHOULD** keep reading version 1 links, so existing signed scopes can still be checked.
- **Allowed in version 1** without a new version: new route ids and local medicine ids (added to the registry), new context keys, once defined in this document (a reader that does not know a key shows that line as an entry it cannot read, and the fingerprint is unaffected), new dm+d codes, and changes to the builder's data.
- **Identifiers** are never reused or renamed. The registry is [`data/frozen_ids.csv`](data/frozen_ids.csv); dm+d re-codings are tracked in `dmd_vtm_prev`. Both are in git, so every change has a date, a reason and an author.

### Change log

| Date | Change |
|---|---|
| 2026-11-26 | Version 1 published. |
