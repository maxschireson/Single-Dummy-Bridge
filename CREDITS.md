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

## Alpha-mu research and the strategy extension

The central strategy-fusion and non-locality search ideas come from:

- Tristan Cazenave and Véronique Ventos, *The αμ Search Algorithm for the Game
  of Bridge*, arXiv:1911.07960 (2019; later published in the Monte Carlo Search
  proceedings). https://arxiv.org/abs/1911.07960
  Author-hosted paper: https://www.lamsade.dauphine.fr/~cazenave/papers/AlphaMu.pdf
- Tristan Cazenave, Swann Legras and Véronique Ventos, *Optimizing αμ* (2021),
  arXiv:2101.12639. https://arxiv.org/abs/2101.12639
  Author-hosted paper:
  https://www.lamsade.dauphine.fr/~cazenave/papers/OptimizingAlphaMu.pdf

The new `bridge_harness/strategy.py` is an independent implementation of the
published algorithmic ideas: shared declarer decisions, per-world outcome
vectors, Pareto fronts and observation-conditioned continuations. The
optimization paper informed incremental Pareto reduction and attention to
inactive worlds. We are not claiming to have invented alpha-mu or to have
reproduced all its optimizations. The literature also builds on earlier work by
Ian Frank, David Basin and Matthew L. Ginsberg on imperfect-information bridge,
vector minimax, achievable sets and partition search.

License check, 8 November 2026: no upstream Apache-licensed alpha-mu source
release was located in the papers, author publication page or repository/web
search. The original arXiv paper uses arXiv's non-exclusive distribution license;
the optimizing paper's arXiv entry links CC BY 4.0. Those are publication
licenses, not evidence of an Apache software release. No upstream alpha-mu
source, paper text, figures or pseudocode were copied into this repository.
The independently written additions use this repository's Apache-2.0 license.
DDS is separately verified Apache-2.0 and retains its existing source notices.

Max Schireson proposed and directed the consistent-strategy and related-layout
experiments. ChatGPT/Codex assisted with the new implementation, independent
policy-enumeration tests, benchmarking and documentation. No endorsement by the
research authors, Nukkai, LAMSADE, DDS or BEN is implied.
