# Technical Description

This document describes the implementation in `src/` and the generated
submission `bot.py`. The official competition documents in `docs/comp/` remain
authoritative.

## Build model

`build.py` concatenates three source files in order:

1. `src/evaluator.py`
2. `src/proofs.py`
3. `src/protocol.py`

It removes `from src...` imports, removes module docstrings, deduplicates
repeated import lines, and adds a small runtime header. The result is a single
file, `bot.py`, that can be executed directly. The build parses the generated
source with Python 3.11 before writing it.

`python3.11 build.py --zip` additionally writes `submission.zip` containing only
`bot.py`.

## Card representation

A card is an integer `rank * 4 + suit`, where rank is `0..12` for `2..A` and
suit is `0..3` for clubs, diamonds, hearts, spades. Protocol strings use the
standard two-character form, for example `As`, `Td`, and `2c`.

`src/proofs.py` validates protocol cards and rejects duplicates. The internal
suit order is not the organizer's discard tie-break order; `default_discard`
uses the rulebook order explicitly.

## Evaluator

`src/evaluator.py` evaluates batches of seven-card hands. It returns an integer
score per hand; higher is better. The score layout is:

```text
category << 20 | tiebreaker ranks, four bits each
```

Categories follow standard poker order: high card, one pair, two pair, trips,
straight, flush, full house, quads, straight flush. The evaluator handles the
wheel straight and straight flush, two trips making a full house, and the best
five cards from seven.

`tests/test_protocol.py` compares the evaluator against the official
starter-kit `rank5` reference on 1,000 random seven-card hands.

## Protocol state machine

`DiscardBot` implements protocol version 1.0. It handles:

- `init`
- `new_hand`
- `discard_request`
- `discard_result`
- `action_request`
- `hand_result`
- `notice`
- `match_end`

Unknown message types and unknown fields are ignored, as required by the
protocol. The bot reads one JSON object per line from standard input and writes
one JSON reply per line to standard output.

The bot validates:

- protocol version and fixed game parameters;
- hand sequencing and alternating seats;
- card counts, duplicate cards, and board continuity;
- public pot and stack conservation;
- action-history legality, including blinds, call amounts, raise minimums,
  raise counts, and stack caps;
- discard consistency and dead-card collisions;
- showdown net values against the public ledger.

If a message is malformed, the bot increments an error counter, marks its
certified score as untrusted, and attempts a safe fallback. For an action
request it prefers check; if a certified continuation is pending it calls;
otherwise it folds before calling. For a discard request it uses the rulebook
default discard.

## Decision policy

The policy is intentionally simple and conservative.

### Equity estimate

For a given board, the bot fixes each candidate own pair from its three-card
holding. It samples uniform random opponent holdings and runouts from the cards
not visible to it. It evaluates every candidate own pair against the strongest
opponent pair in each sample and averages win/tie credit. The pair with the
highest estimate is used for the discard decision.

This is a Monte Carlo estimate under a uniform random opponent model. It is not
an adaptive opponent model, a range estimator, or a game-theoretic equilibrium
strategy.

### Discard

The bot discards the card not in the best estimated pair. If the time budget is
low, if a certified result is already locked without cap-seeking, or if the
match cap is already secured, it uses the rulebook default discard instead.

### Betting

For a legal action request the bot:

1. reconstructs the public ledger and rejects inconsistencies;
2. folds if the call price exceeds the remaining budget;
3. folds if estimated equity is below `price + 0.025`;
4. raises if equity is above `0.72` on the preflop or flop, or above `0.76` on
   the turn or river, and a legal raise fits the budget;
5. otherwise calls or checks.

The raise size is the minimum legal raise, capped by the budget and a
pot-relative target.

## Bankroll and certificate logic

The bot tracks its verified match score and the blind cost of the remaining
hands. When a positive margin exists, it can lock a reserve and avoid spending
through that reserve. This is a conservative bankroll rule intended to protect a
verified lead. It is not a proof that the lead cannot be lost.

Two additional routines are exact for specific states:

- `quads_turn`: checks whether the bot's turn quads cannot be beaten by any
  physical opponent holding and river card, given the public board and both
  exposed discards.
- `river_geometry`: enumerates every physical opponent pair and compares the
  bot's five-card hand against them.

These routines are used only when their preconditions hold. They are not
universal guarantees and do not imply that the bot always wins.

## Compliance notes

- The bot uses only the current hand's public information.
- The bot does not use duplicate-deal inference.
- The bot does not read hidden cards or organizer state.
- The bot does not perform runtime file, network, or process I/O.
- The bot exits after `match_end`.

## Known limitations

- Equity is estimated by Monte Carlo sampling, so decisions are not exact.
- The opponent model is uniform random, not a model of the actual field.
- The bankroll rule is heuristic and can forgo profitable spots.
- The exact certificates cover narrow states; they are not a complete strategy.
- Local validation uses the official starter-kit engine and random opponent.
  It does not reproduce the organizer's full tournament field.
- The submission has not been certified by the organizers.
