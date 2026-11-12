// SPDX-License-Identifier: Apache-2.0
// Rank certificates are DDS's existing winning-rank proof; credit the upstream authors.
#include "related_batch.hpp"

#include <algorithm>
#include <bit>
#include <chrono>
#include <numeric>
#include <stdexcept>
#include <string>
#include <unordered_map>

#include <ab_search.hpp>
#include <api/solve_board.hpp>

namespace related_batch
{
namespace
{
using Clock = std::chrono::steady_clock;

auto elapsed(Clock::time_point start) -> double
{
    return std::chrono::duration<double, std::milli>(Clock::now() - start).count();
}

auto invalid(std::size_t index, const char* reason) -> void
{
    throw std::invalid_argument("layout " + std::to_string(index) + ": " + reason);
}

auto partial_count(const Batch& batch) -> int
{
    return static_cast<int>(std::count_if(
        batch.current_trick_rank.begin(), batch.current_trick_rank.end(),
        [](int rank) { return rank != 0; }));
}

auto shape_key(const Hand& east) -> unsigned
{
    unsigned key = 0;
    for (int suit = 0; suit < 4; ++suit) {
        key |= static_cast<unsigned>(std::popcount(east[suit])) << (4 * suit);
    }
    return key;
}

auto packed(const Hand& hand) -> std::uint64_t
{
    std::uint64_t value = 0;
    for (int suit = 0; suit < 4; ++suit) {
        value |= static_cast<std::uint64_t>(hand[suit] >> 2) << (13 * suit);
    }
    return value;
}

// A small, formally sufficient shape abstraction, independent of search.
// If the leader holds the top k remaining cards of a suit, that hand can
// cash them when no other hand can ruff before trick k. Exact lengths are
// unnecessary: len(suit) >= k OR len(trump) == 0 suffices for each other
// hand. In NT or the trump suit there are no shape conditions at all.
struct CashCertificate
{
    int suit, count;
    unsigned mask;
};

auto cash_certificates(const Deal& first, int tricks) -> std::vector<CashCertificate>
{
    std::vector<CashCertificate> proofs;
    for (int suit = 0; suit < 4; ++suit) {
        unsigned live = 0, mask = 0;
        int count = 0;
        for (int hand = 0; hand < 4; ++hand) {
            live |= first.remainCards[hand][suit];
        }
        for (int rank = 14; rank >= 2 && count < tricks; --rank) {
            if (live & (1u << rank)) {
                mask |= 1u << rank;
                ++count;
                proofs.push_back({suit, count, mask});
            }
        }
    }
    std::stable_sort(proofs.begin(), proofs.end(), [](const auto& a, const auto& b) {
        return a.count > b.count;
    });
    return proofs;
}

auto cash_bound(const Deal& deal, const std::vector<CashCertificate>& proofs) -> int
{
    for (const auto& proof : proofs) {
        if ((deal.remainCards[deal.first][proof.suit] & proof.mask) != proof.mask) {
            continue;
        }
        bool safe = true;
        if (deal.trump != 4 && proof.suit != deal.trump) {
            for (int hand = 0; hand < 4; ++hand) {
                if (hand != deal.first && deal.remainCards[hand][deal.trump] &&
                    std::popcount(deal.remainCards[hand][proof.suit]) < proof.count) {
                    safe = false;
                }
            }
        }
        if (safe) {
            return proof.count;
        }
    }
    return 0;
}

struct Proof
{
    std::uint64_t mask = 0, east = 0;
    int lower = 0, upper = 13;
};

using Proofs = std::unordered_map<unsigned, std::vector<Proof>>;

auto check(const std::vector<Proof>& proofs, std::uint64_t east,
           int& lower, int& upper, Stats& stats) -> void
{
    for (const auto& proof : proofs) {
        ++stats.root_checks;
        if ((east & proof.mask) != proof.east) {
            continue;
        }
        lower = std::max(lower, proof.lower);
        upper = std::min(upper, proof.upper);
        if (lower >= upper) {
            break;
        }
    }
    if (lower > upper) {
        throw std::logic_error("contradictory root certificates");
    }
}

auto record(std::vector<Proof>& proofs, const Deal& deal, const unsigned short ranks[],
            int target, bool value, int tricks, const Options& options, Stats& stats) -> void
{
    Proof proof;
    proof.upper = tricks;
    if (value) {
        proof.lower = target;
    } else {
        proof.upper = target - 1;
    }
    for (int suit = 0; suit < 4; ++suit) {
        // Like DDS TT: every live rank at or above the lowest winning rank
        // matters, not only the winning ranks themselves. N/S and the full
        // remaining deck are fixed by batch validation. E/W lengths are
        // exact in the map key; W ownership is the complement of E.
        unsigned relevant = ranks[suit] ?
            (0x1fffu << std::countr_zero(ranks[suit])) & 0x1fffu : 0;
        relevant &= (deal.remainCards[1][suit] | deal.remainCards[3][suit]) >> 2;
        proof.mask |= static_cast<std::uint64_t>(relevant) << (13 * suit);
        proof.east |= static_cast<std::uint64_t>(
            relevant & (deal.remainCards[1][suit] >> 2)) << (13 * suit);
    }
    for (auto& old : proofs) {
        if (old.mask == proof.mask && old.east == proof.east) {
            old.lower = std::max(old.lower, proof.lower);
            old.upper = std::min(old.upper, proof.upper);
            return;
        }
    }
    if (proofs.size() >= options.max_proofs_per_shape ||
        stats.root_proofs >= options.max_root_proofs) {
        return;
    }
    proofs.push_back(proof);
    ++stats.root_proofs;
}

auto refine(SolverContext& context, const Deal& deal, int partial, int tricks,
            int lower, int upper, std::vector<Proof>& proofs,
            const Options& options, Stats& stats) -> int
{
    using Search = bool (*)(Pos*, int, int, SolverContext&);
    const Search search[4] = {ab_search, ab_search_1, ab_search_2, ab_search_3};
    auto* thread = context.thread_ptr();
    const int depth = context.search().ini_depth();
    const int next = (deal.first + partial) % 4;
    int guess = std::clamp(7 - (next & 1), lower + 1, upper);
    while (lower < upper) {
        context.reset_best_moves_lite();
        const bool value = search[partial](&thread->lookAheadPos, guess, depth, context);
        record(proofs, deal, thread->lookAheadPos.win_ranks[depth], guess, value,
               tricks, options, stats);
        if (value) {
            lower = guess;
        } else {
            upper = guess - 1;
        }
        guess = value ? std::min(guess + 1, upper) : upper;
    }
    return lower;
}

auto solve_layout(SolverContext& context, const Deal& deal, int partial, int tricks,
                  int lower, int upper, std::vector<Proof>* proofs,
                  const Options& options, Stats& stats) -> int
{
    if (lower == upper) {
        ++stats.root_complete_hits;
        return lower;
    }
    if (lower || upper < tricks) {
        ++stats.root_partial_hits;
    }
    if (options.mode == Mode::Cold) {
        context.reset_for_solve();
    }
    FutureTricks result{};
    ++stats.native_solves;
    // target=0 performs ordinary DDS initialization, without a scored search.
    // The scalar batch driver then preserves each completed root proof.
    const int target = proofs && tricks > 1 ? 0 : -1;
    const int mode = options.mode == Mode::Cold ? 1 : 2;
    const int code = solve_board(context, deal, target, 1, mode, &result);
    if (code != RETURN_NO_FAULT) {
        throw std::runtime_error("DDS returned " + std::to_string(code));
    }
    const int score = !proofs || tricks == 1 ? result.score[0] :
        refine(context, deal, partial, tricks, lower, upper, *proofs, options, stats);
    stats.trick_nodes += context.search().trick_nodes();
    stats.tt_lookups += context.thread_ptr()->tt_lookup_count;
    stats.tt_hits += context.thread_ptr()->tt_hit_count;
    stats.tt_mib = std::max(stats.tt_mib, context.trans_table()->memory_in_use() / 1024.0);
    return score;
}

auto validated_current_trick(const Batch& batch, int& partial) -> Hand
{
    Hand on_table{};
    bool gap = false;
    for (int index = 0; index < 3; ++index) {
        const int rank = batch.current_trick_rank[index];
        const int suit = batch.current_trick_suit[index];
        if (!rank) {
            gap = true;
            continue;
        }
        if (gap || rank < 2 || rank > 14 || suit < 0 || suit > 3) {
            throw std::invalid_argument("invalid or noncontiguous current trick");
        }
        if (on_table[suit] & (1u << rank)) {
            throw std::invalid_argument("duplicate current-trick card");
        }
        on_table[suit] |= 1u << rank;
        ++partial;
    }
    return on_table;
}
} // namespace

auto make_deal(const Batch& batch, std::size_t index) -> Deal
{
    if (index >= batch.layouts.size()) {
        throw std::out_of_range("layout index");
    }
    Deal deal{};
    deal.first = batch.first;
    deal.trump = batch.trump;
    for (int suit = 0; suit < 4; ++suit) {
        deal.remainCards[0][suit] = batch.north[suit];
        deal.remainCards[2][suit] = batch.south[suit];
        deal.remainCards[1][suit] = batch.layouts[index].east[suit];
        deal.remainCards[3][suit] = batch.layouts[index].west[suit];
    }
    for (int index = 0; index < 3; ++index) {
        deal.currentTrickRank[index] = batch.current_trick_rank[index];
        deal.currentTrickSuit[index] = batch.current_trick_suit[index];
    }
    return deal;
}

auto validate(const Batch& batch) -> void
{
    if (batch.layouts.empty()) {
        throw std::invalid_argument("batch is empty");
    }
    if (batch.trump < 0 || batch.trump > 4 || batch.first < 0 || batch.first > 3) {
        throw std::invalid_argument("invalid strain or leader");
    }
    int partial = 0;
    const Hand on_table = validated_current_trick(batch, partial);
    Hand universe{};
    for (std::size_t index = 0; index < batch.layouts.size(); ++index) {
        const auto deal = make_deal(batch, index);
        Hand seen = on_table;
        std::array<int, 4> count{};
        for (int hand = 0; hand < 4; ++hand) {
            for (int suit = 0; suit < 4; ++suit) {
                const unsigned cards = deal.remainCards[hand][suit];
                if (cards & ~0x7ffcu) {
                    invalid(index, "rank mask contains bits outside 2..14");
                }
                if (cards & seen[suit]) {
                    invalid(index, "card occurs in more than one hand or on table");
                }
                seen[suit] |= cards;
                count[hand] += std::popcount(cards);
            }
        }
        for (int played = 0; played < partial; ++played) {
            const int hand = (batch.first + played) % 4;
            ++count[hand];
            if (played && batch.current_trick_suit[played] != batch.current_trick_suit[0] &&
                deal.remainCards[hand][batch.current_trick_suit[0]]) {
                invalid(index, "current trick revokes while holding led suit");
            }
        }
        if (count[0] < 1 || count[0] > 13 ||
            !std::all_of(count.begin(), count.end(), [&](int n) { return n == count[0]; })) {
            invalid(index, "hands have inconsistent card counts");
        }
        if (index == 0) {
            universe = seen;
        } else if (seen != universe) {
            invalid(index, "remaining deck differs from first layout");
        }
    }
}

auto solve(const Batch& batch, const Options& requested_options) -> Result
{
    const auto start = Clock::now();
    validate(batch);
    Result output;
    output.stats.validation_ms = elapsed(start);
    Options options = requested_options;
    if (options.memory_mb < 1) {
        throw std::invalid_argument("memory_mb must be positive");
    }
    const int partial = partial_count(batch);
    const int next = (batch.first + partial) % 4;
    const auto first = make_deal(batch, 0);
    int total = partial;
    for (const auto& hand : first.remainCards) {
        for (auto cards : hand) {
            total += std::popcount(cards);
        }
    }
    const int tricks = total / 4;
    if (options.mode == Mode::Automatic) {
        const bool large_batch = batch.layouts.size() > 256;
        const bool short_batch = tricks <= 7 && batch.layouts.size() >= 64;
        options.mode = large_batch || short_batch || options.abstract_cash_bounds ?
            Mode::RootProofs : Mode::Retained;
        options.sort_by_shape = large_batch;
    }
    std::vector<std::size_t> order(batch.layouts.size());
    std::iota(order.begin(), order.end(), 0);
    if (options.sort_by_shape) {
        std::stable_sort(order.begin(), order.end(), [&](auto a, auto b) {
            return shape_key(batch.layouts[a].east) < shape_key(batch.layouts[b].east);
        });
    }
    SolverConfig config;
    config.tt_mem_default_mb_ = std::min(16, options.memory_mb);
    config.tt_mem_maximum_mb_ = options.memory_mb;
    {
        SolverContext context(config);
        Proofs cache;
        output.ns_tricks.resize(order.size());
        const auto cash = options.abstract_cash_bounds && partial == 0 ?
            cash_certificates(first, tricks) : std::vector<CashCertificate>{};
        for (auto index : order) {
            const auto deal = make_deal(batch, index);
            int lower = 0, upper = tricks;
            auto* proofs = options.mode == Mode::RootProofs ?
                &cache[shape_key(batch.layouts[index].east)] : nullptr;
            if (proofs) {
                check(*proofs, packed(batch.layouts[index].east), lower, upper, output.stats);
            }
            if (!cash.empty()) {
                const int bound = cash_bound(deal, cash);
                if (bound > lower) {
                    lower = bound;
                    ++output.stats.shape_bound_hits;
                }
                if (lower > upper) {
                    throw std::logic_error("contradictory cash certificate");
                }
            }
            const int score = solve_layout(context, deal, partial, tricks, lower, upper,
                                           proofs, options, output.stats);
            output.ns_tricks[index] = (next & 1) ? tricks - score : score;
        }
    }
    output.stats.total_ms = elapsed(start);
    return output;
}
} // namespace related_batch
