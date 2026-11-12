// SPDX-License-Identifier: Apache-2.0
// All-root-move adapter for Faster-DDS related-layout reuse. See CREDITS.md.
#include <algorithm>
#include <array>
#include <cstdio>
#include <stdexcept>
#include <string>
#include <api/solve_board.hpp>
#include <related_batch.hpp>
#include <solver_context/solver_context.hpp>

namespace {
// Reuse the related-layout validator for each world, including partial tricks.
// Unlike the scalar N/S-fixed API, this also supports adjacent known hands
// (defender + dummy) and the one-known-hand opening lead.
auto validate(const Deal* deals, int count, unsigned fixed) -> void
{
    if (count < 1 || count > 100000 || fixed > 15)
        throw std::invalid_argument("invalid batch size or fixed-hand mask");
    std::array<unsigned, 4> universe{};
    for (int i = 0; i < count; ++i) {
        const auto& d = deals[i];
        related_batch::Batch b;
        b.first = d.first; b.trump = d.trump;
        related_batch::Defenders ew;
        std::array<unsigned, 4> live{};
        for (int s = 0; s < 4; ++s) {
            b.north[s] = d.remainCards[0][s]; b.south[s] = d.remainCards[2][s];
            ew.east[s] = d.remainCards[1][s]; ew.west[s] = d.remainCards[3][s];
            for (int h = 0; h < 4; ++h) {
                live[s] |= d.remainCards[h][s];
                if ((fixed & (1u << h)) && d.remainCards[h][s] != deals[0].remainCards[h][s])
                    throw std::invalid_argument("fixed hand differs across batch");
            }
        }
        for (int k = 0; k < 3; ++k) {
            b.current_trick_suit[k] = d.currentTrickSuit[k];
            b.current_trick_rank[k] = d.currentTrickRank[k];
            if (d.currentTrickSuit[k] != deals[0].currentTrickSuit[k] ||
                d.currentTrickRank[k] != deals[0].currentTrickRank[k])
                throw std::invalid_argument("current trick differs across batch");
        }
        if (d.first != deals[0].first || d.trump != deals[0].trump)
            throw std::invalid_argument("leader or strain differs across batch");
        b.layouts.push_back(ew);
        try { related_batch::validate(b); }
        catch (const std::exception& e) {
            throw std::invalid_argument("world " + std::to_string(i) + ": " + e.what());
        }
        if (i == 0) universe = live;
        else if (live != universe) throw std::invalid_argument("remaining deck differs across batch");
    }
}
}

// A persistent allocation, but no proof survives a decision boundary. In
// particular, mode 2 must never carry a TT across changing trumps.
// All inputs are validated before either resetting the context or searching.
extern "C" int bridge_dds_all_moves_batch(void* handle, const Deal* deals,
    int count, unsigned fixed, int retain, FutureTricks* output,
    char* error, int error_size)
{
    try {
        if (!handle || !deals || !output) throw std::invalid_argument("null batch argument");
        validate(deals, count, fixed);
        auto& context = *static_cast<SolverContext*>(handle);
        context.reset_for_solve();
        for (int i = 0; i < count; ++i) {
            if (!retain && i) context.reset_for_solve();
            const int code = solve_board(context, deals[i], -1, 3, retain ? 2 : 1, &output[i]);
            if (code != RETURN_NO_FAULT) throw std::runtime_error("DDS status " + std::to_string(code));
        }
        return 1;
    } catch (const std::exception& e) {
        if (error && error_size > 0) std::snprintf(error, error_size, "%s", e.what());
    } catch (...) {
        if (error && error_size > 0) std::snprintf(error, error_size, "unknown native exception");
    }
    return -1;
}
