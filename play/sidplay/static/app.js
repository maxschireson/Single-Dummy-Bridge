'use strict';
/* Sid: play bridge with and against the bot. One page, hash routes, the table long-polled from /api/tables/<id>.
   After each board: the analysis of your play and of Sid's in your seat, history with older/newer navigation, and
   playing any deal again. */

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
/* Replace the page content; null, undefined and false children are skipped (replaceChildren would print them). */
function put(...kids) { $main.replaceChildren(...kids.flat(Infinity).filter(k => k !== null && k !== undefined && k !== false)); }

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
    return renderLobby();
  } catch (e) {
    put(h('p', { class: 'notice bad' }, e.message));
  }
}

/* ---- lobby ------------------------------------------------------------------------- */
async function newTable(replay) {
  try {
    const r = await api('POST', '/api/tables', replay ? { replay } : {});
    await refreshMe();
    location.hash = `#/table/${r.table}`;
  } catch (e) { toast(e.message); }
}

function renderLobby() {
  const open = app.me && app.me.table;
  const actions = open
    ? [h('a', { class: 'btn', href: `#/table/${app.me.table}` }, 'Return to your table'),
       h('button', { class: 'btn secondary', onclick: () => newTable() }, 'Start a new table')]
    : [h('button', { class: 'btn', onclick: () => newTable() }, 'Play now')];
  put(
    h('section', { class: 'lobby' },
      dupboard({ number: 1, dealer: 'N', vul: 'None', me: 'S' }),
      h('div', {},
        h('h1', {}, 'Play bridge with Sid'),
        h('p', {}, 'Sid is a bridge program in development. You sit South with Sid as your partner, against two more Sids. No account needed.'),
        app.me && app.me.bot.stand_in ? h('p', { class: 'notice' }, `Sid itself is not released yet. Until it is, its seats are played by ${app.me.bot.label}, the project’s current arena bot.`) : null,
        h('div', { class: 'actions' }, actions),
        app.me && !app.me.user ? h('p', { class: 'muted' }, 'Your boards stay with this browser. ',
          h('a', { href: '#/signup' }, 'Sign up'), ' for a username and password, and review them from anywhere.') : null)),
    h('section', { class: 'notes' },
      h('div', {}, h('h2', {}, 'After each board'),
        h('p', {}, 'See where tricks were lost and why: double dummy card by card, and the sure-trick test, which shows when you had a line that guaranteed the contract against any layout, and which card gave it away.')),
      h('div', {}, h('h2', {}, 'Sid in your seat'),
        h('p', {}, app.me && app.me.sid_tables
          ? 'Sid also plays each deal at all four seats. You see its auction, its play and its analysis, and your IMPs against it.'
          : 'Each board shows the contract, the tricks and your score.')),
      h('div', {}, h('h2', {}, 'Your history'),
        h('p', {}, 'Step back through every deal you have played, and play any of them again. Deals played again are marked and kept out of your IMP totals.'))));
}

/* ---- the table --------------------------------------------------------------------- */
async function startTable(id) {
  const token = app.pollToken;
  app.tableId = id;
  app.version = -1;
  put(h('p', { class: 'muted' }, 'Opening the table…'));
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
        put(h('p', { class: 'notice bad' }, e.message), h('a', { class: 'btn', href: '#/' }, 'Back to the lobby'));
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

function briefEl(label, a) {
  if (!a || !a.status) return null;
  if (a.status === 'pending') return h('p', { class: 'muted' }, `${label}: analysing…`);
  if (a.status === 'error' || !a.brief) return h('p', { class: 'muted' }, `${label}: the analysis did not finish.`);
  const b = a.brief;
  const own = label === 'Your play' ? 'you' : 'Sid';
  const head = b.side_end !== null && b.side_end !== undefined
    ? `double dummy your side could take ${b.side_start} from the opening lead and took ${b.side_end}; ${own} lost ${b.lost}.`
    : `${own} lost ${b.lost} trick${b.lost === 1 ? '' : 's'} double dummy in the cards played.`;
  return h('div', { class: 'brief' }, h('p', {}, h('b', {}, `${label}: `), head),
    b.events.length ? h('ul', {}, b.events.map(t => h('li', {}, t))) : null);
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
      h('span', { class: 'muted' }, 'Sid in your seat'),
      h('span', {}, contractEl(b.sid.contract, b.sid.declarer),
        b.sid.tricks !== null && b.sid.tricks !== undefined ? `, ${b.sid.tricks} trick${b.sid.tricks === 1 ? '' : 's'} (${b.sid.result})` : '', `: ${signed(b.sid.ns_score)}`),
      h('span', { class: 'muted' }, 'Sid bid'), h('span', {}, b.sid.calls.map((c, i) => [i ? ' ' : '', callEl(c)])));
  }
  return h('div', { class: 'result' },
    b.replay ? h('p', { class: 'tag' }, 'Played again: not counted in your totals') : null,
    h('div', { class: 'lines' }, lines), sid,
    b.imps !== null && b.imps !== undefined ? h('p', {}, h('span', { class: 'muted' }, 'IMPs on this board '), h('span', { class: 'imps' }, impsEl(b.imps))) : null,
    briefEl('Your play', b.analysis), briefEl('Sid in your seat', b.sid_analysis),
    h('div', { class: 'buttons' },
      h('button', { class: 'btn', onclick: () => act('next') }, 'Next board'),
      b.board_id ? h('a', { class: 'btn secondary', href: `#/board/${b.board_id}` }, 'Review and analysis') : null,
      b.board_id ? h('button', { class: 'btn secondary', onclick: () => newTable(b.board_id) }, 'Play it again') : null));
}

function travellerPanel(v) {
  const rows = v.scores.slice().reverse().map(r => h('tr', {},
    h('td', {}, r.board_id ? h('a', { href: `#/board/${r.board_id}` }, r.number) : r.number, r.replay ? h('span', { class: 'again', title: 'Played again' }, ' ↻') : null),
    h('td', {}, shortContract(r.contract, r.declarer, r.tricks === null ? '' : r.result)),
    h('td', { class: 'num' }, signed(r.ns_score)),
    h('td', {}, r.sid ? shortContract(r.sid.contract, r.sid.declarer, r.sid.result || '') : h('span', { class: 'muted' }, '…')),
    h('td', { class: 'num' }, impsEl(r.imps))));
  return h('div', { class: 'panel' }, h('h2', {}, 'Scores at this table'),
    v.scores.length ? h('table', { class: 'traveller' },
      h('thead', {}, h('tr', {}, h('th', {}, 'Bd'), h('th', {}, 'You'), h('th', { class: 'num' }, 'Score'), h('th', {}, 'Sid'), h('th', { class: 'num' }, 'IMPs'))),
      h('tbody', {}, rows),
      h('tfoot', {}, h('tr', {}, h('td', { colspan: 4 }, `${v.totals.boards} board${v.totals.boards === 1 ? '' : 's'}`,
          v.totals.replays ? ` (+${v.totals.replays} played again)` : ''),
        h('td', { class: 'num' }, impsEl(v.totals.compared ? v.totals.imps : null)))))
      : h('p', { class: 'muted' }, 'Finished boards appear here.'));
}

function renderTable(v) {
  if (v.status === 'closed') {
    const why = { idle: 'This table closed after a long pause.' }[v.closed_reason] || 'This table has closed.';
    put(h('p', { class: 'notice' }, why), h('a', { class: 'btn', href: '#/' }, 'Back to the lobby'));
    refreshMe();
    return;
  }
  const b = v.board;
  if (!b) { put(h('p', { class: 'muted' }, 'Dealing…')); return; }
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

  put(h('div', { class: 'room' }, h('section', {}, status, felt, h('div', { class: 'actionbar' }, bar)), side));
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

/* ---- history ------------------------------------------------------------------------ */
async function renderHistory() {
  const token = app.pollToken;
  const data = await api('GET', '/api/history');
  if (token !== app.pollToken) return;
  const t = data.totals;
  const avg = t.compared ? (t.imps / t.compared).toFixed(2) : null;
  const rows = data.boards.map(r => h('tr', {},
    h('td', {}, new Date(r.finished * 1000).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })),
    h('td', {}, h('a', { href: `#/board/${r.id}` }, r.number), r.replay_of ? h('span', { class: 'again', title: 'Played again' }, ' ↻') : null),
    h('td', {}, shortContract(r.contract, r.declarer, r.contract ? resultText(r.contract, r.tricks) : '')),
    h('td', { class: 'num' }, signed(r.ns_score)),
    h('td', {}, r.sid_contract !== undefined && r.imps !== null ? shortContract(r.sid_contract, r.sid_declarer, r.sid_contract ? resultText(r.sid_contract, r.sid_tricks) : '') : h('span', { class: 'muted' }, '—')),
    h('td', { class: 'num' }, r.imps === null ? h('span', { class: 'muted' }, '—') : impsEl(r.imps)),
    h('td', { class: 'num' }, r.lost === null || r.lost === undefined ? h('span', { class: 'muted' }, '—') : r.lost)));
  put(
    h('h1', {}, data.user ? `${data.user}’s boards` : 'Boards from this browser'),
    data.user ? null : h('p', { class: 'muted' }, h('a', { href: '#/signup' }, 'Sign up'), ' for a username and password, so these boards are yours on any device.'),
    h('div', { class: 'summary' },
      h('div', {}, h('b', {}, t.boards), 'boards played'),
      h('div', {}, h('b', {}, t.compared ? signed(t.imps) : '—'), 'IMPs against Sid in your seat'),
      h('div', {}, h('b', {}, avg !== null ? (avg > 0 ? `+${avg}` : avg) : '—'), 'IMPs a board')),
    t.replays ? h('p', { class: 'muted' }, `${t.replays} deal${t.replays === 1 ? '' : 's'} played again (↻) not counted above.`) : null,
    data.boards.length ? h('table', { class: 'traveller history-table' },
      h('thead', {}, h('tr', {}, h('th', {}, 'Date'), h('th', {}, 'Bd'), h('th', {}, 'You'), h('th', { class: 'num' }, 'Score'),
        h('th', {}, 'Sid'), h('th', { class: 'num' }, 'IMPs'), h('th', { class: 'num', title: 'Tricks you lost, double dummy' }, 'Lost'))),
      h('tbody', {}, rows))
      : h('p', {}, 'No boards yet. ', h('a', { href: '#/' }, 'Play one'), '.'));
}

/* ---- one board: review and analysis ------------------------------------------------- */
function staticHand(cards, label, marks) {
  return h('div', { class: 'hand' }, h('div', { class: 'who' }, h('b', {}, label)),
    SUITS.map(s => {
      const these = cards.filter(c => c[0] === s);
      return h('div', { class: 'row' }, h('span', { class: `sym s-${s}` }, SYM[s]),
        these.length ? these.map(c => h('span', { class: `rank s-${s}` }, rankText(c[1]))) : h('span', { class: 'void' }, '—'));
    }));
}

function cardText(code) { return h('span', { class: `s-${code[0]}` }, SYM[code[0]], rankText(code[1])); }
function betterEl(cards) {
  const shown = cards.slice(0, 6);
  return [shown.map((c, i) => [i ? ', ' : '', cardText(c)]), cards.length > 6 ? ` and ${cards.length - 6} more` : ''];
}

function playTable(play, contract, analysis) {
  const strain = contract ? contract.replace(/X/g, '')[1] : null;
  const marks = {};
  if (analysis) for (const r of analysis.cards) if (r.loss) marks[r.n] = r.focus ? 'lost' : 'gave';
  if (analysis) for (const e of analysis.events) if (['gave_away', 'handed_contract', 'sure_trick', 'handed_trick'].includes(e.kind)) marks[e.n] = (marks[e.n] ? marks[e.n] + ' ' : '') + 'sure';
  const tricks = [];
  for (let i = 0; i < play.length; i += 4) tricks.push(play.slice(i, i + 4).map((x, k) => [x[0], x[1], i + k + 1]));
  const cols = ['W', 'N', 'E', 'S'];
  return h('table', { class: 'traveller plays' },
    h('thead', {}, h('tr', {}, h('th', {}, 'Trick'), cols.map(s => h('th', {}, SEAT_NAME[s])))),
    h('tbody', {}, tricks.map((t, i) => {
      const win = t.length === 4 ? trickWinner(t, strain) : null;
      return h('tr', {}, h('td', {}, i + 1), cols.map(seat => {
        const c = t.find(x => x[0] === seat);
        const cls = [c && t[0][0] === seat ? 'lead' : '', seat === win ? 'won' : '', c && marks[c[2]] ? marks[c[2]] : ''].join(' ');
        return h('td', { class: cls }, c ? cardEl(c[1]) : '');
      }));
    })));
}

function chartEl(a) {
  /* Tricks for the analysed side, card by card: double-dummy (step line), guaranteed by the sure-trick search
     (declaring side, exact values only), the contract's line, and the cards that changed the double-dummy count. */
  const cards = a.cards;
  if (!cards.length) return null;
  const decl = a.focus_declares;
  const side = v => decl ? v : 13 - v;
  const dd = cards.map(r => side(r.dd));
  const declSide = SEATS.indexOf(a.declarer) % 2;
  const byDecl = r => SEATS.indexOf(r.seat) % 2 === declSide;
  const last = cards[cards.length - 1];
  const after = side(a.tricks !== null && a.tricks !== undefined ? a.tricks : (byDecl(last) ? last.dd - last.loss : last.dd + last.loss));
  const target = decl ? a.need : 14 - a.need;
  const sure = cards.map(r => (decl && r.sure && r.sure.mode === 'tricks' && !r.sure.unknown) ? r.sure.guaranteed : null);
  const vals = dd.concat([after, target], sure.filter(x => x !== null));
  const lo = Math.max(0, Math.min(...vals) - 1), hi = Math.min(13, Math.max(...vals) + 1);
  const W = Math.max(330, Math.min(640, (window.innerWidth || 640) - 60)), H = W < 500 ? 190 : 210, L = 30, R = 10, T = 12, B = 28;
  const n = cards.length;
  const x = i => L + (W - L - R) * i / n;
  const y = v => T + (H - T - B) * (hi - v) / Math.max(1, hi - lo);
  const NS = 'http://www.w3.org/2000/svg';
  const el = (tag, attrs, text) => { const e = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v); if (text !== undefined) e.textContent = text; return e; };
  const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, class: 'chart', role: 'img',
    'aria-label': `${decl ? 'Declaring' : 'Defending'} side tricks card by card: double dummy ${dd[0]} at the opening lead, ${after} at the end; ${decl ? 'needed' : 'needed to beat it'} ${target}.` });
  for (let v = lo; v <= hi; v++) {
    svg.append(el('line', { x1: L, x2: W - R, y1: y(v), y2: y(v), class: 'grid' }));
    svg.append(el('text', { x: L - 8, y: y(v) + 4, class: 'tick', 'text-anchor': 'end' }, v));
  }
  for (let t = 0; t < 13 && 4 * t < n; t += 2) svg.append(el('text', { x: x(4 * t) + 2, y: H - B + 16, class: 'tick' }, `T${t + 1}`));
  svg.append(el('line', { x1: L, x2: W - R, y1: y(target), y2: y(target), class: 'target' }));
  svg.append(el('text', { x: W - R, y: y(target) - 5, class: 'tick strong', 'text-anchor': 'end' }, decl ? `${target} to make` : `${target} to beat it`));
  // double dummy: value before card i holds over [i, i+1)
  let d = `M${x(0)},${y(dd[0])}`;
  for (let i = 1; i < n; i++) d += `H${x(i)}V${y(dd[i])}`;
  d += `H${x(n)}V${y(after)}`;
  svg.append(el('path', { d, class: 'dd' }));
  // guaranteed: points at analysed decisions, joined where consecutive decisions were analysed
  let g = '', open = false;
  sure.forEach((v, i) => { if (v === null) { open = false; return; } g += `${open ? 'L' : 'M'}${x(i + 0.5)},${y(v)}`; open = true; });
  if (g) svg.append(el('path', { d: g, class: 'sure' }));
  sure.forEach((v, i) => { if (v !== null) svg.append(el('circle', { cx: x(i + 0.5), cy: y(v), r: 4, class: 'sure-dot' })); });
  // cards that changed the double-dummy count
  cards.forEach((r, i) => {
    if (!r.loss) return;
    const own = r.focus, partner = !own && byDecl(r) === decl;
    const cx = x(i + 0.5), cy = y(i + 1 < n ? dd[i + 1] : after);
    const up = !own && !partner;
    svg.append(el('path', { d: up ? `M${cx},${cy - 6}l5,9h-10z` : `M${cx},${cy + 6}l5,-9h-10z`, class: own ? 'mark-lost' : partner ? 'mark-partner' : 'mark-gift' }));
  });
  // hover: crosshair and one readout
  const cross = el('line', { y1: T, y2: H - B, class: 'cross', visibility: 'hidden' });
  svg.append(cross);
  const hit = el('rect', { x: L, y: T, width: W - L - R, height: H - T - B, fill: 'transparent' });
  svg.append(hit);
  const tip = h('div', { class: 'tip', hidden: true });
  const wrap = h('div', { class: 'chartwrap' }, svg, tip);
  const show = evt => {
    const box = svg.getBoundingClientRect();
    const px = (evt.clientX - box.left) * W / box.width;
    const i = Math.max(0, Math.min(n - 1, Math.floor((px - L) / (W - L - R) * n)));
    const r = cards[i];
    cross.setAttribute('x1', x(i + 0.5)); cross.setAttribute('x2', x(i + 0.5)); cross.setAttribute('visibility', 'visible');
    tip.replaceChildren(
      h('div', {}, h('b', {}, `Trick ${r.trick}`), ` ${SEAT_NAME[r.seat]} `, cardText(r.card)),
      h('div', {}, h('b', {}, dd[i]), ' double dummy before it', r.loss ? h('span', {}, ', ', h('b', {}, `${r.loss}`), ` lost by ${r.focus ? (a.who || 'you') : SEAT_NAME[r.by]}`) : null),
      sure[i] !== null ? h('div', {}, h('b', {}, sure[i]), ' guaranteed before it') : null);
    tip.hidden = false;
    const left = (x(i + 0.5) / W) * box.width;
    tip.style.left = `${Math.min(box.width - 190, Math.max(0, left + 10))}px`;
  };
  hit.addEventListener('pointermove', show);
  hit.addEventListener('pointerleave', () => { tip.hidden = true; cross.setAttribute('visibility', 'hidden'); });
  const legend = h('div', { class: 'legend' },
    h('span', {}, h('i', { class: 'key dd' }), 'Double-dummy tricks'),
    decl && sure.some(v => v !== null) ? h('span', {}, h('i', { class: 'key sure' }), `Guaranteed (from ${a.engines.sure_cards} cards left)`) : null,
    h('span', {}, h('i', { class: 'key tri lost' }), `Lost by ${a.who || 'you'}`),
    decl ? null : h('span', {}, h('i', { class: 'key tri partner' }), 'Lost by partner'),
    h('span', {}, h('i', { class: 'key tri gift' }), decl ? 'Given back by the defence' : 'Given back by declarer'));
  return h('div', {}, legend, wrap);
}

function analysisEl(a, status, who) {
  const label = who === 'you' ? 'You' : 'Sid';
  if (status === 'pending') return h('p', { class: 'muted' }, 'Analysing this play… (usually under a minute)');
  if (status === 'error') return h('p', { class: 'muted' }, 'The analysis did not finish. Reload the page in a few minutes to try again.');
  if (!a) return h('p', { class: 'muted' }, 'Nothing to analyse (passed out).');
  a.who = who === 'you' ? 'you' : 'Sid';
  const sm = a.summary || {};
  const decl = a.focus_declares;
  const others = decl ? 'the defence' : 'declarer';
  const parts = [];
  if (sm.side_end !== null && sm.side_end !== undefined) parts.push(`Double dummy, ${decl ? 'your side as declarer' : 'your side on defence'} could take ${sm.side_start} trick${sm.side_start === 1 ? '' : 's'} from the opening lead and took ${sm.side_end}.`);
  else parts.push('The board ended on a claim; this covers the cards played.');
  const counts = [`${label} lost ${sm.lost}`];
  if (!decl) counts.push(`partner lost ${sm.partner_lost}`);
  counts.push(`${others} gave back ${sm.gifts}`);
  parts.push(counts.join(', ') + '.');
  const eng = a.engines || {};
  const lost = a.lost || [], given = a.given || [], events = a.events || [];
  return h('div', { class: 'analysis' },
    h('p', {}, parts.join(' ')),
    chartEl(a),
    h('h3', {}, 'Guarantees'),
    events.length ? h('ul', { class: 'events' }, events.map(e => h('li', { class: `ev ev-${e.kind}` }, e.text)))
      : h('p', { class: 'muted' }, decl ? 'No line guaranteed the contract at any analysed point, and no sure trick was let go.' : 'No card handed declarer anything sure that another card would have withheld.'),
    h('h3', {}, `Where ${who === 'you' ? 'you' : 'Sid'} lost tricks`),
    lost.length ? h('ol', { class: 'lost' }, lost.map(e => h('li', {},
      h('div', {}, h('b', {}, `Trick ${e.trick}: `), cardText(e.card), ` cost ${e.loss} trick${e.loss === 1 ? '' : 's'}`, h('span', { class: 'muted' }, ` (double dummy ${e.dd_before} → ${e.dd_after} for declarer). Better: `), betterEl(e.better)),
      h('div', { class: 'why' }, e.text)))) : h('p', { class: 'muted' }, 'None, double dummy.'),
    given.length ? h('details', {}, h('summary', {}, `Tricks lost by the other seats (${given.reduce((t, e) => t + e.loss, 0)})`),
      h('ul', {}, given.map(e => h('li', {}, `Trick ${e.trick}: ${e.by} `, cardText(e.card), ` cost ${e.loss}. Better: `, betterEl(e.better))))) : null,
    h('p', { class: 'muted small' },
      `Double dummy: every card, all hands known. Guarantees: the sure-trick search from the declaring side’s view (hand sizes and show-outs; the auction is not used), exact from ${eng.sure_cards} cards left, the contract question only above that; ${eng.sure_decisions} decisions analysed${eng.sure_unknown ? `, ${eng.sure_unknown} not finished in time` : ''}${eng.sure_skipped && eng.sure_skipped.budget ? `, ${eng.sure_skipped.budget} skipped for time` : ''}. “It turned on”: exchanges of one unseen card between the hidden hands, consistent with the play, that make the card right.`));
}

function tableSide(title, calls, dealer, vul, contract, declarer, tricks, score) {
  return h('div', { class: 'panel' }, h('h2', {}, title),
    h('div', { class: 'result', style: 'margin:0;padding:0' }, h('div', { class: 'lines' },
      h('span', { class: 'muted' }, 'Contract'), contractEl(contract ? contract.replace(/^([1-7])N/, '$1NT') : null, declarer),
      h('span', { class: 'muted' }, 'Tricks'), h('span', {}, tricks === null || tricks === undefined ? '—' : `${tricks} (${resultText(contract, tricks)})`),
      h('span', { class: 'muted' }, 'Score'), h('b', {}, signed(score)))),
    auctionTable(calls, dealer, vul, false));
}

async function renderReplay(id, shown) {
  const token = app.pollToken;
  const d = await api('GET', `/api/boards/${id}`);
  if (token !== app.pollToken) return;
  const key = `${d.analysis_status}/${d.sid_analysis_status}`;
  if (shown === key) {                     // a poll with nothing new: leave the page (and what is open) alone
    await sleep(3000);
    if (token === app.pollToken) renderReplay(id, key);
    return;
  }
  if (shown === undefined) app.sidOpen = false;
  const order = (a, b) => SUITS.indexOf(a[0]) - SUITS.indexOf(b[0]) || RANKS.indexOf(b[1]) - RANKS.indexOf(a[1]);
  const names = d.seats.map((s, i) => `${s.kind === 'bot' ? 'Sid' : SEATS[i] === d.my_seat ? 'You' : s.name}, ${SEAT_NAME[SEATS[i]]}`);
  const hands = d.hands.map(hd => hd.slice().sort(order));
  const sid = d.sid_table;
  const nav = h('div', { class: 'boardnav' },
    d.older ? h('a', { class: 'btn secondary', href: `#/board/${d.older}` }, '← Older') : h('span', { class: 'btn secondary disabled', 'aria-disabled': 'true' }, '← Older'),
    h('a', { href: '#/history' }, 'All boards'),
    d.newer ? h('a', { class: 'btn secondary', href: `#/board/${d.newer}` }, 'Newer →') : h('span', { class: 'btn secondary disabled', 'aria-disabled': 'true' }, 'Newer →'),
    h('button', { class: 'btn', onclick: () => newTable(d.id) }, 'Play this deal again'));
  const yours = h('details', { class: 'panel', open: true }, h('summary', {}, h('h2', {}, 'Your play')),
    analysisEl(d.analysis, d.analysis_status, 'you'),
    d.play.length ? h('div', {}, h('h3', {}, 'The play'), playTable(d.play, d.contract, d.analysis),
      h('p', { class: 'muted small' }, 'Underlined: the lead. Shaded: the card that won the trick. Red: a card that cost your side a trick double dummy; green: one that cost the other side; orange outline: a guarantee given away.')) : null);
  const sids = sid ? h('details', { class: 'panel', open: app.sidOpen, ontoggle: e => { app.sidOpen = e.target.open; } }, h('summary', {}, h('h2', {}, 'Sid in your seat')),
    analysisEl(d.sid_analysis, d.sid_analysis_status, 'sid'),
    sid.play && sid.play.length ? h('div', {}, h('h3', {}, 'Sid’s play'), playTable(sid.play, sid.contract, d.sid_analysis)) : null) : null;
  put(
    nav,
    h('h1', {}, `Board ${d.number}`, d.replay_of ? h('span', { class: 'tag' }, ' played again') : null),
    h('p', { class: 'muted' }, `${new Date(d.finished * 1000).toLocaleString()}. Dealer ${SEAT_NAME[d.dealer]}. ${vulText(d.vulnerability)}.`),
    h('div', { class: 'replay-grid' },
      h('div', {},
        h('div', { class: 'diagram' },
          h('div', { class: 'n' }, staticHand(hands[0], names[0])), h('div', { class: 'e' }, staticHand(hands[1], names[1])),
          h('div', { class: 's' }, staticHand(hands[2], names[2])), h('div', { class: 'w' }, staticHand(hands[3], names[3])),
          h('div', { class: 'c' }, dupboard({ number: d.number, dealer: d.dealer, vul: d.vulnerability, me: 'S' })))),
      h('div', {},
        tableSide('Your table', d.calls, d.dealer, d.vulnerability, d.contract, d.declarer, d.tricks, d.ns_score),
        sid ? tableSide('Sid in your seat', sid.calls, d.dealer, d.vulnerability, sid.contract, sid.declarer, sid.tricks, sid.ns_score)
          : h('p', { class: 'muted' }, 'Sid’s own table was not played on this deal.'),
        d.imps !== null && d.imps !== undefined ? h('p', {}, h('span', { class: 'muted' }, 'IMPs against Sid in your seat '), h('span', { class: 'imps' }, impsEl(d.imps)),
          d.replay_of ? h('span', { class: 'muted' }, ' (played again: not counted)') : null) : null)),
    yours, sids);
  if (d.analysis_status === 'pending' || d.sid_analysis_status === 'pending') {
    await sleep(3000);
    if (token === app.pollToken) renderReplay(id, key);
  }
}

/* ---- accounts --------------------------------------------------------------------- */
async function renderAuth(mode, next) {
  const signup = mode === 'signup';
  const user = h('input', { name: 'username', autocomplete: 'username', required: true, minlength: 3, maxlength: 20, id: 'u' });
  const pass = h('input', { name: 'password', type: signup ? 'text' : 'password', autocomplete: signup ? 'new-password' : 'current-password', required: true, minlength: signup ? 8 : 1, id: 'p', spellcheck: 'false' });
  const form = h('form', { class: 'form', onsubmit: async e => {
    e.preventDefault();
    try {
      await api('POST', `/api/${mode}`, { username: user.value, password: pass.value });
      await refreshMe();
      location.hash = next === 'history' ? '#/history' : '#/';
    } catch (err) { toast(err.message); }
  } },
  h('h1', {}, signup ? 'Sign up' : 'Sign in'),
  h('p', { class: 'muted' }, signup ? 'Here is a username and password for you. Change either if you like, and keep them somewhere safe: there is no email and no password reset. Boards you played in this browser move into the account.' : 'Welcome back.'),
  h('label', { for: 'u' }, 'Username'), user,
  signup ? h('div', { class: 'hint' }, '3 to 20 letters, digits, - or _.') : null,
  h('label', { for: 'p' }, 'Password'), pass,
  signup ? h('div', { class: 'hint' }, 'At least 8 characters.', ' ', h('button', { type: 'button', class: 'linklike', onclick: async () => {
    try { await navigator.clipboard.writeText(`${user.value} ${pass.value}`); toast('Username and password copied.'); } catch (e) { pass.select(); }
  } }, 'Copy both')) : null,
  h('button', { class: 'btn', type: 'submit' }, signup ? 'Create account' : 'Sign in'),
  h('p', { style: 'margin-top:1rem' }, signup ? 'Have an account? ' : 'New here? ',
    h('a', { href: `#/${signup ? 'login' : 'signup'}${next ? `?next=${encodeURIComponent(next)}` : ''}` }, signup ? 'Sign in' : 'Sign up')));
  put(form);
  if (signup) {
    try {
      const sug = await api('GET', '/api/signup/suggest');
      if (!user.value) user.value = sug.username;
      if (!pass.value) pass.value = sug.password;
    } catch (e) { /* the person types their own */ }
  }
  user.focus();
}

window.addEventListener('hashchange', route);
(async () => {
  try { await refreshMe(); } catch (e) { toast('Sid’s server is not answering. Try again shortly.'); }
  route();
})();
