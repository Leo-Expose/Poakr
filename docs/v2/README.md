# Pokerbot v2 — tested core, official integration pending

**Read `docs/v2/READINESS.md` and `docs/v2/VALIDATION.md` before choosing a submission.**
This is not an official-protocol bot yet. The organizer's custom mechanics and
stdin/stdout grammar were not supplied in the available announcement.

## Files

- `runtime/bot.py`: generated single-file v2 candidate; stdlib + NumPy runtime.
- `src/core.py`, `src/fast_eval.py`: configurable engine and evaluation source.
- `src/adapter.py`: strict **example** JSONL adapter; replace with official grammar.
- `legacy/bot_v1.py`: preserved earlier prototype; useful comparison/rollback,
  not an official-protocol solution either.
- `docs/v2/READINESS.md`: requirement-by-requirement audit and unresolved release gates.
- `docs/v2/PROTOCOL_EXAMPLE.md`: example schema and normalization conventions.
- `docs/v2/VALIDATION.md`: current results, including strategy regressions.
- `tests/`: unit tests, raw benchmark/resource reports and logs.

## Run the example, not the official runner

```bash
python3 runtime/bot.py --config config/example_standard.json \
  < fixtures/example_session.jsonl
```

Default settings disable duplicate inference, proactive bluffing and the
experimental risk dial. `config/example_replay_board.json` enables board-based
inference for a **verified** same-deal seat-swapped replay. The short-deck profile
is only a configuration demonstration, not a claim about the event's rules.

## Rebuild and validate

```bash
python3 bench/build_release.py
python3 -m unittest discover -s tests -v
python3 bench/exhaustive_v2.py
python3 bench/resource_v2.py
python3 bench/matches_v2.py --matches 6 --deals 60 --seed 53000 \
  --release-check --no-mirror --output release_matches_results.json
python3 bench/package_v2.py
```

The syntax is checked against Python 3.11; local execution used Python 3.13.16.
Actual execution under the organizer's Python 3.11 environment is still required.
No runtime installations, network use or file writes are performed by the bot.

**Engineering correctness is not poker optimality.** The final fresh-seed pilot
favored v1 in wins despite v2's higher average chips. Both are retained; neither
should be declared the tournament winner or submitted unchanged without official
rule/protocol integration.
