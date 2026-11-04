# Draft organizer clarification — supplied starter-engine clock

**Prepared 2 November 2026 for the user's review. NOT sent to organizers.** No strategy code was changed to use this behavior. Please report through the authorized channel; do not exploit it.

## Source and observed behavior

Source: user-supplied `combined_files.md`, extracted without edits to `vendor/organizer/Starter_Kit/engine.py` (SHA-256 `7a44eb0ef7518e1343779d2a46163549e380b228d8f583f1d0478adf4fd64ad6`). This is the supplied starter kit, not independently verified tournament-host code.

`Bot.wait_reply` computes:

```python
start = max(self.sent_at, self.startup_deadline)
charged = max(0.0, ts - start)
```

`startup_deadline` is fixed at process launch + five seconds. Consequently, not only initialization but **all action/discard responses received during those first five seconds** are uncharged. The reply deadline is also based on this `start`, potentially extending the early per-request allowance beyond five seconds from request send.

A deterministic unit regression uses request send at 100, receipt at 102, startup deadline at 105: raw request time is 2 seconds; the current supplied implementation charges 0. See `tests/organizer/test_supplied_engine.py`. This is a host-clock observation, not an endorsed expected specification.

The Protocol Specification describes startup as uncharged and action/discard time as measured from request send to flushed complete reply. Please clarify whether the fixed grace window is intended, whether startup completion has a separate definition, and which behavior the tournament host will enforce. If only actual startup is exempt, define readiness separately and charge subsequent requests from their send timestamps. We have not patched the vendor file or asserted a particular unconfirmed fix.

## Real measurements, not zero-time claims

Two direct CLI matches reported 0.00 charged seconds despite finishing 400 and 1000 hands. An external measurement subclass then timestamped reply receipt and recorded raw send-to-receipt latencies, while retaining the engine's clocks. Both processes were externally restricted to CPU affinity `[0]`, 1 GiB address space and single-thread library settings.

| Candidate fixture | Hands | Sum of raw request times | Engine charged | Longest raw reply |
|---|---:|---:|---:|---:|
| Starter, seed241000, A |400|2.218408 s|0 s|0.068450 s|
| Random, seed251000, B |400|1.195479 s|0 s|0.067451 s|
| Starter, seed261000, B |1000|8.519273 s|4.112111 s|0.065674 s|
| Mirror, seed271000, A |1000|10.621562 s|8.126243 s|0.210070 s|

These raw measurements conservatively include the first request's loading delay, rather than using the grace period as a free-compute assumption. All measured candidate sums are below 60/150 seconds, and all observed replies are below five seconds. These are finite local measurements, not worst-case host or Python3.11 guarantees. Full evidence is under `evidence/organizer_runner/measured/`.

## Fair-play boundary

Candidate SHA-256 remains `2de972289c37024c9283d8c29b273c694a2f229d67309ac347cfb7cfff7bb907`, identical to the earlier frozen version. No bot changes, hidden-card inputs, duplicate inference, extra computation based on the grace period, or communication with other participants were introduced. Measurements run outside the bot and are not part of the submission. This report is for clarification/review; no organizer contact or portal upload has been performed.
