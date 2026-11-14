// Vendored for the play server from experiments/sure_tricks/cells/cells.cpp at commit baa062c
// (branch research/conditional-claims-20261113), unchanged below this header.
// Build: g++ -O2 -std=c++17 -o cells cells.cpp   (install.sh does this)
// The cell game: what North-South can guarantee with ONE line of play against every layout in a set of cells.
//
// A cell fixes, for the two hidden hands, East's number of unnamed cards in each suit and which defender holds each
// named card. Unnamed cards are pooled: who holds one is settled only when it is played. The knowledge at any point of
// the search is the set of cells still consistent with the cards the defenders have played ("live" cells).
//   - every shape consistent with hand sizes and show-outs, no named cards  = the game sure.cpp searches
//   - one shape, no named cards                                             = a whole-shape guarantee
//   - cells with named cards                                                = honour-contingent guarantees
// A defender may play a card when some live cell lets him hold it and makes the play legal; the live set shrinks to
// those cells. Declarer sees his two hands and the cards played, so this is a game of perfect information, and
// "North-South take `need` more tricks" is plain minimax: yes means one line wins in every cell of the set.
//
// Search: yes/no on a trick target, transposition table at trick boundaries keyed on rank-relative cards (named cards
// marked), the residual knowledge (an order-free 128-bit hash of the live cells' residual lengths and pins), leader
// and trump. Lower bounds for the declaring side that hold for any split (ported from sure.cpp: declCash, declRun,
// top trumps). No bound for the defenders is used: sure.cpp's assume show-out knowledge only.
//
// Defender's cards (--def):
//   all      every card he may hold (reference)
//   ends     one per run of touching unnamed cards, or lowest + middle + highest when his partner is still to play to
//            the trick and may hold the suit (default)
//   mid      as ends, but a run of three or more is represented by a middle card only
//   two      sure.cpp's rule: lowest + highest (known to be unsound; kept to measure it)
//
// Input (one item per line):
//   P trump leader hN hS pool named [cards already played to the trick]     root position (masks in hex)
//   C eu0 eu1 eu2 eu3 pinE [weight] a cell: East's unnamed cards per suit, the named cards East holds (hex), and a
//                                   weight (only the W query uses it)
//   Q need cards|* cells|*          per root card (comma list or *), 1/0: does it guarantee `need` more tricks in every
//                                   listed cell (comma list of cell numbers, or * for all)
//   V cells|*                       the position's value (root at a trick boundary)
//   W need card cells|*             a set of the listed cells that one line starting with `card` wins, found in one pass
//                                   (measured and not used: asking Q for growing sets was cheaper and no worse)
//   R                               clear the tables
// Output: one JSON line per Q, V or W. Q and V report nodes, tt_hits, low_nodes (nodes with four cards or fewer left)
// and boundary4 (trick-boundary positions searched with exactly four cards left), which is what a resident 4-card
// table would replace by lookups.
// Flags: --def all|ends|mid|two, --nobounds, --noorder, --ttbits N, --stbits N, --maxnodes N (per question).
// Compile with -DNW=k for up to 64 * k cells (default 8).
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>
#if defined(__BMI2__)
#include <immintrin.h>
#endif

using u64 = uint64_t;
static const u64 S13 = 0x1FFFULL;
static inline u64 sm(int s) { return S13 << (13 * s); }
static inline int pc(u64 x) { return __builtin_popcountll(x); }
static inline u64 bit(int c) { return 1ULL << c; }

#ifndef NW
#define NW 8                      // live-set words: up to 64 * NW cells
#endif
static const int MAXC = 64 * NW;
struct LS {
    u64 w[NW];
    bool any() const { for (int i = 0; i < NW; i++) if (w[i]) return true; return false; }
    int count() const { int n = 0; for (int i = 0; i < NW; i++) n += pc(w[i]); return n; }
    bool operator==(const LS& o) const { return !memcmp(w, o.w, sizeof w); }
};
static inline LS operator&(const LS& a, const LS& b) { LS r; for (int i = 0; i < NW; i++) r.w[i] = a.w[i] & b.w[i]; return r; }
static inline LS operator|(const LS& a, const LS& b) { LS r; for (int i = 0; i < NW; i++) r.w[i] = a.w[i] | b.w[i]; return r; }
static inline LS andnot(const LS& a, const LS& b) { LS r; for (int i = 0; i < NW; i++) r.w[i] = a.w[i] & ~b.w[i]; return r; }
static const LS NONE = {};

static int TRUMP = 4;
static u64 NAMED = 0;
static int NC = 0;
static int8_t EU[MAXC][4];        // East's unnamed cards per suit at the root
static u64 PINE[MAXC];            // named cards East holds
static double CWT[MAXC];          // weight of each cell (for the set search)
static int UROOT[4];              // unnamed pool cards per suit at the root
static LS EQE[4][15], GEE[4][15], EQW[4][15], GEW[4][15], PIN[52], ALLC;

static int DEFMODE = 1;           // 0 all, 1 ends (low, mid, high), 2 mid, 3 two (low, high)
static bool USE_BOUNDS = true, USE_ORDER = true;
static u64 nodes = 0, ttHits = 0, MAXNODES = 0, nodeLimit = ~0ULL;
static u64 nodesLeft[15], boundary4 = 0;      // nodes by tricks left; trick-boundary positions searched with 4 cards left
struct Capped {};

struct Pos {
    u64 hN, hS, pool;
    LS live;
    int8_t epu[4], wpu[4];        // unnamed cards East / West have played per suit since the root
    int8_t leader, nt;
    int8_t tc[3];
};

// ---------------------------------------------------------------- knowledge
static inline LS eastVoid(const Pos& p, int L) {
    LS r = EQE[L][p.epu[L]];
    for (u64 m = NAMED & p.pool & sm(L); m; m &= m - 1) r = andnot(r, PIN[__builtin_ctzll(m)]);
    return r;
}
static inline LS westVoid(const Pos& p, int L) {
    LS r = EQW[L][p.wpu[L]];
    for (u64 m = NAMED & p.pool & sm(L); m; m &= m - 1) r = r & PIN[__builtin_ctzll(m)];
    return r;
}

static inline u64 mix(u64 x, u64 k) {
    x ^= k; x *= 0x9E3779B97F4A7C15ULL; x ^= x >> 29; x *= 0xBF58476D1CE4E5B9ULL; x ^= x >> 32; x *= 0x94D049BB133111EBULL; x ^= x >> 31;
    return x;
}
#if defined(__BMI2__)
static inline u64 pextq(u64 x, u64 m) { return _pext_u64(x, m); }
static inline u64 pdepq(u64 x, u64 m) { return _pdep_u64(x, m); }
#else
static inline u64 pextq(u64 x, u64 m) { u64 r = 0; int k = 0; for (; m; m &= m - 1) { if (x & (m & -m)) r |= 1ULL << k; k++; } return r; }
static inline u64 pdepq(u64 x, u64 m) { u64 r = 0; int k = 0; for (; m; m &= m - 1) { if (x >> k & 1) r |= m & -m; k++; } return r; }
#endif

// Order-free hash of the live cells as they are now: unnamed cards East still holds per suit, and who holds the named
// cards that are still unseen (in card order).
static inline void knowHash(const Pos& p, u64& h1, u64& h2) {
    u64 nm = NAMED & p.pool;
    h1 = 0; h2 = 0;
    for (int i = 0; i < NW; i++)
        for (u64 m = p.live.w[i]; m; m &= m - 1) {
            int c = 64 * i + __builtin_ctzll(m);
            u64 code = (u64)(EU[c][0] - p.epu[0]) | (u64)(EU[c][1] - p.epu[1]) << 4 | (u64)(EU[c][2] - p.epu[2]) << 8
                       | (u64)(EU[c][3] - p.epu[3]) << 12 | pextq(PINE[c], nm) << 16;
            h1 += mix(code, 0x243F6A8885A308D3ULL);
            h2 += mix(code, 0x13198A2E03707344ULL);
        }
}

// Who holds each live card of a suit in rank order, 2 bits a card: 0 unnamed unseen, 1 North, 2 South, 3 named unseen;
// then the number of live cards.
static inline u64 suitCode(const Pos& p, int s) {
    u64 n = (p.hN >> (13 * s)) & S13, so = (p.hS >> (13 * s)) & S13, x = (p.pool >> (13 * s)) & S13, nm = ((NAMED & p.pool) >> (13 * s)) & S13;
    u64 live = n | so | x;
    u64 a = pextq(n | nm, live), b = pextq(so | nm, live);
    return pdepq(a, 0x1555555ULL) | pdepq(b, 0x2AAAAAAULL) | (u64)pc(live) << 26;       // 30 bits
}

struct Key {
    u64 a, b, c, d;
    bool operator==(const Key& o) const { return a == o.a && b == o.b && c == o.c && d == o.d; }
};
static inline Key ttKey(const Pos& p) {
    Key k;
    k.a = suitCode(p, 0) | suitCode(p, 1) << 30 | (u64)p.leader << 60;
    k.b = suitCode(p, 2) | suitCode(p, 3) << 30 | (u64)TRUMP << 60;
    knowHash(p, k.c, k.d);
    return k;
}
struct Entry { Key k; int8_t lo, hi, best, used; };
static Entry* TT = nullptr;
static u64 TTMASK = 0;
static void ttClear() { for (u64 i = 0; i <= TTMASK; i++) TT[i].used = 0; }
static inline Entry* ttFind(const Key& k) {
    u64 h = mix(k.a ^ (k.b * 0xD6E8FEB86659FD93ULL), k.c + (k.d << 1)) & TTMASK;
    for (int i = 0; i < 8; i++) {
        Entry& e = TT[(h + i) & TTMASK];
        if (e.used && e.k == k) return &e;
        if (!e.used) { e.k = k; e.lo = 0; e.hi = 13; e.best = -1; e.used = 1; return &e; }
    }
    Entry& e = TT[h];
    e.k = k; e.lo = 0; e.hi = 13; e.best = -1; e.used = 1;
    return &e;
}

// ---------------------------------------------------------------- rules
static inline int trickWinner(int leader, const int8_t* c) {
    int best = 0;
    for (int i = 1; i < 4; i++) {
        int sb = c[best] / 13, si = c[i] / 13;
        if (si == sb) { if (c[i] > c[best]) best = i; }
        else if (si == TRUMP) best = i;
    }
    return (leader + best) & 3;
}

static bool can(const Pos& p, int need);

struct Move { int8_t card; int16_t score; LS live; };

static inline bool advance(const Pos& p, int seat, const Move& m, int need) {
    Pos q = p;
    int c = m.card;
    if (seat == 0) q.hN ^= bit(c);
    else if (seat == 2) q.hS ^= bit(c);
    else {
        q.pool ^= bit(c);
        q.live = m.live;
        if (!(NAMED & bit(c))) { if (seat == 1) q.epu[c / 13]++; else q.wpu[c / 13]++; }
    }
    if (p.nt == 3) {
        int8_t cs[4] = {p.tc[0], p.tc[1], p.tc[2], (int8_t)c};
        int w = trickWinner(p.leader, cs);
        q.leader = (int8_t)w; q.nt = 0;
        return can(q, need - ((w & 1) == 0));
    }
    q.tc[p.nt] = (int8_t)c; q.nt = p.nt + 1;
    return can(q, need);
}

// Declaring side: one card per run of touching cards (no live card of another hand, and no card of the trick, between).
static inline int genDecl(const Pos& p, int seat, u64 live, Move* out) {
    u64 h = seat == 0 ? p.hN : p.hS;
    u64 legal = h;
    if (p.nt) { u64 f = h & sm(p.tc[0] / 13); if (f) legal = f; }
    u64 others = live & ~h;
    int n = 0;
    for (int s = 0; s < 4; s++) {
        u64 cards = (legal >> (13 * s)) & S13;
        if (!cards) continue;
        u64 oth = (others >> (13 * s)) & S13;
        int prev = -1;
        while (cards) {
            int r = __builtin_ctzll(cards);
            cards &= cards - 1;
            if (prev >= 0) {
                u64 between = ((1ULL << r) - 1) & ~((1ULL << (prev + 1)) - 1);
                if (!(oth & between)) { out[n - 1].card = (int8_t)(13 * s + r); prev = r; continue; }
            }
            out[n].card = (int8_t)(13 * s + r); out[n].score = 0; n++;
            prev = r;
        }
    }
    return n;
}

// Defender i (0 East, 1 West): every card some live cell lets him play, with the cells that do.
static inline int genDef(const Pos& p, int i, u64 live, Move* out) {
    int led = p.nt ? p.tc[0] / 13 : -1;
    int partnerSeat = i == 0 ? 3 : 1;
    bool partnerPlayed = false;
    for (int k = 0; k < p.nt; k++) if (((p.leader + k) & 3) == partnerSeat) partnerPlayed = true;
    LS offsuit = p.live;                                   // cells in which he holds none of the suit led
    if (led >= 0) offsuit = p.live & (i == 0 ? eastVoid(p, led) : westVoid(p, led));
    int n = 0;
    for (int s = 0; s < 4; s++) {
        u64 cards = (p.pool >> (13 * s)) & S13;
        if (!cards) continue;
        LS base = (led >= 0 && s != led) ? offsuit : p.live;
        if (!base.any()) continue;
        u64 nm = ((NAMED & p.pool) >> (13 * s)) & S13;
        for (u64 m = nm; m; m &= m - 1) {                  // named cards: his in the cells that pin them to him
            int r = __builtin_ctzll(m), c = 13 * s + r;
            LS l = i == 0 ? (base & PIN[c]) : andnot(base, PIN[c]);
            if (l.any()) { out[n].card = (int8_t)c; out[n].score = 0; out[n].live = l; n++; }
        }
        u64 un = cards & ~nm;
        if (!un) continue;
        int played = i == 0 ? p.epu[s] : p.wpu[s];
        LS l = base & (i == 0 ? GEE[s][played + 1] : GEW[s][played + 1]);
        if (!l.any()) continue;
        if (DEFMODE == 0) {
            for (u64 m = un; m; m &= m - 1) { out[n].card = (int8_t)(13 * s + __builtin_ctzll(m)); out[n].score = 0; out[n].live = l; n++; }
            continue;
        }
        // may his partner still play an unnamed card of this suit to this trick?
        int pplayed = i == 0 ? p.wpu[s] : p.epu[s];
        bool partnerMay = !partnerPlayed && (l & (i == 0 ? GEW[s][pplayed + 1] : GEE[s][pplayed + 1])).any();
        bool both = partnerMay && (led < 0 || s == led || s == TRUMP);
        u64 block = ((live & ~p.pool) >> (13 * s) & S13) | nm;
        int run[13], len = 0;
        u64 rest = un;
        while (true) {
            int r = rest ? __builtin_ctzll(rest) : -1;
            bool newRun = r < 0;
            if (!newRun && len) {
                u64 between = ((1ULL << r) - 1) & ~((1ULL << (run[len - 1] + 1)) - 1);
                if (block & between) newRun = true;
            }
            if (newRun && len) {
                int pick[3], np = 0;
                if (!both || len == 1) pick[np++] = run[0];
                else if (len == 2) { pick[np++] = run[0]; pick[np++] = run[1]; }
                else if (DEFMODE == 2) pick[np++] = run[len / 2];
                else if (DEFMODE == 3) { pick[np++] = run[0]; pick[np++] = run[len - 1]; }
                else { pick[np++] = run[0]; pick[np++] = run[len / 2]; pick[np++] = run[len - 1]; }
                for (int k = 0; k < np; k++) { out[n].card = (int8_t)(13 * s + pick[k]); out[n].score = 0; out[n].live = l; n++; }
                len = 0;
            }
            if (r < 0) break;
            rest &= rest - 1;
            run[len++] = r;
        }
    }
    return n;
}

// ---------------------------------------------------------------- lower bounds for the declaring side (any split)
static inline int declCash(const Pos& p) {
    u64 h = p.leader == 0 ? p.hN : p.hS, other = p.leader == 0 ? p.hS : p.hN;
    bool ruffable = TRUMP < 4 && (p.pool & sm(TRUMP));
    int safeSum = 0, unsafeMax = 0;
    for (int s = 0; s < 4; s++) {
        u64 mine = (h >> (13 * s)) & S13;
        if (!mine) continue;
        if (ruffable && s != TRUMP) continue;
        u64 x = (p.pool >> (13 * s)) & S13;
        int top = x ? 63 - __builtin_clzll(x) : -1;
        u64 mast = mine & ~((1ULL << (top + 1)) - 1);
        if (!mast) continue;
        u64 po = (other >> (13 * s)) & S13;
        int m = pc(mast);
        if (!po || 63 - __builtin_clzll(po) < __builtin_ctzll(mast)) { safeSum += m; continue; }
        int t = 0;
        u64 lead = mast, part = po;
        while (lead) {
            int c = 63 - __builtin_clzll(lead);
            lead ^= 1ULL << c;
            t++;
            if (!part) continue;
            int low = __builtin_ctzll(part);
            part ^= 1ULL << low;
            if (low > c) break;
        }
        unsafeMax = std::max(unsafeMax, t);
    }
    return safeSum + unsafeMax;
}
static inline int declRun(const Pos& p) {
    u64 h[2] = {p.hN, p.hS};
    int me = p.leader == 0 ? 0 : 1;
    bool ruff = TRUMP < 4 && (p.pool & sm(TRUMP));
    u64 mast[2] = {0, 0};
    for (int s = 0; s < 4; s++) {
        if (ruff && s != TRUMP) continue;
        u64 x = (p.pool >> (13 * s)) & S13;
        int top = x ? 63 - __builtin_clzll(x) : -1;
        u64 above = (~((1ULL << (top + 1)) - 1) & S13) << (13 * s);
        mast[0] |= p.hN & above; mast[1] |= p.hS & above;
    }
    int t = 0;
    while (true) {
        int pd = 1 - me;
        u64 m = mast[me] & h[me];
        if (m) {
            int c = -1;
            for (u64 r = m; r; r &= r - 1) {
                int k = __builtin_ctzll(r), s = k / 13;
                u64 ps = h[pd] & sm(s);
                if (!ps || __builtin_ctzll(ps) < k) { c = k; break; }
                if (c < 0) c = k;
            }
            int s = c / 13;
            u64 ps = h[pd] & sm(s);
            h[me] ^= bit(c);
            t++;
            if (ps) {
                int low = __builtin_ctzll(ps);
                h[pd] ^= bit(low);
                if (low > c) me = pd;
            } else if (h[pd]) {
                u64 spare = h[pd] & ~mast[pd];
                h[pd] ^= bit(__builtin_ctzll(spare ? spare : h[pd]));
            }
            continue;
        }
        u64 pm = mast[pd] & h[pd];
        int c = -1, pc_ = -1;
        for (u64 r = pm; r; r &= r - 1) {
            int k = __builtin_ctzll(r), s = k / 13;
            u64 mine = h[me] & sm(s);
            if (mine) { c = __builtin_ctzll(mine); pc_ = k; break; }
        }
        if (c < 0) break;
        h[me] ^= bit(c); h[pd] ^= bit(pc_);
        t++;
        me = pd;
    }
    return t;
}
static inline int declTrumpSure(const Pos& p) {
    if (TRUMP >= 4) return 0;
    u64 x = (p.pool >> (13 * TRUMP)) & S13;
    int top = x ? 63 - __builtin_clzll(x) : -1;
    u64 above = ~((1ULL << (top + 1)) - 1) & S13;
    return std::max(pc((p.hN >> (13 * TRUMP)) & above), pc((p.hS >> (13 * TRUMP)) & above));
}

// ---------------------------------------------------------------- search
static int8_t killer[14][4][2];
static int orderMoves(const Pos& p, int seat, int left, int ttBest, Move* mv);

static bool can(const Pos& p, int need) {
    if (need <= 0) return true;
    int seat = (p.leader + p.nt) & 3;
    int left = (pc(p.hN) + pc(p.hS) + pc(p.pool) + p.nt) / 4;      // tricks still to be completed, counting the one in progress
    if (left < need) return false;
    Entry* e = nullptr;
    Key tk{0, 0, 0, 0};
    int ttBest = -1, cutCard = -1;
    if (p.nt == 0) {
        tk = ttKey(p);
        e = ttFind(tk);
        if (need <= e->lo) { ttHits++; return true; }
        if (need > e->hi) { ttHits++; return false; }
        ttBest = e->best;
        if (USE_BOUNDS) {
            if ((seat & 1) == 0) {
                int t = declCash(p);
                if (t > e->lo) e->lo = (int8_t)std::min(t, left);
                if (need <= e->lo) return true;
                t = declRun(p);
                if (t > e->lo) e->lo = (int8_t)std::min(t, left);
                if (need <= e->lo) return true;
            }
            if (TRUMP < 4) {
                int a = declTrumpSure(p);
                if (a > e->lo) e->lo = (int8_t)std::min(a, left);
                if (need <= e->lo) return true;
            }
        }
    }
    nodes++;
    nodesLeft[left]++;
    if (p.nt == 0 && left == 4) boundary4++;
    if (nodes > nodeLimit) throw Capped();
    Move mv[40];
    bool result;
    int n = orderMoves(p, seat, left, ttBest, mv);
    if ((seat & 1) == 0) {
        result = false;
        for (int k = 0; k < n; k++)
            if (advance(p, seat, mv[k], need)) { result = true; cutCard = mv[k].card; break; }
    } else {
        result = true;
        for (int k = 0; k < n; k++)
            if (!advance(p, seat, mv[k], need)) { result = false; cutCard = mv[k].card; break; }
    }
    if (p.nt == 0) {
        if (cutCard >= 0 && killer[left][seat][0] != cutCard) { killer[left][seat][1] = killer[left][seat][0]; killer[left][seat][0] = (int8_t)cutCard; }
        if (!(e->used && e->k == tk)) e = ttFind(tk);
        if (cutCard >= 0) e->best = (int8_t)cutCard;
        if (result) { if (need > e->lo) e->lo = (int8_t)need; }
        else { if (need - 1 < e->hi) e->hi = (int8_t)(need - 1); }
    }
    return result;
}

// The cards of the seat to play, best guess first.
static int orderMoves(const Pos& p, int seat, int left, int ttBest, Move* mv) {
    u64 live = p.hN | p.hS | p.pool;
    for (int k = 0; k < p.nt; k++) live |= bit(p.tc[k]);
    int holder = 0, bestc = 0, bs = 0;
    if (p.nt) {
        int b = 0;
        for (int k = 1; k < p.nt; k++) {
            int sb = p.tc[b] / 13, sk = p.tc[k] / 13;
            if (sk == sb) { if (p.tc[k] > p.tc[b]) b = k; }
            else if (sk == TRUMP) b = k;
        }
        holder = (p.leader + b) & 3; bestc = p.tc[b]; bs = bestc / 13;
    }
    int n;
    if ((seat & 1) == 0) {
        n = genDecl(p, seat, live, mv);
        if (USE_ORDER) {
            u64 h = seat == 0 ? p.hN : p.hS;
            for (int k = 0; k < n; k++) {
                int c = mv[k].card, s = c / 13, r = c % 13, sc = 0;
                u64 x = (p.pool >> (13 * s)) & S13;
                bool master = !(x >> (r + 1));
                if (c == ttBest) sc += 1000;
                if (p.nt == 0) {
                    if (master) sc += 60 + (s == TRUMP ? 10 : 0);
                    else sc += 20 - r;
                    sc += pc((h >> (13 * s)) & S13);
                    if (c == killer[left][seat][0]) sc += 200; else if (c == killer[left][seat][1]) sc += 150;
                } else {
                    bool win = s == bs ? c > bestc : s == TRUMP;
                    if ((holder & 1) == 0) sc += 30 - r;
                    else if (win) sc += 50 - r;
                    else sc += 20 - r;
                }
                mv[k].score = (int16_t)sc;
            }
        }
    } else {
        n = genDef(p, seat >> 1, live, mv);
        if (USE_ORDER) {
            for (int k = 0; k < n; k++) {
                int c = mv[k].card, s = c / 13, r = c % 13, sc = 0;
                if (c == ttBest) sc += 1000;
                if (p.nt == 0) {
                    u64 ns = ((p.hN | p.hS) >> (13 * s)) & S13;
                    bool master = !(ns >> (r + 1));
                    sc += master ? 60 : 10 + r;
                    if (c == killer[left][seat][0]) sc += 200; else if (c == killer[left][seat][1]) sc += 150;
                } else {
                    bool win = s == bs ? c > bestc : s == TRUMP;
                    if (holder & 1) sc += 25 - r + (win ? 10 : 0);
                    else if (win) sc += 50 - r;
                    else sc += 20 - r;
                }
                mv[k].score = (int16_t)sc;
            }
        }
    }
    if (USE_ORDER) std::stable_sort(mv, mv + n, [](const Move& a, const Move& b) { return a.score > b.score; });
    return n;
}

// ---------------------------------------------------------------- set search
// win(p, need): a set of live cells that ONE line wins (takes `need` more tricks in every cell of the set), chosen
// greedily: where the declaring side plays, the card whose set weighs most; where a defender plays, a cell survives
// only if it survives every card that cell lets him play, and each card is searched for the cells still alive.
// The result is always a set one line wins (a floor); it need not be the heaviest such set.
// Exact-state table at trick boundaries (cells are numbered from the root, so nothing is shared between roots).
static inline double weightOf(const LS& a) {
    double w = 0;
    for (int i = 0; i < NW; i++) for (u64 m = a.w[i]; m; m &= m - 1) w += CWT[64 * i + __builtin_ctzll(m)];
    return w;
}
struct SEntry { u64 k1, k2; LS w; uint8_t used; };
static SEntry* ST = nullptr;
static u64 STMASK = 0;
static u64 setNodes = 0;
static void stClear() { if (ST) for (u64 i = 0; i <= STMASK; i++) ST[i].used = 0; }
static inline void stateKey(const Pos& p, int need, u64& a, u64& b) {
    u64 x = mix(p.hN, 0x1234567ULL), y = mix(p.hS, 0x7654321ULL);
    x = mix(x ^ p.pool, (u64)p.leader | (u64)need << 8 | (u64)TRUMP << 16);
    u64 e = 0;
    for (int s = 0; s < 4; s++) e |= (u64)p.epu[s] << (8 * s) | (u64)p.wpu[s] << (32 + 8 * s);
    y = mix(y ^ e, 0xA5A5A5A5ULL);
    for (int i = 0; i < NW; i++) { x = mix(x ^ p.live.w[i], 0x100 + i); y = mix(y + p.live.w[i] * 0x9E3779B97F4A7C15ULL, 0x200 + i); }
    a = x; b = y;
}
static LS win(const Pos& p, int need) {
    if (need <= 0) return p.live;
    int left = (pc(p.hN) + pc(p.hS) + pc(p.pool) + p.nt) / 4;
    if (left < need) return NONE;
    if (p.nt == 0 || p.live.count() == 1) {                 // the whole set at once: the yes/no search and its table
        if (can(p, need)) return p.live;
        if (p.live.count() == 1) return NONE;
    }
    SEntry* e = nullptr;
    u64 k1 = 0, k2 = 0;
    if (p.nt == 0) {
        stateKey(p, need, k1, k2);
        u64 h = k1 & STMASK;
        for (int i = 0; i < 4; i++) {
            SEntry& x = ST[(h + i) & STMASK];
            if (x.used && x.k1 == k1 && x.k2 == k2) return x.w;
            if (!x.used) { e = &x; break; }
        }
        if (!e) e = &ST[h];
    }
    nodes++; setNodes++;
    if (nodes > nodeLimit) throw Capped();
    int seat = (p.leader + p.nt) & 3;
    Move mv[40];
    int n = orderMoves(p, seat, left, -1, mv);
    LS res;
    if ((seat & 1) == 0) {
        res = NONE;
        double bw = -1;
        for (int k = 0; k < n; k++) {
            Pos q = p;
            int c = mv[k].card;
            if (seat == 0) q.hN ^= bit(c); else q.hS ^= bit(c);
            int nd = need;
            if (p.nt == 3) {
                int8_t cs[4] = {p.tc[0], p.tc[1], p.tc[2], (int8_t)c};
                int w = trickWinner(p.leader, cs);
                q.leader = (int8_t)w; q.nt = 0; nd = need - ((w & 1) == 0);
            } else { q.tc[p.nt] = (int8_t)c; q.nt = p.nt + 1; }
            LS W = win(q, nd);
            double w = weightOf(W);
            if (w > bw) { bw = w; res = W; }
            if (W == p.live) break;
        }
    } else {
        res = p.live;
        for (int k = 0; k < n; k++) {
            LS l = mv[k].live & res;
            if (!l.any()) continue;
            Pos q = p;
            int c = mv[k].card;
            q.pool ^= bit(c);
            q.live = l;
            if (!(NAMED & bit(c))) { if (seat == 1) q.epu[c / 13]++; else q.wpu[c / 13]++; }
            int nd = need;
            if (p.nt == 3) {
                int8_t cs[4] = {p.tc[0], p.tc[1], p.tc[2], (int8_t)c};
                int w = trickWinner(p.leader, cs);
                q.leader = (int8_t)w; q.nt = 0; nd = need - ((w & 1) == 0);
            } else { q.tc[p.nt] = (int8_t)c; q.nt = p.nt + 1; }
            LS W = win(q, nd);
            res = andnot(res, andnot(l, W));
            if (!res.any()) break;
        }
    }
    if (p.nt == 0) {
        if (!(e->used == 0 || (e->k1 == k1 && e->k2 == k2))) { /* slot reused meanwhile: overwrite */ }
        e->k1 = k1; e->k2 = k2; e->w = res; e->used = 1;
    }
    return res;
}

// ---------------------------------------------------------------- driver
static Pos ROOT;
static bool haveRoot = false;

static void buildSets() {
    for (int s = 0; s < 4; s++)
        for (int v = 0; v < 15; v++) EQE[s][v] = GEE[s][v] = EQW[s][v] = GEW[s][v] = NONE;
    for (int c = 0; c < 52; c++) PIN[c] = NONE;
    ALLC = NONE;
    for (int i = 0; i < NC; i++) {
        ALLC.w[i >> 6] |= 1ULL << (i & 63);
        for (int s = 0; s < 4; s++) {
            int e = EU[i][s], w = UROOT[s] - e;
            EQE[s][e].w[i >> 6] |= 1ULL << (i & 63);
            EQW[s][w].w[i >> 6] |= 1ULL << (i & 63);
            for (int v = 0; v <= e; v++) GEE[s][v].w[i >> 6] |= 1ULL << (i & 63);
            for (int v = 0; v <= w; v++) GEW[s][v].w[i >> 6] |= 1ULL << (i & 63);
        }
        for (u64 m = PINE[i]; m; m &= m - 1) PIN[__builtin_ctzll(m)].w[i >> 6] |= 1ULL << (i & 63);
    }
}

static bool parseCells(const std::string& tok, LS& out) {
    out = NONE;
    if (tok == "*") { out = ALLC; return true; }
    std::stringstream ss(tok);
    std::string item;
    while (std::getline(ss, item, ',')) {
        int i = atoi(item.c_str());
        if (i < 0 || i >= NC) return false;
        out.w[i >> 6] |= 1ULL << (i & 63);
    }
    return true;
}

int main(int argc, char** argv) {
    int ttbits = 20, stbits = 18;
    for (int i = 1; i < argc; i++) {
        std::string a = argv[i];
        if (a == "--def") { std::string v = argv[++i]; DEFMODE = v == "all" ? 0 : v == "ends" ? 1 : v == "mid" ? 2 : 3; }
        else if (a == "--nobounds") USE_BOUNDS = false;
        else if (a == "--noorder") USE_ORDER = false;
        else if (a == "--ttbits") ttbits = atoi(argv[++i]);
        else if (a == "--stbits") stbits = atoi(argv[++i]);
        else if (a == "--maxnodes") MAXNODES = strtoull(argv[++i], nullptr, 10);
        else { fprintf(stderr, "unknown flag %s\n", a.c_str()); return 2; }
    }
    TTMASK = (1ULL << ttbits) - 1;
    TT = (Entry*)calloc(TTMASK + 1, sizeof(Entry));
    STMASK = (1ULL << stbits) - 1;
    ST = (SEntry*)calloc(STMASK + 1, sizeof(SEntry));
    memset(killer, -1, sizeof killer);
    std::string lineText;
    bool setsBuilt = false;
    while (std::getline(std::cin, lineText)) {
        if (lineText.empty()) continue;
        std::stringstream ss(lineText);
        std::string kind;
        ss >> kind;
        if (kind == "R") { ttClear(); stClear(); memset(killer, -1, sizeof killer); continue; }
        if (kind == "P") {
            int leader;
            ss >> TRUMP >> leader >> std::hex >> ROOT.hN >> ROOT.hS >> ROOT.pool >> NAMED >> std::dec;
            ROOT.leader = (int8_t)leader; ROOT.nt = 0;
            int c;
            while (ss >> c) { ROOT.tc[ROOT.nt++] = (int8_t)c; }
            memset(ROOT.epu, 0, 4); memset(ROOT.wpu, 0, 4);
            for (int s = 0; s < 4; s++) UROOT[s] = pc(ROOT.pool & ~NAMED & sm(s));
            NC = 0; haveRoot = true; setsBuilt = false; stClear();
            if (NAMED & ~ROOT.pool) { printf("{\"error\": \"named cards must be unseen\"}\n"); fflush(stdout); haveRoot = false; }
            continue;
        }
        if (kind == "C") {
            if (NC >= MAXC) { printf("{\"error\": \"too many cells\"}\n"); fflush(stdout); continue; }
            int e[4];
            u64 pin;
            double wt = 1;
            ss >> e[0] >> e[1] >> e[2] >> e[3] >> std::hex >> pin >> std::dec;
            if (!(ss >> wt)) wt = 1;
            bool ok = !(pin & ~NAMED);
            for (int s = 0; s < 4; s++) { ok = ok && e[s] >= 0 && e[s] <= UROOT[s]; EU[NC][s] = (int8_t)e[s]; }
            if (!ok) { printf("{\"error\": \"bad cell\"}\n"); fflush(stdout); continue; }
            PINE[NC] = pin; CWT[NC] = wt; NC++; setsBuilt = false;
            continue;
        }
        if (kind == "W") {                                  // W need card cells|* : the set of cells one line starting with `card` wins
            if (!haveRoot || !NC) { printf("{\"error\": \"no position or no cells\"}\n"); fflush(stdout); continue; }
            if (!setsBuilt) { buildSets(); setsBuilt = true; stClear(); }
            int need, c;
            std::string cellTok;
            ss >> need >> c >> cellTok;
            Pos p = ROOT;
            int seat = (p.leader + p.nt) & 3;
            u64 h = seat == 0 ? p.hN : seat == 2 ? p.hS : 0;
            if (!parseCells(cellTok, p.live) || !p.live.any() || !(h & bit(c))) { printf("{\"error\": \"bad W query\"}\n"); fflush(stdout); continue; }
            u64 n0 = nodes, s0 = setNodes;
            nodeLimit = MAXNODES ? nodes + MAXNODES : ~0ULL;
            auto t0 = std::chrono::steady_clock::now();
            bool capped = false;
            LS W = NONE;
            try {
                Pos q = p;
                if (seat == 0) q.hN ^= bit(c); else q.hS ^= bit(c);
                int nd = need;
                if (p.nt == 3) {
                    int8_t cs[4] = {p.tc[0], p.tc[1], p.tc[2], (int8_t)c};
                    int w = trickWinner(p.leader, cs);
                    q.leader = (int8_t)w; q.nt = 0; nd = need - ((w & 1) == 0);
                } else { q.tc[p.nt] = (int8_t)c; q.nt = p.nt + 1; }
                W = win(q, nd);
            } catch (const Capped&) { capped = true; }
            double sec = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
            if (capped) { printf("{\"capped\": true, \"nodes\": %llu, \"sec\": %.6f}\n", (unsigned long long)(nodes - n0), sec); fflush(stdout); continue; }
            std::string body = "\"set\": [";
            bool first = true;
            for (int i = 0; i < NC; i++) if (W.w[i >> 6] >> (i & 63) & 1) { body += (first ? "" : ", ") + std::to_string(i); first = false; }
            printf("{%s], \"weight\": %.9g, \"nodes\": %llu, \"set_nodes\": %llu, \"sec\": %.6f}\n", body.c_str(), weightOf(W),
                   (unsigned long long)(nodes - n0), (unsigned long long)(setNodes - s0), sec);
            fflush(stdout);
            continue;
        }
        if (kind == "Q" || kind == "V") {
            if (!haveRoot || !NC) { printf("{\"error\": \"no position or no cells\"}\n"); fflush(stdout); continue; }
            if (!setsBuilt) { buildSets(); setsBuilt = true; }
            int need = 0;
            std::string cardTok = "*", cellTok;
            if (kind == "Q") ss >> need >> cardTok >> cellTok; else ss >> cellTok;
            Pos p = ROOT;
            if (!parseCells(cellTok, p.live) || !p.live.any()) { printf("{\"error\": \"bad cell list\"}\n"); fflush(stdout); continue; }
            u64 n0 = nodes, h0 = ttHits, b0 = boundary4;
            u64 low0 = nodesLeft[1] + nodesLeft[2] + nodesLeft[3] + nodesLeft[4];
            nodeLimit = MAXNODES ? nodes + MAXNODES : ~0ULL;
            auto t0 = std::chrono::steady_clock::now();
            int seat = (p.leader + p.nt) & 3;
            std::string body;
            bool capped = false;
            try {
                if (kind == "V") {
                    int left = std::max(pc(p.hN), pc(p.hS)), v = left;
                    while (v > 0 && !can(p, v)) v--;
                    body = "\"value\": " + std::to_string(v);
                } else {
                    if (seat & 1) { printf("{\"error\": \"Q needs the declaring side to play\"}\n"); fflush(stdout); continue; }
                    u64 want = 0;
                    bool every = cardTok == "*";
                    if (!every) { std::stringstream cs(cardTok); std::string it; while (std::getline(cs, it, ',')) want |= bit(atoi(it.c_str())); }
                    u64 live = p.hN | p.hS | p.pool;
                    for (int k = 0; k < p.nt; k++) live |= bit(p.tc[k]);
                    u64 h = seat == 0 ? p.hN : p.hS, legal = h;
                    if (p.nt) { u64 f = h & sm(p.tc[0] / 13); if (f) legal = f; }
                    u64 others = live & ~h;
                    // runs of touching legal cards share one answer
                    std::vector<std::vector<int>> runs;
                    int prevCard = -1;
                    for (u64 m = legal; m; m &= m - 1) {
                        int c = __builtin_ctzll(m);
                        bool same = false;
                        if (prevCard >= 0 && prevCard / 13 == c / 13) {
                            u64 between = (bit(c) - 1) & ~(bit(prevCard + 1) - 1);
                            same = !(others & between);
                        }
                        if (!same) runs.emplace_back();
                        runs.back().push_back(c);
                        prevCard = c;
                    }
                    body = "\"cards\": {";
                    bool first = true;
                    for (auto& run : runs) {
                        bool asked = every;
                        for (int c : run) if (want & bit(c)) asked = true;
                        if (!asked) continue;
                        Move mvv; mvv.card = (int8_t)run[0]; mvv.score = 0; mvv.live = p.live;
                        int ans = advance(p, seat, mvv, need) ? 1 : 0;
                        for (int c : run) {
                            if (!every && !(want & bit(c))) continue;
                            body += (first ? "\"" : ", \"") + std::to_string(c) + "\": " + std::to_string(ans);
                            first = false;
                        }
                    }
                    body += "}";
                }
            } catch (const Capped&) { capped = true; }
            double sec = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
            if (capped) printf("{\"capped\": true, \"nodes\": %llu, \"sec\": %.6f}\n", (unsigned long long)(nodes - n0), sec);
            else printf("{%s, \"nodes\": %llu, \"tt_hits\": %llu, \"low_nodes\": %llu, \"boundary4\": %llu, \"sec\": %.6f}\n", body.c_str(), (unsigned long long)(nodes - n0), (unsigned long long)(ttHits - h0),
                        (unsigned long long)(nodesLeft[1] + nodesLeft[2] + nodesLeft[3] + nodesLeft[4] - low0), (unsigned long long)(boundary4 - b0), sec);
            fflush(stdout);
            continue;
        }
        printf("{\"error\": \"unknown line\"}\n");
        fflush(stdout);
    }
    return 0;
}
