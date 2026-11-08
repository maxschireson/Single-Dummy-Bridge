# Credits and provenance

Max Schireson initiated and directed this bridge research project, defined its
goals, and guided the design and evaluation priorities. OpenAI's ChatGPT/Codex
assisted with implementation, testing, experiments, analysis, documentation,
and preparation of this source upload.

The native solver is [DDS](https://github.com/dds-bridge/dds), created by
Bo Haglund and developed by Søren Hein, Martin Nygren and the DDS contributors. Its search
algorithms and engineering make this harness's double-dummy evaluations
possible. The bundled sources retain their original notices and Apache 2.0
license. See `vendor/DDS_SOURCE.md` for the exact upstream revision.

The self-play branch incorporates the compact-rank and related-layout work in
[Faster-DDS](https://github.com/maxschireson/Faster-DDS/tree/codex/related-layout-batches-20261108).
DDS's existing transposition-table proof generalization supplies the reuse;
the additions validate related worlds, manage safe cache lifetime, expose
all-move batches to Python, and collect information-legal training examples.
Max Schireson specified the self-play, near-tie exploration, policy-learning
and belief-learning objectives; OpenAI ChatGPT/Codex assisted with the adapter,
data pipeline, tests, measurement and documentation. These additions retain
Apache-2.0 licensing. No alpha-mu implementation is incorporated in this branch.

The external-engine adapter and historical integration experiment use
[BEN](https://github.com/lorserker/ben) and the work of its contributors.
BEN code and model weights are external; their own license
terms apply. See `VALIDATION.md` for the tested revision and configuration.

This harness is independent research work. It is not an official DDS or BEN
release, and no endorsement by those projects or their authors is implied.
