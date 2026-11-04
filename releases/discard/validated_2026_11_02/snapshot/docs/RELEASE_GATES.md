# Official release gates — 2 November 2026

All three supplied PDFs and starter-kit source are now present. [Reconciliation](organizer/RULES_RECONCILIATION.md). Historical frozen reports are not rewritten.

| Gate | Current evidence | Still required |
|---|---|---|
| Game/rules | 1-November statement read; all five worked examples exercised; three-card/discard, equal200 resets, blinds1/2, four aggressions and duplicate layout confirmed | Future amendments; no unmentioned fees/antes |
| Protocol/runner | Six full supplied-engine matches, clocks ON, zero notices; two direct CLI and four externally instrumented runs | Actual tournament host may differ from supplied starter code |
| Interpreter | Python3.11 grammar passes; execution uses3.13.16 | Actual3.11 and organizer NumPy/image |
| Resources | Measured children:CPU[0],1GiB address-space cap, single-thread library settings; zero audited forbidden attempts | OS-enforced read-only/network isolation, native behavior, actual host |
| Clocks | Raw request sums1.195–10.622s in measured400/1000-hand fixtures; max observed reply0.210070s | Supplied first-five-second charging clarification; final banks/clocks and host measurement |
| Scoring | Raw match net wins; match-total clipping C400/C1000; candidate normal400/1000-stage inference matches | Final caps; custom stage/hand combinations are not validated; unilateral forfeiter delta clarification if needed |
| Fair play | Candidate unchanged; no duplicate inference/hidden-input use; standard algorithms and allowed libraries | Organizer review; [clock draft](organizer/CLOCK_CLARIFICATION.md) prepared, not sent |
| Strength | Starter/random fixture wins; mirror+212/−212; exact conditional bounds | Strong adaptive holdouts; no initial-state nonloss, minimax, tournament-rate or qualification guarantee |
| Upload/eligibility | Single30,730-byte bot or root-bot ZIP; deadline15Nov2026 23:59IST | Two-person valid registration and actual final valid portal upload; none performed |

## Candidate versus certification

`releases/discard/v1/` is the immutable candidate; `releases/discard/validated_2026_11_02/` supplements evidence without changing it. [Current results and reproduction](discard/SUPPLIED_ENGINE_VALIDATION.md). The whole organized workspace ZIP is not an upload artifact. Missing statement/runner/duplicate-layout gates are **resolved**, not silently retained as blockers.

## Certificate-specific premises

- Banked net independently reconciled against accepted histories and payouts; exact remaining alternating blind costs.
- Turn credit requires actual retained pair, four public cards, both confirmed exposed discards and a sound higher-quads/straight-flush obstruction; legal check/call continues through validated payout.
- River proof covers all903 physically legal retained peer pairs, not posterior-truncated support.
- Cap-seeking commitment ceiling includes already-paid money and never erodes the initial certified positive floor. Not counterfactual passive dominance or optimal tie-break policy.
- Standard equal-reset-stack matching/refund/payout semantics, no fees, no forfeit. Detecting an inconsistency withdraws trust; it does not prove universal recovery.
- Timing/audit fixtures do not prove worst-case scheduling or universal no-forfeit survival.

Fresh evidence:118tests (10supplied-engine +21Discard +53historical CORA/guarantee +34v2), four constrained supplied-engine matches and two direct CLI matches. Keep self-authored-engine and supplied-engine evidence separate; neither is the actual tournament host.
