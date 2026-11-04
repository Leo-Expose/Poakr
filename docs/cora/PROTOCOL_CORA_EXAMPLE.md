# CORA EXAMPLE JSONL protocol — not official

The executable is a self-contained standard two-hole/five-board Hold'em research prototype. It has no runtime dependency on the project package or preflop JSON file. It requires preinstalled NumPy and standard Python. It does **not** implement the organizer's undisclosed schema or modified game.

One JSON object per input line. Action responses alone go to stdout; diagnostic exception names go to stderr. Unknown root and nested action/history fields are rejected. Maximum line size is inherited from the bounded core reader (128 KiB). The public action history is bounded to 256 events.

## Start a fresh match

```json
{"type":"start_match","match_id":"m","starting_stack":200,"sb":1,"bb":2,"max_raises":4,"hands_total":400,"timebank_s":60,"raw_net_abandonment_contract":false}
```

The last field defaults to false. Set it true only after verifying the raw-net scoring, reset-stack, fixed-posting, and free-abandonment premises in PROOFS.md. It is an assertion about the game contract, not a fact inferred by the bot. With false the bot uses inference without the hard lock. Unknown capped-chip scoring is not equivalent to this contract.

Seat 0 means SB and first actor preflop. Seat 1 means BB and first actor postflop. Roles are local to the current hand, not persistent player identities.

## Decision

```json
{"type":"decision","match_id":"m","request_id":"r0","hand_id":"h0","hole":["Ac","Ad"],"board":[],"pot":3,"to_call":1,"my_stack":199,"opp_stack":198,"hands_left":400,"banked_net":0,"seat":0,"history":[],"legal":[{"kind":"fold"},{"kind":"call"},{"kind":"bet","pay":4}]}
```

- `hole`: own cards only. `board`: actually public cards only.
- Cards may be names in standard `23456789TJQKA` / `cdhs` notation, or integers `4*rank_index+suit_index`.
- `pot`: all paid chips in the middle, including current street commitments.
- `to_call`: current amount owed before stack truncation.
- Stacks are current uncommitted chips. They must match replay of the full public history and declared blinds.
- `hands_left` includes the current hand. `banked_net` is own profit from completed hands, not twice that difference or a capped score.
- Legal actions are canonical dictionaries. **Bet `pay` is actual additional chips paid now, INCLUDING the call component**, not a raise-to total or a pure raise increment. A displayed pot-fraction button is not this wire representation.
- The caller supplies genuine legal actions; the bot returns one from that set. Deduplicate identical capped bet amounts.

Response example:

```json
{"type":"action","request_id":"r0","action":{"kind":"call"}}
```

Response selection need not reproduce that example on every interpreter/machine: sampling/deadline timing can differ.

## Public history and hand completion

History is the complete chronological prefix for the current hand:

```json
[{"street":0,"actor":0,"action":{"kind":"call"}},{"street":0,"actor":1,"action":{"kind":"check"}}]
```

Street indices: preflop 0, flop 1, turn 2, river 3. Bet entries have `pay` in actual chips. Other kinds have only `kind`. Actor order, closed rounds, betting bounds, public money replay, same-hand own-card/board continuity, and application of previous responses are checked. Historical retries use the original request ID; they are acknowledgements of the old decision, not permission to execute an action twice.

```json
{"type":"hand_end","match_id":"m","hand_id":"h0","seat":0,"board":[],"outcome":null,"history":[{"street":0,"actor":0,"action":{"kind":"fold"}}]}
```

That history must reflect the action actually taken; it is not a continuation of the earlier call-response illustration. `outcome` is `+1`, `0`, or `-1` for a public showdown's own win/tie/loss, and `null` for a fold. The board must contain only actual public cards. **Never send opponent hole cards or an unrevealed future runout.** If a hand ends before the bot receives a decision, hand-end may still be sent; previous own private state is discarded.

The current request cache holds 512 responses and the completed-hand replay registry holds 1600 entries. Idempotence is bounded by these caches; there is no unlimited historical replay guarantee.

## Budget and lifecycle

Optional `time_left_s` on decision, hand-end, or status is a public host remaining-budget report. It can reduce the local available estimate. Waiting for input is not locally charged; official clock accounting must be verified.

```json
{"type":"status","match_id":"m","time_left_s":42}
{"type":"end_match","match_id":"m"}
```

Start/end create and destroy match-local policy, budget, and private state. Reusing a completed match ID is rejected. Input errors do not make arbitrary unknown schemas safe: a new malformed decision can receive a validated legal fallback, but conflicting cached IDs/unknown control traffic may produce no response. Correct official adaptation is a release prerequisite.
