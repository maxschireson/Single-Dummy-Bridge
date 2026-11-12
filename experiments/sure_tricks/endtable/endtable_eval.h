// One-trick evaluator for the ending-table build (TABLE_BUILD.md section 6.2).
// value(k-card entry) = minimax over the four plays of the trick of
//     (1 if North or South wins the trick) + table[k-1](position after the trick, winner on lead),  table[0] = 0.
// The rules of play and the knowledge update are a transcription of pooled_ref.py (defender_plays, normalize,
// trick_winner). Alpha-beta, fail-soft, over the range 0..k. No transposition table, bounds or move ordering.
//
// A defender's cards are never reduced: every pool card he may hold and legally play is tried, as in pooled_ref.py.
// Pool cards have no hand until played, so two pool cards with no declarer card between them are not equivalent: which
// one is played decides what partner can still do (REPORT.md, "Defender equivalences").
// equiv = false: every legal card for North and South too (a direct transcription of pooled_ref.py).
// equiv = true:  North or South plays one card per run of his own legal cards with no live card of another hand, and no
//                card of the current trick, between them.
#ifndef SDB_ENDTABLE_EVAL_H
#define SDB_ENDTABLE_EVAL_H

#include "endtable.h"

namespace endtable {

struct OneTrick {
    int k;                      // hand size of the entries evaluated
    const Index* prev;          // index of the (k-1)-card table; unused when k == 1
    const uint8_t* prevData;    // its data section
    int prevBits;
    bool equiv;
    u64 nodes = 0, leaves = 0;  // counters (per evaluator object)

    // per evaluation
    int trump = 4, leader = 0;
    int8_t tc[4];

    struct St {
        u64 hN, hS, pool;
        int cE, cW;
        int8_t el[4];
    };

    OneTrick(int k_, const Index* prev_, const uint8_t* prevData_, int prevBits_, bool equiv_)
        : k(k_), prev(prev_), prevData(prevData_), prevBits(prevBits_), equiv(equiv_) {}

    // Value of a k-card trick-boundary position with consistent knowledge.
    int value(const Position& p) {
        int x[4];
        St st;
        st.hN = p.hN; st.hS = p.hS; st.pool = p.pool; st.cE = k; st.cW = k;
        for (int s = 0; s < 4; s++) { x[s] = popc(p.pool >> (13 * s) & SUIT13); st.el[s] = p.el[s]; }
        if (!normalizeKnowledge(x, k, k, st.el)) { fprintf(stderr, "OneTrick: inconsistent knowledge\n"); abort(); }
        trump = p.trump;
        leader = p.leader;
        return node(st, 0, 0, k);
    }

    static inline u64 suit(int s) { return SUIT13 << (13 * s); }

    // Declaring side: the lowest card of each run of `cards` (a 13-bit rank mask of one suit of one hand), runs being
    // separated by any card of `block` (the live cards of the other three hands and the cards of the current trick).
    static inline int runReps(u64 cards, u64 block, int8_t* out, int base) {
        int n = 0, hi = -1;
        while (cards) {
            int r = __builtin_ctzll(cards);
            cards &= cards - 1;
            if (hi < 0 || (block & ((1ULL << r) - 1) & ~((2ULL << hi) - 1))) out[n++] = (int8_t)(base + r);
            hi = r;
        }
        return n;
    }

    inline int finish(const St& q) {
        leaves++;
        int best = 0;
        for (int i = 1; i < 4; i++) {
            int sb = tc[best] / 13, si = tc[i] / 13;
            if (si == sb) { if (tc[i] > tc[best]) best = i; }
            else if (si == trump) best = i;
        }
        int w = (leader + best) & 3;
        int ns = (w & 1) == 0;
        if (k == 1) return ns;
        u64 sl = prev->slot(q.hN, q.hS, q.pool, q.el, trump, w);
        if (sl >= prev->entries) { fprintf(stderr, "OneTrick: position after the trick has no slot\n"); abort(); }
        return ns + readEntry(prevData, prevBits, sl);
    }

    int node(const St& st, int nt, int alpha, int beta) {
        nodes++;
        int seat = (leader + nt) & 3;
        int led = nt ? tc[0] / 13 : -1;
        u64 trickCards = 0;
        for (int i = 0; i < nt; i++) trickCards |= 1ULL << tc[i];
        u64 live = st.hN | st.hS | st.pool | trickCards;
        int8_t mv[32];
        int n = 0;
        if ((seat & 1) == 0) {
            u64 h = seat == 0 ? st.hN : st.hS;
            u64 legal = h;
            if (led >= 0 && (h & suit(led))) legal = h & suit(led);
            if (equiv) {
                u64 others = live & ~h;
                for (int s = 0; s < 4; s++) {
                    u64 c = legal >> (13 * s) & SUIT13;
                    if (c) n += runReps(c, others >> (13 * s) & SUIT13, mv + n, 13 * s);
                }
            } else {
                for (u64 m = legal; m; m &= m - 1) mv[n++] = (int8_t)__builtin_ctzll(m);
            }
            int best = -1;
            for (int i = 0; i < n; i++) {
                int c = mv[i];
                St q = st;
                if (seat == 0) q.hN ^= 1ULL << c; else q.hS ^= 1ULL << c;
                tc[nt] = (int8_t)c;
                int a = alpha > best ? alpha : best;
                int v = nt == 3 ? finish(q) : node(q, nt + 1, a, beta);
                if (v > best) { best = v; if (best >= beta) break; }
            }
            return best;
        }
        bool east = seat == 1;
        int x[4];
        for (int s = 0; s < 4; s++) x[s] = popc(st.pool >> (13 * s) & SUIT13);
        int best = 99;
        for (int s = 0; s < 4; s++) {
            u64 cards = st.pool >> (13 * s) & SUIT13;
            if (!cards) continue;
            int8_t e2[4] = {st.el[0], st.el[1], st.el[2], st.el[3]};
            if (led >= 0 && s != led) {                 // not following: he holds none of the suit led
                int vv = east ? 0 : x[led];
                if (e2[led] < 0) e2[led] = (int8_t)vv;
                else if (e2[led] != vv) continue;
            }
            if (e2[s] >= 0) {                           // he must be able to hold a card of s
                if (east) { if (e2[s] < 1) continue; e2[s]--; }
                else if (x[s] - e2[s] < 1) continue;
            }
            int x2[4] = {x[0], x[1], x[2], x[3]};
            x2[s]--;
            if (!normalizeKnowledge(x2, st.cE - (east ? 1 : 0), st.cW - (east ? 0 : 1), e2)) continue;
            int m = 0;                                  // every card of the suit: no equivalences for a defender
            for (u64 c = cards; c; c &= c - 1) mv[m++] = (int8_t)(13 * s + __builtin_ctzll(c));
            for (int i = 0; i < m; i++) {
                int c = mv[i];
                St q = st;
                q.pool ^= 1ULL << c;
                if (east) q.cE--; else q.cW--;
                memcpy(q.el, e2, 4);
                tc[nt] = (int8_t)c;
                int b = beta < best ? beta : best;
                int v = nt == 3 ? finish(q) : node(q, nt + 1, alpha, b);
                if (v < best) { best = v; if (best <= alpha) return best; }
            }
        }
        return best;
    }
};

}  // namespace endtable

#endif  // SDB_ENDTABLE_EVAL_H
