# Guarantee research roadmap

> Update, 31 October: the supplied PDFs now specify Discard Hold’em. This page describes the earlier isolated lab. See [actual-game candidate](../discard/REPORT.md) and [PDF reconciliation](../organizer/RULES_RECONCILIATION.md). Its per-hand clipping contract is NOT the official match-level tie-break.


## Completed now

- Preserved the frozen CORA/v2 algorithms and release bytes during organization.
- Exact rational arbitrary-post and specifically defined per-hand capped-score certificates.
- All-physical-peer safe river settlement credit, including a negative-banked-net comeback example.
- Symbolic dominating-quads rainbow-turn certificate, verified against all 45,540 physical pair/runout worlds for the example; no runtime runout enumeration.
- Exact toy-poker primal/dual value and legal forced-loss/duplicate-no-strict-win witnesses.
- 12 mathematical guarantee tests + 18 reference-controller tests; 53 CORA/guarantee and 34 v2 tests pass.
- Integer-tick contribution/payout ledger, score reconciliation, immutable requests and consumed decision points.
- Separate proof-aware settlement controller, deadline-selection path and validated payout transition.
- 375 accounting cases and 480 complete bounded financial paths, alongside the 45,540-world card test.
- v2 rebuild/report inclusion and historical-evidence overwrite protections repaired.
- Constrained turn/river controller traces and source-pinned performance evidence. See [implementation report](IMPLEMENTATION_REPORT.md).

## Next: contract and state verification

1. Obtain official card/rank/payout, action, forced-fee, scoring/cap, clock, and lifecycle specifications. Do not guess them.
2. Adapt the completed reference ledger to actual paid actions/payouts and official scoreboards. Verify adapter facts independently; the prototype does not authenticate or self-verify the host.
3. Prove future forced-cost upper bounds from the real schedule. Unknown growth/fees disable that certificate.
4. Map the completed hand/card/rule/revision/action binding to official request IDs and lifecycle semantics.

## Implemented reference controller; remaining integration

- Separate `SETTLE_SAFE_HAND` state is implemented; it does not reuse the immediate-fold lock.
- Check/call and validated-payout transitions are implemented. Integrate them with verified host action confirmation and transport reconciliation.
- Recovery selection preserves the required current continuation. Still integrate the actual deadline/time-bank lifecycle; ordinary fold fallback remains unsafe.
- Bounded response/accounting tests pass. Extend to an independently implemented official game adapter, actual betting trees, showdown/fold legality, side conditions, and transport failures.
- Published policy remains immutable. The reference controller is frozen as a research snapshot; a complete integrated policy still needs a separate version and fresh independent holdout.

## Then: improve pre-certificate protection

- Use robust full-information-set game solving on small games first. Verify primal/dual or Bellman certificates, not only sampled rewards.
- Distinguish expectation bounds against adversaries from pointwise chance guarantees.
- Develop interval decision bounds on the current physical card geometry; test uncertainty/model misspecification. No posterior support truncation in a universal claim.
- Evaluate stronger adaptive/duplicate-aware opponents using only organizer-authorized information. Current six-family evidence is not tournament dominance.

## Runtime proof work

- Execute on actual Python 3.11 and organizer NumPy.
- Audit cold startup, complete wire transport, bounded parser/history work, hand-end and match-end accounting under the exact host bank.
- Test an OS-level read-only/network-isolated sandbox, not only Python audit hooks.
- Derive supported request-count/fee/raise bounds and measured margins. A finite benchmark is not a worst-case scheduling theorem.

## Acceptance criteria

A new guarantee is accepted only with: explicit quantified scope; verified premises; a specified legal continuation; exact or conservative inequalities; counterexample/invalid-state tests; fresh frozen policy/evidence when gameplay changes; and no prohibited information/runtime dependency.

The research target is a larger **provably winning state region at low compute**, not an impossible claim that every initial game against every opponent is a strict victory.
