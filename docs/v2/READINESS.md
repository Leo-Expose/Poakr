# Pokerbot v2 — full audit and readiness ledger

**Meaning of “ready”:** a tested, configurable engineering core and an example
adapter. **Not** certified optimal play or an official competition submission.
The organizers have announced a custom variant and a predefined protocol but have
not supplied either specification in the material available here.

## Confirmed requirements from the announcement

- Python 3.11; stdlib, NumPy and SciPy only; no runtime installation.
- 1 vCPU; 1 GB RAM; read-only filesystem; zero network access.
- Cumulative match bank, approximately 60 seconds for 400 hands; exhaustion or
  crashes forfeit. Exact accounting, startup charges and finals bank are unknown.
- stdin/stdout protocol, grammar and bot-process lifetime undisclosed.
- Duplicate deals: each deal twice with seats swapped. Scheduling/order and
  available identifiers undisclosed; retention permissions should be confirmed.
- Swiss: six rounds, approximately 200 pairs / 400 hands; win/draw/loss = 1/.5/0.
- Finals: top 32, full round robin, approximately 500 pairs / 1000 hands per match;
  scores reset. With 32 teams, a team plays 31 other teams in the round robin.
- Tie-break: capped chips per hand; cap and exact aggregation undisclosed.
- Exactly two team members; one team per person. Last valid upload before
  November 15, 23:59 IST counts; source review, no copying/collusion/network calls.

## Audit ledger

| Area | Implemented / tested now | Remaining release gate |
|---|---|---|
| Runtime dependency boundary | Built single file; stdlib + NumPy; no source-package imports | Execute under real Python 3.11; local interpreter is 3.13 |
| Originality / review | Auditable local source, deterministic build, legacy baseline retained | Team authorship declaration and organizer review; cannot certify prize eligibility |
| CPU | Thread limits before NumPy import; pinned-CPU stress | Organizer CPU speed and charging model |
| RAM | Bounded input, arrays, caches and history; 1 GiB address-space test | Official 1 GB decimal/binary definition and runner overhead |
| Read-only / network | Runtime no filesystem writes or network operations; audit-blocked stress and read-only standalone test | Actual competition container / sandbox |
| Time bank | Full request processing charged; startup charge, host time-left tightening, reserve, per-decision limits | Host clock semantics and finals allowance |
| Watchdog | POSIX timer where safe; preserve existing host timer; deadline checks + bounded batches elsewhere | NumPy signal-delivery latency and actual host watchdog |
| Match lifecycle | One BotSession per match; state/RNG/model reset; explicit start/end; no global opponent state | Persistence across hands/matches/restarts |
| Protocol | Strict EXAMPLE JSONL schema; replies only to decisions; exact pay semantics | Replace adapter with official grammar and legal-action semantics |
| Request integrity | IDs, replay caching, conflict rejection, bounded input, nonfinite/magnitude validation | Official ID/sequence/ack guarantees |
| Cards | Strict configured-deck validation; no duplicate/overlapping cards | Official labels and integer mapping |
| Hand evaluation | Standard fast evaluator + configured subset evaluator; independent differential tests | Unspecified mechanics outside supported rule family |
| Rule changes | Rank/suit set, reveal counts, ranking order, wheel patterns, exact hole-card usage | Wild cards, lowball or other mechanics require a new evaluator plugin |
| Equity | Known-hand enumeration when tractable; otherwise uniform distinct-card MC | Opponent range calibration and actual custom sampling semantics |
| Sampling confidence | Hoeffding + alpha spending at every look; resumable samples preserve look count | Bounds apply to sampled showdown equity, not strategy EV or whole-match accuracy |
| Duplicate memory | Explicit modes; unique card-disjoint shared-prefix inference; no adjacency guessing; showdown contradiction switch | Actual swapped-hole semantics, scheduling, memory permissions |
| Hidden-data boundary | Memory sees only cards in own requests; benchmark never supplies unrevealed runout | Official showdown visibility fields |
| Legal actions | Validated normalized legal set; select a supplied action, not guessed sizing | Official continuous sizing, min-raise, units and rounding |
| Pot accounting | Canonical pot includes outstanding bet; unmatched overbet refund handled for price | Antes, rake, side pots, effective-stack accounting in official variant |
| Opponent learning | Explicit public events, sequence dedupe, size/street contexts, conservative fold bound | Actual history fields; nonstationarity, selection bias and range inference |
| Betting strategy | Pot-odds calls; known-hand value actions; experimental observed-fold bluffs | Future betting, conditional calling ranges and stronger adversaries |
| Match utility | Risk dial configurable and OFF by default | No strong evidence current risk heuristic improves match points |
| Tie-breaking | Priority kept on match points; raw benchmark chips retained | Exact cap/formula needed before tie-break optimization |
| Regression evidence | Fresh seeds, info/bluff ablations, frozen v1 comparison, independent duplicate-aware mirror | Larger independent holdouts and actual runner tests |
| Reproducibility | Build script, source, fixtures, tests, raw reports, checksums | Timing-dependent sample counts prevent universal bitwise action reproducibility |
| Submission operations | Single-file artifact, manifest, packaging smoke test, integration checklist | Upload interface, entry point, validation tool and team registration |

## Explicitly unsupported conclusions

- No guarantee of winning, never forfeiting, mathematical optimality or global
  research novelty.
- Exact standard-hand evaluation does not imply exact strategy or exact preflop
  equity. General variants may be slower than the optimized standard path.
- Replayed boards support, but do not alone prove, swapped hole cards. Both bots
  can track; the advantage is not inherently one-sided.
- An exception barrier cannot invent a legal reply when the protocol/legal set is
  unknown. Malformed requests without a known legal fallback produce a diagnostic
  on stderr, not a fabricated stdout action.
- Historical v1 wins do not become evidence for rewritten v2. Reports keep them
  separate.

## Integration steps once the details arrive

1. Set `Rules` from the actual deck, reveal schedule, ranking and card-selection
   rules. If those mechanics exceed this family, implement/test an evaluator
   plugin rather than forcing them into the existing configuration.
2. Implement the official adapter in `src/adapter.py`: message lifecycle, card
   encoding, pot interpretation, IDs, legal-action normalization, and exact output.
3. Supply per-match hand count and time bank from the runner; never assume finals
   use the qualifier bank or a fixed 400-hand denominator.
4. Run golden protocol transcripts against the official runner, including all-in,
   min-raise, EOF, status, showdown, duplicate request and match-reset cases.
5. Confirm card-retention/replay policy. Enable board or pair-ID inference only
   after its semantic and fair-play gates are satisfied.
6. Re-run resource stress and full match ablations on the actual variant. Retest
   against duplicate-aware and adaptive policies before selecting the submission.
7. Check exactly two-member registration and validate the uploaded artifact.
   Keep a known-valid rollback; leave time for the last valid upload to be checked.
