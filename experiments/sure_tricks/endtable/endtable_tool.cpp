// Checks and utilities for the ending table (TABLE_BUILD.md section 8).
//
//   endtable_tool sizes                                   T1: counts for k = 1..4 against section 4.6
//   endtable_tool vectors FILE [k=TABLE ...]              T2/T4: slot and canonical line of every test vector; values if tables given
//   endtable_tool roundtrip K [SAMPLES] [SEED]            T2: unrank then rank; every slot when SAMPLES is 0
//   endtable_tool transform K SAMPLES [SEED]              T3: transformed positions map to the same slot
//   endtable_tool normdump                                knowledge normalization on every small state (for check_normalize.py)
//   endtable_tool mono TABLE SAMPLES [SEED]               T5: fixing an unknown suit's length never lowers the value
//   endtable_tool showout TABLE (all | SAMPLES) SEED EXPECT_FILE   sure_cpp --value input lines, entries with show-out knowledge only
//   endtable_tool equiv PREV SAMPLES [SEED]               T6: evaluator with and without card equivalences on random entries
//   endtable_tool evalbench K PREV SAMPLES [SEED] [plain] µs per entry of the one-trick evaluator
//   endtable_tool slotbench TABLE SAMPLES [SEED]          ns per slot computation and per lookup, random raw positions
//   endtable_tool verify TABLE                            header, counts and data hash; value histogram
//   endtable_tool line TABLE SLOT...                      canonical line and value of slots
// PREV is the (K-1)-card table (absent for K = 1: pass "-").
#include <chrono>
#include <cinttypes>
#include <fstream>
#include <iostream>
#include <map>
#include <random>
#include <string>
#include <thread>
#include <vector>

#include "endtable.h"
#include "endtable_eval.h"
#include "sha256.h"

using namespace endtable;

static double now() { return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count(); }

static std::string lineOf(const Position& p, int k) {
    char b[160];
    snprintf(b, sizeof b, "%d %d %" PRIx64 " %" PRIx64 " %" PRIx64 " %d %d", p.trump, p.leader, p.hN, p.hS, p.pool, k, k);
    std::string s = b;
    for (int i = 0; i < 4; i++) s += p.el[i] < 0 ? std::string(" -") : " " + std::to_string(p.el[i]);
    return s;
}

static bool parseLine(const std::string& l, Position& p, int& cE, int& cW) {
    char e[4][8];
    unsigned long long a, b, c;
    if (sscanf(l.c_str(), "%d %d %llx %llx %llx %d %d %7s %7s %7s %7s", &p.trump, &p.leader, &a, &b, &c, &cE, &cW, e[0], e[1], e[2], e[3]) != 11) return false;
    p.hN = a; p.hS = b; p.pool = c;
    for (int i = 0; i < 4; i++) p.el[i] = e[i][0] == '-' ? -1 : (int8_t)atoi(e[i]);
    return true;
}

static int poolLen(const Position& p, int s) { return popc(p.pool >> (13 * s) & SUIT13); }

// Random raw position sharing an entry with p (the transformations of check_endtable_ref.py, plus two more:
// a notrump entry given an empty suit as trump, and any set of exact lengths that normalization restores).
static Position transform(std::mt19937_64& rng, const Position& p0, int k) {
    Position p = p0;
    std::uniform_real_distribution<double> U(0, 1);
    int x[4];
    for (int s = 0; s < 4; s++) x[s] = poolLen(p, s);
    // forced lengths removed
    if (U(rng) < 0.5) {
        int8_t trial[4];
        for (int attempt = 0; attempt < 4; attempt++) {
            memcpy(trial, p.el, 4);
            for (int s = 0; s < 4; s++) if (trial[s] >= 0 && U(rng) < 0.5) trial[s] = -1;
            int8_t norm[4];
            memcpy(norm, trial, 4);
            if (normalizeKnowledge(x, k, k, norm) && memcmp(norm, p.el, 4) == 0) { memcpy(p.el, trial, 4); break; }
        }
    }
    // half-turn
    if (U(rng) < 0.5) {
        std::swap(p.hN, p.hS);
        for (int s = 0; s < 4; s++) if (p.el[s] >= 0) p.el[s] = (int8_t)(x[s] - p.el[s]);
        p.leader += 2;
    }
    // suit permutation (trump keeps its role) and new ranks in the same order
    int perm[4] = {0, 1, 2, 3};
    std::shuffle(perm, perm + 4, rng);
    Position q = p;
    q.hN = q.hS = q.pool = 0;
    for (int s = 0; s < 4; s++) {
        u64 live = (p.hN | p.hS | p.pool) >> (13 * s) & SUIT13;
        int L = popc(live);
        int ranks[13];
        for (int i = 0; i < 13; i++) ranks[i] = i;
        std::shuffle(ranks, ranks + 13, rng);
        std::sort(ranks, ranks + L);
        int i = 0;
        for (u64 m = live; m; m &= m - 1, i++) {
            int r = __builtin_ctzll(m);
            u64 src = 1ULL << (13 * s + r), dst = 1ULL << (13 * perm[s] + ranks[i]);
            if (p.hN & src) q.hN |= dst; else if (p.hS & src) q.hS |= dst; else q.pool |= dst;
        }
        q.el[perm[s]] = p.el[s];
    }
    q.trump = p.trump < 4 ? perm[p.trump] : 4;
    if (q.trump == 4 && U(rng) < 0.5) {             // an empty suit as trump is notrump
        int empty[4], ne = 0;
        for (int s = 0; s < 4; s++) if (!((q.hN | q.hS | q.pool) >> (13 * s) & SUIT13)) empty[ne++] = s;
        if (ne) q.trump = empty[rng() % ne];
    }
    return q;
}

static EndTable* openOrDie(const char* path, bool rows) {
    EndTable* t = endtable_open_ex(path, rows);
    if (!t) { fprintf(stderr, "cannot open table %s\n", path); exit(1); }
    return t;
}

static int lookupSlot(const EndTable* t, u64 slot) { return readEntry(t->data, t->ix.bits, slot); }

int main(int argc, char** argv) {
    if (argc < 2) { fprintf(stderr, "see the comment at the top of endtable_tool.cpp\n"); return 2; }
    std::string cmd = argv[1];

    if (cmd == "sizes") {
        struct Exp { u64 types, nc, np, tc, tp, entries, bytes; } E[5] = {
            {0, 0, 0, 0, 0, 0, 0},
            {32, 21, 69, 52, 144, 426, 107},
            {171, 1008, 21113, 3374, 63116, 168458, 42115},
            {544, 18290, 4725808, 68230, 16232054, 41915724, 10478931},
            {1230, 184288, 800290430, 711733, 2928416406ULL, 7457413672ULL, 2796530127ULL}};
        int bad = 0;
        for (int k = 1; k <= 4; k++) {
            double t0 = now();
            Index ix(k, true);
            double dt = now() - t0;
            bool ok = ix.types.size() == E[k].types && ix.nClasses[0] == E[k].nc && ix.M[0] == E[k].np && ix.nClasses[1] == E[k].tc &&
                      ix.M[1] == E[k].tp && ix.entries == E[k].entries && ix.dataBytes() == E[k].bytes;
            bad += !ok;
            printf("k=%d: %zu suit types; notrump %" PRIu64 " classes, %" PRIu64 " positions; trump %" PRIu64 " classes, %" PRIu64
                   " positions; entries %" PRIu64 "; %d bits; %" PRIu64 " bytes of data; class table %.3f s: %s\n",
                   k, ix.types.size(), ix.nClasses[0], ix.M[0], ix.nClasses[1], ix.M[1], ix.entries, ix.bits, ix.dataBytes(), dt,
                   ok ? "as specified" : "DIFFERS FROM SECTION 4.6");
        }
        return bad ? 1 : 0;
    }

    if (cmd == "vectors") {
        if (argc < 3) return 2;
        std::map<int, EndTable*> tables;
        for (int i = 3; i < argc; i++) {
            std::string a = argv[i];
            int k = atoi(a.substr(0, a.find('=')).c_str());
            tables[k] = openOrDie(a.substr(a.find('=') + 1).c_str(), true);
        }
        Index* ixs[5] = {nullptr, nullptr, nullptr, nullptr, nullptr};
        std::ifstream f(argv[2]);
        std::string l;
        u64 n[5] = {0}, badSlot[5] = {0}, badLine[5] = {0}, badVal[5] = {0}, valChecked[5] = {0};
        while (std::getline(f, l)) {
            if (l.empty()) continue;
            int k = atoi(l.c_str() + l.find("\"k\":") + 4);
            u64 slot = strtoull(l.c_str() + l.find("\"slot\":") + 7, nullptr, 10);
            size_t a = l.find("\"line\": \"") + 9;
            std::string ln = l.substr(a, l.find('"', a) - a);
            int value = atoi(l.c_str() + l.find("\"value\":") + 8);
            if (!ixs[k]) ixs[k] = new Index(k, true);
            Position p;
            int cE, cW;
            if (!parseLine(ln, p, cE, cW)) { fprintf(stderr, "bad line %s\n", l.c_str()); return 1; }
            n[k]++;
            u64 s = ixs[k]->slot(p);
            if (s != slot) { if (badSlot[k]++ < 3) fprintf(stderr, "k=%d slot %" PRIu64 ": endtable_slot gives %" PRIu64 " for %s\n", k, slot, s, ln.c_str()); }
            Position u;
            ixs[k]->unrank(slot, u);
            if (lineOf(u, k) != ln) { if (badLine[k]++ < 3) fprintf(stderr, "k=%d slot %" PRIu64 ": unrank gives %s, vector %s\n", k, slot, lineOf(u, k).c_str(), ln.c_str()); }
            if (tables.count(k)) {
                valChecked[k]++;
                int v = endtable_lookup(tables[k], p.hN, p.hS, p.pool, p.el, p.trump, p.leader);
                if (v != value) { if (badVal[k]++ < 5) fprintf(stderr, "k=%d slot %" PRIu64 ": table %d, vector %d (%s)\n", k, slot, v, value, ln.c_str()); }
            }
        }
        int bad = 0;
        for (int k = 1; k <= 4; k++) {
            if (!n[k]) continue;
            printf("k=%d: %" PRIu64 " vectors; slot mismatches %" PRIu64 "; unrank-line mismatches %" PRIu64, k, n[k], badSlot[k], badLine[k]);
            if (valChecked[k]) printf("; values checked %" PRIu64 ", mismatches %" PRIu64, valChecked[k], badVal[k]);
            printf("\n");
            bad += badSlot[k] + badLine[k] + badVal[k] > 0;
        }
        return bad ? 1 : 0;
    }

    if (cmd == "roundtrip" || cmd == "transform") {
        int k = atoi(argv[2]);
        u64 samples = argc > 3 ? strtoull(argv[3], nullptr, 10) : 0;
        u64 seed = argc > 4 ? strtoull(argv[4], nullptr, 10) : 1;
        Index ix(k, true);
        bool all = cmd == "roundtrip" && samples == 0;
        u64 count = all ? ix.entries : samples;
        int T = (int)std::max(1u, std::thread::hardware_concurrency());
        std::vector<u64> bad(T, 0);
        std::vector<std::string> example(T);
        double t0 = now();
        std::vector<std::thread> th;
        for (int w = 0; w < T; w++)
            th.emplace_back([&, w]() {
                std::mt19937_64 rng(seed * 1000003 + (u64)w);
                Position p;
                for (u64 i = w; i < count; i += (u64)T) {
                    u64 slot = all ? i : rng() % ix.entries;
                    ix.unrank(slot, p);
                    Position q = cmd == "transform" ? transform(rng, p, k) : p;
                    u64 s = ix.slot(q);
                    if (s != slot) { if (!bad[w]++) example[w] = std::to_string(slot) + " -> " + lineOf(q, k) + " -> " + std::to_string(s); }
                }
            });
        for (auto& t : th) t.join();
        u64 nb = 0;
        for (int w = 0; w < T; w++) { nb += bad[w]; if (!example[w].empty()) fprintf(stderr, "example: %s\n", example[w].c_str()); }
        printf("k=%d %s: %" PRIu64 " %s, failures %" PRIu64 " (%.1f s, %d threads)\n", k, cmd.c_str(), count,
               all ? "slots (every slot)" : "random slots", nb, now() - t0, T);
        return nb ? 1 : 0;
    }

    if (cmd == "normdump") {             // every pool of up to 8 cards by suit lengths, every split of counts, every knowledge
        u64 n = 0;
        for (int tot = 0; tot <= 8; tot++)
            for (int a = 0; a <= tot; a++) for (int b = 0; a + b <= tot; b++) for (int c = 0; a + b + c <= tot; c++) {
                int x[4] = {a, b, c, tot - a - b - c};
                for (int cE = -1; cE <= tot + 1; cE++) {
                    int cW = tot - cE;
                    int8_t el[4];
                    for (int e0 = -1; e0 <= x[0] + 1; e0++) for (int e1 = -1; e1 <= x[1] + 1; e1++)
                        for (int e2 = -1; e2 <= x[2] + 1; e2++) for (int e3 = -1; e3 <= x[3] + 1; e3++) {
                            el[0] = (int8_t)e0; el[1] = (int8_t)e1; el[2] = (int8_t)e2; el[3] = (int8_t)e3;
                            int8_t o[4];
                            memcpy(o, el, 4);
                            bool ok = normalizeKnowledge(x, cE, cW, o);
                            printf("%d %d %d %d %d %d %d %d %d %d", x[0], x[1], x[2], x[3], cE, cW, e0, e1, e2, e3);
                            if (ok) printf(" -> %d %d %d %d\n", o[0], o[1], o[2], o[3]); else printf(" -> none\n");
                            n++;
                        }
                }
            }
        fprintf(stderr, "%" PRIu64 " states\n", n);
        return 0;
    }

    if (cmd == "mono") {
        EndTable* t = openOrDie(argv[2], true);
        u64 samples = strtoull(argv[3], nullptr, 10), seed = argc > 4 ? strtoull(argv[4], nullptr, 10) : 1;
        const Index& ix = t->ix;
        int k = ix.k;
        std::mt19937_64 rng(seed);
        u64 entries = 0, checks = 0, bad = 0, draws = 0;
        Position p;
        double t0 = now();
        while (entries < samples) {
            u64 slot = rng() % ix.entries;
            draws++;
            ix.unrank(slot, p);
            int x[4], unk = 0;
            for (int s = 0; s < 4; s++) { x[s] = poolLen(p, s); if (p.el[s] < 0) unk++; }
            if (!unk) continue;
            entries++;
            int v = lookupSlot(t, slot);
            for (int s = 0; s < 4; s++) {
                if (p.el[s] >= 0) continue;
                for (int e = 0; e <= x[s]; e++) {
                    int8_t el[4];
                    memcpy(el, p.el, 4);
                    el[s] = (int8_t)e;
                    int8_t norm[4];
                    memcpy(norm, el, 4);
                    if (!normalizeKnowledge(x, k, k, norm)) continue;
                    checks++;
                    int w = endtable_lookup(t, p.hN, p.hS, p.pool, el, p.trump, p.leader);
                    if (w < v) { if (bad++ < 5) fprintf(stderr, "k=%d slot %" PRIu64 " value %d; with East holding %d of suit %d: %d (%s)\n", k, slot, v, e, s, w, lineOf(p, k).c_str()); }
                }
            }
        }
        printf("k=%d mono: %" PRIu64 " random entries with an unknown suit (%" PRIu64 " drawn), %" PRIu64 " fixed-length comparisons, %" PRIu64 " lower (%.1f s)\n",
               k, entries, draws, checks, bad, now() - t0);
        return bad ? 1 : 0;
    }

    if (cmd == "showout") {
        EndTable* t = openOrDie(argv[2], true);
        bool all = std::string(argv[3]) == "all";
        u64 samples = all ? 0 : strtoull(argv[3], nullptr, 10), seed = strtoull(argv[4], nullptr, 10);
        FILE* ex = fopen(argv[5], "w");
        const Index& ix = t->ix;
        int k = ix.k;
        std::mt19937_64 rng(seed);
        Position p;
        u64 emitted = 0, examined = 0;
        std::vector<char> buf;
        for (u64 i = 0; all ? i < ix.entries : emitted < samples; i++) {
            u64 slot = all ? i : rng() % ix.entries;
            examined++;
            ix.unrank(slot, p);
            int vE = 0, vW = 0;
            bool ok = true;
            for (int s = 0; s < 4; s++) {
                int x = poolLen(p, s);
                if (p.el[s] < 0 || x == 0) continue;
                if (p.el[s] == 0) vE |= 1 << s;
                else if (p.el[s] == x) vW |= 1 << s;
                else ok = false;
            }
            if (!ok) continue;
            printf("%d %d %" PRIx64 " %" PRIx64 " %" PRIx64 " %d %d %d %d\n", p.trump, p.leader, p.hN, p.hS, p.pool, k, k, vE, vW);
            fprintf(ex, "%" PRIu64 " %d\n", slot, lookupSlot(t, slot));
            emitted++;
        }
        fclose(ex);
        fprintf(stderr, "k=%d showout: %" PRIu64 " entries emitted of %" PRIu64 " examined\n", k, emitted, examined);
        return 0;
    }

    if (cmd == "equiv" || cmd == "evalbench") {
        int k;
        const char* prevPath;
        int a = 2;
        if (cmd == "evalbench") k = atoi(argv[a++]);
        prevPath = argv[a++];
        EndTable* prev = std::string(prevPath) == "-" ? nullptr : openOrDie(prevPath, false);
        if (cmd == "equiv") k = prev ? endtable_cards(prev) + 1 : 1;
        u64 samples = strtoull(argv[a++], nullptr, 10);
        u64 seed = argc > a ? strtoull(argv[a++], nullptr, 10) : 1;
        bool plainOnly = argc > a && std::string(argv[a]) == "plain";
        Index ix(k, true);
        int T = (int)std::max(1u, std::thread::hardware_concurrency());
        if (cmd == "evalbench") T = 1;
        std::vector<u64> bad(T, 0), nodesE(T, 0), leavesE(T, 0), nodesP(T, 0), leavesP(T, 0);
        std::vector<double> tE(T, 0), tP(T, 0);
        std::vector<std::thread> th;
        double t0 = now();
        for (int w = 0; w < T; w++)
            th.emplace_back([&, w]() {
                std::mt19937_64 rng(seed * 7919 + (u64)w);
                const Index* pix = prev ? &prev->ix : nullptr;
                const uint8_t* pd = prev ? prev->data : nullptr;
                int pb = prev ? prev->ix.bits : 0;
                OneTrick eq(k, pix, pd, pb, true), pl(k, pix, pd, pb, false);
                std::vector<Position> ps;
                u64 mine = samples / (u64)T + ((u64)w < samples % (u64)T);
                ps.resize(mine);
                for (u64 i = 0; i < mine; i++) ix.unrank(rng() % ix.entries, ps[i]);
                std::vector<uint8_t> ve(mine), vp(mine);
                double s0 = now();
                if (!plainOnly) for (u64 i = 0; i < mine; i++) ve[i] = (uint8_t)eq.value(ps[i]);
                double s1 = now();
                if (cmd == "equiv" || plainOnly) for (u64 i = 0; i < mine; i++) vp[i] = (uint8_t)pl.value(ps[i]);
                double s2 = now();
                tE[w] = s1 - s0; tP[w] = s2 - s1;
                nodesE[w] = eq.nodes; leavesE[w] = eq.leaves; nodesP[w] = pl.nodes; leavesP[w] = pl.leaves;
                if (cmd == "equiv")
                    for (u64 i = 0; i < mine; i++)
                        if (ve[i] != vp[i] && bad[w]++ < 3) fprintf(stderr, "k=%d: equivalences %d, plain %d at %s\n", k, ve[i], vp[i], lineOf(ps[i], k).c_str());
            });
        for (auto& t : th) t.join();
        u64 nb = 0, ne = 0, le = 0, np = 0, lp = 0;
        double te = 0, tp = 0;
        for (int w = 0; w < T; w++) { nb += bad[w]; ne += nodesE[w]; le += leavesE[w]; np += nodesP[w]; lp += leavesP[w]; te += tE[w]; tp += tP[w]; }
        double n = (double)samples;
        if (cmd == "equiv")
            printf("k=%d equiv: %" PRIu64 " random entries, %" PRIu64 " differ; with equivalences %.2f core-us %.1f nodes %.1f leaves per entry, plain %.2f core-us %.1f nodes %.1f leaves (%.0f s, %d threads)\n",
                   k, samples, nb, 1e6 * te / n, ne / n, le / n, 1e6 * tp / n, np / n, lp / n, now() - t0, T);
        else if (plainOnly)
            printf("k=%d evalbench plain: %" PRIu64 " random entries, %.3f us, %.1f nodes, %.1f leaves per entry\n", k, samples, 1e6 * tp / n, np / n, lp / n);
        else
            printf("k=%d evalbench equivalences: %" PRIu64 " random entries, %.3f us, %.1f nodes, %.1f leaves per entry\n", k, samples, 1e6 * te / n, ne / n, le / n);
        return nb ? 1 : 0;
    }

    if (cmd == "slotbench") {
        EndTable* t = openOrDie(argv[2], true);
        u64 samples = strtoull(argv[3], nullptr, 10), seed = argc > 4 ? strtoull(argv[4], nullptr, 10) : 1;
        const Index& ix = t->ix;
        std::mt19937_64 rng(seed);
        std::vector<Position> ps(samples);
        std::vector<u64> want(samples);
        for (u64 i = 0; i < samples; i++) {
            want[i] = rng() % ix.entries;
            Position p;
            ix.unrank(want[i], p);
            ps[i] = transform(rng, p, ix.k);
        }
        double best = 1e9, bestL = 1e9;
        u64 sink = 0, bad = 0;
        for (int rep = 0; rep < 5; rep++) {
            double t0 = now();
            for (u64 i = 0; i < samples; i++) sink += endtable_slot(t, ps[i].hN, ps[i].hS, ps[i].pool, ps[i].el, ps[i].trump, ps[i].leader);
            double t1 = now();
            for (u64 i = 0; i < samples; i++) sink += (u64)endtable_lookup(t, ps[i].hN, ps[i].hS, ps[i].pool, ps[i].el, ps[i].trump, ps[i].leader);
            double t2 = now();
            best = std::min(best, t1 - t0);
            bestL = std::min(bestL, t2 - t1);
        }
        for (u64 i = 0; i < samples; i++) bad += endtable_slot(t, ps[i].hN, ps[i].hS, ps[i].pool, ps[i].el, ps[i].trump, ps[i].leader) != want[i];
        printf("k=%d slotbench: %" PRIu64 " random raw positions, best of 5: slot %.1f ns, slot + read %.1f ns; wrong slots %" PRIu64 " (sink %" PRIu64 ")\n",
               ix.k, samples, 1e9 * best / (double)samples, 1e9 * bestL / (double)samples, bad, sink & 1);
        return bad ? 1 : 0;
    }

    if (cmd == "verify") {
        EndTable* t = openOrDie(argv[2], false);
        const Index& ix = t->ix;
        Sha256 h;
        h.update(t->data, (size_t)ix.dataBytes());
        uint8_t d[32];
        h.final(d);
        bool hashOk = memcmp(d, t->header.sha256, 32) == 0;
        bool tailOk = true;
        u64 tailBits = ix.dataBytes() * 8 - ix.entries * (u64)ix.bits;
        if (tailBits) tailOk = (t->data[ix.dataBytes() - 1] >> (8 - tailBits)) == 0;
        for (u64 i = 0; i < TAIL_ZERO_BYTES; i++) tailOk = tailOk && t->data[ix.dataBytes() + i] == 0;
        std::vector<u64> hist(8, 0);
        for (u64 s = 0; s < ix.entries; s++) hist[readEntry(t->data, ix.bits, s)]++;
        printf("{\"file\": \"%s\", \"k\": %d, \"entries\": %" PRIu64 ", \"sha256\": \"%s\", \"hash_ok\": %s, \"padding_zero\": %s, \"histogram\": [",
               argv[2], ix.k, ix.entries, hex32(d).c_str(), hashOk ? "true" : "false", tailOk ? "true" : "false");
        for (int v = 0; v <= ix.k; v++) printf("%s%" PRIu64, v ? ", " : "", hist[v]);
        u64 over = 0;
        for (int v = ix.k + 1; v < 8; v++) over += hist[v];
        printf("], \"values_above_k\": %" PRIu64 "}\n", over);
        return hashOk && tailOk && !over ? 0 : 1;
    }

    if (cmd == "diff") {                 // entries where two tables of the same k differ
        EndTable* a = openOrDie(argv[2], true);
        EndTable* b = openOrDie(argv[3], false);
        u64 show = argc > 4 ? strtoull(argv[4], nullptr, 10) : 20;
        if (a->ix.k != b->ix.k) { fprintf(stderr, "different k\n"); return 1; }
        u64 n = 0;
        std::map<std::pair<int, int>, u64> pairs;
        for (u64 s = 0; s < a->ix.entries; s++) {
            int va = lookupSlot(a, s), vb = lookupSlot(b, s);
            if (va == vb) continue;
            pairs[{va, vb}]++;
            if (n++ < show) {
                Position p;
                a->ix.unrank(s, p);
                printf("%" PRIu64 " %s : %d vs %d\n", s, lineOf(p, a->ix.k).c_str(), va, vb);
            }
        }
        printf("k=%d: %" PRIu64 " of %" PRIu64 " entries differ;", a->ix.k, n, a->ix.entries);
        for (auto& kv : pairs) printf(" %d vs %d: %" PRIu64 ";", kv.first.first, kv.first.second, kv.second);
        printf("\n");
        return n ? 1 : 0;
    }

    if (cmd == "line") {
        EndTable* t = openOrDie(argv[2], true);
        for (int i = 3; i < argc; i++) {
            u64 slot = strtoull(argv[i], nullptr, 10);
            Position p;
            t->ix.unrank(slot, p);
            printf("%" PRIu64 " %s value %d\n", slot, lineOf(p, t->ix.k).c_str(), lookupSlot(t, slot));
        }
        return 0;
    }

    fprintf(stderr, "unknown command %s\n", cmd.c_str());
    return 2;
}
