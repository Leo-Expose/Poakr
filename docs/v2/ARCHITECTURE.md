# Pokerbot v2 — architecture

## What is shipped

`runtime/bot.py` is a generated, standalone file. It needs Python and NumPy only.
It makes no network calls, installs nothing, and writes no runtime files.
`bench/build_release.py` assembles it deterministically from the auditable source:

| Source | Responsibility |
|---|---|
| `src/core.py` | Rules, validation, normalized observations/actions, equity, memory, models, policy, match session |
| `src/fast_eval.py` | Optimized exact seven-card evaluator for standard ranking/deck geometry |
| `src/adapter.py` | Strict **example** JSONL lifecycle and transport; replace with official protocol |

The old prototype is preserved as `legacy/bot_v1.py`. Old scores are historical
baseline evidence, not evidence for rewritten code.

## Normalization boundary

The internal observation has explicit IDs, our hole cards, public board, pot,
call amount, stacks, and a discrete set of known legal `Action` objects.

- Pot includes the outstanding opponent bet.
- `Action('bet', pay)` means chips contributed **now**, including any call.
- Check, fold and call have no numeric pay field; call uses the observation's
  capped call amount.
- An unmatched opponent overbet is removed from the pot used for all-in price.
- No guessing of raise-to versus raise-by, fractions versus chips, minimum raise,
  continuous sizing, or output tokens occurs in the core. The adapter must convert
  those official semantics and supply legal candidates.
- A caller's advertised legal set is validated. A policy selects a member of it;
  there is no silent simulator coercion hiding illegal decisions.

`src/adapter.py` demonstrates translation, not the undisclosed official grammar.
It emits JSON actions only for decisions; no blank acknowledgments for unrelated
messages. Invalid input never leads to invented sizing or invented legal actions.
A known legal set can provide a fallback; otherwise only stderr diagnostics are
emitted. That is an engineering boundary, not a guarantee against forfeits.

## Match-state ownership

Each `BotSession` owns its RNGs, compute bank, equity cache, duplicate memory,
opponent counts and response cache. Independent bots do not share models.
Start/end events reset a match; a duplicate start cannot erase its time usage.
Request IDs make recent retries idempotent; reused IDs with different payloads
are rejected. Caches and history are bounded, so ancient transport replays beyond
retention require an official sequence/retry contract.

Published terminal boards can extend memory, including runouts from hands where
we had no postflop decision. This is allowed only when the official adapter
identifies them as public information. Unrevealed simulator runouts never enter
the bot's memory. Finished hand IDs cannot receive new decision requests.

## Configured rule family

The generic exact evaluator supports:

- 5–15 ordered rank symbols; 2–4 suits.
- 1–4 hole cards; final hole-plus-board size 5–9 cards.
- A configured reveal schedule and category ordering.
- Wheel on/off or explicit straight patterns.
- Unrestricted best five cards, or an exact required number of hole cards.

It evaluates only permitted five-card subsets with bounded NumPy batches.
Standard 13-rank/four-suit, two-hole/five-board evaluation uses the optimized
seven-card path. Different street reveal schedules can still use that fast path
if final evaluation semantics are identical.

This is **not universal poker support**. Five-of-a-kind, wild cards, lowball,
mandatory suit combinations, unusual payouts or other unspecified mechanics
require explicit plugin/normalization changes and independent tests. Configuration
never silently pretends an unsupported rule is understood.

## Equity and confidence

Known-hand runouts are enumerated if their count is at most the configured exact
limit. For standard Hold'em this gives 990 flop runouts, 44 turn runouts and one
river comparison. Larger spaces use uniformly sampled distinct cards.

Unknown-opponent equity currently samples a uniform random unseen hand. That is a
baseline range assumption, not an opponent-range solution. An exact evaluator
cannot make a mistaken range assumption exact.

Sequential sampling uses a Hoeffding interval with alpha spent as
`alpha / (look * (look + 1))`. The sum of this spending is at most alpha, so
inspecting multiple completed batches does not invalidate the per-estimate bound.
Cached Monte Carlo samples resume without resetting sample/look counts. Exact
results are reusable; timed-out enumeration prefixes are discarded, not reported
as an unbiased equity estimate. Completed Monte Carlo batches may be used after a
watchdog timeout with their existing confidence interval.

The intervals concern sampled showdown equity. They do not certify action EV,
whole-match error rates, optimal betting or conditional calling ranges.

## Time and resource discipline

- BLAS/OpenMP thread counts are set to one before NumPy imports.
- The bank charges whole adapter request handling, serialization and flush, and
  conservatively charges runtime startup when a session begins.
- Hand count is per match, supplied by the adapter: 400 and 1000 both work.
- Host-reported time left can tighten but not increase the local allowance.
- A reserve remains outside planned compute; depleted budgets return known legal
  safe actions.
- Exact enumeration and Monte Carlo have bounded batch sizes and deadlines.
- A POSIX main-thread timer supplies a per-decision watchdog only if no host timer
  already exists. Existing host timers are not replaced. Other platforms/threads
  use deadline checks. NumPy signal delivery may be delayed until a C kernel
  returns; no universal wall-clock guarantee is claimed.

The local stress harness pins one CPU, caps virtual address space at 1 GiB,
blocks network/process creation/file-write operations, and tests both stages.
This is separate from poker-performance measurement and not the official runner.

## Duplicate inference

Modes: `off` (default), `board`, or `pair_id`.

- Board mode needs replay evidence and one compatible candidate hole hand.
- All shared board cards must agree; inferred cards must be disjoint from current
  known cards; ambiguous candidates are rejected.
- Adjacency alone **never** identifies copy phase or enables preflop inference.
- Pair-ID mode uses only an explicitly normalized duplicate-pair identifier.
- Matching public opponent reveals count confirmations; contradictions disable
  inference for the match.
- Repeated boards alone cannot prove hole swapping or legal permission to retain
  cards. Those are official integration gates.

An informed opponent can also track the pair. The information advantage is not
inherently one-sided; a duplicate-aware mirror is included as a diagnostic.

## Policy and opponent model

The policy is a fast heuristic: showdown equity, call price, value sizing and
optionally observation-supported bluffing. Public opponent events are validated
and deduplicated; fold counts are stratified by street and faced-size bin.
An unobserved prior does not justify a bluff. Nonstationarity, selection bias,
trapping, bet-dependent ranges and future betting remain strategic limitations.

The experimental match-risk dial and proactive bluff feature are **off by
default**. A normal approximation can motivate match-level risk considerations,
but it does not prove this threshold dial is optimal. Chip gains and match-point
gains are reported separately. Tie-break optimization awaits the actual cap and
aggregation formula.

## Evidence and remaining gates

Read `docs/v2/VALIDATION.md` for the current measured results, and `docs/v2/READINESS.md` for the
complete requirement-by-requirement ledger. `docs/v2/PROTOCOL_EXAMPLE.md` describes the
example schema only. Source, raw logs, tests and build instructions accompany the
release. No guarantee of perfection, tournament wins, global novelty or organizer
approval is established.
