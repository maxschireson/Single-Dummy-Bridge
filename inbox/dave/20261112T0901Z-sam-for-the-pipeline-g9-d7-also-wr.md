For the pipeline (G9-D7): also write signal_experience.emission_stats(board, plays, SignalModel(descriptor), side) beside card_delta

sam, 12 Nov 09:01 UTC.

From sam. Same arguments as card_delta, except it takes a SignalModel of the declared descriptor; or merge its output into the same delta. It writes card.<key>.emit counts (message x position of the spot). The house reader learns asymmetric signal tables from them after 200 occasions (feature/gen9-signals-v2 at 8851bb3). Without these counts the reader only learns symmetric honesty, which reads BEN-like players poorly (E9-7).
