// Ending table for the pooled-defender game: index (canonical form, class table, rank, unrank) and reader.
// Specification: ../TABLE_BUILD.md.  Normative references: ../endtable_ref.py (index), ../pooled_ref.py (game).
// C++17, no dependencies beyond the standard library and POSIX mmap. GCC or Clang (uses __builtin_popcountll).
//
// Public interface (section 7 of the specification), at global scope:
//     EndTable* endtable_open(const char* path);
//     void      endtable_close(EndTable*);
//     int       endtable_cards(const EndTable*);
//     uint64_t  endtable_slot(const EndTable*, hN, hS, pool, el, trump, leader);
//     int       endtable_lookup(const EndTable*, hN, hS, pool, el, trump, leader);
// Everything else lives in namespace endtable.
//
// Conventions: card = 13 * suit + rank, rank 0 (the two) .. 12 (the ace); seats 0..3 = N, E, S, W;
// trump 0..3, or 4 = notrump; el[s] = -1 unknown, else East's exact number of pool cards in suit s.
#ifndef SDB_ENDTABLE_H
#define SDB_ENDTABLE_H

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

#if defined(__BMI2__)
#include <immintrin.h>
#endif

#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

namespace endtable {

typedef uint64_t u64;
typedef uint32_t u32;

static const u64 SUIT13 = 0x1FFFULL;
static const int MAXK = 4;                 // largest hand size this code supports
static const u32 NONE32 = 0xFFFFFFFFu;

static inline int popc(u64 x) { return __builtin_popcountll(x); }

// ------------------------------------------------------------------------------------------ small tables
struct BinomTable { u32 c[17][9]; };       // c[n][r] = C(n, r), n <= 16, r <= 8
constexpr BinomTable makeBinom() {
    BinomTable t{};
    for (int n = 0; n < 17; n++)
        for (int r = 0; r < 9; r++) t.c[n][r] = 0;
    t.c[0][0] = 1;
    for (int n = 1; n < 17; n++) {
        t.c[n][0] = 1;
        for (int r = 1; r < 9; r++) t.c[n][r] = t.c[n - 1][r - 1] + t.c[n - 1][r];
    }
    return t;
}
static constexpr BinomTable BINOM = makeBinom();

// C(n, r) for small r and any n that keeps the result in 64 bits. Exact at every step.
static inline u64 choose(u64 n, int r) {
    if (r < 0 || (u64)r > n) return 0;
    u64 v = 1;
    for (int i = 1; i <= r; i++) v = v * (n - (u64)r + (u64)i) / (u64)i;
    return v;
}

// C(n, r) for r = 0..4 without division by a variable (divisors are constants). n <= 2^15 keeps it in 64 bits.
static inline u64 chooseSmall(u64 n, int r) {
    switch (r) {
    case 0: return 1;
    case 1: return n;
    case 2: return n < 2 ? 0 : n * (n - 1) / 2;
    case 3: return n < 3 ? 0 : n * (n - 1) * (n - 2) / 6;
    default: return n < 4 ? 0 : n * (n - 1) * (n - 2) * (n - 3) / 24;
    }
}

// Colex unrank of an r-subset of positions: the subset with colex rank `rank`, as a bit mask.
static inline u32 subsetUnrank(u32 rank, int r) {
    u32 mask = 0;
    for (int i = r; i >= 1; i--) {
        int c = i - 1;
        while (BINOM.c[c + 1][i] <= rank) c++;
        mask |= 1u << c;
        rank -= BINOM.c[c][i];
    }
    return mask;
}

// Colex rank of the set of positions in a 13-bit mask: sum of C(p_i, i) over its positions p_1 < p_2 < ...
// (exact for masks of up to 8 positions; the index uses it for at most MAXK)
struct ColexTable { uint16_t r[8192]; };
constexpr ColexTable makeColex() {
    ColexTable t{};
    for (u32 m = 0; m < 8192; m++) {
        u32 v = 0;
        int i = 0;
        for (int p = 0; p < 13 && i < 8; p++) if (m >> p & 1) v += BINOM.c[p][++i];     // masks used have <= 4 bits
        t.r[m] = (uint16_t)v;
    }
    return t;
}
static constexpr ColexTable COLEX = makeColex();

// Bits of x at the positions of mask, packed to the bottom (parallel bit extract).
static inline u64 extractBits(u64 x, u64 mask) {
#if defined(__BMI2__)
    return _pext_u64(x, mask);
#else
    u64 out = 0;
    int i = 0;
    for (u64 m = mask; m; m &= m - 1, i++) if (x & m & (0 - m)) out |= 1ULL << i;
    return out;
#endif
}

// Pattern rank of one suit. n, so, xx: 13-bit rank masks of North's, South's and the unseen cards.
static inline u32 patternRank(u64 n, u64 so, u64 xx) {
    u64 live = n | so | xx, oth = so | xx;
    u32 rn = COLEX.r[extractBits(n, live)];
    u32 rs = COLEX.r[extractBits(so, oth)];
    return rn * BINOM.c[popc(oth)][popc(so)] + rs;
}

// Inverse: position masks (bit i = the i-th lowest remaining card of the suit) for pattern rank r.
static inline void patternUnrank(u32 r, int n, int s, int x, u32& nmask, u32& smask) {
    int L = n + s + x;
    u32 cs = BINOM.c[L - n][s];
    u32 rn = r / cs, rs = r % cs;
    nmask = subsetUnrank(rn, n);
    u32 sub = subsetUnrank(rs, s);          // over the positions North does not hold, renumbered from 0
    smask = 0;
    int q = 0;
    for (u32 f = ((1u << L) - 1) & ~nmask; f; f &= f - 1, q++)
        if (sub >> q & 1) smask |= f & (0 - f);
}

// Knowledge normalization (pooled_ref.normalize). x[s] = pool cards in suit s. Returns false when no split of the
// pool is consistent. On success el holds the canonical knowledge: every forced length exact.
static inline bool normalizeKnowledge(const int x[4], int cE, int cW, int8_t el[4]) {
    if (cE < 0 || cW < 0 || cE + cW != x[0] + x[1] + x[2] + x[3]) return false;
    int eK = 0, wK = 0, unk = 0, nunk = 0;
    for (int s = 0; s < 4; s++) {
        if (x[s] == 0) el[s] = 0;
        int e = el[s];
        if (e < 0) { unk |= 1 << s; nunk++; continue; }
        if (e > x[s]) return false;
        eK += e;
        wK += x[s] - e;
    }
    if (eK > cE || wK > cW) return false;
    if (!nunk) return true;
    int eu = cE - eK, wu = cW - wK;         // East's and West's cards in the unknown suits; eu + wu = their pool cards
    if (eu == 0) { for (int s = 0; s < 4; s++) if (unk >> s & 1) el[s] = 0; }
    else if (wu == 0) { for (int s = 0; s < 4; s++) if (unk >> s & 1) el[s] = (int8_t)x[s]; }
    else if (nunk == 1) { for (int s = 0; s < 4; s++) if (unk >> s & 1) el[s] = (int8_t)eu; }
    return true;
}

// ------------------------------------------------------------------------------------------ index
struct TypeInfo {
    u32 P;                  // pattern count
    int8_t n, s, x, kn;     // North's, South's, unseen cards; knowledge code (-1 unknown, else East's length)
    uint8_t dig, rad;       // knowledge digit and radix inside a shape block: x ? kn + 1 : 0,  x ? x + 2 : 1
};

struct ClassRow {
    uint16_t id[4];         // type ids in canonical order
    u64 offset;             // positions in the classes before this one (same strain)
};

struct Position {           // a concrete position at a trick boundary
    u64 hN, hS, pool;
    int8_t el[4];
    int trump, leader;
};

struct Index {
    int k = 0;
    int bits = 0;                           // bits per entry in the table file
    int nTriples = 0;
    std::vector<TypeInfo> types;            // by type id
    std::vector<u64> radix;                 // radix[5 * id + m] = C(P + m - 1, m): multiset radix of m suits of this type
    uint16_t typeBase[MAXK + 1][MAXK + 1][2 * MAXK + 1];    // id of the first type of a triple (0xFFFF: no such triple)
    std::vector<ClassRow> rows[2];          // [0] notrump, [1] trump; in class order, plus one sentinel row (offset = M)
    u64 nClasses[2] = {0, 0};
    u64 M[2] = {0, 0};                      // positions per strain
    u64 base[2] = {0, 0};
    u64 entries = 0;
    // Fast class lookup: the four (n, s, x) triples in canonical order select a block, the knowledge codes an element.
    int nCompNS = 0, nCompX = 0;
    uint8_t compNS[125];                    // [(a0 * 5 + a1) * 5 + a2], a3 = k - a0 - a1 - a2  -> composition number
    uint16_t compX[729];                    // [(x0 * 9 + x1) * 9 + x2], x3 = 2k - x0 - x1 - x2 -> composition number
    std::vector<u32> shapeBase[2];          // [(cN * nCompNS + cS) * nCompX + cX] -> start of the block in knOff
    std::vector<u32> knOff;                 // class offset, or NONE32

    u64 dataBytes() const { return (entries * (u64)bits + 7) / 8; }

    explicit Index(int k_, bool keepRows = true) { build(k_, keepRows); }

    static bool knowledgeOk(int k, const TypeInfo* const t[4]) {
        int unknown = 0, eK = 0, wK = 0;
        for (int i = 0; i < 4; i++) {
            if (t[i]->kn < 0) unknown++;
            else { eK += t[i]->kn; wK += t[i]->x - t[i]->kn; }
        }
        if (!unknown) return eK == k && wK == k;
        return unknown >= 2 && eK < k && wK < k;
    }

    u64 classSize(int strain, const uint16_t id[4]) const {
        u64 size = 1;
        int i = 0;
        if (strain) { size = types[id[0]].P; i = 1; }
        while (i < 4) {
            int j = i + 1;
            while (j < 4 && id[j] == id[i]) j++;
            size *= choose((u64)types[id[i]].P + (u64)(j - i) - 1, j - i);
            i = j;
        }
        return size;
    }

    u32 shapeIndex(const uint16_t id[4]) const {
        const TypeInfo &a = types[id[0]], &b = types[id[1]], &c = types[id[2]], &d = types[id[3]];
        (void)d;
        u32 cN = compNS[(a.n * 5 + b.n) * 5 + c.n];
        u32 cS = compNS[(a.s * 5 + b.s) * 5 + c.s];
        u32 cX = compX[(a.x * 9 + b.x) * 9 + c.x];
        return (cN * (u32)nCompNS + cS) * (u32)nCompX + cX;
    }
    u32 knIndex(const uint16_t id[4]) const {
        const TypeInfo &a = types[id[0]], &b = types[id[1]], &c = types[id[2]], &d = types[id[3]];
        return ((a.dig * (u32)b.rad + b.dig) * (u32)c.rad + c.dig) * (u32)d.rad + d.dig;
    }

    void build(int k_, bool keepRows) {
        k = k_;
        if (k < 1 || k > MAXK) { fprintf(stderr, "endtable: hand size %d not supported\n", k); abort(); }
        bits = k <= 3 ? 2 : 3;
        // triples and types, in tuple order
        struct Tri { int8_t n, s, x; };
        std::vector<Tri> tri;
        std::vector<int> triFirstType;
        memset(typeBase, 0xFF, sizeof typeBase);
        types.clear();
        for (int n = 0; n <= k; n++)
            for (int s = 0; s <= k; s++)
                for (int x = 0; x <= 2 * k; x++) {
                    if (n + s + x > 13) continue;
                    tri.push_back({(int8_t)n, (int8_t)s, (int8_t)x});
                    triFirstType.push_back((int)types.size());
                    typeBase[n][s][x] = (uint16_t)types.size();
                    u32 P = BINOM.c[n + s + x][n] * BINOM.c[s + x][s];
                    for (int kn = (x == 0 ? 0 : -1); kn <= x; kn++)
                        types.push_back({P, (int8_t)n, (int8_t)s, (int8_t)x, (int8_t)kn,
                                         (uint8_t)(x ? kn + 1 : 0), (uint8_t)(x ? x + 2 : 1)});
                }
        nTriples = (int)tri.size();
        radix.assign(5 * types.size(), 0);
        for (size_t t = 0; t < types.size(); t++)
            for (int m = 0; m <= 4; m++) radix[5 * t + (size_t)m] = choose((u64)types[t].P + (u64)m - 1 + (m == 0), m);
        // compositions
        memset(compNS, 0xFF, sizeof compNS);
        nCompNS = 0;
        for (int a = 0; a <= k; a++) for (int b = 0; a + b <= k; b++) for (int c = 0; a + b + c <= k; c++)
            compNS[(a * 5 + b) * 5 + c] = (uint8_t)nCompNS++;
        memset(compX, 0xFF, sizeof compX);
        nCompX = 0;
        for (int a = 0; a <= 2 * k; a++) for (int b = 0; a + b <= 2 * k; b++) for (int c = 0; a + b + c <= 2 * k; c++)
            compX[(a * 9 + b) * 9 + c] = (uint16_t)nCompX++;
        // classes
        knOff.clear();
        for (int strain = 0; strain < 2; strain++) {
            std::vector<u64> keys;                      // four 16-bit type ids, most significant first
            const int nt = nTriples;
            auto emit = [&](const int t[4]) {           // t = four triple numbers: (trump,) side suits ascending
                int lo[4], hi[4];
                for (int i = 0; i < 4; i++) {
                    lo[i] = triFirstType[t[i]];
                    hi[i] = lo[i] + (tri[t[i]].x == 0 ? 0 : tri[t[i]].x + 1);
                }
                int first = strain;                     // side suits start here
                for (int a = lo[0]; a <= hi[0]; a++)
                    for (int b = lo[1]; b <= hi[1]; b++) {
                        if (first < 1 && b < a) continue;
                        for (int c = lo[2]; c <= hi[2]; c++) {
                            if (c < b) continue;
                            for (int d = lo[3]; d <= hi[3]; d++) {
                                if (d < c) continue;
                                const TypeInfo* tp[4] = {&types[a], &types[b], &types[c], &types[d]};
                                if (!knowledgeOk(k, tp)) continue;
                                keys.push_back((u64)a << 48 | (u64)b << 32 | (u64)c << 16 | (u64)d);
                            }
                        }
                    }
            };
            int t[4];
            if (strain == 0) {
                for (t[0] = 0; t[0] < nt; t[0]++)
                    for (t[1] = t[0]; t[1] < nt; t[1]++) {
                        int n2 = tri[t[0]].n + tri[t[1]].n, s2 = tri[t[0]].s + tri[t[1]].s, x2 = tri[t[0]].x + tri[t[1]].x;
                        if (n2 > k || s2 > k || x2 > 2 * k) continue;
                        for (t[2] = t[1]; t[2] < nt; t[2]++) {
                            int n3 = n2 + tri[t[2]].n, s3 = s2 + tri[t[2]].s, x3 = x2 + tri[t[2]].x;
                            if (n3 > k || s3 > k || x3 > 2 * k) continue;
                            int n4 = k - n3, s4 = k - s3, x4 = 2 * k - x3;
                            if (n4 + s4 + x4 > 13) continue;
                            t[3] = lookupTriple(tri, n4, s4, x4);
                            if (t[3] < t[2]) continue;
                            emit(t);
                        }
                    }
            } else {
                for (t[0] = 0; t[0] < nt; t[0]++) {
                    if (tri[t[0]].n + tri[t[0]].s + tri[t[0]].x == 0) continue;     // the trump suit has cards
                    for (t[1] = 0; t[1] < nt; t[1]++) {
                        int n2 = tri[t[0]].n + tri[t[1]].n, s2 = tri[t[0]].s + tri[t[1]].s, x2 = tri[t[0]].x + tri[t[1]].x;
                        if (n2 > k || s2 > k || x2 > 2 * k) continue;
                        for (t[2] = t[1]; t[2] < nt; t[2]++) {
                            int n3 = n2 + tri[t[2]].n, s3 = s2 + tri[t[2]].s, x3 = x2 + tri[t[2]].x;
                            if (n3 > k || s3 > k || x3 > 2 * k) continue;
                            int n4 = k - n3, s4 = k - s3, x4 = 2 * k - x3;
                            if (n4 + s4 + x4 > 13) continue;
                            t[3] = lookupTriple(tri, n4, s4, x4);
                            if (t[3] < t[2]) continue;
                            emit(t);
                        }
                    }
                }
            }
            std::sort(keys.begin(), keys.end());
            nClasses[strain] = keys.size();
            shapeBase[strain].assign((size_t)nCompNS * nCompNS * nCompX, NONE32);
            std::vector<ClassRow>& rw = rows[strain];
            rw.clear();
            rw.reserve(keys.size() + 1);
            u64 off = 0;
            for (u64 key : keys) {
                ClassRow r;
                r.id[0] = (uint16_t)(key >> 48); r.id[1] = (uint16_t)(key >> 32); r.id[2] = (uint16_t)(key >> 16); r.id[3] = (uint16_t)key;
                r.offset = off;
                u32 sh = shapeIndex(r.id);
                if (shapeBase[strain][sh] == NONE32) {
                    u32 block = (u32)types[r.id[0]].rad * types[r.id[1]].rad * types[r.id[2]].rad * types[r.id[3]].rad;
                    shapeBase[strain][sh] = (u32)knOff.size();
                    knOff.resize(knOff.size() + block, NONE32);
                }
                if (off >= NONE32) { fprintf(stderr, "endtable: class offset does not fit 32 bits\n"); abort(); }
                knOff[shapeBase[strain][sh] + knIndex(r.id)] = (u32)off;
                rw.push_back(r);
                off += classSize(strain, r.id);
            }
            M[strain] = off;
            ClassRow sentinel;
            sentinel.id[0] = sentinel.id[1] = sentinel.id[2] = sentinel.id[3] = 0xFFFF;
            sentinel.offset = off;
            rw.push_back(sentinel);
            if (!keepRows) { std::vector<ClassRow>().swap(rw); }
        }
        base[0] = 0;
        base[1] = 2 * M[0];
        entries = 2 * (M[0] + M[1]);
    }

    template <class V> static int lookupTriple(const V& tri, int n, int s, int x) {
        // triples are in tuple order: binary search
        int lo = 0, hi = (int)tri.size() - 1;
        while (lo <= hi) {
            int mid = (lo + hi) / 2;
            int c = tri[mid].n != n ? (tri[mid].n < n ? -1 : 1) : tri[mid].s != s ? (tri[mid].s < s ? -1 : 1) : tri[mid].x != x ? (tri[mid].x < x ? -1 : 1) : 0;
            if (c == 0) return mid;
            if (c < 0) lo = mid + 1; else hi = mid - 1;
        }
        return -1;
    }

    // ---------------------------------------------------------------------------------- rank
    // Slot of a position at a trick boundary with k cards in each hand. The knowledge must be consistent; it need
    // not be normalized. Returns ~0 if the position does not belong to the table (wrong counts, inconsistent knowledge).
    u64 slot(u64 hN, u64 hS, u64 pool, const int8_t elIn[4], int trump, int leader) const {
        if (popc(hN) != k || popc(hS) != k) return ~0ULL;
        int x[4];
        int8_t el[4];
        for (int s = 0; s < 4; s++) { x[s] = popc(pool >> (13 * s) & SUIT13); el[s] = elIn[s]; }
        if (!normalizeKnowledge(x, k, k, el)) return ~0ULL;
        if (leader >= 2) {                              // half-turn
            std::swap(hN, hS);
            for (int s = 0; s < 4; s++) if (el[s] >= 0) el[s] = (int8_t)(x[s] - el[s]);
            leader -= 2;
        }
        u64 key[4];                                     // type id << 32 | pattern rank
        for (int s = 0; s < 4; s++) {
            u64 n = hN >> (13 * s) & SUIT13, so = hS >> (13 * s) & SUIT13, xx = pool >> (13 * s) & SUIT13;
            int cn = popc(n), cs = popc(so);
            if (cn > k || cs > k) return ~0ULL;
            u32 tid = (u32)typeBase[cn][cs][x[s]] + (u32)(x[s] ? el[s] + 1 : 0);
            key[s] = (u64)tid << 32 | patternRank(n, so, xx);
        }
        int strain = trump < 4 && ((hN | hS | pool) >> (13 * trump) & SUIT13) ? 1 : 0;
#define SDB_ET_CSWAP(a, b) { u64 lo_ = key[a] < key[b] ? key[a] : key[b], hi_ = key[a] < key[b] ? key[b] : key[a]; key[a] = lo_; key[b] = hi_; }
        if (strain) {
            std::swap(key[0], key[trump]);
            SDB_ET_CSWAP(1, 2) SDB_ET_CSWAP(2, 3) SDB_ET_CSWAP(1, 2)
        } else {
            SDB_ET_CSWAP(0, 1) SDB_ET_CSWAP(2, 3) SDB_ET_CSWAP(0, 2) SDB_ET_CSWAP(1, 3) SDB_ET_CSWAP(1, 2)
        }
#undef SDB_ET_CSWAP
        uint16_t id[4] = {(uint16_t)(key[0] >> 32), (uint16_t)(key[1] >> 32), (uint16_t)(key[2] >> 32), (uint16_t)(key[3] >> 32)};
        u64 r = 0;
        int i = 0;
        if (strain) { r = (u32)key[0]; i = 1; }
        while (i < 4) {
            if (i == 3 || id[i + 1] != id[i]) { r = r * types[id[i]].P + (u32)key[i]; i++; continue; }
            int j = i + 1;
            while (j < 4 && id[j] == id[i]) j++;
            int m = j - i;
            u64 d = (u32)key[i];
            for (int q = 1; q < m; q++) d += chooseSmall((u64)(u32)key[i + q] + (u64)q, q + 1);
            r = r * radix[5 * (size_t)id[i] + (size_t)m] + d;
            i = j;
        }
        u32 sb = shapeBase[strain][shapeIndex(id)];
        if (sb == NONE32) return ~0ULL;
        u32 off = knOff[sb + knIndex(id)];
        if (off == NONE32) return ~0ULL;
        return base[strain] + 2 * ((u64)off + r) + (u64)leader;
    }
    u64 slot(const Position& p) const { return slot(p.hN, p.hS, p.pool, p.el, p.trump, p.leader); }

    // ---------------------------------------------------------------------------------- unrank
    // Class number (within its strain) holding position number `pos`. Needs the class rows.
    size_t classOf(int strain, u64 pos) const {
        const std::vector<ClassRow>& rw = rows[strain];
        size_t lo = 0, hi = rw.size() - 2;              // last row is the sentinel
        while (lo < hi) {
            size_t mid = (lo + hi + 1) / 2;
            if (rw[mid].offset <= pos) lo = mid; else hi = mid - 1;
        }
        return lo;
    }

    // The canonical concrete position of rank r in class ci: suits in canonical order as suits 0..3 on the lowest
    // ranks, trump 0 for a trump entry and 4 for notrump.
    void unrankInClass(int strain, size_t ci, u64 r, int leaderBit, Position& out) const {
        const ClassRow& row = rows[strain][ci];
        u32 pr[4] = {0, 0, 0, 0};
        int gi[4], gm[4], ng = 0;
        u64 gr[4];
        for (int i = strain; i < 4;) {
            int j = i + 1;
            while (j < 4 && row.id[j] == row.id[i]) j++;
            gi[ng] = i; gm[ng] = j - i; gr[ng] = choose((u64)types[row.id[i]].P + (u64)(j - i) - 1, j - i); ng++;
            i = j;
        }
        for (int g = ng - 1; g >= 0; g--) {
            u64 d = r % gr[g];
            r /= gr[g];
            if (gm[g] == 1) { pr[gi[g]] = (u32)d; continue; }
            for (int i = gm[g]; i >= 1; i--) {          // multiset unrank, highest first
                u64 lo = (u64)i - 1, hi = (u64)types[row.id[gi[g]]].P + (u64)gm[g];     // largest c with C(c, i) <= d
                while (lo < hi) {
                    u64 mid = (lo + hi + 1) / 2;
                    if (choose(mid, i) <= d) lo = mid; else hi = mid - 1;
                }
                pr[gi[g] + i - 1] = (u32)(lo - ((u64)i - 1));
                d -= choose(lo, i);
            }
        }
        if (strain) pr[0] = (u32)r;
        out.hN = out.hS = out.pool = 0;
        for (int s = 0; s < 4; s++) {
            const TypeInfo& t = types[row.id[s]];
            u32 nmask, smask;
            patternUnrank(pr[s], t.n, t.s, t.x, nmask, smask);
            u32 all = (1u << (t.n + t.s + t.x)) - 1;
            out.hN |= (u64)nmask << (13 * s);
            out.hS |= (u64)smask << (13 * s);
            out.pool |= (u64)(all & ~nmask & ~smask) << (13 * s);
            out.el[s] = t.kn;
        }
        out.trump = strain ? 0 : 4;
        out.leader = leaderBit;
    }

    void unrank(u64 slot, Position& out) const {
        int strain = slot >= base[1] ? 1 : 0;
        u64 pos = (slot - base[strain]) >> 1;
        size_t ci = classOf(strain, pos);
        unrankInClass(strain, ci, pos - rows[strain][ci].offset, (int)((slot - base[strain]) & 1), out);
    }
};

// ------------------------------------------------------------------------------------------ file format
static const char MAGIC[9] = "SDBET001";
static const u64 HEADER_BYTES = 4096;
static const u64 TAIL_ZERO_BYTES = 8;

struct Header {                             // decoded header fields
    u32 version, k, kind, bits;
    u64 entries, mNotrump, mTrump, cNotrump, cTrump;
    uint8_t sha256[32];
};

static inline void put32(uint8_t* p, u32 v) { for (int i = 0; i < 4; i++) p[i] = (uint8_t)(v >> (8 * i)); }
static inline void put64(uint8_t* p, u64 v) { for (int i = 0; i < 8; i++) p[i] = (uint8_t)(v >> (8 * i)); }
static inline u32 get32(const uint8_t* p) { u32 v = 0; for (int i = 0; i < 4; i++) v |= (u32)p[i] << (8 * i); return v; }
static inline u64 get64(const uint8_t* p) { u64 v = 0; for (int i = 0; i < 8; i++) v |= (u64)p[i] << (8 * i); return v; }

static inline void encodeHeader(const Index& ix, const uint8_t sha[32], uint8_t out[4096]) {
    memset(out, 0, HEADER_BYTES);
    memcpy(out, MAGIC, 8);
    put32(out + 8, 1);
    put32(out + 12, (u32)ix.k);
    put32(out + 16, 1);
    put32(out + 20, (u32)ix.bits);
    put64(out + 24, ix.entries);
    put64(out + 32, ix.M[0]);
    put64(out + 40, ix.M[1]);
    put64(out + 48, ix.nClasses[0]);
    put64(out + 56, ix.nClasses[1]);
    memcpy(out + 64, sha, 32);
}

static inline bool decodeHeader(const uint8_t in[4096], Header& h) {
    if (memcmp(in, MAGIC, 8) != 0) return false;
    h.version = get32(in + 8); h.k = get32(in + 12); h.kind = get32(in + 16); h.bits = get32(in + 20);
    h.entries = get64(in + 24); h.mNotrump = get64(in + 32); h.mTrump = get64(in + 40);
    h.cNotrump = get64(in + 48); h.cTrump = get64(in + 56);
    memcpy(h.sha256, in + 64, 32);
    for (u64 i = 96; i < HEADER_BYTES; i++) if (in[i]) return false;
    return true;
}

// Entry `slot` of a packed data section: bits [bits * slot, bits * (slot + 1)), least significant bit first.
// Reads up to 8 bytes from the entry's first byte, which the 8 zero bytes after the data make safe.
static inline int readEntry(const uint8_t* data, int bits, u64 slot) {
    u64 bit = slot * (u64)bits;
    const uint8_t* p = data + (bit >> 3);
#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    uint16_t w;
    memcpy(&w, p, 2);
#else
    uint16_t w = (uint16_t)(p[0] | p[1] << 8);
#endif
    return (int)((w >> (bit & 7)) & ((1u << bits) - 1));
}

}  // namespace endtable

// ---------------------------------------------------------------------------------------------- reader
struct EndTable {
    endtable::Index ix;
    void* map;
    size_t mapBytes;
    const uint8_t* data;
    endtable::Header header;
    explicit EndTable(int k, bool keepRows) : ix(k, keepRows), map(nullptr), mapBytes(0), data(nullptr), header() {}
};

// Opens with the class rows kept (needed for unrank) when keepRows is true; the search does not need them.
static inline EndTable* endtable_open_ex(const char* path, bool keepRows) {
    int fd = open(path, O_RDONLY);
    if (fd < 0) return nullptr;
    struct stat st;
    uint8_t head[4096];
    endtable::Header h;
    if (fstat(fd, &st) != 0 || (endtable::u64)st.st_size < endtable::HEADER_BYTES ||
        pread(fd, head, sizeof head, 0) != (ssize_t)sizeof head || !endtable::decodeHeader(head, h) ||
        h.version != 1 || h.kind != 1 || h.k < 1 || h.k > (endtable::u32)endtable::MAXK) {
        close(fd);
        return nullptr;
    }
    EndTable* t = new EndTable((int)h.k, keepRows);
    const endtable::Index& ix = t->ix;
    bool ok = h.bits == (endtable::u32)ix.bits && h.entries == ix.entries && h.mNotrump == ix.M[0] && h.mTrump == ix.M[1] &&
              h.cNotrump == ix.nClasses[0] && h.cTrump == ix.nClasses[1] &&
              (endtable::u64)st.st_size >= endtable::HEADER_BYTES + ix.dataBytes() + endtable::TAIL_ZERO_BYTES;
    void* m = ok ? mmap(nullptr, (size_t)st.st_size, PROT_READ, MAP_SHARED, fd, 0) : MAP_FAILED;
    close(fd);
    if (m == MAP_FAILED) { delete t; return nullptr; }
    t->map = m;
    t->mapBytes = (size_t)st.st_size;
    t->data = (const uint8_t*)m + endtable::HEADER_BYTES;
    t->header = h;
    return t;
}

static inline EndTable* endtable_open(const char* path) { return endtable_open_ex(path, false); }

static inline void endtable_close(EndTable* t) {
    if (!t) return;
    if (t->map) munmap(t->map, t->mapBytes);
    delete t;
}

static inline int endtable_cards(const EndTable* t) { return t->ix.k; }

static inline uint64_t endtable_slot(const EndTable* t, uint64_t hN, uint64_t hS, uint64_t pool,
                                     const int8_t el[4], int trump, int leader) {
    return t->ix.slot(hN, hS, pool, el, trump, leader);
}

// A position that is not a k-card trick-boundary position with consistent knowledge has no slot: that is a caller
// error, and the reader stops the process rather than return a wrong value.
static inline int endtable_lookup(const EndTable* t, uint64_t hN, uint64_t hS, uint64_t pool,
                                  const int8_t el[4], int trump, int leader) {
    uint64_t s = t->ix.slot(hN, hS, pool, el, trump, leader);
    if (s >= t->ix.entries) {
        fprintf(stderr, "endtable_lookup: position has no slot (hN %llx hS %llx pool %llx el %d %d %d %d trump %d leader %d)\n",
                (unsigned long long)hN, (unsigned long long)hS, (unsigned long long)pool, el[0], el[1], el[2], el[3], trump, leader);
        abort();
    }
    return endtable::readEntry(t->data, t->ix.bits, s);
}

#endif  // SDB_ENDTABLE_H
