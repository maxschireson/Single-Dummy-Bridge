// Builder for the ending table (TABLE_BUILD.md section 6): bottom-up, parallel, resumable, deterministic.
//
//   endtable_build K OUT [--prev FILE] [--threads N] [--chunk ENTRIES] [--plain]
//
// K       hand size 1..4. K > 1 needs --prev, the built (K-1)-card table; its data hash is checked on open.
// OUT     the table file. The build writes OUT.part and a record of finished chunks, OUT.part.chunks; the header and
//         the hash are written last and OUT.part is then renamed to OUT. Re-running the same command after an
//         interruption resumes: chunks in the record are not recomputed. The record's first line holds the build
//         parameters, and a resume with different parameters is refused.
// --chunk entries per chunk, a multiple of 8 (default 2^22), so that no two chunks share a byte.
// --plain no card equivalences (the direct transcription of pooled_ref.py).
// Prints one JSON line with counts, times and the data hash when done.
#include <atomic>
#include <chrono>
#include <cinttypes>
#include <mutex>
#include <set>
#include <string>
#include <thread>
#include <vector>

#include <time.h>

#include "endtable.h"
#include "endtable_eval.h"
#include "sha256.h"

using namespace endtable;

static double now() { return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count(); }
static double cpuNow() { timespec t; clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &t); return t.tv_sec + 1e-9 * t.tv_nsec; }

static bool fileSha(int fd, u64 offset, u64 bytes, uint8_t out[32]) {
    Sha256 h;
    std::vector<uint8_t> buf(1 << 22);
    u64 done = 0;
    while (done < bytes) {
        size_t want = (size_t)std::min<u64>(buf.size(), bytes - done);
        ssize_t got = pread(fd, buf.data(), want, (off_t)(offset + done));
        if (got <= 0) return false;
        h.update(buf.data(), (size_t)got);
        done += (u64)got;
    }
    h.final(out);
    return true;
}

static void writeAll(int fd, const void* p, size_t n, u64 off) {
    const uint8_t* b = (const uint8_t*)p;
    while (n) {
        ssize_t w = pwrite(fd, b, n, (off_t)off);
        if (w <= 0) { perror("pwrite"); exit(1); }
        b += w; n -= (size_t)w; off += (u64)w;
    }
}

int main(int argc, char** argv) {
    if (argc < 3) { fprintf(stderr, "usage: endtable_build K OUT [--prev FILE] [--threads N] [--chunk ENTRIES] [--plain]\n"); return 2; }
    int K = atoi(argv[1]);
    std::string out = argv[2];
    std::string prevPath;
    int threads = (int)std::thread::hardware_concurrency();
    u64 chunk = 1ULL << 22;
    bool plain = false;
    for (int i = 3; i < argc; i++) {
        std::string a = argv[i];
        if (a == "--prev") prevPath = argv[++i];
        else if (a == "--threads") threads = atoi(argv[++i]);
        else if (a == "--chunk") chunk = strtoull(argv[++i], nullptr, 10);
        else if (a == "--plain") plain = true;
        else { fprintf(stderr, "unknown argument %s\n", a.c_str()); return 2; }
    }
    if (K < 1 || K > MAXK || chunk == 0 || chunk % 8 || threads < 1) { fprintf(stderr, "bad arguments\n"); return 2; }
    double t0 = now(), c0 = cpuNow();

    // (K-1)-card table
    EndTable* prev = nullptr;
    std::string prevSha = "none";
    if (K > 1) {
        if (prevPath.empty()) { fprintf(stderr, "K > 1 needs --prev\n"); return 2; }
        prev = endtable_open(prevPath.c_str());
        if (!prev || endtable_cards(prev) != K - 1) { fprintf(stderr, "cannot open %s as a %d-card table\n", prevPath.c_str(), K - 1); return 1; }
        int fd = open(prevPath.c_str(), O_RDONLY);
        uint8_t h[32];
        if (fd < 0 || !fileSha(fd, HEADER_BYTES, prev->ix.dataBytes(), h) || memcmp(h, prev->header.sha256, 32) != 0) {
            fprintf(stderr, "%s: data hash does not match its header\n", prevPath.c_str());
            return 1;
        }
        close(fd);
        prevSha = hex32(h);
    }

    Index ix(K, true);
    const u64 entries = ix.entries, dataBytes = ix.dataBytes();
    const u64 nChunks = (entries + chunk - 1) / chunk;
    double tIndex = now() - t0;

    // resumable output
    std::string part = out + ".part", rec = part + ".chunks";
    char params[512];
    snprintf(params, sizeof params, "endtable_build k=%d entries=%" PRIu64 " bits=%d chunk=%" PRIu64 " plain=%d prev=%s",
             K, entries, ix.bits, chunk, plain ? 1 : 0, prevSha.c_str());
    std::set<u64> done;
    FILE* rf = fopen(rec.c_str(), "r");
    if (rf) {
        char line[600];
        if (!fgets(line, sizeof line, rf) || std::string(line) != std::string(params) + "\n") {
            fprintf(stderr, "%s exists with other build parameters; remove it and %s to start over\n", rec.c_str(), part.c_str());
            return 1;
        }
        while (fgets(line, sizeof line, rf)) {
            size_t len = strlen(line);
            if (len && line[len - 1] == '\n') done.insert(strtoull(line, nullptr, 10));   // a torn last line is ignored
        }
        fclose(rf);
    }
    int fd = open(part.c_str(), O_RDWR | O_CREAT, 0644);
    if (fd < 0) { perror(part.c_str()); return 1; }
    const u64 fileBytes = HEADER_BYTES + dataBytes + TAIL_ZERO_BYTES;
    if (done.empty()) {                                  // fresh start: zero header, zero data
        if (ftruncate(fd, 0) != 0 || ftruncate(fd, (off_t)fileBytes) != 0) { perror("ftruncate"); return 1; }
        FILE* w = fopen(rec.c_str(), "w");
        fprintf(w, "%s\n", params);
        fclose(w);
    } else {
        struct stat st;
        if (fstat(fd, &st) != 0 || (u64)st.st_size != fileBytes) { fprintf(stderr, "%s has the wrong size for a resume\n", part.c_str()); return 1; }
    }
    int recFd = open(rec.c_str(), O_WRONLY | O_APPEND);
    if (recFd < 0) { perror(rec.c_str()); return 1; }
    const u64 resumed = done.size();

    std::atomic<u64> next(0), computed(0), nodes(0), leaves(0);
    std::mutex recMutex;
    double tStart = now();
    auto worker = [&]() {
        OneTrick ev(K, prev ? &prev->ix : nullptr, prev ? prev->data : nullptr, prev ? prev->ix.bits : 0, !plain);
        std::vector<uint8_t> buf((size_t)(chunk * (u64)ix.bits / 8 + 8));
        Position p;
        for (;;) {
            u64 c = next.fetch_add(1);
            if (c >= nChunks) break;
            if (done.count(c)) continue;
            u64 a = c * chunk, b = std::min(entries, a + chunk);
            std::fill(buf.begin(), buf.end(), 0);
            // walk the positions of [a, b): slots come in pairs (leader bit 0, 1); a is even
            int strain = a >= ix.base[1] ? 1 : 0;
            u64 pos = (a - ix.base[strain]) >> 1;
            size_t ci = ix.classOf(strain, pos);
            u64 r = pos - ix.rows[strain][ci].offset;
            for (u64 s = a; s < b; s += 2) {
                if (strain == 0 && s >= ix.base[1]) { strain = 1; ci = 0; r = 0; }
                while (r >= ix.rows[strain][ci + 1].offset - ix.rows[strain][ci].offset) { r = 0; ci++; }
                ix.unrankInClass(strain, ci, r, 0, p);
                for (int lead = 0; lead < 2 && s + lead < b; lead++) {
                    p.leader = lead;
                    u64 v = (u64)ev.value(p);
                    u64 bit = (s + lead - a) * (u64)ix.bits;
                    buf[bit >> 3] |= (uint8_t)(v << (bit & 7));
                    if ((bit & 7) + ix.bits > 8) buf[(bit >> 3) + 1] |= (uint8_t)(v >> (8 - (bit & 7)));
                }
                r++;
            }
            u64 off = a * (u64)ix.bits / 8, len = ((b - a) * (u64)ix.bits + 7) / 8;
            writeAll(fd, buf.data(), (size_t)len, HEADER_BYTES + off);
            if (fdatasync(fd) != 0) { perror("fdatasync"); exit(1); }
            {
                std::lock_guard<std::mutex> g(recMutex);
                char l[32];
                int n = snprintf(l, sizeof l, "%" PRIu64 "\n", c);
                if (write(recFd, l, (size_t)n) != n || fdatasync(recFd) != 0) { perror("chunk record"); exit(1); }
                u64 k2 = computed.fetch_add(1) + 1;
                if (k2 % 64 == 0 || k2 + resumed == nChunks) {
                    double el = now() - tStart;
                    fprintf(stderr, "k=%d: %" PRIu64 "/%" PRIu64 " chunks (%" PRIu64 " this run, %.0f s, %.2f core-us per entry)\n",
                            K, k2 + resumed, nChunks, k2, el, el * threads * 1e6 / (double)(k2 * chunk));
                }
            }
        }
        nodes += ev.nodes;
        leaves += ev.leaves;
    };
    std::vector<std::thread> pool;
    for (int i = 0; i < threads; i++) pool.emplace_back(worker);
    for (auto& t : pool) t.join();
    double tBuild = now() - tStart;
    close(recFd);

    // hash, header, rename
    uint8_t sha[32];
    if (!fileSha(fd, HEADER_BYTES, dataBytes, sha)) { fprintf(stderr, "reading back the data failed\n"); return 1; }
    uint8_t head[4096];
    encodeHeader(ix, sha, head);
    writeAll(fd, head, sizeof head, 0);
    if (fsync(fd) != 0) { perror("fsync"); return 1; }
    close(fd);
    if (rename(part.c_str(), out.c_str()) != 0) { perror("rename"); return 1; }
    unlink(rec.c_str());

    u64 nComp = computed.load();
    u64 entriesComputed = 0;
    for (u64 c = 0; c < nChunks; c++) if (!done.count(c)) entriesComputed += std::min(entries, (c + 1) * chunk) - c * chunk;
    (void)nComp;
    double cpu = cpuNow() - c0;
    printf("{\"k\": %d, \"file\": \"%s\", \"entries\": %" PRIu64 ", \"entries_computed\": %" PRIu64 ", \"chunks\": %" PRIu64
           ", \"chunks_resumed\": %" PRIu64 ", \"threads\": %d, \"plain\": %s, \"index_seconds\": %.3f, \"build_seconds\": %.1f"
           ", \"cpu_seconds\": %.1f, \"core_us_per_entry\": %.3f, \"nodes_per_entry\": %.2f, \"leaves_per_entry\": %.2f, \"sha256\": \"%s\"}\n",
           K, out.c_str(), entries, entriesComputed, nChunks, resumed, threads, plain ? "true" : "false", tIndex, tBuild, cpu,
           entriesComputed ? tBuild * threads * 1e6 / (double)entriesComputed : 0.0,
           entriesComputed ? (double)nodes.load() / (double)entriesComputed : 0.0,
           entriesComputed ? (double)leaves.load() / (double)entriesComputed : 0.0, hex32(sha).c_str());
    endtable_close(prev);
    return 0;
}
