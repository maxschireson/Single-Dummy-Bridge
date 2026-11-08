# Credits and provenance

Max Schireson initiated and directed this bridge research project, defined its
goals, and guided the design and evaluation priorities. OpenAI's ChatGPT/Codex
assisted with implementation, testing, experiments, analysis, documentation,
and preparation of this source upload.

The native solver is [DDS](https://github.com/dds-bridge/dds), created by
Bo Haglund and developed by Soren Hein and the DDS contributors. Its search
algorithms and engineering make this harness's double-dummy evaluations
possible. The bundled sources retain their original notices and Apache 2.0
license. See `vendor/DDS_SOURCE.md` for the exact upstream revision.

The external-engine adapter and historical integration experiment use
[BEN](https://github.com/lorserker/ben) and the work of its contributors.
BEN code and model weights are external; their own license
terms apply. See `VALIDATION.md` for the tested revision and configuration.

This harness is independent research work. It is not an official DDS or BEN
release, and no endorsement by those projects or their authors is implied.
