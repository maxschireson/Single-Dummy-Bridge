// SPDX-License-Identifier: Apache-2.0
// Faster-DDS additions by Max Schireson's project with OpenAI ChatGPT/Codex assistance.
#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <vector>

#include <api/dds_data_types.hpp>

namespace related_batch
{
using Hand = std::array<unsigned, 4>;

struct Defenders
{
    Hand east{}, west{};
};

/**
 * Fixed N/S, fixed strain and current trick, and allocations of one fixed E/W pool.
 * Masks use DDS public bits 2..14, in S,H,D,C order. Current-trick cards are
 * excluded from all hands. Repeated layouts are permitted.
 */
struct Batch
{
    Hand north{}, south{};
    std::vector<Defenders> layouts;
    int trump = 4;
    int first = 3;
    std::array<int, 3> current_trick_suit{}, current_trick_rank{};
};

enum class Mode { Cold, Retained, RootProofs, Automatic };

struct Options
{
    // Automatic adds root certificates above 256 layouts, or from 64 layouts
    // when at most seven tricks remain. Shape ordering starts above 256.
    // Explicit cash bounds opt in to the root driver even for small batches.
    Mode mode = Mode::Automatic;
    // Automatic chooses ordering; select an explicit mode to override it.
    bool sort_by_shape = false;
    bool abstract_cash_bounds = false;
    int memory_mb = 256;
    std::size_t max_root_proofs = 65536;
    std::size_t max_proofs_per_shape = 128;
};

struct Stats
{
    // DDS counts completed-trick transitions, not every card-play node.
    std::uint64_t trick_nodes = 0, tt_lookups = 0, tt_hits = 0;
    // These presearch hit counts include the optional cashing certificates.
    std::size_t native_solves = 0, root_complete_hits = 0, root_partial_hits = 0;
    std::size_t root_proofs = 0, root_checks = 0, shape_bound_hits = 0;
    // total_ms includes validation, ordering, context creation and destruction.
    // tt_mib reports sampled peak TT usage, excluding the small root cache.
    double validation_ms = 0, total_ms = 0, tt_mib = 0;
};

struct Result
{
    std::vector<int> ns_tricks;
    Stats stats;
};

/** Validate every layout before allocating a solver or doing any search.
 * Throws std::invalid_argument with the layout index and cause.
 * Supports 1..13 cards per hand at the start of the current trick.
 */
auto validate(const Batch& batch) -> void;

/** Assemble an individual DDS deal; this does not perform batch validation. */
auto make_deal(const Batch& batch, std::size_t index) -> Deal;

/** Exact double-dummy N/S remaining tricks, including an incomplete trick.
 * Returns one score per input layout in original order. Each call owns its
 * context and caches, preventing incompatible strains/families from sharing
 * bounds. Separate calls may run concurrently using separate input objects.
 * Scalar scores only: no best move or common information-limited policy.
 */
auto solve(const Batch& batch, const Options& options = {}) -> Result;
} // namespace related_batch
