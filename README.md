# Pokerbot: Discard Hold'em

A single-file Python bot for the Discard Hold'em competition described in
[`docs/comp/problem statement.md`](docs/comp/problem%20statement.md).

The submitted bot uses only the Python standard library and NumPy. It performs
no runtime file, network, or process I/O.

## Status

Local validation only. The bot has not been certified by the organizers. See
[`docs/VALIDATION.md`](docs/VALIDATION.md) for the exact tests and match results.

## Repository layout

| Path | Purpose |
| --- | --- |
| `bot.py` | Generated single-file submission. |
| `build.py` | Builds `bot.py` from `src/`; optional `--zip`. |
| `src/evaluator.py` | Vectorized 7-card hand evaluator. |
| `src/proofs.py` | Card parsing, blind schedule, and physical-outcome helpers. |
| `src/protocol.py` | Protocol 1.0 state machine and decision policy. |
| `tests/` | Unit, protocol, evaluator, and match tests. |
| `tools/engine.py` | Copy of the official starter-kit match runner. |
| `tools/random_bot.py` | Copy of the official starter-kit random opponent. |
| `docs/comp/` | Official problem statement, rulebook, and protocol. |

The files in `tools/` are unmodified copies of the official starter kit. They
are for local testing only and are not part of the submission.

## Build

Requirements: Python 3.11 and NumPy.

```sh
python3.11 -m pip install -r requirements.txt
python3.11 build.py
```

To also create `submission.zip`, which contains only `bot.py`:

```sh
python3.11 build.py --zip
```

## Test

```sh
python3.11 -m unittest discover -s tests -v
```

The test suite covers:

- evaluator agreement with the official starter-kit `rank5` reference;
- protocol parsing, replay, betting limits, discard handling, and fallbacks;
- exact turn and river certificate checks over all physical opponent holdings
  in the tested states;
- a short match through the official starter-kit engine.

## Run a local match

```sh
python3.11 tools/engine.py bot.py tools/random_bot.py --hands 400 --seed 173000
```

If the engine's default interpreter differs from the interpreter that has
NumPy installed, pass it explicitly:

```sh
python3.11 tools/engine.py bot.py tools/random_bot.py \
  --hands 400 --seed 173000 --python /path/to/python
```

Use `--stage 2` for the 1,000-hand stage. Use `--log-dir ""` to disable log
files.

## Bot design

The bot is a conservative protocol implementation with exact checks for narrow
states:

- It reconstructs the public betting ledger from the action history and rejects
  requests that disagree with the reconstructed pot, stacks, raise count, board,
  or call price.
- It estimates equity with a fixed own discard pair and a uniform random model
  of opponent holdings and runouts. It chooses the discard pair with the highest
  estimated equity.
- It folds when equity is below the pot-odds price plus a small margin, raises
  at high equity thresholds, and otherwise calls or checks.
- Once a positive match margin is established, it reserves enough of that margin
  to protect the result. This is a bankroll rule, not a claim of a mathematical
  guarantee.
- The turn and river certificate routines are exact for the specific board
  states they cover. They are not universal win certificates.

The bot does not infer anything from duplicate deals and does not use hidden
cards. It relies only on the current hand's public information.

## Documentation

- [Problem statement](docs/comp/problem%20statement.md)
- [Rulebook](docs/comp/rulebook.md)
- [Protocol](docs/comp/protocol.md)
- [Technical description](docs/TECHNICAL.md)
- [Validation report](docs/VALIDATION.md)
