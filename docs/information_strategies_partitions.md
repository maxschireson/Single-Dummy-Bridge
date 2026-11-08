# Information states, strategies and certified partitions

Design contract, 8 November 2026. This describes the intended semantic model;
implementation status is explicit below. It extends the consistent-strategy
prototype, rather than treating its sampled worlds as a complete knowledge model.
Max Schireson emphasized semantic partitioning and the need to model knowledge,
strategies and reusable proofs together. ChatGPT/Codex assisted with this design.

## Objects and boundaries

| Object | Meaning | Who may access it |
|---|---|---|
| World/history | Complete card allocation and trajectory; persistent opponent types and private state when modeled | Simulator, verifier, training critic |
| Public record | Contract, vulnerability, auction, exposed cards, played cards and public agreements | Every actor |
| Actor view | Public record plus that actor's private cards and permitted memory; declarer also controls dummy | That actor's policy and belief builder |
| Information set | All histories indistinguishable to an actor under the observation rules | Reasoning layer; represented by constraints or hypotheses |
| Belief | Weighted uncertainty over histories/worlds and opponent types, conditional on an actor view and an inference model | That actor's planner |
| Strategy | Mapping from actor views and permitted memory to legal action distributions, including observations, fallback and replanning | Executor and evaluator |
| Partition | An abstraction with a declared preservation property and domain | Search/cache/verifier; never implicitly authoritative |
| Certificate | A strategy or bound, its assumptions and domain, and evidence for its preservation property | Cache and verifier |

Information-set membership is a statement about distinguishability, not a
probability. Hard knowledge follows from rules and observations. A model assigning
zero probability to a legal layout is not the same as proving it impossible.
Finite particles approximate a belief; they do not redefine the observation
rules. Sampling IDs, the actual hidden layout and simulator type labels never
enter an actor view.

At perfect recall, views preserve all observations and the actor's own actions
that can affect later decisions. A compact state may replace the record only
under an explicit sufficiency argument for the policy and inference model. A
void summary can preserve hard card constraints while losing the likelihood
information in a discretionary discard. Rank or suit names can matter to signals
and agreements even when their card-play mechanics are interchangeable.

## Mathematical contract

Let `h` be a complete history, including latent opponent types and any private
memory that affects their responses. The observation map `O_i(h)` determines
what actor `i` can distinguish:

`h ~_i h'` exactly when `O_i(h) = O_i(h')`.

A legal strategy `pi_i` has the same action distribution at any two histories in
the same information set. Its support lies inside the legal actions of that
view. This is a constraint on the strategy, independent of which worlds a sampler
happened to draw. A public action can refine different actors' information sets
in different ways because their private cards differ.

A belief `b_i(h, theta)` is conditional on that view and a versioned generative
model. Updating on another player's observed action `a` requires that player's
action likelihood from **their** view:

`b_i'(h a, theta) proportional to b_i(h, theta) * pi_j(a | O_j(h), theta_j)`.

Rule consistency gives the hard support filter. The action likelihood adds
soft inference: failure to cash an ace can be unlikely for a strong player while
remaining possible for another type. The current uniform sampler implements
only the hard filter. Zero likelihood from a model remains distinct from logical
impossibility. With uncertain opponent policies, integrate over their persistent
types rather than drawing a fresh skill level at every move.

For the current deterministic-declarer/omniscient-defence model, each executable
policy has a vector `v_pi(w)` of guaranteed outcomes, one per world. The search
problem is `max_pi sum_w b(w) v_pi(w)`. A vector whose coordinates come from
different, incompatible declarer policies is not admissible. Under frozen
information-limited defender policies, replace the coordinate by the conditional
expected outcome against those policies; history/type variables must be present
where they change those responses. Under equilibrium or strategic adaptation,
this fixed-vector calculation alone is insufficient.

For a semantic partition `P` and policy `pi`, cell mass is
`B(C) = sum_{w in C} b(w)`. It suffices for **evaluating that policy** if `v_pi`
is constant on each cell. Different policies can use different partitions; to
compare them, evaluate each against the same original belief, or use a common
refinement. If values vary inside a cell, retain bounds or refine it. Cell mass
alone is insufficient to update beliefs after an action unless the likelihood
and successor-cell behavior are also preserved.

Thus the minimal semantic unit is a **proof-scoped decision problem**, not a
remaining-card diagram or a label such as "finesse". It includes the rule state,
actor distinctions, belief/model assumptions, admissible strategies and objective.
The existing immutable `Observation` is the execution boundary; `Position` is
verifier/simulator data. Generalized information-state and certificate keys must
retain the distinctions above rather than introducing a second lossy policy API.

## Each player's knowledge

There is one physical world and a different observation function for each actor.
Declarer's outer world family fixes declarer and dummy. A defender's beliefs fix
that defender and exposed dummy and must allow concealed declarer/partner cards
to vary. Conditioning declarer's family is not a valid defender belief builder.

Model defensive agreements and skill/style types as persistent latent variables,
with joint uncertainty where appropriate. The two defenders remain separate
actors with separate private views. An omniscient defensive coalition is an
explicit benchmark model, not an implementation of information-limited defence.

We need not materialize an unbounded hierarchy of "I think you think" objects to
get a sound initial model. Given a generative world model, actor observation maps,
and frozen policies that form beliefs from those views, their differing knowledge
is induced by simulation. Nested strategic reasoning can later be added with
explicit depth and model versions. A reweightable certificate must hold those
opponent responses/inference assumptions fixed.

## Strategy objects

A strategy consists of decisions, observation-conditioned branches, memory
updates, and a complete continuation rule. A decision guard must be computable
from the actor view: indistinguishable histories must give the same action
distribution. Randomization must be independent of concealed simulator facts.

The executor, rollout evaluator and training target must refer to the same policy
version, including its fallback and replanning behavior. Replanning changes which
policy is being evaluated unless that rule was included in the strategy definition.
The prototype's committed-prefix player deliberately avoids that ambiguity.

A world predicate such as "West holds the queen" may classify where a strategy
succeeds. It is **not** an admissible action guard until the actor can establish
it from observations. This separates semantic analysis of outcomes from an
illegal hidden-card lookup policy.

Useful strategy macros can express actions such as preserve an entry, cash a
suit, or exit to a defender. A macro must still account for intervening replies,
discards, ruffs, observations and resource use. Its verifier must not skip an
unforced response just because the macro has a short name.

## Different partitions preserve different things

| Partition property | What may safely be reused | What does not follow |
|---|---|---|
| Equal DD value | A perfect-information value/bound | Existence of one common declarer strategy |
| Equal outcome of one certified strategy | That policy's value/bound in its proven domain | Optimality or interchangeability of observations |
| Equivalent execution for a policy | Actions, observation transitions and rewards for that policy | Preservation of all alternative policies |
| Equivalent decision problem | The complete achievable strategy frontier under the stated model | Validity for different models, rules or scoring |
| Same best strategy for a belief region | The chosen strategy for those weights | Validity for arbitrary weights or changed support semantics |

Equal values at the current node are not enough to merge information states.
For an execution abstraction we must preserve legal actions, their correspondence
across indistinguishable histories, subsequent observable distinctions, relevant
rewards and (under a stochastic model) the corresponding transition likelihoods.
For optimization equivalence this must hold for all admissible alternatives, not
only one chosen policy. Accumulated tricks, trump, leader, the current trick,
entries and timing cannot disappear unless their irrelevance is established.

The quantifier order explains the difference between a DD region and a reusable
single-dummy plan. A common DD lower bound may say:

`for every world w in R, there exists a strategy pi_w that wins k tricks`.

A common single-dummy guarantee must instead provide:

`there exists one information-consistent strategy pi that wins k tricks in every world w in R`.

Both statements also quantify over the allowed defender responses. Contingent
branches in the latter strategy are allowed, but only on observations. Reusing
the first statement as if it were the second is strategy fusion.

## Proposed certificate format

A durable certificate should identify:

1. The rule/scoring versions, actor role, opponent model and inference assumptions.
2. The exact input domain: known cards, unseen pool, ownership constraints, public
   history/state and any required knowledge predicates.
3. A strategy witness (preferably a shared graph or verified macro program).
4. Its outcome function or lower/upper bounds on semantic cells of that domain.
5. The observation mapping that makes its branches executable.
6. The proof scope: exhaustive domain, formal proof, sampled verification or
   unverified hypothesis. These scopes are never interchangeable cache entries.
7. Canonicalization maps and any probability/likelihood transforms used on lookup.

World predicates may include honour ownership, suit-length intervals, voids,
entry availability, trump control and whether an exit can be taken safely. A
certificate's knowledge predicates state what can be inferred before a choice.
The allowed predicate language should grow from failed verification cases rather
than from an attempt to encode every bridge concept in advance.

Lower-bound certificates can generalize further than exact-value certificates.
For example, a common plan that guarantees two tricks may remain valid after
changes that permit a third trick in some worlds. We should preserve that useful
bound without claiming to have proved the optimal value in all of them.

## Beliefs and reweighting

For a fixed opponent model and complete executable policy, store outcomes as a
function of the world (and opponent type, if modeled), rather than as one scalar
value at one belief. A new belief changes the masses of the semantic cells and
therefore the strategy's weighted value. The best strategy is selected only after
that aggregation; the actor never observes which hidden cell is actually true.

For a completely solved finite domain, the root Pareto frontier can be reweighted
for any nonnegative weights. A strategy on a reduced support can be extended to
extra zero-weight worlds; keeping the full-domain frontier therefore also serves
those sub-supports. This claim assumes unchanged observations, legality and
opponent model. It does not justify reweighting an eight-world sample as if it
covered unexamined layouts.

Each policy's fixed-model expected value is linear in the weights, so the regions
of belief space selecting particular policies can be represented implicitly.
A table for every possible probability vector is unnecessary. However, the
number and size of policies/frontier regions may still be large. Full Pareto
frontiers remain necessary during adversarial composition; pruning merely to a
locally favorite strategy repeats the non-locality error.

## Symmetry, relevance and counterexamples

For DD, preserving the rank order within each suit and permuting equivalent suits
are safe mechanical symmetries. For single dummy, any renaming must be consistent
across the entire world family and all observation/action maps. Normalizing each
world independently can change which histories are distinguishable. Under a
realistic defender model, carding conventions and action likelihoods must also
transform consistently; a mechanical symmetry alone is insufficient.

Beyond isomorphism, use a generate/verify/refine loop:

1. Solve a concrete information-state family and retain an executable witness.
2. Propose erasing a fact or replacing it by a weaker semantic condition.
3. Verify the proposed region, including every relevant defender response and
   future observation distinction under the stated model.
4. If verification fails, retain a counterexample classified as illegal action,
   missed observation, incorrect reward, or changed response likelihood.
5. Refine only the distinctions needed to repair the certificate; measure lookup
   and verification cost as well as coverage.

A successful spot check cannot certify the untested part of a proposed region.
A language model or learned network may suggest predicates/macros, but promotion
to a sound cache entry belongs to the verifier. Approximate learned value models
remain useful and should occupy a separate, explicitly approximate cache path.

## What this revision actually implements

`partitions.EndingDomain` enumerates the complete East/West allocation family at
a trick boundary, with fixed declarer/dummy cards and optional hard voids.
`certify_domain` computes a complete alpha-mu frontier and executes every retained
policy against all legal omniscient defensive responses in every domain member.
`OutcomePartition` describes policy outcomes using ownership and suit-length
predicates, checks those cells exhaustively on the declared finite domain, and
rejects out-of-domain queries. `CertifiedFrontier.best` can reweight the proven
frontier without another search, including zero-weight sub-supports.

This is a small, concrete foundation for the model above. The outcome trees are
not universal semantic proofs, do not generalize outside the enumerated domain,
and are not yet a cache of arbitrary three-card information states. Their hidden
predicates are evaluator-only; play still uses the original executable witness.
Persistent disk caching, compact verified macros, inference over opponent types,
and sound generalization beyond the finite domain remain future work.
The partition benchmark additionally measures exact policy-suffix sharing and
compressed witness payloads, then decodes and executes every witness again.
Those payloads omit domain/model/proof metadata and are not standalone cache
entries. Measured results and reproduction commands are in
[the cost and partition report](../reports/strategy_cost_and_partitions.md).

## Related research

Isaac Stone, Nathan R. Sturtevant and Jonathan Schaeffer's *Set-Based Retrograde
Analysis: Precomputing the Solution to 28-card Bridge Double Dummy Deals*
(IJCAI 2025) supplies important evidence that set representations can compress
bridge endings. It concerns double dummy; equal DD values do not establish our
stronger common-strategy/observation requirements. No source code from that work
is incorporated here.
https://www.ijcai.org/proceedings/2025/0995.pdf

The alpha-mu attribution and source/license distinctions remain in `CREDITS.md`.

## Near-term player: better beliefs and learned selection around PIMC

Max Schireson's follow-up proposal is the preferred next experiment: retain
PIMC as the tactical evaluator, learn better hidden-layout populations, and
learn to choose among PIMC-equal plays from self-play outcomes. The present
1,000-board measurements do not justify paying for alpha-mu at every small ending.
The changes below are a design and experiment plan; no trained network is
included in this revision.

**Belief model.** Input is the actor view, including auction/play history and
public agreements, plus uncertainty over persistent opponent types. Output is
a calibrated distribution over legal *joint* layouts. Independent per-card
marginals can be features, but they do not by themselves describe correlated
honor locations or a valid hand allocation. Begin by scoring/resampling the
existing constraint-valid hypotheses, keeping a uniform component to reduce
the chance of losing important low-probability worlds. That mixture is an
explicitly tempered belief if used directly. If it is only a sampling proposal
for a different target posterior, carry the proper importance weights. Do not
apply likelihood weights twice. Monitor effective sample size and posterior
calibration, then grade the resulting choices by actual tricks and total cost.
For a fixed proposal budget, scoring cannot recover a layout absent from every
proposal; broader proposals or a constrained generative sampler are later steps.

**Move selection.** Preserve all legal moves tied at the best PIMC estimate for
the first ablation. A second ablation includes near-ties based on the *paired*
per-world value differences between moves, a small held-out tuned margin, and
later a learned model-error estimate. Sampling confidence alone does not cover
strategy-fusion bias. For example, a falsely optimistic move can be uniquely
best under DD and exclude the actual single-dummy best move under a hard tie-only
gate. Measure how often that gate excludes a good move on reference endings.

Feed the selector the actor view, candidate cards, belief summaries and aggregate
PIMC features. Predict realized continuation value or relative advantage for
each candidate. There is no need to expose a supposed "actual" hidden layout.
Per-world tactical payoff vectors may inform aggregate features because they are
simulated hypotheses, but their arbitrary ordering must not become an input
signal. The same actor view and controlled random seed must still yield the same
action distribution in different actual worlds.

A useful later parameterization is `Q_actual(I,a) = Q_PIMC(I,a) + r_theta(I,a)`,
with the residual learned from continuation outcomes in the same trick units.
At an exact tie the residual alone ranks the moves. It need not always be
negative: imperfect defenders can concede more than the DD result. The residual
is an empirical correction, not a certified fusion penalty. Start with the
restricted selector before permitting a residual to overturn larger DD gaps.

**Targets and self-play.** Use real episode trick totals and, selectively, paired
continuation rollouts starting from the same information state. Branch the
candidate actions across the same held-out hidden layouts and frozen opponent
versions to reduce noise. Every continuation player receives only its own view;
no branch is labeled by simply playing DD thereafter. Full state may be a label
or a training critic input, never a deployed actor input. Log exploration and
action propensities to avoid treating unchosen moves as observed failures.
Train over a retained pool of opponents, agreements and policy generations;
split by original deal/fixed-NS family, not by decision rows. Freeze belief,
selector and defender versions during each evaluation. This avoids claiming
general strength from a convention or weakness unique to one self-play pair.

Belief supervision predicts the actual hidden cards from permitted information.
Policy supervision predicts outcomes attainable by the deployed continuation.
These targets must remain separate: directly optimizing belief weights to make
PIMC win can turn a nominal probability model into an uncalibrated action heuristic.
Shared encoders are possible, but their output semantics and calibration remain
separately testable.

**Exact search and partitions.** Keep alpha-mu as a reference oracle under its
stated omniscient-defence model, a producer of strategy witnesses/fusion examples,
and a candidate for selective escalation. It is not an optimal teacher against
every realistic defender pool. Semantic outcome predicates can provide auxiliary
learning targets, e.g. whether a particular policy succeeds when an honor is on
one side, while observation-conditioned policy branches teach how that success
can be achieved without being told the honor's actual location. A learned
selector approximates the strategy-ranking calculation in a forward pass; it
does not certify a strategy or eliminate fusion by construction.

**Arena matrix.** Compare baseline PIMC-8, PIMC-16, belief+PIMC-8,
selector+PIMC-8, and belief+selector+PIMC-8. Separate exact-tie and near-tie gates;
test any learned override of clear PIMC preferences as a further ablation. Start
with the existing 1,000-board suite for development, then freeze choices and use
a new held-out suite with several defensive opponents for promotion. Include
all belief/selector inference in playing-time cost. Track training/data generation
compute separately, including an amortized view at declared numbers of boards.
Rank by tricks/board versus compute on a Pareto curve, and report the requested
tricks per board per time doubling for meaningful slower/faster comparisons.
If added inference has almost no cost, emphasize absolute gain and cost rather
than inflating a ratio whose denominator is near zero.

Related prior work includes *All Simulations Are Not Equal: Simulation Reweighing
for Imperfect Information Games*, an ICLR 2020 submission whose retrieved
primary version is anonymous. It describes learned likelihoods of past play to
weight bridge simulations. This supports exploring learned beliefs; it does not
establish the performance of our proposed selector. No code or text is copied.
https://openreview.net/attachment?id=HJlyLgrFvB&name=original_pdf
