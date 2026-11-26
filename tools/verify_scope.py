#!/usr/bin/env python3
"""Independently verify a scope link: decode it and recompute its fingerprint.

    python3 tools/verify_scope.py '<scope link or the part after #s=>'
    python3 tools/verify_scope.py --leaves '<link>'     # also print every leaf
    python3 tools/verify_scope.py --self-test           # check this implementation

Standard library only, and it does not import anything from the builder, so a governance reviewer can
read this one file and check a fingerprint without trusting the web page.

The format is defined in SPEC.md ("Scope link and fingerprint format, version 1"). This file is its
reference implementation, and the page must agree with it: CI checks both against tests/vectors.json.

In short: the link is <builder URL>#s=<payload>, where the payload is 'z' + base64url(raw DEFLATE(text))
or 't' + base64url(text), and the text is 'scope-builder/1', optional t=/p=/c=/f= context lines, then one
<medicine>|<route>=<code>[:<note>] line per decision. The fingerprint is the RFC 6962 Merkle Tree Hash
(SHA-256) over 'scope-builder scope v1' followed by the granting lines (i, r, c, s, e; notes only on r,
normalised), sorted by their UTF-8 bytes. The check code is the root's first 80 bits in Crockford base32.
"""
import base64, hashlib, json, re, sys, unicodedata, zlib
from pathlib import Path

HEADER = 'scope-builder/1'
ROOT_LEAF = 'scope-builder scope v1'
GRANTS = set('ircse')
NOTED = set('rd')
B32 = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'  # Crockford: no I, L, O, U


WHITESPACE = re.compile('[ \t\n\r\f\v\u00a0]+')  # an explicit set, so every implementation agrees


def clean_note(note):
    return WHITESPACE.sub(' ', unicodedata.normalize('NFC', note or '')).strip(' ')


def med_key(med):
    """dm+d keys list their VTM codes sorted as strings, so the same medicine always has one key."""
    return 'dmd:' + '+'.join(sorted(med[4:].split('+'))) if med.startswith('dmd:') else med


def item_line(med, route, code, note=''):
    med = med_key(med)
    note = clean_note(note) if code in NOTED else ''
    return f'{med}|{route}={code}' + (f':{note}' if note else '')


def leaf_lines(item_lines):
    """The fingerprint leaves: header, then granting items (notes only on r), sorted by UTF-8 bytes."""
    grants = []
    for line in item_lines:
        key, _, rest = line.partition('=')
        code, _, note = rest.partition(':')
        if code in GRANTS:
            grants.append(item_line(*key.split('|', 1), code, note if code == 'r' else ''))
    return [ROOT_LEAF] + sorted(set(grants), key=lambda s: s.encode('utf-8'))


def mth(leaves):
    """RFC 6962 Merkle Tree Hash over a list of byte strings."""
    if not leaves:
        return hashlib.sha256(b'').digest()
    if len(leaves) == 1:
        return hashlib.sha256(b'\x00' + leaves[0]).digest()
    k = 1
    while k * 2 < len(leaves):
        k *= 2
    return hashlib.sha256(b'\x01' + mth(leaves[:k]) + mth(leaves[k:])).digest()


def fingerprint(item_lines):
    return mth([l.encode('utf-8') for l in leaf_lines(item_lines)]).hex()


def check_code(root_hex):
    bits = ''.join(f'{b:08b}' for b in bytes.fromhex(root_hex)[:10])
    code = ''.join(B32[int(bits[i:i + 5], 2)] for i in range(0, 80, 5))
    return '-'.join(code[i:i + 4] for i in range(0, 16, 4))


def decode_payload(payload):
    payload = payload.split('#s=', 1)[-1].strip()
    data = base64.urlsafe_b64decode(payload[1:] + '=' * (-len(payload[1:]) % 4))
    text = zlib.decompress(data, -15).decode('utf-8') if payload[0] == 'z' else data.decode('utf-8')
    lines = text.split('\n')
    if lines[0] != HEADER:
        raise ValueError(f'not a version 1 scope link (starts {lines[0]!r})')
    ctx, items = {}, []
    for line in lines[1:]:
        if line[:2] in ('t=', 'p=', 'c=', 'f='):
            ctx[line[0]] = line[2:]
        elif line:
            items.append(line)
    return ctx, items


def encode_payload(ctx, item_lines):
    text = '\n'.join([HEADER] + [f'{k}={v}' for k, v in ctx.items() if v] + item_lines).encode('utf-8')
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    return 'z' + base64.urlsafe_b64encode(c.compress(text) + c.flush()).decode().rstrip('=')


def self_test():
    assert hashlib.sha256(b'abc').hexdigest() == 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'
    vectors = json.loads((Path(__file__).resolve().parent.parent / 'tests' / 'vectors.json').read_text())
    for v in vectors['fingerprints']:
        got = fingerprint(v['items'])
        assert got == v['root'], (v['name'], got, v['root'])
        assert check_code(got) == v['check_code'], v['name']
    for v in vectors['payloads']:
        ctx, items = decode_payload(v['payload'])
        assert items == v['items'] and ctx == v['context'], v['name']
    # SPEC.md's worked example must stay true: it is one of the vectors
    spec = (Path(__file__).resolve().parent.parent / 'SPEC.md').read_text(encoding='utf-8')
    ex = next(v for v in vectors['fingerprints'] if v['name'] == 'SPEC.md worked example')
    assert ex['root'] in spec and ex['check_code'] in spec, 'SPEC.md worked example does not match the vectors'
    print(f"self-test passed: {len(vectors['fingerprints'])} fingerprint vectors, {len(vectors['payloads'])} payload vectors")


def main(argv):
    if argv[:1] == ['--self-test']:
        return self_test()
    show = argv[:1] == ['--leaves']
    args = argv[1:] if show else argv
    if not args:
        sys.exit(__doc__)
    ctx, items = decode_payload(args[0])
    root = fingerprint(items)
    print(f"trust:        {ctx.get('t', '?')}")
    if ctx.get('p'):
        print(f"profession:   {ctx['p']} (context only)")
    if ctx.get('c'):
        print(f"data context: {ctx['c']}")
    grants = len(leaf_lines(items)) - 1
    print(f'items:        {len(items)} in the link, {grants} granting permission')
    print(f'fingerprint:  {root}')
    print(f'check code:   {check_code(root)}')
    if show:
        for i, l in enumerate(leaf_lines(items)):
            print(f'  leaf {i:3}: {l}')


if __name__ == '__main__':
    main(sys.argv[1:])
