# OpenSpiel and the “never loses” target

**2 November 2026. Champion unchanged. OpenSpiel algorithms NOT executed here.**

## Bottom line

OpenSpiel is relevant for finding best responses, measuring exploitability, and researching low-exploitability policies. It cannot make a mathematically impossible 100% strict-win requirement possible. The framework paper lists CFR, CFR-BR, best response/exploitability and Monte Carlo CFR. [1](https://arxiv.org/pdf/1908.09453)

I reviewed the official algorithm catalog, game catalog, developer guide, concepts and API reference. Local probes found neither `pyspiel` nor `open_spiel`. No package was downloaded or installed, and neither was added to the submitted bot. All executable results below use our own standard-Python/NumPy/SciPy research code and the supplied evaluator, **not an OpenSpiel solver run**.

## 1. Three different requirements

| Requirement | What it actually says | Current status |
|---|---|---|
| 100% strict wins | Final match net >0 against every legal opponent and deal | Impossible under the legal-outcome quantifier: shared-royal counterexample below |
| Never loses | Final net >=0 on every legal opponent/deal/execution path | Not established; existing candidate has actual recorded losses. The royal tie witness alone does not disprove every hypothetical nonloss strategy |
| Conditional certified win | Once a verified positive floor is armed, preserve that original floor against all legal continuations | Existing proof-backed controller; conditional on correct rules/accounting, legal completion and no forfeit |

A zero-exploitability equilibrium protects an expected game value against best responses in the specified model. It does **not** make every realized hand/match a win or remove adverse chance. More CFR iterations do not turn an expectation guarantee into a pointwise one.

## 2. Executable actual-variant counterexample

- Hero retained cards: `2c 3d`.
- Public board: `Ts Js Qs Ks As`.
- Public discards: `4h 7h`.
- Every one of the **903 physically legal opposing retained pairs** ties on the board.
- Our physical-pair engine and the **supplied organizer evaluator both agree**: royal flush, no strictly winning hero showdown.

Use a legal opponent that always checks/calls and discards a legal private card. It never gives up the pot. Equal reset stacks let it match every legal wager. Hero reaching showdown nets0; hero folding loses its contribution. Repeat legal shared-royal duplicate deals: the hero's total cannot be positive, regardless of its betting/discard policy or realized random choices.

This is a legal-world impossibility witness, not a prediction that royal boards are the practical dominant failure mode, and not an exploit of the runner's seed implementation. The argument is mathematical; exhaustive ranking verifies its card fact, not an enumeration of every betting policy. Source/evidence: `tools/openspiel/audit_guarantees.py`, `evidence/openspiel/2026_11_02/objective_audit.json`.

## 3. What OpenSpiel contributes

The reviewed official documentation describes these capabilities:

| Capability | Useful role here | Does NOT establish |
|---|---|---|
| CFR / external-sampling MCCFR | Offline equilibrium research on a correct finite game or declared abstraction | Perfect play after a finite run, 100% match wins, or safety outside the model |
| Best response / exploitability | Attack a fixed policy with an information-respecting adversary | Low true exploitability from merely failing to train a strong attacker |
| CFR-BR / restricted-response approaches | Research robustness/exploitation trade-offs | A free improvement with no downside; catalog testing status varies |
| Game/State and information-state APIs | Represent chance, private cards, legal actions and public history | Correctness of a custom adapter merely because it loads |
| Simultaneous-to-turn-based transformation | Model two hidden commitments without revealing the first choice | Permission to show the first player's discard before the other acts |

Sources: [official algorithms](https://openspiel.readthedocs.io/en/latest/algorithms.html), [concepts and transformations](https://openspiel.readthedocs.io/en/latest/concepts.html), [developer guide](https://openspiel.readthedocs.io/en/latest/developer_guide.html), [API](https://openspiel.readthedocs.io/en/latest/api_reference.html). These are documentation snapshots consulted on this date, not a locally installed/pinned OpenSpiel release.

The reviewed [game catalog](https://openspiel.readthedocs.io/en/latest/games.html) lists Kuhn, Leduc and ACPC-backed Hold'em. It does not establish a ready-made game matching our Discard Hold'em. Setting a hole-card count to3 is not a verified implementation of simultaneous exposed postflop discarding, all-in discarding, dead-card removal, our raise rules, duplicate match lifecycle, or match-level scoring. **Treat a custom, differentially tested game adapter as required.** No such full adapter is claimed implemented here.

## 4. New exact objective audit: distinguish money from winning

I extended our own fully enumerated three-card Kuhn lab. Each player has64 complete own-card-only pure strategies; there are6 ordered deals, giving **24,576 strategy-pair/deal outcomes**. Strategies choose a single action per information state, not a different action after seeing an opponent's private card.

SciPy locates primal/dual LP candidates. Exact `Fraction` arithmetic then checks all inequalities and confirms a zero rational gap for every reported value. No statistical sampling or floating tolerance is used as the final certificate.

| Objective, first player | Uniform chance, worst opponent | Worst legal deal and opponent |
|---|---:|---:|
| Expected chip payoff | −1/18 | −1 |
| Probability of strict win | 1/2 | 0 |
| Probability of nonloss | 1/2 | 0 |

The adverse-deal column still averages over the hero's own mixed-strategy randomness; a value0 or negative already precludes a 100% favorable-path claim. Kuhn has no terminal ties, so win/nonloss coincide **there**, unlike Discard Hold'em. These are exact **toy-game** results, not the value, exploitability or win probability of our real candidate. OpenSpiel was not used to produce them. They are a future independent comparison oracle, not a claimed cross-library comparison.

Files: `research/openspiel_bridge/objectives.py`, `evidence/openspiel/2026_11_02/objective_audit.json`.

## 5. New information-safety foundation

Implemented `research/openspiel_bridge/discard_information.py`: a small immutable **discard-stage information contract**, not a `pyspiel.Game` or a full betting engine.

Its policy key includes ordered own original cards, exposed flop, public accepted-action history, own/opponent paid amounts, seat, hand/total, configured match cap and public match net. It excludes:

- actual opposing private cards;
- the predealt turn and river;
- the other player's sealed discard commitment.

The joint choice has3×3 legal discard combinations. Either commitment order produces the same joint result; neither discard is exposed until both have committed. A player cannot take a second discard decision. All three possible first-player choices produce an identical second-player information key and action set. Tests also change hidden peer cards and future board while preserving visible state and verify identical keys.

The contract retains own-card order and complete supplied public history rather than silently claiming a lossless card abstraction. It validates card collisions, matching flop contributions and basic fields. **Full history replay, chance sampling, legal betting transitions, showdown, match lifecycle and actual OpenSpiel registration remain unimplemented in this contract.** Do not mistake privacy tests for whole-game semantic validation.

## 6. Correct objective and evaluation plan

The tournament's primary outcome is match points (win1/draw0.5/loss0), not merely expected hand chips. Model total match net B at termination:

- chip utility: B;
- match-point utility: sign(B), an affine equivalent of match points;
- strict-win utility: indicator[B>0];
- nonloss utility: indicator[B>=0].

Those objectives are not interchangeable. A chip-equilibrium hand policy is not automatically a match-win-optimal policy. The official clipped MATCH net remains a secondary tie-break; do not replace it with per-hand clipping or an unannounced weighted reward. Full match score/hands remaining increase the state needed for an exact match objective.

Recommended staged work:

1. **Exact semantic adapter:** cross-check full transitions against the supplied engine, including all five worked examples, minimum/short-all-in raises, simultaneous discard, exposed dead cards, folded three-card results, payouts and normal stage caps.
2. **Information-set audit:** merge only states with the same permitted observations/recall; keep sealed commitments hidden. A best responder cannot choose after inspecting hidden peer cards. New tests cover the discard-contract foundation only.
3. **Small-game reference:** when OpenSpiel is available in an approved offline environment, compare Kuhn values/BRs against our independent exact audit. Pin its release/commit and build features. No install/version is currently validated.
4. **Explicit abstraction:** begin with declared small deck/action sets. State which opponent actions were removed. Low abstract-game exploitability is not a full-game certificate; removing adversary actions can hide exploitation.
5. **Adversarial evaluation:** exact information-set best responses where tractable; legal learned responses elsewhere. A learned attack gives a lower bound on best possible exploitation, not a certified upper bound when it finds little gain.
6. **Production export:** only an approved, compact own policy representation in the stdlib/NumPy bot. No `pyspiel`, OpenSpiel native library, runtime files/network/processes or runtime installs. Keep exact certified-floor logic as an independent shield.
7. **Promotion:** fresh adaptive opponents/holdouts, lower-tail and match-point reporting, no weakened proof gates, real Python3.11/image and clock-enabled host validation. The earlier challenger is still not promoted.

For a two-player zero-sum profile, report the exact exploitability convention (e.g. half the sum of each player's best-response improvement), payoff units, chance distribution, action support and information abstraction. Do not label approximate attack scores as exact full-game exploitability.

## 7. Executed versus pending

**Executed:** optional-dependency probe; own exact six-objective LP audit;903-pair actual-variant royal witness against the supplied evaluator;14 new information/objective regression tests. Combined with the prior129 suites, **143 tests pass**. Champion bytes and all frozen releases remain unchanged.

**Not executed:** OpenSpiel import/training, CFR, full-game best response, custom `pyspiel.Game`, full-game exploitability, runtime-policy change, new strategy matches or target-host certification. Neither a perfect strategy nor a real-game minimax/nonloss value was obtained.

Reproduce with dependencies already installed; always fresh evidence paths:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 -m unittest discover -s tests/openspiel -v
python3 tools/openspiel/probe.py --output evidence/openspiel/fresh_probe.json
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 tools/openspiel/audit_guarantees.py --output evidence/openspiel/fresh_audit.json
python3 tools/maintenance/verify_workspace.py
```

The optional probe never installs/downloads anything. Do not ship it in the bot. Current evidence is under `evidence/openspiel/2026_11_02/`; previous research remains immutable. External research in this continuation was limited to the requested framework/documentation/paper; no competing bot repositories were opened or copied.
