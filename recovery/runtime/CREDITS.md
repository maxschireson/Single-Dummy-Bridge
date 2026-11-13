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

The fast auction collector calls the externally installed BEN v3 encoder and
neural bidder (revision `9b5f43104aeac713a80b73513f2f2d6daf9f8769`). BEN is
GPL-3.0; its source and trained models are not redistributed here, and their
own licensing terms apply. BEN and its contributors supplied the bidding
models and feature encoding; this project adds batching, collection/audit
logic, explicit data separation and the small experimental belief models.

The DDS-only bidding league was requested and directed by Max Schireson, with
implementation and validation assisted by OpenAI ChatGPT/Codex. Its initial
policy is BEN's external `GIB-BBO-8742_2026-10-23-E30.keras`, trained by BEN's
contributors on auctions from Edward Piwowar's EPBot/Bridge Bidding Analyser.
The new encoder implements the public 193-feature model interface and is
audited against BEN at runtime; no BEN source or weights are bundled. External
and fine-tuned model artifacts remain subject to the applicable upstream terms.

The design is informed by Edward Lockhart et al., *Human-Agent Cooperation in
Bridge Bidding* (2020), https://arxiv.org/abs/2011.14124, and John Schulman et al.,
*Proximal Policy Optimization Algorithms* (2017), https://arxiv.org/abs/1707.06347.
This implementation uses direct paired terminal-reward PPO, not the bridge
paper's search-distillation implementation. No code from either paper is copied.
