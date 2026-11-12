// Single-dummy sure tricks: what North-South can guarantee against every split of the unseen cards.
// The defenders' cards are one pool; who holds a card is settled when it is played, subject to hand
// sizes and show-outs. Perfect-information minimax over that pooled game (see sure.py for the
// reference implementation this is checked against).
//
// Search: target-based (can declarer guarantee `need` more tricks?), transposition table at trick
// boundaries keyed on rank-relative cards + show-out state + leader, storing lower/upper bounds.
// Borrowed from DDS and adapted to the pooled game: a remembered best lead per depth, keys built from
// relative ranks, quick tricks for the side on lead using both hands, later tricks for top trumps.
// With --front K the search stops at K-card trick-boundary positions and asks a table. The table is
// simulated: a memory-resident map filled on first use by an unbounded search whose time and nodes are
// accounted separately, so that "search time above the table" and "table probes" are both reported.
//
// Input, one position per line:  trump leader hN hS pool cE cW vE vW [cards already played to the trick]
//   trump 0..3 = S,H,D,C, 4 = notrump; leader 0..3 = N,E,S,W; masks in hex, card = 13*suit + rank(2..A = 0..12).
// North-South is always the declaring side.
//
// Flags: --need N      per legal card, 1/0: does it guarantee N more tricks (otherwise the exact value of every card)
//        --front K     stop at K-card trick boundaries and read the table
//        --warm        fill the table in an untimed first pass, then time a second pass from an empty transposition table
//        --mem GB      one read of a real array of this size per table read (hashed address, caches flushed before timing)
//        --keep        keep the table and the transposition table from one input line to the next
//        --ttbits N    transposition table of 2^N entries (default 18)
//        --stats       nodes by depth and huge-page use, to stderr
//        --value       one number per position (what a table entry holds) instead of one per card
//        --cells GB    with --warm: read table values from a real array of this size (cache lines flushed first; --noflush keeps them)
//        --huge --hugett   2 MB pages for the cells / the transposition table
//        --replay      with --warm: free lookups, the table's answers replayed in recorded order
//        --dupkey N --dupbound N   compute the table key / the frontier bound N extra times (rough pricing)
//        --table FILE  (built with -DENDTABLE) read values from a built ending table through endtable/endtable.h
// A line may start with N<k> to set --need for that line.
//        --nobounds --noorder --nokiller --norun --norunfront --notrumpbounds --hist
//                      switch off: sure-winner bounds, move ordering, lead memory, two-hand quick tricks (everywhere /
//                      before table reads only), trump later-tricks bounds; switch on: the history heuristic
// Output, one JSON line per position: cards {card: value}, seconds, search_seconds (seconds minus table fill),
// nodes_above, nodes_below (table fill), probes, table_new, tt_hits.
#include <algorithm>
#include <sys/mman.h>
#if defined(__x86_64__) || defined(_M_X64)
#include <immintrin.h>
#define SURE_X86 1
#endif
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <sstream>
#include <string>
#include <unordered_map>
#include <vector>

using u64 = uint64_t;
static const u64 S13 = 0x1FFFULL;
static inline u64 sm(int s) { return S13 << (13 * s); }
static inline int pc(u64 x) { return __builtin_popcountll(x); }
static inline u64 bit(int c) { return 1ULL << c; }

static int TRUMP = 4;
static int FRONT = 0;            // 0 = no table
static bool IN_ORACLE = false;
static bool USE_BOUNDS = true;
static bool USE_ORDER = true;
static u64 nodesAbove = 0, nodesBelow = 0, probes = 0, ttHits = 0;
static double oracleSeconds = 0;
static bool USE_HIST = false;
// Lead memory (DDS keeps a best move per depth): the two leads that last settled a node for this seat with this many
// cards left are tried first, after the transposition table's move. Tried and dropped because they searched more
// nodes: the same memory for the second to fourth seats, a reply-to-the-last-card table, a global history count.
static bool USE_KILLER = true;
static int8_t killer[14][4][2];    // [cards left][seat][most recent, the one before]
static uint32_t hist[2][52];
static u64 subNoRead[14], subRead[14];        // boundary nodes searched, by cards left: no table read below / some
static u64 cutAt[2][2][6], allNodes[2][2];   // [side][boundary?][index of the move that settled it], and nodes where every move was tried
static u64 levelNodes[14][4];   // nodes above the table by cards left and cards already in the trick (--stats)

struct Pos {
    u64 hN, hS, pool;
    uint8_t cnt[2];   // cards held by East, West
    uint8_t vd[2];    // suits East, West have shown out of (bit per suit)
    int8_t leader, nt; // nt = cards already played to the current trick
    int8_t tc[3];
};

// ---------------------------------------------------------------- keys
struct Key {
    u64 a, b;
    bool operator==(const Key& o) const { return a == o.a && b == o.b; }
};
struct KeyHash {
    size_t operator()(const Key& k) const {
        u64 x = k.a * 0x9E3779B97F4A7C15ULL ^ (k.b + 0xC2B2AE3D27D4EB4FULL + (k.a << 6) + (k.a >> 2));
        x ^= x >> 29; x *= 0xBF58476D1CE4E5B9ULL; x ^= x >> 32;
        return (size_t)x;
    }
};

// Who holds each live card of a suit, in rank order, in 26 bits.
// With BMI2: 2 bits per card, 0 = unseen, 1 = North, 2 = South, and a 3 after the last card (none for 13 cards).
// Without: the same information built by a loop, 1 = North, 2 = South, 3 = unseen.
#if defined(__BMI2__)
static inline u64 suitCode(const Pos& p, int s, bool mirror) {
    u64 n = (p.hN >> (13 * s)) & S13, so = (p.hS >> (13 * s)) & S13, x = (p.pool >> (13 * s)) & S13;
    if (mirror) std::swap(n, so);
    u64 live = n | so | x;
    u64 code = _pdep_u64(_pext_u64(n, live), 0x1555555ULL) | _pdep_u64(_pext_u64(so, live), 0x2AAAAAAULL);
    int L = pc(live);
    if (L < 13) code |= 3ULL << (2 * L);
    return code;
}
#else
static inline u64 suitCode(const Pos& p, int s, bool mirror) {
    u64 n = (p.hN >> (13 * s)) & S13, so = (p.hS >> (13 * s)) & S13, x = (p.pool >> (13 * s)) & S13;
    if (mirror) std::swap(n, so);
    u64 live = n | so | x, code = 0;
    int pos = 0;
    while (live) {
        u64 b = live & -live;
        live ^= b;
        code |= (u64)((n & b) ? 1 : (so & b) ? 2 : 3) << (2 * pos++);
    }
    return code;
}
#endif

// Transposition key inside one search: suits in place.
static inline Key ttKey(const Pos& p) {
    Key k;
    k.a = suitCode(p, 0, false) | suitCode(p, 1, false) << 26 | (u64)p.vd[0] << 52 | (u64)p.vd[1] << 56 | (u64)p.leader << 60;
    k.b = suitCode(p, 2, false) | suitCode(p, 3, false) << 26 | (u64)TRUMP << 52;
    return k;
}

// Table key: canonical under the half-turn of the table (leader becomes North or East) and under
// permutation of the suits (all four at notrump, the three side suits otherwise).
static inline Key frontKey(const Pos& p) {
    bool mirror = p.leader >= 2;
    int vE = mirror ? p.vd[1] : p.vd[0], vW = mirror ? p.vd[0] : p.vd[1];
    u64 rec[4];
    for (int s = 0; s < 4; s++)
        rec[s] = suitCode(p, s, mirror) | (u64)(vE >> s & 1) << 26 | (u64)(vW >> s & 1) << 27;   // 28 bits
    if (TRUMP < 4) {
        std::swap(rec[0], rec[TRUMP]);
        std::sort(rec + 1, rec + 4);
    } else {
        std::sort(rec, rec + 4);
    }
    Key k;
    k.a = rec[0] | rec[1] << 28 | (u64)(p.leader & 1) << 56 | (u64)(TRUMP < 4) << 57;
    k.b = rec[2] | rec[3] << 28;
    return k;
}

// ---------------------------------------------------------------- transposition table
struct Entry {
    Key k;
    int8_t lo, hi, best, used;
};
static Entry* TT = nullptr;
static u64 TTMASK = 0;
static void* allocBig(size_t bytes, bool huge) {       // page-aligned block; 2 MB pages when asked (needs THP madvise or always)
    size_t align = huge ? (2u << 20) : 4096;
    bytes = (bytes + align - 1) / align * align;
    void* p = aligned_alloc(align, bytes);
#ifdef MADV_HUGEPAGE
    madvise(p, bytes, huge ? MADV_HUGEPAGE : MADV_NOHUGEPAGE);
#endif
    return p;
}
static void ttClear() { std::fill(TT, TT + TTMASK + 1, Entry{{0, 0}, 0, 13, -1, 0}); }
static inline Entry* ttFind(const Key& k, bool create) {
    u64 h = KeyHash()(k) & TTMASK;
    for (int i = 0; i < 8; i++) {
        Entry& e = TT[(h + i) & TTMASK];
        if (e.used && e.k == k) return &e;
        if (!e.used) {
            if (!create) return nullptr;
            e.k = k; e.lo = 0; e.hi = 13; e.best = -1; e.used = 1;
            return &e;
        }
    }
    if (!create) return nullptr;
    Entry& e = TT[h];
    e.k = k; e.lo = 0; e.hi = 13; e.best = -1; e.used = 1;
    return &e;
}

static std::unordered_map<Key, uint8_t, KeyHash> TABLE;   // stand-in for the resident ending table
#ifdef ENDTABLE
// A built table: compile with -DENDTABLE and run with --table FILE (and --front K matching the file).
// The reader is endtable/endtable.h, specified in TABLE_BUILD.md; nothing else in this file knows about it.
#include "endtable/endtable.h"
static EndTable* ET = nullptr;
#endif
// --mem GB puts a real array of that size behind every probe: one read at a hashed address per probe, so the
// cache/TLB cost of a resident table is in the measured search time. Hashed addresses are the worst case
// (a real table indexed by position would put related endings near each other).
static std::vector<uint8_t> BIG;
static u64 bigSink = 0;
// --cells GB: a real table in memory. Open-addressed 4-byte cells (24-bit tag, value) at a hashed slot. With --warm
// the fill pass writes each value it needs into the cells, their cache lines are flushed, and the timed pass reads
// values from the cells only: one dependent memory read per table lookup and no hash map, as with a built table.
static uint32_t* CELLS = nullptr;
static size_t NCELLS = 0;
static std::vector<size_t> cellTouched;
static bool CELLS_READ = false;
static u64 cellMisses = 0;
// --replay: the fill pass records the value of every table lookup in order; the timed pass returns them in the
// same order without computing a key or touching the table. That is the search with free lookups.
static std::vector<uint8_t> SEQ;
static size_t seqPos = 0;
static bool SEQ_RECORD = false, SEQ_READ = false;
static int DUPBOUND = 0;               // --dupbound N: compute the frontier bound N extra times per frontier visit
static int DUPKEY = 0;                 // --dupkey N: compute the table key N extra times per lookup (to price it)
static volatile u64 dupSink = 0;
static volatile uint8_t VZERO = 0;
static inline u64 hash2(const Key& k) {
    u64 x = (k.a ^ 0x9E3779B97F4A7C15ULL) * 0xD6E8FEB86659FD93ULL;
    x ^= k.b * 0xCA5A826395121157ULL; x ^= x >> 32; x *= 0xD6E8FEB86659FD93ULL; x ^= x >> 29;
    return x;
}

// ---------------------------------------------------------------- rules
static inline bool feasible(u64 pool, int cE, int cW, int vE, int vW) {
    int mustE = 0, mustW = 0;
    for (int s = 0; s < 4; s++) {
        int n = pc(pool & sm(s));
        if (!n) continue;
        bool e = vE >> s & 1, w = vW >> s & 1;
        if (e && w) return false;
        if (e) mustW += n;
        else if (w) mustE += n;
    }
    return mustE <= cE && mustW <= cW;
}

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

// Play card c from `seat`; nv = that defender's show-out mask afterwards (ignored for North/South).
static inline bool advance(const Pos& p, int seat, int c, int nv, int need) {
    Pos q = p;
    if (seat == 0) q.hN ^= bit(c);
    else if (seat == 2) q.hS ^= bit(c);
    else { q.pool ^= bit(c); q.cnt[seat >> 1]--; q.vd[seat >> 1] = (uint8_t)nv; }
    if (p.nt == 3) {
        int8_t cs[4] = {p.tc[0], p.tc[1], p.tc[2], (int8_t)c};
        int w = trickWinner(p.leader, cs);
        q.leader = (int8_t)w; q.nt = 0;
        return can(q, need - ((w & 1) == 0));
    }
    q.tc[p.nt] = (int8_t)c; q.nt = p.nt + 1;
    return can(q, need);
}

struct Move { int8_t card; uint8_t nv; int16_t score; };
static inline void pickBest(Move* mv, int k, int n) {      // bring the highest-scored of mv[k..n) to mv[k]
    int b = k;
    for (int j = k + 1; j < n; j++) if (mv[j].score > mv[b].score) b = j;
    if (b != k) std::swap(mv[k], mv[b]);
}

// Declaring side: one card per run of touching cards (no live card of another hand in between).
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
                if (!(oth & between)) { out[n - 1].card = (int8_t)(13 * s + r); prev = r; continue; }   // same run: keep its top card
            }
            out[n].card = (int8_t)(13 * s + r); out[n].nv = 0; out[n].score = 0; n++;
            prev = r;
        }
    }
    return n;
}

// Defender i (0 East, 1 West): every card he may turn up with. Touching pool cards: once his partner has
// played to the trick (or cannot hold the suit) one per run; otherwise both ends of each run.
static inline int genDef(const Pos& p, int i, u64 live, Move* out) {
    int led = p.nt ? p.tc[0] / 13 : -1;
    int partnerSeat = i == 0 ? 3 : 1;
    bool partnerPlayed = false;
    for (int k = 0; k < p.nt; k++) if (((p.leader + k) & 3) == partnerSeat) partnerPlayed = true;
    int n = 0;
    int cE = p.cnt[0] - (i == 0), cW = p.cnt[1] - (i == 1);
    int ns[4];
    for (int s = 0; s < 4; s++) ns[s] = pc(p.pool & sm(s));
    for (int s = 0; s < 4; s++) {
        u64 cards = (p.pool >> (13 * s)) & S13;
        if (!cards || (p.vd[i] >> s & 1)) continue;
        int nv = p.vd[i];
        if (led >= 0 && s != led) nv |= 1 << led;
        // feasibility depends on the suit only: the state after he plays one card of suit s
        int vE = i == 0 ? nv : p.vd[0], vW = i == 1 ? nv : p.vd[1];
        int mustE = 0, mustW = 0;
        bool ok = true;
        for (int t = 0; t < 4; t++) {
            int m = ns[t] - (t == s);
            if (!m) continue;
            bool ev = vE >> t & 1, wv = vW >> t & 1;
            if (ev && wv) { ok = false; break; }
            if (ev) mustW += m; else if (wv) mustE += m;
        }
        if (!ok || mustE > cE || mustW > cW) continue;
        // a plain discard cannot take the trick, so its rank against partner's card does not matter
        bool both = !partnerPlayed && !(p.vd[1 - i] >> s & 1) && (led < 0 || s == led || s == TRUMP);
        u64 block = ((live & ~p.pool) >> (13 * s)) & S13;
        int lo = -1, hi = -1;
        u64 rest = cards;
        while (true) {
            int r = rest ? __builtin_ctzll(rest) : -1;
            bool newRun = r < 0;
            if (!newRun && lo >= 0) {
                u64 between = ((1ULL << r) - 1) & ~((1ULL << (hi + 1)) - 1);
                if (block & between) newRun = true;
            }
            if (newRun && lo >= 0) {
                out[n].card = (int8_t)(13 * s + lo); out[n].nv = (uint8_t)nv; out[n].score = 0; n++;
                if (both && hi != lo) { out[n].card = (int8_t)(13 * s + hi); out[n].nv = (uint8_t)nv; out[n].score = 0; n++; }
                lo = -1;
            }
            if (r < 0) break;
            rest &= rest - 1;
            if (lo < 0) lo = r;
            hi = r;
        }
    }
    return n;
}

// Would card c win the trick as it stands (cards tc[0..nt-1] played)?
static inline bool beatsTrick(const Pos& p, int c) {
    int best = p.tc[0];
    for (int k = 1; k < p.nt; k++) {
        int sb = best / 13, sk = p.tc[k] / 13;
        if (sk == sb) { if (p.tc[k] > best) best = p.tc[k]; }
        else if (sk == TRUMP) best = p.tc[k];
    }
    int sb = best / 13, sc = c / 13;
    if (sc == sb) return c > best;
    return sc == TRUMP;
}
static inline int trickHolder(const Pos& p) {       // seat currently winning the trick
    int best = 0;
    for (int k = 1; k < p.nt; k++) {
        int sb = p.tc[best] / 13, sk = p.tc[k] / 13;
        if (sk == sb) { if (p.tc[k] > p.tc[best]) best = k; }
        else if (sk == TRUMP) best = k;
    }
    return (p.leader + best) & 3;
}

// ---------------------------------------------------------------- bounds at a trick boundary
// Lower bound with North or South on lead: masters (cards above every unseen card of the suit) cashed
// from the top, in suits nobody can ruff. A suit in which partner might be forced to overtake is
// cashed last and only as far as the lead stays put.
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
        // partner follows with his lowest each time; count tricks until he has to overtake
        int t = 0;
        u64 lead = mast, part = po;
        while (lead) {
            int c = 63 - __builtin_clzll(lead);
            lead ^= 1ULL << c;
            t++;
            if (!part) continue;
            int low = __builtin_ctzll(part);
            part ^= 1ULL << low;
            if (low > c) break;                      // partner wins the trick: stop here
        }
        unsafeMax = std::max(unsafeMax, t);
    }
    return safeSum + unsafeMax;
}

// Upper bound with a defender on lead: masters (unseen cards above every North-South card of the suit)
// that the leader can be given and cash while both declaring hands must follow or cannot ruff.
static inline int defCash(const Pos& p) {
    int i = p.leader >> 1;
    int must = 0;
    for (int s = 0; s < 4; s++) if (p.vd[1 - i] >> s & 1) must += pc(p.pool & sm(s));
    int freeSlots = p.cnt[i] - must, t = 0;
    for (int s = 0; s < 4; s++) {
        u64 x = (p.pool >> (13 * s)) & S13;
        if (!x || (p.vd[i] >> s & 1)) continue;
        u64 n = (p.hN >> (13 * s)) & S13, so = (p.hS >> (13 * s)) & S13;
        bool nRuff = TRUMP < 4 && s != TRUMP && (p.hN & sm(TRUMP)), sRuff = TRUMP < 4 && s != TRUMP && (p.hS & sm(TRUMP));
        u64 ns = n | so;
        int top = ns ? 63 - __builtin_clzll(ns) : -1;
        int masters = pc(x & ~((1ULL << (top + 1)) - 1));
        if (nRuff) masters = std::min(masters, pc(n));
        if (sRuff) masters = std::min(masters, pc(so));
        if (masters <= 0) continue;
        if (p.vd[1 - i] >> s & 1) t += masters;      // his anyway
        else { int take = std::min(masters, freeSlots); t += take; freeSlots -= take; }
    }
    return std::min(t, (int)p.cnt[i]);
}

// Quick tricks with both declaring hands (after DDS's QuickTricks, simplified): a line of play in which every
// trick is certain, counted until the certainty runs out. With North or South on lead and in suits the defenders
// cannot ruff: cash a master (a card above every unseen card of its suit); or lead low to a master in partner's
// hand. Any such line is a lower bound, whatever the defenders hold or play. Masters are judged against the
// unseen cards as they are now, which only gets easier as unseen cards are played.
static bool USE_RUN = true, RUN_FRONT = true;
static inline int declRun(const Pos& p) {
    u64 h[2] = {p.hN, p.hS};
    int me = p.leader == 0 ? 0 : 1;
    bool ruff = TRUMP < 4 && (p.pool & sm(TRUMP));
    u64 mast[2] = {0, 0};                       // masters by hand
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
            // cash a master; prefer a suit where partner can follow with a card below it or has none
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
                if (low > c) me = pd;                           // partner had to overtake
            } else if (h[pd]) {
                u64 spare = h[pd] & ~mast[pd];                  // throw a card that is not a master if he has one
                h[pd] ^= bit(__builtin_ctzll(spare ? spare : h[pd]));
            }
            continue;
        }
        // no master here: lead low to a master in partner's hand
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

// Bounds that hold whoever is on lead (after DDS's later-tricks checks, for trumps only).
// A trump above every trump of the other side wins the trick it is played on for its side, and the trumps of one
// hand go on different tricks. So North-South win at least as many tricks as the larger of their two holdings of
// such trumps, and the defenders at least as many as one defender can be given of theirs.
static bool USE_TRUMP_BOUNDS = true;
static inline int declTrumpSure(const Pos& p) {
    if (TRUMP >= 4) return 0;
    u64 x = (p.pool >> (13 * TRUMP)) & S13;
    int top = x ? 63 - __builtin_clzll(x) : -1;
    u64 above = ~((1ULL << (top + 1)) - 1) & S13;
    return std::max(pc((p.hN >> (13 * TRUMP)) & above), pc((p.hS >> (13 * TRUMP)) & above));
}
static inline int defTrumpSure(const Pos& p) {
    if (TRUMP >= 4) return 0;
    u64 x = (p.pool >> (13 * TRUMP)) & S13;
    if (!x) return 0;
    u64 ns = ((p.hN | p.hS) >> (13 * TRUMP)) & S13;
    int top = ns ? 63 - __builtin_clzll(ns) : -1;
    int t = pc(x & ~((1ULL << (top + 1)) - 1));
    if (!t) return 0;
    int best = 0;
    for (int i = 0; i < 2; i++) {
        if (p.vd[i] >> TRUMP & 1) continue;                               // he has no trumps
        if (p.vd[1 - i] >> TRUMP & 1) { best = std::max(best, t); continue; }   // he has all of them
        int must = 0;
        for (int s = 0; s < 4; s++) if (p.vd[1 - i] >> s & 1) must += pc(p.pool & sm(s));
        best = std::max(best, std::min(t, (int)p.cnt[i] - must));
    }
    return best;
}

// ---------------------------------------------------------------- search
static int tableValue(const Pos& p);

static bool can(const Pos& p, int need) {
    if (need <= 0) return true;
    int seat = (p.leader + p.nt) & 3;
    int left = seat == 0 ? pc(p.hN) : seat == 2 ? pc(p.hS) : p.cnt[seat >> 1];
    if (left < need) return false;
    Entry* e = nullptr;
    Key tk{0, 0};
    int ttBest = -1, cutCard = -1;
    if (p.nt == 0) {
        if (FRONT && left == FRONT && !IN_ORACLE) {
            for (int i = 0; i < DUPBOUND; i++) { Pos q = p; q.vd[0] ^= VZERO; dupSink = dupSink + ((seat & 1) == 0 ? declCash(q) : defCash(q)); }
            if (USE_BOUNDS) {                       // cheap bounds first: many frontier positions never need the probe
                if ((seat & 1) == 0) { if (declCash(p) >= need) return true; if (RUN_FRONT && declRun(p) >= need) return true; }
                else { if (left - defCash(p) < need) return false; }
                if (USE_TRUMP_BOUNDS && TRUMP < 4) {
                    if (declTrumpSure(p) >= need) return true;
                    if (left - defTrumpSure(p) < need) return false;
                }
            }
            return tableValue(p) >= need;
        }
        tk = ttKey(p);
        e = ttFind(tk, true);
        if (need <= e->lo) { ttHits++; return true; }
        if (need > e->hi) { ttHits++; return false; }
        ttBest = e->best;
        if (USE_BOUNDS) {
            if ((seat & 1) == 0) {
                int t = declCash(p);
                if (t > e->lo) e->lo = (int8_t)std::min(t, left);
                if (need <= e->lo) return true;
                if (USE_RUN) {
                    t = declRun(p);
                    if (t > e->lo) e->lo = (int8_t)std::min(t, left);
                    if (need <= e->lo) return true;
                }
            } else {
                int t = defCash(p);
                if (left - t < e->hi) e->hi = (int8_t)(left - t);
                if (need > e->hi) return false;
            }
            if (USE_TRUMP_BOUNDS && TRUMP < 4) {
                int a = declTrumpSure(p), d = defTrumpSure(p);
                if (a > e->lo) e->lo = (int8_t)std::min(a, left);
                if (left - d < e->hi) e->hi = (int8_t)(left - d);
                if (need <= e->lo) return true;
                if (need > e->hi) return false;
            }
        }
    }
    if (IN_ORACLE) nodesBelow++; else { nodesAbove++; levelNodes[left][p.nt]++; }
    u64 probes0 = probes;
    u64 live = p.hN | p.hS | p.pool;
    for (int k = 0; k < p.nt; k++) live |= bit(p.tc[k]);
    Move mv[40];
    bool result;
    int holder = 0, bestc = 0, bs = 0;         // the trick so far: seat winning it, its card, that card's suit
    if (p.nt) {
        int b = 0;
        for (int k = 1; k < p.nt; k++) {
            int sb = p.tc[b] / 13, sk = p.tc[k] / 13;
            if (sk == sb) { if (p.tc[k] > p.tc[b]) b = k; }
            else if (sk == TRUMP) b = k;
        }
        holder = (p.leader + b) & 3; bestc = p.tc[b]; bs = bestc / 13;
    }
    if ((seat & 1) == 0) {
        int n = genDecl(p, seat, live, mv);
        if (USE_ORDER) {
            u64 h = seat == 0 ? p.hN : p.hS;
            for (int k = 0; k < n; k++) {
                int c = mv[k].card, s = c / 13, r = c % 13, sc = 0, cs = s;
                u64 x = (p.pool >> (13 * s)) & S13;
                bool master = !(x >> (r + 1));               // no unseen card above it
                if (c == ttBest) sc += 1000;
                if (p.nt == 0) {
                    if (master) sc += 60 + (s == TRUMP ? 10 : 0);
                    else sc += 20 - r;                         // low cards before middling ones
                    sc += pc((h >> (13 * s)) & S13);          // longer suits first
                } else {
                    bool win = cs == bs ? c > bestc : cs == TRUMP;
                    if ((holder & 1) == 0) sc += 30 - r;      // partner is winning: play low
                    else if (win) sc += 50 - r;               // win as cheaply as possible
                    else sc += 20 - r;
                }
                if (USE_KILLER && p.nt == 0) { if (c == killer[left][seat][0]) sc += 200; else if (c == killer[left][seat][1]) sc += 150; }
                if (USE_HIST) sc += (int)std::min<uint32_t>(hist[0][c] >> 6, 45);
                mv[k].score = (int16_t)sc;
            }
        }
        result = false;
        for (int k = 0; k < n; k++) {
            if (USE_ORDER) pickBest(mv, k, n);
            if (advance(p, seat, mv[k].card, 0, need)) { result = true; cutCard = mv[k].card; if (!IN_ORACLE) cutAt[0][p.nt == 0][std::min(k, 5)]++; if (USE_HIST) hist[0][mv[k].card] += left * left; break; }
        }
    } else {
        int i = seat >> 1;
        int n = genDef(p, i, live, mv);
        if (USE_ORDER) {
            for (int k = 0; k < n; k++) {
                int c = mv[k].card, s = c / 13, r = c % 13, sc = 0, cs = s;
                if (c == ttBest) sc += 1000;
                if (p.nt == 0) {
                    u64 ns = ((p.hN | p.hS) >> (13 * s)) & S13;
                    bool master = !(ns >> (r + 1));
                    sc += master ? 60 : 10 + r;
                } else {
                    bool win = cs == bs ? c > bestc : cs == TRUMP;
                    if (holder & 1) sc += 25 - r + (win ? 10 : 0);   // partner is winning: usually low, sometimes overtake
                    else if (win) sc += 50 - r;
                    else sc += 20 - r;
                }
                if (USE_KILLER && p.nt == 0) { if (c == killer[left][seat][0]) sc += 200; else if (c == killer[left][seat][1]) sc += 150; }
                if (USE_HIST) sc += (int)std::min<uint32_t>(hist[1][c] >> 6, 45);
                mv[k].score = (int16_t)sc;
            }
        }
        result = true;
        for (int k = 0; k < n; k++) {
            if (USE_ORDER) pickBest(mv, k, n);
            if (!advance(p, seat, mv[k].card, mv[k].nv, need)) { result = false; cutCard = mv[k].card; if (!IN_ORACLE) cutAt[1][p.nt == 0][std::min(k, 5)]++; if (USE_HIST) hist[1][mv[k].card] += left * left; break; }
        }
    }
    if (cutCard < 0 && !IN_ORACLE) allNodes[seat & 1][p.nt == 0]++;
    if (p.nt == 0 && !IN_ORACLE) { if (probes == probes0) subNoRead[left]++; else subRead[left]++; }
    if (cutCard >= 0 && p.nt == 0 && killer[left][seat][0] != cutCard) { killer[left][seat][1] = killer[left][seat][0]; killer[left][seat][0] = (int8_t)cutCard; }
    if (p.nt == 0) {
        if (!(e->used && e->k == tk)) e = ttFind(tk, true);   // still ours unless it was replaced meanwhile
        if (cutCard >= 0) e->best = (int8_t)cutCard;
        if (result) { if (need > e->lo) e->lo = (int8_t)need; }
        else { if (need - 1 < e->hi) e->hi = (int8_t)(need - 1); }
    }
    return result;
}

static int valueOf(const Pos& p, int left) {
    int v = left;
    while (v > 0 && !can(p, v)) v--;
    return v;
}

static int tableValue(const Pos& p) {
    probes++;
    if (SEQ_READ && seqPos < SEQ.size()) return SEQ[seqPos++];
#ifdef ENDTABLE
    if (ET) {                                   // show-outs as exact lengths: East void = 0, West void = all of them
        int8_t el[4];
        for (int s = 0; s < 4; s++)
            el[s] = (p.vd[0] >> s & 1) ? 0 : (p.vd[1] >> s & 1) ? (int8_t)pc(p.pool & sm(s)) : -1;
        return endtable_lookup(ET, p.hN, p.hS, p.pool, el, TRUMP, p.leader);
    }
#endif
    Key k = frontKey(p);
    for (int i = 0; i < DUPKEY; i++) { Pos q = p; q.vd[0] ^= VZERO; dupSink = dupSink + frontKey(q).a; }
    size_t slot = 0;
    uint32_t tag = 0;
    if (NCELLS) {
        slot = (size_t)(((unsigned __int128)KeyHash()(k) * NCELLS) >> 64);
        tag = (uint32_t)(hash2(k) >> 40) | 1;
        if (CELLS_READ) {
            size_t sl = slot;
            for (;;) {
                uint32_t c = CELLS[sl];
                if ((c >> 8) == tag) return (int)(c & 0xFF);
                if (c == 0) break;
                if (++sl == NCELLS) sl = 0;
            }
            cellMisses++;                     // not met in the fill pass: fall back to the map
        }
    }
    if (!BIG.empty()) bigSink += BIG[KeyHash()(k) % BIG.size()];
    int v;
    auto it = TABLE.find(k);
    if (it != TABLE.end()) v = it->second;
    else {
        auto t0 = std::chrono::steady_clock::now();
        IN_ORACLE = true;
        v = valueOf(p, FRONT);
        IN_ORACLE = false;
        oracleSeconds += std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
        TABLE.emplace(k, (uint8_t)v);
    }
    if (NCELLS) {
        for (;;) {
            uint32_t c = CELLS[slot];
            if (c == 0) { CELLS[slot] = tag << 8 | (uint32_t)v; cellTouched.push_back(slot); break; }
            if ((c >> 8) == tag) break;
            if (++slot == NCELLS) slot = 0;
        }
    }
    if (SEQ_RECORD) SEQ.push_back((uint8_t)v);
    return v;
}

int main(int argc, char** argv) {
    int ttBits = 18, needArg = -1;
    double memGB = 0, cellsGB = 0;
    bool warm = false, stats = false, valueMode = false, noFlush = false, huge = false, hugeTT = false, replay = false;
    bool keep = false;
    for (int i = 1; i < argc; i++) {
        std::string a = argv[i];
        if (a == "--front") FRONT = atoi(argv[++i]);
        else if (a == "--ttbits") ttBits = atoi(argv[++i]);
        else if (a == "--nobounds") USE_BOUNDS = false;
        else if (a == "--notrumpbounds") USE_TRUMP_BOUNDS = false;
        else if (a == "--norun") USE_RUN = false;
        else if (a == "--norunfront") RUN_FRONT = false;
        else if (a == "--noorder") USE_ORDER = false;
        else if (a == "--nokiller") USE_KILLER = false;
        else if (a == "--hist") USE_HIST = true;        // history heuristic: measured no gain, off by default
        else if (a == "--mem") memGB = atof(argv[++i]);
        else if (a == "--cells") cellsGB = atof(argv[++i]);
        else if (a == "--dupkey") DUPKEY = atoi(argv[++i]);
        else if (a == "--huge") huge = true;            // 2 MB pages for the cells
        else if (a == "--hugett") hugeTT = true;        // 2 MB pages for the transposition table
        else if (a == "--dupbound") DUPBOUND = atoi(argv[++i]);
        else if (a == "--replay") replay = true;
#ifdef ENDTABLE
        else if (a == "--table") { ET = endtable_open(argv[++i]); if (!ET) { fprintf(stderr, "cannot open table\n"); return 1; } }
#endif
        else if (a == "--noflush") noFlush = true;      // leave the table lines in cache after the fill pass
        else if (a == "--stats") stats = true;
        else if (a == "--value") valueMode = true;     // one number per position (what a table entry holds), not per card
        else if (a == "--warm") warm = true;          // fill the table in an untimed first pass, then time a second pass from a cold TT
        else if (a == "--keep") keep = true;          // keep table and TT between positions
        else if (a == "--need") needArg = atoi(argv[++i]);   // only ask: does each card guarantee this many more tricks?
    }
#ifdef ENDTABLE
    if (ET && endtable_cards(ET) != FRONT) { fprintf(stderr, "--front must equal the table's hand size (%d)\n", endtable_cards(ET)); return 1; }
#endif
    TTMASK = (1ULL << ttBits) - 1;
    TT = (Entry*)allocBig((TTMASK + 1) * sizeof(Entry), hugeTT);
    ttClear();
    if (memGB > 0) { BIG.assign((size_t)(memGB * (1ULL << 30)), 1); }
    if (cellsGB > 0) {
        NCELLS = (size_t)(cellsGB * (1ULL << 30) / 4);
        CELLS = (uint32_t*)allocBig(NCELLS * 4, huge);
        memset(CELLS, 0, NCELLS * 4);
    }
    if (stats) {                      // how much of this process is on 2 MB pages
        FILE* f = fopen("/proc/self/smaps_rollup", "r"); char buf[256];
        while (f && fgets(buf, sizeof buf, f)) if (!strncmp(buf, "AnonHugePages", 13) || !strncmp(buf, "Rss", 3)) fputs(buf, stderr);
        if (f) fclose(f);
    }
    std::vector<uint8_t> FLUSH(warm ? (96u << 20) : 0, 1);
    std::string line;
    while (std::getline(std::cin, line)) {
        if (line.empty() || line[0] == '#') continue;
        int needLine = needArg;
        if (line[0] == 'N') { needLine = atoi(line.c_str() + 1); line = line.substr(line.find(' ') + 1); }
        std::istringstream in(line);
        Pos p;
        memset(&p, 0, sizeof p);
        int trump, leader, cE, cW, vE, vW;
        std::string a, b, c;
        in >> trump >> leader >> a >> b >> c >> cE >> cW >> vE >> vW;
        TRUMP = trump;
        p.leader = (int8_t)leader;
        p.hN = strtoull(a.c_str(), nullptr, 16); p.hS = strtoull(b.c_str(), nullptr, 16); p.pool = strtoull(c.c_str(), nullptr, 16);
        p.cnt[0] = (uint8_t)cE; p.cnt[1] = (uint8_t)cW; p.vd[0] = (uint8_t)vE; p.vd[1] = (uint8_t)vW;
        int x;
        while (in >> x) p.tc[p.nt++] = (int8_t)x;
        if (!keep) {
            ttClear();
            TABLE.clear();
        }
        size_t table0 = TABLE.size();
        const int firstPass = warm ? (replay ? -1 : 0) : 1;
        int redo = 0;
        bool firstRun = true;
        for (int pass = firstPass; pass < 2; pass++) {
        bool show = pass == 1;
        size_t tsize0 = TABLE.size();
        if (warm && pass < 1 && !firstRun) ttClear();        // every untimed pass after the first starts from a clean table too
        CELLS_READ = warm && pass == 1 && NCELLS;
        SEQ_RECORD = replay && warm && pass == 0; SEQ_READ = replay && warm && pass == 1; seqPos = 0;
        if (SEQ_RECORD) SEQ.clear();
        if (firstRun) cellTouched.clear();
        firstRun = false;
        if (warm && pass == 1) {
            ttClear();
            // push the first pass's table lines out of the CPU caches so the timed probes are cold
            if (!BIG.empty()) { size_t n = std::min<size_t>(BIG.size(), 512u << 20); for (size_t i = 0; i < n; i += 64) bigSink += BIG[BIG.size() - 1 - i]; }
#ifdef SURE_X86
            if (!noFlush) for (size_t sl : cellTouched) _mm_clflush(&CELLS[sl]);            // table lines out of every cache level
#endif
            for (size_t i = 0; i < FLUSH.size(); i += 64) bigSink += FLUSH[i];   // and the rest of L1/L2 and the TLB
#ifdef SURE_X86
            _mm_mfence();
#endif
            table0 = TABLE.size();
        }
        nodesAbove = nodesBelow = probes = ttHits = cellMisses = 0;
        memset(levelNodes, 0, sizeof levelNodes); memset(cutAt, 0, sizeof cutAt); memset(allNodes, 0, sizeof allNodes); memset(subNoRead, 0, sizeof subNoRead); memset(subRead, 0, sizeof subRead);
        if (!keep) memset(hist, 0, sizeof hist);
        memset(killer, -1, sizeof killer);
        oracleSeconds = 0;
        auto t0 = std::chrono::steady_clock::now();
        int seat = (p.leader + p.nt) & 3;
        int left = seat == 0 ? pc(p.hN) : seat == 2 ? pc(p.hS) : p.cnt[seat >> 1];
        u64 live = p.hN | p.hS | p.pool;
        for (int k = 0; k < p.nt; k++) live |= bit(p.tc[k]);
        if (valueMode && p.nt == 0) {
            int v = valueOf(p, left);
            double tot = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
            if (show) printf("{\"left\": %d, \"value\": %d, \"seconds\": %.7f, \"search_seconds\": %.7f, \"nodes_above\": %llu, \"probes\": %llu}\n",
                             left, v, tot, tot - oracleSeconds, (unsigned long long)nodesAbove, (unsigned long long)probes);
            continue;
        }
        Move mv[40];
        int n = (seat & 1) == 0 ? genDecl(p, seat, live, mv) : genDef(p, seat >> 1, live, mv);
        if (show) printf("{\"left\": %d, \"cards\": {", left);
        for (int k = 0; k < n; k++) {
            int v;
            if (needLine >= 0) {
                v = advance(p, seat, mv[k].card, mv[k].nv, needLine) ? 1 : 0;     // 1 = guarantees needArg tricks
            } else {
                // value of the position after this card, in tricks from now on
                v = left;
                while (v > 0 && !advance(p, seat, mv[k].card, mv[k].nv, v)) v--;
            }
            if (show) printf("%s\"%d\": %d", k ? ", " : "", mv[k].card, v);
        }
        double total = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
        if (show) printf("}, \"seconds\": %.6f, \"search_seconds\": %.6f, \"nodes_above\": %llu, \"nodes_below\": %llu, \"probes\": %llu, "
               "\"table_new\": %zu, \"tt_hits\": %llu, \"cell_misses\": %llu, \"replay_left\": %lld}\n",
               total, total - oracleSeconds, (unsigned long long)nodesAbove, (unsigned long long)nodesBelow,
               (unsigned long long)probes, TABLE.size() - table0, (unsigned long long)ttHits, (unsigned long long)cellMisses, SEQ_READ ? (long long)SEQ.size() - (long long)seqPos : 0LL);
        fflush(stdout);
        if (show && stats)
            for (int l = 13; l >= 1; l--) if (subNoRead[l] | subRead[l])
                fprintf(stderr, "  lead nodes searched with %d cards left: %llu with no table read below, %llu with some\n", l, (unsigned long long)subNoRead[l], (unsigned long long)subRead[l]);
        if (show && stats)
            for (int a = 0; a < 2; a++) for (int b = 1; b >= 0; b--)
                fprintf(stderr, "  %s %s: settled by move 1: %llu, 2: %llu, 3: %llu, 4: %llu, 5: %llu, later: %llu; every move tried: %llu\n", a ? "defender" : "declarer", b ? "on lead " : "following",
                        (unsigned long long)cutAt[a][b][0], (unsigned long long)cutAt[a][b][1], (unsigned long long)cutAt[a][b][2], (unsigned long long)cutAt[a][b][3], (unsigned long long)cutAt[a][b][4], (unsigned long long)cutAt[a][b][5], (unsigned long long)allNodes[a][b]);
        // An untimed pass that still had to compute table values searched differently from the timed pass
        // (those computations disturb the transposition table). Repeat it until it needs none.
        if (warm && pass < 1 && TABLE.size() != tsize0 && ++redo < 10) { pass--; continue; }
        if (show && stats)
            for (int l = 13; l >= 1; l--)
                if (levelNodes[l][0] | levelNodes[l][1] | levelNodes[l][2] | levelNodes[l][3])
                    fprintf(stderr, "  %2d cards left: lead %llu, 2nd %llu, 3rd %llu, 4th %llu\n", l, (unsigned long long)levelNodes[l][0],
                            (unsigned long long)levelNodes[l][1], (unsigned long long)levelNodes[l][2], (unsigned long long)levelNodes[l][3]);
        }
    }
    return 0;
}
