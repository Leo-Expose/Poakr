# Pokerbot — hardened prototype

## Scope and validation boundary

The **shipped decision engine is `runtime/bot.py`**: a single Python file using
stdlib and NumPy. No network, package installation, or development-package
imports are required at runtime.

**It currently evaluates standard 52-card Hold'em: two hole cards, five board
cards, standard hand ranking.** A configurable offline game engine does not make
the shipped evaluator variant-agnostic. A custom competition variant must be
implemented explicitly before submission.

The wire parser accepts several plausible formats, but it is **not yet an
adapter verified against the official competition protocol**. Neither successful
local tests nor an exception barrier guarantees that tournament forfeits are
impossible. The official runner, lifecycle, action grammar, legal sizing, scoring,
and replay semantics remain release gates.

## Layers

| Layer | Implementation | Qualification |
|---|---|---|
| Match objective | Signed risk dial based on lead and remaining fraction | Heuristic; ablate rather than assume it helps |
| Equity | Embedded NumPy evaluator, random-opponent Monte Carlo, early stopping | Random-range model is not a calibrated opponent range |
| Time bank | Cumulative equity-time accounting, bounded requests, exhausted-bank safe action | Does not account for every external scheduling/import/serialization cost |
| Features | Equity, pot odds, street, stacks, legal actions | Transferable features do not automatically transfer the rules |
| Shell | Parsing, exception barrier, legal-action projection | Official protocol integration still required |
| Opponent model | Beta counts for explicit observed responses | Never learn from mere mentions in legal-action lists |
| Duplicate inference | Unique, card-disjoint board matches; optional pair IDs and showdown verification | Conditional on actual same-deal seat-swapped replay |

## Duplicate inference: what is and is not justified

If a deal fixes `(H1, H2, board)` and is replayed with seats swapped, our copy-1
hole cards are the opponent's copy-2 hole cards. Remembering our own previously
observed cards is not hidden-state access. **Official format and code-review rules
must still confirm this use is allowed**; no local test can certify legality.

Both players could track the replay. We must not assume opponents are unaware.
If they are unaware, value betting known winners can exploit the asymmetry. If
they also track, the betting game changes; checking down is not generally a
universal optimal strategy either.

### Safety rules in the shipped tracker

- Store only hole cards and boards present in our requests; never feed it the
  simulator's unrevealed full runout.
- Require at least three observed replay matches before enabling inference.
  Early folds censor boards, so backward-match rate need not be exactly 50%.
- Match every shared board prefix. A matching flop followed by a conflicting
  turn is rejected.
- Require one unique candidate hand; reject overlap with our hole cards or the
  current board.
- Use explicit hand IDs for boundaries when present. Without IDs, canonical hole
  changes or a board reset are best-effort boundaries, not a complete protocol.
- **Never infer preflop from adjacency alone.** After copy 2, the next hand is a
  new copy 1; the previous hand is not its partner. Preflop inference requires an
  explicit `duplicate_pair_id` with the announced semantic meaning.
- An optional structured `type=showdown`, `hand_id`, `opponent_hole` event is
  compared only against an inference recorded for that same hand. A contradiction
  disables all subsequent duplicate inference for this tracker instance.
- No showdown field means the hidden-card swap remains unverified. Repeated
  boards alone do not prove hole cards were swapped.

The 0.7/0.85 confidence values are engineering gates, **not calibrated posterior
probabilities**. They cannot justify a guarantee of no harm.

### Known-hand equity and actions

`equity_vs_known` uses the embedded batch evaluator:

- River: one deterministic comparison.
- Turn: all 44 possible river cards (both hole pairs are known).
- Flop: all 990 unordered turn/river combinations.
- Preflop, when an explicit pair ID permits inference: 512 uniformly sampled
  boards; this is an estimate, not exact equity.

Invalid/overlapping cards raise instead of fabricating 50% equity. The decision
caller falls back to hidden-information play. Compute is charged to the time bank.

Calls use `equity > call_amount / (pot + call_amount)`, rather than an arbitrary
52% threshold. Value sizes are projected onto the actual legal set. Speculative
known-hand bluffs require observations, not merely an unobserved fold-rate prior.
These remain heuristics: future betting, opponent ranges, and match utility can
make raw showdown equity insufficient for optimal play.

## Match-risk mathematics

For approximately independent, stationary per-pair returns with mean `mu` and
standard deviation `sigma`, a normal approximation gives

`P(final net > 0) ≈ Phi(mu * sqrt(n) / sigma)`.

This explains why chip expectation alone may not maximize match win probability.
It does **not** prove that our particular threshold dial is optimal. Duplicate
correlation must be handled at the pair level; adaptive policies and heavy tails
can invalidate a stationary normal approximation. The benchmark includes a
neutral-risk-dial ablation to test the implemented heuristic.

## Reproducible local validation

```bash
python3 bench/test_bot.py
python3 bench/test_duplicate_safety.py
python3 bench/fullmatch.py --matches 8 --deals 60
python3 bench/fullmatch.py --matches 16 --deals 100 --seed-base 23000 \
  --aggressor --risk-ablation --output holdout_results.json
```

The match harness drives the shipped `decide()` function. It maps the offline
engine's street indexing to the shell's indexing, supplies the configured raise
limit, preserves RNG state, resets the time bank per match, and asserts legality
rather than allowing simulator coercion to hide errors.

It feeds public end-of-hand action histories into the opponent model. An official
protocol must expose equivalent structured observations to reproduce that part of
the result. The benchmark therefore tests the decision core plus a public-history
adapter, not the official wire implementation.

Opponents are synthetic random-equity policies: an over-folder, a calling station,
a moderate policy labeled `Balanced`, and optionally an aggressive policy.
`Balanced` does not mean equilibrium-optimal. Tests against these policies are
useful diagnostics, not proof of dominance against strong or duplicate-aware bots.

## Evidence files

- `bench/bot_safety.log`: shell/sanity/basic-time tests.
- `bench/duplicate_safety.log`: adversarial duplicate/equity/portability tests.
- `bench/fullmatch_results.json`: earlier paired pilot; eight 60-pair matches per
  opponent, three opponents. Full policy won 23/24; no-duplicate ablation 20/24.
- `bench/holdout_results.json`: longer, fresh-seed test including risk ablation.
- `VALIDATION.md`: consolidated results and release limitations.

Earlier prototype chip-edge measurements are exploratory; the integrated paired
results should take precedence. No claim of globally novel research, optimal
strategy, guaranteed safety, or guaranteed tournament success is established.
