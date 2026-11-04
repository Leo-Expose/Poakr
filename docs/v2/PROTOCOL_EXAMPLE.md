# Example JSONL protocol — NOT the official protocol

This schema exists to test the core end-to-end while the organizer's stdin/stdout
specification is unavailable. Do not submit it unchanged on the assumption that
the official runner uses these messages.

## Configuration / startup

```bash
python3 runtime/bot.py --config config/example_standard.json
```

Optional read-only config has only `rules` and `settings` objects. Example files
show standard rules, board-based replay inference, and a short-deck configuration.
These are examples, **not assertions about the actual custom variant**.

- IDs are nonempty strings or integers, normalized to strings; maximum 128 chars.
- Money/time fields are finite numbers, never booleans; monetary arithmetic is
  bounded to prevent overflow.
- Duplicate JSON keys, nonfinite constants and excessive input size are rejected.
- Input is bounded to 131,072 characters per line (up to approximately 512 KiB of
  UTF-8 text). The implementation's historical constant name is `MAX_LINE_BYTES`.
- stdout contains only action responses. Diagnostics go to stderr.

## Start match — no response

```json
{"type":"start_match","match_id":"m1","hands_total":400,"timebank_s":60}
```

Each match needs its actual total hand count and allowance. Finals can supply
`hands_total:1000`; the announcement does not establish an exact finals time bank.
An active match must end before another begins. A duplicate start is an error,
not a reset of the state or bank.

## Decision — exactly one action for a valid request

```json
{"type":"decision","match_id":"m1","request_id":"h0-r0","hand_id":"h0","hole":["Ac","Ad"],"board":[],"pot":3,"to_call":1,"my_stack":199,"opp_stack":198,"hands_left":400,"chip_lead":0,"legal":[{"kind":"fold"},{"kind":"call"},{"kind":"bet","pay":4}]}
```

Required fields: type, match_id, request_id, hand_id, hole, board, pot, to_call,
my_stack, opp_stack, legal. Optional: pair_id, hands_left, chip_lead, time_left_s.
`pair_id` must mean the replayed deal, **not** an ordinary hand identifier.

Cards are configured-deck IDs or strict rank/suit strings. IDs encode
`rank_index * suit_count + suit_index`. Strings use the configured rank/suit
symbols; standard `10s` and suit symbols such as `A♠` are accepted.

**Pot includes the outstanding opponent bet.** A bet's `pay` is the amount
contributed **now**, including the call. It is neither a pot fraction nor a
raise-to amount. A discrete legal set must be normalized by the adapter; continuous
ranges, minimum raises and rounding rules require explicit official translation.

Reply example:

```json
{"type":"action","request_id":"h0-r0","action":{"kind":"call"}}
```

Or a legal bet:

```json
{"type":"action","request_id":"h0-r0","action":{"kind":"bet","pay":4.0}}
```

Recent exact request retries return the cached action. A reused request ID with a
different normalized payload is rejected. Transport retries outside the bounded
cache are an integration issue requiring an official sequence/retry contract.

## Public opponent event — no response

```json
{"type":"opponent_event","match_id":"m1","seq":12,"street":2,"kind":"fold","faced_bet":true,"faced_ratio":0.5}
```

Sequence numbers increase per match. Repeated/out-of-order events are ignored for
learning. Street is zero preflop, then configured reveal index. `faced_ratio` is
the actual faced extra bet divided by the pot before the bet, including proper
all-in capping. Only events explicitly attributed to the opponent should be
translated to this message. Legal-action mentions and echoed action menus are
never observations.

## Hand end / showdown — no response

```json
{"type":"hand_end","match_id":"m1","hand_id":"h0","board":["2c","7d","9s"]}
```

```json
{"type":"showdown","match_id":"m1","hand_id":"h0","board":["2c","7d","9s","3h","5s"],"opponent_hole":["Kc","Kd"]}
```

Only the board and opponent cards **actually publicly revealed by the runner**
may be passed here. Optional board extends the observed prefix; it must not
conflict with earlier observations or either hole hand. Optional opponent_hole
verifies any inferred hand. A valid contradiction disables replay inference.
Impossible reveals are rejected before committing terminal memory. Finished
hand IDs cannot receive new decisions (cached retries remain idempotent).

## Status / end match — no response

```json
{"type":"status","match_id":"m1","time_left_s":55}
```

```json
{"type":"end_match","match_id":"m1"}
```

Status can tighten the time allowance. End disposes of the active session; the
next match begins with fresh models, RNGs, memory and bank.

## Invalid input

Errors produce a bounded error-class diagnostic on stderr. For a malformed
**decision** in the active match, a valid advertised legal list can supply a safe
fallback. If match/IDs/legal actions are unknown or conflicting, the adapter
emits no invented action. This is not a promise that malformed official requests
cannot cause a forfeit; exact official protocol integration remains mandatory.
