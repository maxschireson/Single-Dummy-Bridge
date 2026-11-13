'use strict';
/* Sid: play bridge against the bot. One page, hash routes, the table long-polled from /api/tables/<id>. */

const SEATS = ['N', 'E', 'S', 'W'];
const SEAT_NAME = { N: 'North', E: 'East', S: 'South', W: 'West' };
const SUITS = ['S', 'H', 'D', 'C'];
const SYM = { S: '♠', H: '♥', D: '♦', C: '♣' };
const SUIT_NAME = { S: 'spades', H: 'hearts', D: 'diamonds', C: 'clubs' };
const RANK_NAME = { A: 'ace', K: 'king', Q: 'queen', J: 'jack', T: 'ten' };
const RANKS = '23456789TJQKA';
const SYSTEMS = {
  'house-gen6': 'Its bidding grew out of BEN\u2019s network, which learned from GIB auctions (broadly 2/1 game forcing), and has since been retrained to reach good contracts, so treat it as a style rather than a written system. It makes no alerts and gives no explanations.',
};

const app = { me: null, view: null, version: -1, pollToken: 0, tableId: null };
const $main = document.getElementById('main');

/* ---- small helpers ----------------------------------------------------------------- */
function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else if (k === 'style') el.setAttribute('style', v);
    else el.setAttribute(k, v === true ? '' : v);
  }
  for (const kid of kids.flat(Infinity)) {
    if (kid === null || kid === undefined || kid === false) continue;
    el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return el;
}
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function api(method, path, body) {
  const opts = { method, credentials: 'same-origin', headers: {} };
  if (method === 'POST') {
    opts.headers['X-Sid'] = '1';
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body || {});
  }
  const r = await fetch(path, opts);
  let data = null;
  try { data = await r.json(); } catch (e) { /* not JSON */ }
  if (!r.ok) {
    const err = new Error((data && data.error) || `The server answered ${r.status}.`);
    err.status = r.status;
    throw err;
  }
  return data;
}

let toastTimer = 0;
function toast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 3500);
}

function rankText(r) { return r === 'T' ? '10' : r; }
function cardEl(c) {
  return h('span', { class: `s-${c[0]}` }, rankText(c[1]), SYM[c[0]]);
}
function callEl(call) {
  if (call === 'PASS') return h('span', {}, 'Pass');
  if (call === 'X') return h('span', { class: 's-H' }, 'Dbl');
  if (call === 'XX') return h('span', { style: 'color:var(--rdbl)' }, 'Rdbl');
  const strain = call[1];
  if (strain === 'N') return h('span', {}, call[0] + 'NT');
  return h('span', {}, call[0], h('span', { class: `s-${strain}` }, SYM[strain]));
}
function contractEl(text, declarer) {
  if (!text || text === 'Pass') return h('span', {}, 'Passed out');
  const m = text.match(/^([1-7])(NT|N|[SHDC])(X{0,2})$/);
  if (!m) return h('span', {}, text);
  const strain = m[2][0] === 'N' ? h('span', {}, 'NT') : h('span', { class: `s-${m[2]}` }, SYM[m[2]]);
  return h('span', {}, m[1], strain, m[3], declarer ? ` by ${SEAT_NAME[declarer]}` : '');
}
function shortContract(text, declarer, result) {
  if (!text || text === 'Pass') return h('span', {}, 'Pass');
  const m = text.match(/^([1-7])(NT|N|[SHDC])(X{0,2})$/);
  if (!m) return h('span', {}, text);
  const strain = m[2][0] === 'N' ? 'NT' : h('span', { class: `s-${m[2]}` }, SYM[m[2]]);
  return h('span', {}, m[1], strain, m[3], ' ', declarer || '', ' ', result || '');
}
function signed(n) { return n > 0 ? `+${n}` : `${n}`; }
function impsEl(n) {
  if (n === null || n === undefined) return h('span', { class: 'muted' }, '…');
  return h('span', { class: n > 0 ? 'pos' : n < 0 ? 'neg' : '' }, signed(n));
}
function vulText(v) {
  return { None: 'Nobody vulnerable', NS: 'North–South vulnerable', EW: 'East–West vulnerable', Both: 'Both vulnerable' }[v];
}
function isVul(vul, seat) { return vul === 'Both' || (vul === 'NS' && 'NS'.includes(seat)) || (vul === 'EW' && 'EW'.includes(seat)); }
function positions(me) {
  const i = SEATS.indexOf(me);
  return { bottom: SEATS[i], left: SEATS[(i + 1) % 4], top: SEATS[(i + 2) % 4], right: SEATS[(i + 3) % 4] };
}
function posOf(me, seat) {
  const p = positions(me);
  return Object.keys(p).find(k => p[k] === seat);
}
function resultText(contract, tricks) {
  if (!contract) return 'Passed out';
  const over = tricks - Number(contract[0]) - 6;
  return over === 0 ? '=' : signed(over);
}
function trickWinner(cards, strain) {
  const trump = strain === 'N' ? null : strain;
  const led = cards[0][1][0];
  let best = cards[0];
  for (const c of cards.slice(1)) {
    const [bs, br] = [best[1][0], RANKS.indexOf(best[1][1])];
    const [cs, cr] = [c[1][0], RANKS.indexOf(c[1][1])];
    if ((cs === trump && bs !== trump) || (cs === bs && cr > br)) best = c;
    else if (cs === led && bs !== trump && bs !== led) best = c;
  }
  return best[0];
}

/* ---- the duplicate board ----------------------------------------------------------- */
function dupboard({ number, dealer, vul, me, trick, last }) {
  const p = positions(me || 'S');
  const edges = Object.entries(p).map(([pos, seat]) => h('div', {
    class: `edge ${pos}${isVul(vul, seat) ? ' vul' : ''}`,
    title: `${SEAT_NAME[seat]}${isVul(vul, seat) ? ', vulnerable' : ''}${dealer === seat ? ', dealer' : ''}`,
  }, seat, dealer === seat ? h('span', { class: 'dealer', 'aria-label': 'dealer' }, 'D') : null));
  const kids = [h('div', { class: 'number', 'aria-label': `Board ${number}` }, number), ...edges];
  const shown = trick && trick.length ? trick : last ? last.cards : null;
  if (shown) {
    kids.push(h('div', { class: `trick${trick && trick.length ? '' : ' last'}` },
      shown.map(([seat, c]) => h('div', {
        class: `pcard at-${posOf(me || 'S', seat)}${!(trick && trick.length) && last && last.winner === seat ? ' won' : ''}`,
        'aria-label': `${SEAT_NAME[seat]} played ${RANK_NAME[c[1]] || c[1]} of ${SUIT_NAME[c[0]]}`,
      }, h('span', { class: `s-${c[0]}` }, rankText(c[1])), h('span', { class: `suit s-${c[0]}` }, SYM[c[0]])))));
  }
  return h('div', { class: 'dupboard', role: 'img', 'aria-label': `Board ${number}, dealer ${SEAT_NAME[dealer]}, ${vulText(vul)}` }, kids);
}

/* ---- routing ----------------------------------------------------------------------- */
async function refreshMe() {
  app.me = await api('GET', '/api/me');
  const acct = document.getElementById('account');
  acct.replaceChildren(app.me.user
    ? h('span', {}, h('b', {}, app.me.user), ' ', h('button', { class: 'linklike', onclick: logout }, 'Sign out'))
    : h('a', { href: '#/login' }, 'Sign in'));
  const sys = SYSTEMS[app.me.bot.system] || 'It makes no alerts and gives no explanations.';
  document.getElementById('colophon').replaceChildren(h('p', {}, app.me.bot.stand_in
    ? `Sid is a bridge program in development and is not released yet. Until it is, the seats marked Sid are played by ${app.me.bot.label}, the project\u2019s current arena bot. ${sys}`
    : `Sid is a bridge program in development. These tables run ${app.me.bot.label}. ${sys}`));
}

async function logout() {
  await api('POST', '/api/logout');
  await refreshMe();
  location.hash = '#/';
}

function setNav() {
  for (const a of document.querySelectorAll('.masthead nav a')) {
    const target = a.getAttribute('href');
    const here = location.hash || '#/';
    a.toggleAttribute('aria-current', target === here || (target === '#/' && here.startsWith('#/table')));
    if (a.hasAttribute('aria-current')) a.setAttribute('aria-current', 'page');
  }
}

async function route() {
  app.pollToken++;
  setNav();
  const hash = location.hash || '#/';
  const [path, query] = hash.slice(1).split('?');
  const parts = path.split('/').filter(Boolean);
  const params = new URLSearchParams(query || '');
  try {
    if (parts[0] === 'table' && parts[1]) return startTable(parts[1]);
    if (parts[0] === 'history') return renderHistory();
    if (parts[0] === 'board' && parts[1]) return renderReplay(parts[1]);
    if (parts[0] === 'login' || parts[0] === 'signup') return renderAuth(parts[0], params.get('next'));
    if (parts[0] === 'join' && parts[1]) return renderJoin(parts[1]);
    return renderLobby();
  } catch (e) {
    $main.replaceChildren(h('p', { class: 'notice bad' }, e.message));
  }
}

/* ---- lobby ------------------------------------------------------------------------- */
async function newTable(mode) {
  try {
    const r = await api('POST', '/api/tables', { mode });
    await refreshMe();
    location.hash = `#/table/${r.table}`;
  } catch (e) {
    if (e.status === 409 && mode === 'pair' && !app.me.user) location.hash = '#/login?next=pair';
    else toast(e.message);
  }
}

function renderLobby() {
  const open = app.me && app.me.table;
  const actions = open
    ? [h('a', { class: 'btn', href: `#/table/${app.me.table}` }, 'Return to your table'),
       h('button', { class: 'btn secondary', onclick: () => newTable('solo') }, 'Start a new table')]
    : [h('button', { class: 'btn', onclick: () => newTable('solo') }, 'Play now'),
       h('button', { class: 'btn secondary', onclick: () => newTable('pair') }, 'Play with a partner')];
  $main.replaceChildren(
    h('section', { class: 'lobby' },
      dupboard({ number: 1, dealer: 'N', vul: 'None', me: 'S' }),
      h('div', {},
        h('h1', {}, 'Play bridge against Sid'),
        h('p', {}, 'Sid is a bridge program in development. Sit South and Sid takes the other three seats, or bring a partner and the two of you play North–South against two Sids.'),
        app.me && app.me.bot.stand_in ? h('p', { class: 'notice' }, `Sid itself is not released yet. Until it is, its seats are played by ${app.me.bot.label}, the project\u2019s current arena bot.`) : null,
        h('div', { class: 'actions' }, actions),
        app.me && !app.me.user ? h('p', { class: 'muted' }, 'No account needed to play alone. ',
          h('a', { href: '#/signup' }, 'Sign up'), ' to play with a partner and keep your history.') : null)),
    h('section', { class: 'notes' },
      h('div', {}, h('h2', {}, 'How each board is scored'),
        h('p', {}, app.me && app.me.sid_tables
          ? 'After you finish a board, Sid plays the same deal at all four seats. Your score against that table is your IMPs for the board, so a plus means you did better than Sid would have in your chair.'
          : 'Each board shows the contract, the tricks and your score.')),
      h('div', {}, h('h2', {}, 'Declaring and claims'),
        h('p', {}, 'When your side wins the contract, you declare and play dummy too. You can claim any time as declarer; Sid accepts a claim if it holds against any defence.')),
      h('div', {}, h('h2', {}, 'Your history'),
        h('p', {}, 'Every finished board is kept with its auction and play. Boards you play as a guest stay with this browser, and move to your account when you sign up.'))));
}

/* ---- the table --------------------------------------------------------------------- */
async function startTable(id) {
  const token = app.pollToken;
  app.tableId = id;
  app.version = -1;
  $main.replaceChildren(h('p', { class: 'muted' }, 'Opening the table…'));
  while (app.pollToken === token) {
    try {
      const v = await api('GET', `/api/tables/${id}?since=${app.version}`);
      if (app.pollToken !== token) return;
      app.version = v.version;
      app.view = v;
      renderTable(v);
      if (v.status === 'closed') return;
    } catch (e) {
      if (app.pollToken !== token) return;
      if (e.status === 409 || e.status === 404) {
        $main.replaceChildren(h('p', { class: 'notice bad' }, e.message), h('a', { class: 'btn', href: '#/' }, 'Back to the lobby'));
        refreshMe();
        return;
      }
      await sleep(2000);
    }
  }
}

async function act(path, body) {
  try { await api('POST', `/api/tables/${app.tableId}/${path}`, body); } catch (e) { toast(e.message); }
}

function handBox(v, seat, pos) {
  const b = v.board;
  const info = v.seats[SEATS.indexOf(seat)];
  const hand = b.hands[seat];
  const isMe = seat === v.me;
  const turn = b.turn && b.turn.seat === seat;
  const name = isMe ? 'You' : info.kind === 'bot' ? 'Sid' : info.name;
  const role = b.phase !== 'auction' && b.dummy === seat ? 'Dummy' : b.phase !== 'auction' && b.declarer === seat ? 'Declarer' : '';
  const who = h('div', { class: 'who' },
    h('span', {}, h('b', {}, name), ` ${SEAT_NAME[seat]}`),
    h('span', {}, b.thinking === seat ? h('span', { class: 'thinking', 'aria-label': 'thinking' }, h('i'), h('i'), h('i')) : role));
  if (!hand.cards) {
    return h('div', { class: `hand hidden pos-${pos}${turn ? ' turn' : ''}` }, who,
      h('div', { class: 'backs' }, h('span', { class: 'stack', 'aria-hidden': 'true' }), `${hand.count} cards`));
  }
  const canPlay = b.turn && b.turn.mine && b.turn.kind === 'card' && b.turn.seat === seat;
  const legal = new Set(canPlay ? b.legal : []);
  const rows = SUITS.map(s => {
    const cards = hand.cards.filter(c => c[0] === s);
    return h('div', { class: 'row' }, h('span', { class: `sym s-${s}`, 'aria-hidden': 'true' }, SYM[s]),
      cards.length ? cards.map(c => {
        const ok = legal.has(c);
        return h('button', {
          class: `rank s-${s}${ok ? ' playable' : ''}${canPlay && !ok ? ' dim' : ''}`,
          disabled: !ok, 'aria-label': `${RANK_NAME[c[1]] || c[1]} of ${SUIT_NAME[s]}`,
          onclick: ok ? () => act('card', { card: c }) : null,
        }, rankText(c[1]));
      }) : h('span', { class: 'void' }, '—'));
  });
  return h('div', { class: `hand pos-${pos}${turn ? ' turn' : ''}` }, who, rows);
}

function auctionTable(calls, dealer, vul, open) {
  const order = ['W', 'N', 'E', 'S'];
  const cells = Array(order.indexOf(dealer)).fill(null).concat(calls.map(c => callEl(c)));
  if (open) cells.push('now');
  const rows = [];
  for (let i = 0; i < cells.length; i += 4) {
    rows.push(h('tr', {}, order.map((_, j) => {
      const c = cells[i + j];
      return c === 'now' ? h('td', { class: 'now' }, '?') : h('td', {}, c || '');
    })));
  }
  return h('table', { class: 'auction' },
    h('thead', {}, h('tr', {}, order.map(s => h('th', { class: isVul(vul, s) ? 'vul' : null }, SEAT_NAME[s])))),
    h('tbody', {}, rows));
}

function bidBox(legal) {
  const bids = legal.filter(c => /^[1-7]/.test(c));
  const low = bids.length ? Number(bids[0][0]) : 8;
  const set = new Set(legal);
  const grid = [];
  for (let level = low; level <= 7; level++) {
    for (const strain of ['C', 'D', 'H', 'S', 'N']) {
      const call = `${level}${strain}`;
      grid.push(h('button', { disabled: !set.has(call), onclick: () => act('call', { call }),
        'aria-label': `Bid ${level} ${strain === 'N' ? 'no trump' : SUIT_NAME[strain]}` }, callEl(call)));
    }
  }
  return h('div', { class: 'bidbox' }, grid,
    h('div', { class: 'calls' },
      h('button', { class: 'pass', disabled: !set.has('PASS'), onclick: () => act('call', { call: 'PASS' }) }, 'Pass'),
      h('button', { class: 'dbl', disabled: !set.has('X'), onclick: () => act('call', { call: 'X' }) }, 'Dbl'),
      h('button', { class: 'rdbl', disabled: !set.has('XX'), onclick: () => act('call', { call: 'XX' }) }, 'Rdbl')));
}

function claimBar(b) {
  const input = h('input', { type: 'number', min: 0, max: b.remaining, value: b.remaining, 'aria-label': 'Tricks to claim' });
  return h('div', { class: 'claimbar' },
    h('span', {}, 'Claim'), input, h('span', {}, `of the remaining ${b.remaining} tricks`),
    h('button', { class: 'btn secondary', onclick: () => act('claim', { tricks: Number(input.value) }) }, 'Claim'));
}

function resultPanel(v) {
  const b = v.board, r = b.result;
  const score = r.ns_score;
  const lines = [
    h('span', { class: 'muted' }, 'Contract'), contractEl(r.contract, r.declarer),
    h('span', { class: 'muted' }, 'Result'),
    h('span', {}, r.tricks === null ? 'Passed out' : `${r.tricks} trick${r.tricks === 1 ? '' : 's'} (${r.result})${r.claimed !== null && r.claimed !== undefined ? ', claimed' : ''}`),
    h('span', { class: 'muted' }, 'Your score'), h('b', {}, signed(score)),
  ];
  let sid;
  if (b.sid === 'pending') sid = h('p', { class: 'muted' }, 'Sid is playing this deal at all four seats…');
  else if (b.sid === 'error') sid = h('p', { class: 'muted' }, 'Sid’s own table could not be played on this deal.');
  else if (b.sid) {
    sid = h('div', { class: 'lines' },
      h('span', { class: 'muted' }, 'Sid’s table'),
      h('span', {}, contractEl(b.sid.contract, b.sid.declarer),
        b.sid.tricks !== null && b.sid.tricks !== undefined ? `, ${b.sid.tricks} trick${b.sid.tricks === 1 ? '' : 's'} (${b.sid.result})` : '', `: ${signed(b.sid.ns_score)}`),
      h('span', { class: 'muted' }, 'Sid bid'), h('span', {}, b.sid.calls.map((c, i) => [i ? ' ' : '', callEl(c)])));
  }
  return h('div', { class: 'result' },
    h('div', { class: 'lines' }, lines), sid,
    b.imps !== null && b.imps !== undefined ? h('p', {}, h('span', { class: 'muted' }, 'IMPs on this board '), h('span', { class: 'imps' }, impsEl(b.imps))) : null,
    h('div', {},
      h('button', { class: 'btn', onclick: () => act('next') }, 'Next board'),
      b.board_id ? h('a', { class: 'btn secondary', href: `#/board/${b.board_id}` }, 'Review this board') : null));
}

function travellerPanel(v) {
  const rows = v.scores.slice().reverse().map(r => h('tr', {},
    h('td', {}, r.board_id ? h('a', { href: `#/board/${r.board_id}` }, r.number) : r.number),
    h('td', {}, shortContract(r.contract, r.declarer, r.tricks === null ? '' : r.result)),
    h('td', { class: 'num' }, signed(r.ns_score)),
    h('td', {}, r.sid ? shortContract(r.sid.contract, r.sid.declarer, r.sid.result || '') : h('span', { class: 'muted' }, '…')),
    h('td', { class: 'num' }, impsEl(r.imps))));
  return h('div', { class: 'panel' }, h('h2', {}, 'Scores at this table'),
    v.scores.length ? h('table', { class: 'traveller' },
      h('thead', {}, h('tr', {}, h('th', {}, 'Bd'), h('th', {}, 'You'), h('th', { class: 'num' }, 'Score'), h('th', {}, 'Sid'), h('th', { class: 'num' }, 'IMPs'))),
      h('tbody', {}, rows),
      h('tfoot', {}, h('tr', {}, h('td', { colspan: 4 }, `${v.totals.boards} board${v.totals.boards === 1 ? '' : 's'}`),
        h('td', { class: 'num' }, impsEl(v.totals.compared ? v.totals.imps : null)))))
      : h('p', { class: 'muted' }, 'Finished boards appear here.'));
}

function renderTable(v) {
  if (v.status === 'closed') {
    const why = { idle: 'This table closed after a long pause.', expired: 'Nobody joined this table in time.' }[v.closed_reason] || 'This table has closed.';
    $main.replaceChildren(h('p', { class: 'notice' }, why), h('a', { class: 'btn', href: '#/' }, 'Back to the lobby'));
    refreshMe();
    return;
  }
  if (v.status === 'waiting') {
    const link = `${location.origin}/#/join/${v.invite}`;
    const input = h('input', { value: link, readonly: true, 'aria-label': 'Invitation link' });
    $main.replaceChildren(h('h1', {}, 'Waiting for your partner'),
      h('p', {}, 'Send this link to your partner. They sign in (or sign up), open it, and the first board is dealt. You sit South, your partner North.'),
      h('div', { class: 'invite' }, input,
        h('button', { class: 'btn', onclick: async () => {
          try { await navigator.clipboard.writeText(link); toast('Link copied.'); } catch (e) { input.select(); }
        } }, 'Copy link')),
      h('button', { class: 'btn secondary', onclick: leaveTable }, 'Cancel'));
    return;
  }
  const b = v.board;
  if (!b) { $main.replaceChildren(h('p', { class: 'muted' }, 'Dealing…')); return; }
  const p = positions(v.me);
  const center = h('div', { class: 'center' }, dupboard({ number: b.number, dealer: b.dealer, vul: b.vul, me: v.me, trick: b.trick, last: b.last_trick }));
  const felt = h('div', { class: 'felt' },
    ['top', 'left', 'right', 'bottom'].map(pos => handBox(v, p[pos], pos)), center);

  const status = h('div', { class: 'status-line' },
    h('div', {}, h('strong', {}, `Board ${b.number}`), ' ', h('span', { class: 'muted' }, `Dealer ${SEAT_NAME[b.dealer]}. ${vulText(b.vul)}.`)),
    h('div', {}, b.contract ? h('span', {}, contractEl(b.contract, b.declarer)) : null,
      b.tricks ? h('span', { class: 'muted tricks' }, `Declarer ${b.tricks.declarer}, defence ${b.tricks.defence}`) : null));

  const bar = [];
  if (b.error) {
    bar.push(h('p', { class: 'notice bad' }, b.error), h('button', { class: 'btn', onclick: () => act('next') }, 'Next board'));
  } else if (b.phase === 'done') {
    bar.push(resultPanel(v));
  } else if (b.phase === 'auction') {
    if (b.turn && b.turn.mine) bar.push(bidBox(b.legal));
    else if (b.turn) bar.push(h('p', { class: 'muted' }, `${seatLabel(v, b.turn.seat)} to call.`));
  } else {
    if (b.claim && !b.claim.accepted) bar.push(h('p', { class: 'notice' }, `Sid did not accept a claim of ${b.claim.tricks} trick${b.claim.tricks === 1 ? '' : 's'}. Play on.`));
    if (b.turn && b.turn.mine) {
      const fromDummy = b.turn.seat !== v.me;
      bar.push(h('p', {}, fromDummy ? `Play a card from ${SEAT_NAME[b.turn.seat]}${b.turn.seat === b.dummy ? ' (dummy)' : ''}.` : 'Your card.'));
    } else if (b.turn) bar.push(h('p', { class: 'muted' }, `${seatLabel(v, b.turn.seat)} to play.`));
    if (b.can_claim) bar.push(claimBar(b));
  }

  const side = h('aside', {},
    h('div', { class: 'panel' }, h('h2', {}, 'Auction'), auctionTable(b.calls, b.dealer, b.vul, b.phase === 'auction')),
    travellerPanel(v),
    h('p', {}, h('button', { class: 'linklike', onclick: leaveTable }, 'Leave this table')));

  $main.replaceChildren(h('div', { class: 'room' }, h('section', {}, status, felt, h('div', { class: 'actionbar' }, bar)), side));
}

function seatLabel(v, seat) {
  const info = v.seats[SEATS.indexOf(seat)];
  if (seat === v.me) return 'You';
  return `${info.kind === 'bot' ? 'Sid' : info.name} (${SEAT_NAME[seat]})`;
}

async function leaveTable() {
  try { await api('POST', `/api/tables/${app.tableId}/leave`); } catch (e) { /* already closed */ }
  app.pollToken++;
  await refreshMe();
  location.hash = '#/';
}

/* ---- history and replays ----------------------------------------------------------- */
async function renderHistory() {
  const token = app.pollToken;
  const data = await api('GET', '/api/history');
  if (token !== app.pollToken) return;
  const t = data.totals;
  const avg = t.compared ? (t.imps / t.compared).toFixed(2) : null;
  const rows = data.boards.map(r => h('tr', {},
    h('td', {}, new Date(r.finished * 1000).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })),
    h('td', {}, h('a', { href: `#/board/${r.id}` }, r.number)),
    h('td', {}, shortContract(r.contract, r.declarer, r.contract ? resultText(r.contract, r.tricks) : '')),
    h('td', { class: 'num' }, signed(r.ns_score)),
    h('td', {}, r.sid_contract !== undefined && r.imps !== null ? shortContract(r.sid_contract, r.sid_declarer, r.sid_contract ? resultText(r.sid_contract, r.sid_tricks) : '') : h('span', { class: 'muted' }, '—')),
    h('td', { class: 'num' }, r.imps === null ? h('span', { class: 'muted' }, '—') : impsEl(r.imps))));
  $main.replaceChildren(
    h('h1', {}, data.user ? `${data.user}’s boards` : 'Boards from this browser'),
    data.user ? null : h('p', { class: 'muted' }, h('a', { href: '#/signup' }, 'Sign up'), ' to keep these boards in an account and see them on any device.'),
    h('div', { class: 'summary' },
      h('div', {}, h('b', {}, t.boards), 'boards played'),
      h('div', {}, h('b', {}, t.compared ? signed(t.imps) : '—'), 'IMPs against Sid’s table'),
      h('div', {}, h('b', {}, avg !== null ? (avg > 0 ? `+${avg}` : avg) : '—'), 'IMPs a board')),
    data.boards.length ? h('table', { class: 'traveller history-table' },
      h('thead', {}, h('tr', {}, h('th', {}, 'Date'), h('th', {}, 'Bd'), h('th', {}, 'You'), h('th', { class: 'num' }, 'Score'), h('th', {}, 'Sid'), h('th', { class: 'num' }, 'IMPs'))),
      h('tbody', {}, rows))
      : h('p', {}, 'No boards yet. ', h('a', { href: '#/' }, 'Play one'), '.'));
}

function staticHand(cards, label) {
  return h('div', { class: 'hand' }, h('div', { class: 'who' }, h('b', {}, label)),
    SUITS.map(s => {
      const these = cards.filter(c => c[0] === s);
      return h('div', { class: 'row' }, h('span', { class: `sym s-${s}` }, SYM[s]),
        these.length ? these.map(c => h('span', { class: `rank s-${s}` }, rankText(c[1]))) : h('span', { class: 'void' }, '—'));
    }));
}

async function renderReplay(id) {
  const token = app.pollToken;
  const d = await api('GET', `/api/boards/${id}`);
  if (token !== app.pollToken) return;
  const order = (a, b) => SUITS.indexOf(a[0]) - SUITS.indexOf(b[0]) || RANKS.indexOf(b[1]) - RANKS.indexOf(a[1]);
  const names = d.seats.map((s, i) => `${s.kind === 'bot' ? 'Sid' : SEATS[i] === d.my_seat ? 'You' : s.name}, ${SEAT_NAME[SEATS[i]]}`);
  const hands = d.hands.map(hd => hd.slice().sort(order));
  const strain = d.contract ? d.contract.replace(/X/g, '')[1] : null;
  const tricks = [];
  for (let i = 0; i < d.play.length; i += 4) tricks.push(d.play.slice(i, i + 4));
  const cols = ['W', 'N', 'E', 'S'];
  const playRows = tricks.map((t, i) => {
    const win = t.length === 4 ? trickWinner(t, strain) : null;
    return h('tr', {}, h('td', {}, i + 1), cols.map(seat => {
      const c = t.find(x => x[0] === seat);
      return h('td', { class: `${c && t[0][0] === seat ? 'lead' : ''} ${seat === win ? 'won' : ''}` }, c ? cardEl(c[1]) : '');
    }));
  });
  const contractStr = d.contract ? d.contract.replace(/^([1-7])N/, '$1NT') : null;
  const sid = d.sid_table;
  $main.replaceChildren(
    h('p', {}, h('a', { href: '#/history' }, 'All boards')),
    h('h1', {}, `Board ${d.number}`),
    h('p', { class: 'muted' }, `${new Date(d.finished * 1000).toLocaleString()}. Dealer ${SEAT_NAME[d.dealer]}. ${vulText(d.vulnerability)}.`),
    h('div', { class: 'replay-grid' },
      h('div', {},
        h('div', { class: 'diagram' },
          h('div', { class: 'n' }, staticHand(hands[0], names[0])), h('div', { class: 'e' }, staticHand(hands[1], names[1])),
          h('div', { class: 's' }, staticHand(hands[2], names[2])), h('div', { class: 'w' }, staticHand(hands[3], names[3])),
          h('div', { class: 'c' }, dupboard({ number: d.number, dealer: d.dealer, vul: d.vulnerability, me: 'S' })))),
      h('div', {},
        h('div', { class: 'panel' }, h('h2', {}, 'Auction'), auctionTable(d.calls, d.dealer, d.vulnerability, false)),
        h('div', { class: 'panel' }, h('h2', {}, 'Result'),
          h('div', { class: 'result', style: 'margin:0;padding:0' }, h('div', { class: 'lines' },
            h('span', { class: 'muted' }, 'Contract'), contractEl(contractStr, d.declarer),
            h('span', { class: 'muted' }, 'Tricks'), h('span', {}, d.tricks === null ? '—' : `${d.tricks} (${resultText(d.contract, d.tricks)})${d.claimed !== null ? ', claimed' : ''}`),
            h('span', { class: 'muted' }, 'Your score'), h('b', {}, signed(d.ns_score)),
            sid ? [h('span', { class: 'muted' }, 'Sid’s table'),
              h('span', {}, contractEl(sid.contract ? sid.contract.replace(/^([1-7])N/, '$1NT') : null, sid.declarer),
                sid.tricks !== null ? `, ${sid.tricks} tricks` : '', `: ${signed(sid.ns_score)}`),
              h('span', { class: 'muted' }, 'Sid bid'), h('span', {}, sid.calls.map((c, i) => [i ? ' ' : '', callEl(c)])),
              h('span', { class: 'muted' }, 'IMPs'), h('b', {}, impsEl(d.imps))] : null))))),
    d.play.length ? h('div', { class: 'panel' }, h('h2', {}, 'Play'),
      h('table', { class: 'traveller plays' },
        h('thead', {}, h('tr', {}, h('th', {}, 'Trick'), cols.map(s => h('th', {}, SEAT_NAME[s])))),
        h('tbody', {}, playRows)),
      h('p', { class: 'muted', style: 'margin-top:.5rem' }, 'Underlined: the lead. Highlighted: the card that won the trick.')) : null);
}

/* ---- accounts and invitations ------------------------------------------------------ */
function renderAuth(mode, next) {
  const signup = mode === 'signup';
  const user = h('input', { name: 'username', autocomplete: 'username', required: true, minlength: 3, maxlength: 20 });
  const pass = h('input', { name: 'password', type: 'password', autocomplete: signup ? 'new-password' : 'current-password', required: true, minlength: signup ? 8 : 1 });
  const form = h('form', { class: 'form', onsubmit: async e => {
    e.preventDefault();
    try {
      await api('POST', `/api/${mode}`, { username: user.value, password: pass.value });
      await refreshMe();
      if (next === 'pair') return newTable('pair');
      if (next && next.startsWith('join-')) { location.hash = `#/join/${next.slice(5)}`; return; }
      location.hash = '#/';
    } catch (err) { toast(err.message); }
  } },
  h('h1', {}, signup ? 'Create an account' : 'Sign in'),
  h('p', { class: 'muted' }, signup ? 'An account keeps your boards and lets you bring a partner. No email needed.' : 'Welcome back.'),
  h('label', { for: 'u' }, 'Username'), Object.assign(user, { id: 'u' }),
  signup ? h('div', { class: 'hint' }, '3 to 20 letters, digits, - or _.') : null,
  h('label', { for: 'p' }, 'Password'), Object.assign(pass, { id: 'p' }),
  signup ? h('div', { class: 'hint' }, 'At least 8 characters. There is no password reset, so keep it somewhere safe.') : null,
  h('button', { class: 'btn', type: 'submit' }, signup ? 'Create account' : 'Sign in'),
  h('p', { style: 'margin-top:1rem' }, signup ? 'Have an account? ' : 'New here? ',
    h('a', { href: `#/${signup ? 'login' : 'signup'}${next ? `?next=${encodeURIComponent(next)}` : ''}` }, signup ? 'Sign in' : 'Create an account')));
  $main.replaceChildren(form);
  user.focus();
}

async function renderJoin(code) {
  if (!app.me.user) {
    $main.replaceChildren(h('h1', {}, 'Join your partner'),
      h('p', {}, 'Sign in or create a free account to take the North seat.'),
      h('a', { class: 'btn', href: `#/login?next=join-${encodeURIComponent(code)}` }, 'Sign in'),
      h('a', { class: 'btn secondary', href: `#/signup?next=join-${encodeURIComponent(code)}` }, 'Create an account'));
    return;
  }
  try {
    const r = await api('POST', '/api/join', { code });
    await refreshMe();
    location.hash = `#/table/${r.table}`;
  } catch (e) {
    $main.replaceChildren(h('p', { class: 'notice bad' }, e.message), h('a', { class: 'btn', href: '#/' }, 'Back to the lobby'));
  }
}

window.addEventListener('hashchange', route);
(async () => {
  try { await refreshMe(); } catch (e) { toast('Sid’s server is not answering. Try again shortly.'); }
  route();
})();
