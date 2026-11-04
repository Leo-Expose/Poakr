# CORA: scope and proofs

CORA means **Certified Outcome-and-Range Algebra**. This is a substantially different architecture from this project's previous scalar-equity controller. It is not a claim of worldwide research priority. Inclusion–exclusion, Bayesian conditioning, exact aggregation, and stopping certificates are established mathematical tools; this workspace-only work cannot establish whether this combination has appeared elsewhere.

## 1. Exact blocker-incidence geometry

Fix a fully public final board and a two-hole-card game. Let `M` be the number of cards outside that board, `N = choose(M, 2)`, and evaluate the final score of every candidate pair exactly once. For a candidate `h = {a,b}`, define:

- `G_<`: number of all candidate pairs with score strictly below h;
- `G_=`: number tied with h;
- `I_a,<`, `I_b,<`: corresponding strict-lower incidences of cards a and b;
- `I_a,=`, `I_b,=`: corresponding tie incidences.

A legal opposing pair contains neither a nor b. By inclusion–exclusion:

```
L(h) = G_< - I_a,< - I_b,<
T(h) = G_= - I_a,= - I_b,= + 1
q(h) = [L(h) + T(h)/2] / choose(M-2, 2)
```

The strict-lower intersection term is zero: the only pair containing both a and b is h itself, whose score is not strictly lower. The tied intersection term is one, which explains the easily missed `+1`.

For standard Hold'em, M=47, N=1081, and each candidate has 990 disjoint peers. This derives **all candidates' uniform-opponent river equities**, not just the hero's, without evaluating every candidate–peer pair. Opponent percentile is a possible policy feature, not knowledge of their actual cards.

Implementation complexity, excluding the score evaluator's internals: score grouping `O(N log N)`, incidence/prefix construction `O(D U + N)`, storage `O(D U + N)`, where D is deck size and U is the number of distinct scores. Do not describe this dense-prefix implementation as an unconditional `O(N log N)` algorithm. Its worst-case variable-deck histogram cost is larger. The quadratic oracle instead visits approximately N² candidate–peer relationships.

Exactness is relative to the supplied deck, rank rules, and final-board evaluator. The controller/transport currently support only the documented standard two-hole, five-board EXAMPLE game. Kernel tests additionally cover short-deck and no-wheel scoring; they do not certify the entire controller for those variants.

## 2. Exact behavioral quotient, not approximate card clustering

For the hero's known cards and the final board, remove all incompatible opposing pairs. Associate each surviving pair u with:

```
key(u) = (opponent percentile z(u), hero outcome g(u))
g ∈ {-1, 0, +1}
```

The implemented 144 policy types use only z and public context for their action likelihood. Represented terminal payoffs use only g and public amounts. Thus two pairs with the same key have identical likelihoods and represented payoffs for every implemented query.

Let J(t,u) be the dense policy-type/card joint mass. Store instead:

```
Q(t,c) = Σ[u in class c] J(t,u)
```

Initially, each class receives its actual cardinality divided by the number of legal opposing pairs—NOT equal mass per class. For any represented observation with likelihood l(t,c):

```
Σ[u in c] J(t,u) l(t,c) = Q(t,c) l(t,c)
```

Normalization uses the same total mass. Induction establishes equality after every represented update. Expected payoff and continuation/win masses are also identical because their integrands are constant inside each class. This is an exact sufficient representation **for this likelihood/payoff/observation family**.

It is not lossless for arbitrary poker strategies. Suit-specific actions, additional revealed card identities, changed rules, or richer payoff/likelihood functions may require splitting classes. Early streets with future public cards are not covered by this river quotient theorem.

## 3. Proper public-action likelihoods and exact showdown conditioning

The corrected implementation represents 144 types:

```
4 value thresholds × 3 bluff rates × 3 call slacks
× 2 raise rates × 2 value/weak-only styles = 144
```

For legal action probabilities p(a), use a small uniform contamination component:

```
p_robust(a) = (1 - k ε) p(a) + ε
ε = .002; k = number of legal action kinds
```

The resulting probabilities sum to one. Only check is possible in a forced free-action context; faced actions are fold/call, plus raise only when available. The continuation query sums the same legal call/raise probabilities, including their contamination mass. It respects whether a re-raise is actually available after the proposed bet.

**Audit correction:** the earlier version independently clipped three action likelihoods, which could make their sum exceed one. Its older holdout and exploratory scores are preserved, but they are not final corrected-version evidence.

For a noiseless public showdown outcome o, multiply the card joint mass by `1[g(u)=o]`, then normalize. An impossible outcome is rejected. No actual opposing hole cards are required or read. This differs from the earlier `.002` soft outcome mismatch.

The next modeled hand's type prior includes `.005` uniform contamination to tolerate strategy changes. This is a specified regularization/transition assumption, not proof that the true opponent belongs to the family. Exact arithmetic/aggregation do not make a misspecified opponent model correct. The early-street frequency adjustment, sampled preflop table, sampled flop/turn equity, and one-response river value remain approximations.

### Interruption/replay invariant

Action update calculations use local arrays. Only after normalization succeeds is `(joint, event_id, evidence_count)` replaced in one assignment. An injected interruption before that commit leaves the prior state unchanged. Replayed event indices do not apply evidence again. This addresses recoverable deadline exceptions, not recovery from an external process kill. The latter causes forfeiture under the stated competition rules.

## 4. Conditional match-win certificate

Let B be own raw chip profit from **completed** hands, C actual chips already paid in the current hand, H hands remaining **including the current one**, and F an upper bound on the own forced posting cost in each later hand. Under a legal perpetual check/fold abandonment policy:

```
final own net >= B - C - (H-1)F
```

The current hand can lose no more than its paid contribution if no further voluntary payment occurs. Each later hand loses no more than its forced-post bound. Summing those adversarial lower bounds proves the inequality.

If the right side is strictly positive, raw-net match scoring yields a guaranteed match win, conditional on these premises:

1. B is completed-hand own net, not twice that chip difference or a capped score.
2. C is actual paid contribution, not pot size or a displayed bet target.
3. Stacks reset and all mandatory charges are bounded by F.
4. The declared posting bound remains valid: no unaccounted antes, growth, or fees.
5. Free check/fold abandonment remains legally available on every future request.
6. Positive final raw net is the relevant match-win criterion.
7. The process finishes legally within its clock; a forfeiture is not a chip outcome.

The EXAMPLE adapter enables this only with an explicitly asserted contract. The unknown official rules do not yet establish it. A boundary equal to zero guarantees no win; the code uses a strict positive threshold.

This certificate does **not** guarantee a win before the condition is reached. It also does not optimize the unknown chip tie-break. Locking deliberately sacrifices surplus expected chips after a primary match point is secured. Consequently there is no claim of universal no-tradeoff tournament dominance.

## 5. Preflop amortization

The 169-class table was generated once with 16,384 independent-model draws per class. The simultaneous 98% Hoeffding bound is approximately ±.01724, assuming the stated independent uniform-draw model. The runtime reports a conservative ±.018 interval. These are sampled estimates, not exact preflop equities and not confidence intervals on win rate. Offline work is included in provenance, not hidden as free computation.

## What is—and is not—certified

**Exact:** final-board combinatorial geometry; represented quotient; normalization of the specified policy probabilities; conditioning on a valid public showdown; the conditional raw-net lower-bound theorem.

**Empirical:** strategic win rate, latency, memory, and recovered deadlines on the supplied synthetic fixture/opponent families.

**Unproven/unknown:** true opponent range, full-game optimality, performance against strong adaptive competitors, global novelty, official variant/protocol/clock compatibility, tournament tie-break dominance, Python 3.11 execution, and winning every game.
