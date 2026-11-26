// Fingerprint playground for fingerprint.html. It runs the same crypto block as the builder (inserted
// before this file at build time), so what it shows is exactly how real fingerprints are made.
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const OPTS = [['include', 'Include'], ['restricted', 'Include with restriction'], ['continuation', 'Continuation only'], ['specialist', 'Specialist advice only'],
  ['emergency', 'Emergency use only'], ['developmental', 'Developmental'], ['exclude', 'Exclude']];
const GRANTING = new Set(['include', 'restricted', 'continuation', 'specialist', 'emergency']);
const pill = r => `<span class="rp f-${esc(r.family)}" title="${esc(r.route_name)}">${esc(r.short)}</span>`;
const SELF_TEST = hex(sha256(UTF8.encode('abc'))) === 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad';

// ---- the sample scope ----
let rows = SAMPLE.map((s, i) => ({ ...s, i }));
// Colours compare with the recorded fingerprint (the one governance checks against); the flash marks the last edit.
let recorded = null, recordedState = null, recordedNodes = new Set(), recordedLeaves = new Map(), prevFp = null, prevNodes = new Set();
const nodeSet = t => { const s = new Set(); (function all(n) { s.add(n.h); n.kids?.forEach(all); })(t); return s; };

const lineOf = r => itemLine(r.med, r.route, CODE[r.d], r.note);
const scopeLines = () => rows.map(lineOf);

// The same Merkle Tree Hash as mth(), but keeping every node so the tree can be drawn.
// Each node knows its path from the root (L/R), so a box chosen in the inspector survives a redraw.
function tree(leaves, lo = 0, path = '') {
  if (leaves.length === 1) return { h: hex(sha256(cat(new Uint8Array([0]), leaves[0]))), leaf: lo, lo, hi: lo, path };
  let k = 1; while (k * 2 < leaves.length) k *= 2;
  const L = tree(leaves.slice(0, k), lo, path + 'L'), R = tree(leaves.slice(k), lo + k, path + 'R');
  return { h: hex(sha256(cat(new Uint8Array([1]), fromHex(L.h), fromHex(R.h)))), kids: [L, R], lo, hi: R.hi, path };
}
const fromHex = h => Uint8Array.from(h.match(/../g), x => parseInt(x, 16));

function diffHex(before, after, group = 16) {
  let out = '';
  for (let i = 0; i < after.length; i++) {
    if (i && i % group === 0) out += ' ';
    // against a reference, changed characters are marked and unchanged ones shown as matching
    out += !before ? after[i] : before[i] !== after[i] ? `<mark>${after[i]}</mark>` : `<span class="s">${after[i]}</span>`;
  }
  return out;
}
const changedCount = (a, b) => a ? [...b].filter((c, i) => a[i] !== c).length : 0;

function drawTree(root, nLeaves, names) {
  const W = 50, H = 58, BW = 42, BH = 22, pad = 8, LABEL = 96; // labels run diagonally under the leaves
  let depth = 0;
  (function d(n, k) { depth = Math.max(depth, k); n.kids?.forEach(c => d(c, k + 1)); })(root, 0);
  const nodes = [], edges = [];
  (function place(n, k) {
    if (n.kids) { n.kids.forEach(c => place(c, k + 1)); n.x = (n.kids[0].x + n.kids[1].x) / 2; n.y = k; }
    else { n.x = n.leaf; n.y = depth; }
    nodes.push(n); n.kids?.forEach(c => edges.push([n, c]));
  })(root, 0);
  const X = n => pad + n.x * W + W / 2, Y = n => pad + n.y * H + BH / 2;
  const diff = n => !recordedNodes.has(n.h), flash = n => prevNodes.size && !prevNodes.has(n.h);
  const width = nLeaves * W + pad * 2 + LABEL, height = depth * H + BH + pad * 2 + LABEL;
  const svg = [`<svg class="mtree" viewBox="0 0 ${width} ${height}" width="${width}" aria-label="Merkle tree of the sample scope: green boxes match the recorded fingerprint, red boxes differ">`];
  edges.forEach(([p, c]) => svg.push(`<line x1="${X(c)}" y1="${Y(c) - BH / 2}" x2="${X(p)}" y2="${Y(p) + BH / 2}" class="${diff(c) && diff(p) ? 'diff' : ''}"/>`));
  nodes.forEach(n => svg.push(`<g class="node ${diff(n) ? 'diff' : 'same'}${flash(n) ? ' flash' : ''}${n === root ? ' root' : ''}" data-path="${n.path}" tabindex="0" role="button"
    aria-label="${n.leaf !== undefined ? `Leaf: ${esc(names[n.leaf])}` : n === root ? 'The root: the fingerprint' : 'A joining box'}. Show its details">
    <rect class="hit" x="${X(n) - W / 2}" y="${Y(n) - H / 2}" width="${W}" height="${H}"/>
    <rect class="box" x="${X(n) - BW / 2}" y="${Y(n) - BH / 2}" width="${BW}" height="${BH}" rx="5"/><text x="${X(n)}" y="${Y(n) + 4}">${n.h.slice(0, 4)}</text>
    ${n.leaf !== undefined ? `<text class="lbl" transform="translate(${X(n) - 4} ${Y(n) + BH / 2 + 12}) rotate(40)">${esc(names[n.leaf])}</text>` : ''}</g>`));
  svg.push('</svg>');
  return svg.join('');
}

function render(reason) {
  const lines = scopeLines(), leaves = leafLines(lines);
  const fp = fingerprintHex(lines);
  const t = tree(leaves.map(l => UTF8.encode(l)));
  if (t.h !== fp) throw new Error('tree and fingerprint disagree');
  const byLine = new Map(rows.map(r => [itemLine(r.med, r.route, CODE[r.d], r.d === 'restricted' ? r.note : ''), r]));
  const label = l => (r => r ? `${r.name} ${r.short}` : l)(byLine.get(l));
  if (recorded === null) {
    recorded = fp; recordedState = rows.map(r => ({ i: r.i, d: r.d, note: r.note }));
    recordedNodes = nodeSet(t); recordedLeaves = new Map(leaves.slice(1).map(l => [l, label(l)]));
  }
  const match = fp === recorded;

  // the fingerprint, with the characters that differ from the recorded one highlighted
  $('pgCode').textContent = checkCode(fp);
  $('pgCode').className = 'fp ' + (match ? 'ok' : 'bad');
  $('pgHex').innerHTML = diffHex(recorded, fp);
  $('pgHex').className = 'fphex pg-hex ' + (match ? 'ok' : 'bad');
  const n = changedCount(recorded, fp);
  let msg = '';
  if (prevFp === null) msg = 'This is the fingerprint of the sample scope, recorded as if it had just been signed off. Change anything below and watch it.';
  else if (prevFp === fp) msg = `<b>Same fingerprint.</b> ${reason || 'What this scope permits has not changed.'}`;
  else if (match) msg = '<b>Back to the recorded fingerprint.</b> The same permissions always give exactly the same fingerprint.';
  else msg = `<b>${n} of 64 characters differ from the recorded fingerprint.</b> There is no pattern to it: any change gives a completely different fingerprint.`;
  $('pgMsg').innerHTML = msg;
  $('pgStatus').innerHTML = match
    ? `<span class="badge b-ok">✓ Matches the recorded fingerprint</span>`
    : `<span class="badge b-no">✗ Does not match the recorded fingerprint</span> <span class="small muted">This is what a governance check would show for an edited scope.</span>`;
  $('pgRecorded').textContent = checkCode(recorded);
  $('pgUndo').hidden = match;

  const names = leaves.map((l, i) => i === 0 ? 'Format label' : label(l));
  const removed = [...recordedLeaves].filter(([l]) => !leaves.includes(l)).map(([, name]) => name);
  $('pgGone').innerHTML = removed.length ? `Removed since recorded: ${removed.map(esc).join(', ')}` : '';
  const left = rows.filter(r => !GRANTING.has(r.d));
  $('pgLeft').innerHTML = left.length ? `Not in the fingerprint: ${left.map(r => `${esc(r.name)} ${pill(r)} (${r.d === 'exclude' ? 'excluded' : 'developmental'})`).join(', ')}.` : '';
  $('pgTree').innerHTML = drawTree(t, leaves.length, names);
  CUR = { t, leaves, names, byLine, nodes: new Map() };
  (function all(n) { CUR.nodes.set(n.path, n); n.kids?.forEach(all); })(t);
  inspect(pinned);

  prevNodes = nodeSet(t);
  prevFp = fp;
}

// ---- the inspector: explains whichever box is hovered, tapped or focused (the root by default) ----
let CUR = null, pinned = '';
const groupHex = h => h.match(/.{16}/g).join(' ');
function inspect(path) {
  const n = CUR.nodes.get(path) || CUR.t, isRoot = n === CUR.t;
  document.querySelectorAll('svg.mtree g.node').forEach(g => {
    g.classList.toggle('sel', g.dataset.path === n.path);
    g.classList.toggle('kid', !!n.kids && (g.dataset.path === n.path + 'L' || g.dataset.path === n.path + 'R'));
  });
  const status = recordedNodes.has(n.h) ? '<span class="badge b-ok">Same as in the recorded fingerprint</span>' : '<span class="badge b-no">Differs from the recorded fingerprint</span>';
  let head, how;
  if (n.kids) {
    const [L, R] = n.kids, covers = CUR.names.slice(n.lo, n.hi + 1);
    head = isRoot ? '<b>The root: this is the fingerprint</b>' : `<b>A joining box</b> <span class="muted">covering ${covers.length} leaves: ${covers.map(esc).join(', ')}</span>`;
    how = `<p>Made by hashing the two boxes below it, left then right:</p>
      <p class="formula">SHA-256( <code>01</code> + <code class="k">${L.h.slice(0, 4)}…</code> + <code class="k">${R.h.slice(0, 4)}…</code> )</p>
      <p class="small muted">The <code>01</code> marks it as a joining box, so it can never be confused with a leaf. Change anything below it and this box changes too.${isRoot ? ' Every leaf is below the root, so any change reaches it.' : ''}</p>`;
  } else {
    const line = CUR.leaves[n.leaf], r = CUR.byLine.get(line);
    head = n.leaf === 0 ? '<b>Format label</b> <span class="muted">always the first leaf</span>'
      : `<b>${esc(r.name)}</b> ${pill(r)} <span class="muted">${esc(OPTS.find(o => o[0] === r.d)[1])}${r.d === 'restricted' && r.note ? `: ${esc(r.note)}` : ''}</span>`;
    how = `<p>Made by hashing its line of text:</p>
      <p class="formula">SHA-256( <code>00</code> + <code>${esc(line)}</code> )</p>
      <p class="small muted">The <code>00</code> marks it as a leaf. ${n.leaf === 0 ? 'This fixed label means a scope fingerprint can never be mistaken for any other kind of hash.' : 'Only its own line goes in, not its position, so it keeps the same hash when it moves along the row.'}</p>`;
  }
  $('pgInspect').innerHTML = `<div class="ins-head">${head}</div>${how}
    <p class="ins-hash"><span class="muted small">Its full hash</span><code class="fphex">${groupHex(n.h)}</code></p>${status}`;
}
function initInspector() {
  const box = $('pgTree'), pathOf = e => e.target.closest?.('g.node')?.dataset.path;
  box.addEventListener('mouseover', e => { const p = pathOf(e); if (p !== undefined) inspect(p); });
  box.addEventListener('mouseleave', () => inspect(pinned));
  box.addEventListener('click', e => { const p = pathOf(e); if (p !== undefined) { pinned = p; inspect(p); } });
  box.addEventListener('focusin', e => { const p = pathOf(e); if (p !== undefined) { pinned = p; inspect(p); } });
  box.addEventListener('keydown', e => { if ((e.key === 'Enter' || e.key === ' ') && pathOf(e) !== undefined) { e.preventDefault(); pinned = pathOf(e); inspect(pinned); } });
}

function renderRows() {
  $('pgRows').innerHTML = rows.map(r => `<div class="pg-row">
    <div><b>${esc(r.name)}</b> ${pill(r)}</div>
    <select class="dec v-${r.d}" data-i="${r.i}" aria-label="Decision for ${esc(r.name)} ${esc(r.route_name)}">${OPTS.map(([v, t]) => `<option value="${v}"${v === r.d ? ' selected' : ''}>${t}</option>`).join('')}</select>
    ${r.d === 'restricted' || r.d === 'developmental' ? `<input type="text" data-note="${r.i}" value="${esc(r.note)}" aria-label="${r.d === 'restricted' ? 'Restriction' : 'Development plan'} for ${esc(r.name)}" placeholder="${r.d === 'restricted' ? 'Restriction' : 'Development plan'}">` : ''}
  </div>`).join('');
}
const row = i => rows.find(r => r.i === +i);

function why(before, after) {
  if (!GRANTING.has(before) && !GRANTING.has(after)) return 'Developmental and excluded items are not permissions, so they are not part of the fingerprint.';
  return '';
}

function init() {
  if (!SELF_TEST) { $('pgBox').innerHTML = '<p class="notice">This browser failed the SHA-256 self-test, so the playground is switched off.</p>'; return; }
  initInspector(); renderRows(); render();
  $('pgRows').addEventListener('change', e => {
    const i = e.target.dataset.i; if (i === undefined) return;
    const r = row(i), before = r.d; r.d = e.target.value;
    renderRows(); render(why(before, r.d));
  });
  $('pgRows').addEventListener('input', e => {
    const i = e.target.dataset.note; if (i === undefined) return;
    const r = row(i); r.note = e.target.value;
    render(r.d === 'developmental' ? 'Development plans are not part of the fingerprint; only restrictions are.'
      : 'Extra spaces, and spaces at either end, are ignored, so retyping a restriction slightly differently does not change it.');
  });
  $('pgShuffle').addEventListener('click', () => {
    for (let i = rows.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [rows[i], rows[j]] = [rows[j], rows[i]]; }
    renderRows(); render('The order does not matter. Items are sorted by their code before hashing, so the same permissions always give the same fingerprint.');
  });
  $('pgRecord').addEventListener('click', () => {
    recorded = null; prevFp = null; prevNodes = new Set(); render();
    $('pgMsg').innerHTML = '<b>Recorded.</b> This is now the fingerprint on the signed scope. Change something and see whether it still matches.';
  });
  $('pgUndo').addEventListener('click', () => {
    recordedState.forEach(s => Object.assign(row(s.i), { d: s.d, note: s.note }));
    initInspector(); renderRows(); render();
    $('pgMsg').innerHTML = '<b>Back to the recorded scope, and the fingerprint matches again.</b> The same permissions always give the same fingerprint, on any computer.';
  });

  // a single hash on its own, always compared with the starting text
  const REF = $('hIn').value, refH = hex(sha256(UTF8.encode(REF)));
  $('hRef').innerHTML = `Code for the starting text “${esc(REF)}”: <code>${refH.match(/.{16}/g).join(' ')}</code>`;
  const hashIt = () => {
    const text = $('hIn').value, h = hex(sha256(UTF8.encode(text)));
    $('hOut').innerHTML = diffHex(refH, h);
    $('hMsg').innerHTML = text === REF ? `<span class="badge b-ok">✓ Same text as at the start, so exactly the same code</span>`
      : `<span class="badge b-no">${changedCount(refH, h)} of 64 characters differ</span> from the code for “${esc(REF)}”. Change it back and they match again.`;
  };
  $('hIn').addEventListener('input', hashIt); hashIt();
}
init();
