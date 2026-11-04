# Validation Report

This report records the local validation performed on the cleaned repository.
It is not an organizer certification.

## Environment

| Item | Value |
| --- | --- |
| Python | 3.11.15 |
| NumPy | 2.4.6 |
| SciPy | 1.17.1 |
| Interpreter | `/home/leo/Documents/Poker/venv/bin/python` |
| Engine | `tools/engine.py`, copied from the official starter kit |
| Opponent | `tools/random_bot.py`, copied from the official starter kit |

The system Python 3.11 installation does not include NumPy, so the virtual
environment interpreter is used for all commands below.

## Build

Command:

```sh
/home/leo/Documents/Poker/venv/bin/python build.py
```

Result:

```text
/home/leo/Documents/Poker/pokerbot/bot.py  30518 bytes
sha256=cec8f746dd6d633653e8bb27b42a3ac37eff45363877e12aed311cfb23b09a0c
```

## Test suite

Command:

```sh
/home/leo/Documents/Poker/venv/bin/python -m unittest discover -s tests -v
```

Result: 21 tests passed.

The suite includes:

- 1,000 random seven-card comparisons against the official starter-kit
  `rank5` reference;
- protocol replay, raise-limit, discard, fallback, and stdio tests;
- exhaustive physical-opponent checks for the turn quads and river certificate
  routines over all 39,732 opponent/river combinations in the tested states;
- a short match through the official starter-kit engine.

## Match results

### 400-hand match

Command:

```sh
/home/leo/Documents/Poker/venv/bin/python tools/engine.py bot.py tools/random_bot.py \
  --hands 400 --seed 173000 --log-dir /tmp/opencode/val400 \
  --python /home/leo/Documents/Poker/venv/bin/python
```

Result:

```text
Seed 173000 | 400 of 400 hands played (2 legs of 200)
  A  bot.py              net    +743   time used   0.00 s (bank 30 s per leg)   notices 0
  B  tools/random_bot.py net    -743   time used   0.00 s (bank 30 s per leg)   notices 0
Result: A wins
Capped delta: A +400, B -400 (C = 400)
```

### 1,000-hand stage-2 match

Command:

```sh
/home/leo/Documents/Poker/venv/bin/python tools/engine.py bot.py tools/random_bot.py \
  --stage 2 --seed 181000 --log-dir /tmp/opencode/val1000 \
  --python /home/leo/Documents/Poker/venv/bin/python
```

Result:

```text
Seed 181000 | 1000 of 1000 hands played (2 legs of 500)
  A  bot.py              net   +2361   time used   0.00 s (bank 75 s per leg)   notices 0
  B  tools/random_bot.py net   -2361   time used   0.00 s (bank 75 s per leg)   notices 0
Result: A wins
Capped delta: A +1000, B -1000 (C = 1000)
```

### 40-hand smoke match

Command:

```sh
/home/leo/Documents/Poker/venv/bin/python tools/engine.py bot.py tools/random_bot.py \
  --hands 40 --seed 123 --log-dir "" \
  --python /home/leo/Documents/Poker/venv/bin/python
```

Result:

```text
Seed 123 | 40 of 40 hands played (2 legs of 20)
  A  bot.py              net     +49   time used   0.00 s (bank 30 s per leg)   notices 0
  B  tools/random_bot.py net     -49   time used   0.00 s (bank 30 s per leg)   notices 0
Result: A wins
Capped delta: A +49, B -49 (C = 400)
```

## Interpretation

The local tests show that the bot:

- builds successfully as a single file;
- passes the protocol and evaluator tests;
- completes 400-hand and 1,000-hand matches through the official starter-kit
  engine without forfeits or notices;
- produces a positive raw net against the starter-kit random opponent in the
  tested seeds.

The starter kit reports `0.00 s` of bank usage for both bots in these runs. This
is the starter kit's displayed timing; it should not be read as a precise
measurement of runtime.

The starter-kit random opponent uses Python's unseeded `random` module. Deal
seeds are deterministic, but opponent actions and therefore net results vary
between runs. The results above are single runs.

These results are local and limited to the starter-kit random opponent. They do
not establish performance against the tournament field, and they are not an
organizer certification.

## Reproduction notes

- Use the virtual-environment interpreter so that NumPy is available.
- Keep `tools/engine.py` and `tools/random_bot.py` identical to the official
  starter-kit copies.
- Use `--log-dir ""` to disable log files for a quick smoke test.
- The engine's `--stage` option selects the 400-hand stage 1 or the 1,000-hand
  stage 2 configuration.
