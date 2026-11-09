// Experimental opt-in search budget. Never changes an exact search result.
#pragma once
#include <cstdint>
namespace approx_dds {
struct Exhausted {};
inline thread_local bool enabled=false;
inline thread_local uint64_t limit=0, visited=0;
inline void tick() {
    if (enabled) {
        if (visited>=limit) throw Exhausted{};
        ++visited;
    }
}
}
