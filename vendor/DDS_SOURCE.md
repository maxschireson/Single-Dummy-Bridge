# DDS provenance

Source: https://github.com/dds-bridge/dds

Commit: `0f969b86a4841f438fd0cdff2924c4f2404abf6a`

`dds/library/src`, `dds/LICENSE`, and `dds/README.md` were exported from that
commit. This branch additionally applies the compact relative-rank table patch
and includes `related_batch.cpp/.hpp` from
`maxschireson/Faster-DDS` commit `2850a1b686e3e865d037488082fac32ffec93beb`
(branch `codex/related-layout-batches-20261108`). Only the production source
parts of those patches are vendored; their upstream tests and study are in that
repository. The source license is Apache 2.0; see `dds/LICENSE` and notices.
`scripts/build_dds.py` compiles these sources with C++20 and links their public
pointer-based C ABI for `ctypes`. The build wrapper and `native/pimc_batch.cpp`
are part of this harness. The latter extends the related batch validation and
native transposition-table retention approach to all-root-move output and
arbitrary visible-seat sets. It does not use scalar root certificates as move
certificates. A context is reset at each batch boundary, and retained only
within one validated strain/current-trick/remaining-deck batch.
