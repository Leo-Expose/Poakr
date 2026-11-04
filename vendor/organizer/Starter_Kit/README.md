# Pokerbots Starter Kit: Discard Hold'em

| File | What it is |
|---|---|
| `bot.py` | Starter bot (Protocol Specification §11). Replace its strategy with yours. |
| `engine.py` | Local match runner. Plays a full match between two bots under the official rules. |
| `example_bots/random_bot.py` | A random opponent to test against. |

Read the Problem Statement (game rules), the Protocol Specification (messages) and the
Rulebook (tournament, limits, conduct) before you start.

## Requirements

Python 3.11. The runner uses only the standard library; your bot may also use numpy and scipy.

## Quick start

    python3.11 engine.py bot.py example_bots/random_bot.py

This plays a 400-hand Stage 1 match (200 duplicate deals) and prints a summary.

## Options

| Option | Meaning |
|---|---|
| `--stage 2` | Stage 2 match: 1000 hands, 150 s time bank, 450 s wall-clock |
| `--hands N` | Play N hands (must be even) |
| `--seed S` | Fixed deal seed, so the same seed replays the same cards |
| `--verbose` | Print every hand to the console |
| `--log-dir DIR` | Where logs are written (default `logs`; `''` disables) |
| `--python PATH` | Interpreter used to run the bots |
| `--no-time-limits` | Turn off all clocks, for debugging only. Never judge timing with this on. |

## Logs

- `logs/match.log`: one line per hand: hole cards, board, discards, actions
  (`x` check, `c6` call to 6, `r20` raise to 20, `f` fold) and the result.
- `logs/A_stderr.txt`, `logs/B_stderr.txt`: each bot's stderr (first 64 KB). Print your debug
  output with `print(..., file=sys.stderr)`. Anything else on stdout breaks the protocol.

## What the runner enforces (same as the official engine)

- Duplicate deals, alternating seats, 200 chips per hand, blinds 1 and 2
- Minimum raises, all-in amounts and the 4-bet cap per street
- The simultaneous, exposed discard after the flop (also when all-in)
- Corrections: illegal or malformed actions become check, else fold; illegal discards become the
  lowest-ranked card (ties: spades, hearts, diamonds, clubs). A `notice` is sent each time.
- Time bank, 5 s per reply, 5 s start-up (not charged), wall-clock kill. Exceeding any of them,
  crashing or closing stdout forfeits the match.

## Before you upload

- [ ] `python3.11 bot.py` runs with only the standard library, numpy and scipy
- [ ] Nothing but protocol JSON goes to stdout, and every reply is flushed
- [ ] The bot answers both `action_request` and `discard_request`
- [ ] The bot ignores message types and fields it does not know
- [ ] A full 400-hand match runs inside the time bank with zero notices:
      `python3.11 engine.py bot.py example_bots/random_bot.py`
- [ ] Also try `--stage 2` to check your timing over 1000 hands

You may reuse any code from this kit, including the hand evaluator in `engine.py`. Material
supplied by the organisers is allowed under Rulebook 10.1.
