# DDS provenance

Source: https://github.com/dds-bridge/dds

Commit: `0f969b86a4841f438fd0cdff2924c4f2404abf6a`

`dds/library/src`, `dds/LICENSE`, and `dds/README.md` were exported unchanged from
that commit. No solver optimization experiments or private edits are included.
The source license is Apache 2.0; see `dds/LICENSE` and source file notices.
`scripts/build_dds.py` compiles these sources with C++20 and links their public
pointer-based C ABI for `ctypes`. The build wrapper is part of this harness.
