# Benchmark Results & Validation Logs

All tests run on local hardware with single-core pinning under **native Python 3.11.15** using the official starter-kit engine (`Starter Kit/Starter_Kit/engine.py`).  
Every match follows official tournament rules: duplicate deals, seat swaps in Leg 2, 200 starting chips per hand, blinds 1 and 2, and official time limits.

---

## 1. Official Starter Kit Benchmarks vs `random_bot.py`

Reproducible benchmarks against the starter kit's `example_bots/random_bot.py` under Python 3.11:

| Stage | Deal Seed | Total Hands | Net Chips | Capped Delta | Time Used (Both Legs) | Time Bank Limit | Notices | Forfeits |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Stage 1** | `42` | 400 | **$+5,879$** | **$+400$** | **$22.24\text{ s}$** | $30.0\text{ s}$ per leg | **0** | **0** |
| **Stage 1** | `249269332` | 400 | **$+4,423$** | **$+400$** | **$20.42\text{ s}$** | $30.0\text{ s}$ per leg | **0** | **0** |
| **Stage 2** | `42` | 1,000 | **$+17,958$** | **$+1000$** | **$72.05\text{ s}$** | $75.0\text{ s}$ per leg | **0** | **0** |
| **Stage 2** | `822630635` | 1,000 | **$+16,535$** | **$+1000$** | **$77.93\text{ s}$** | $75.0\text{ s}$ per leg | **0** | **0** |

*Takeaway:* In all runs, the bot cleanly completes the match within the time bank, receives **0 notices**, and hits the maximum capped score ($+400$ in Stage 1, $+1000$ in Stage 2).

---

## 2. Hardware & Sandbox Metrics

Measured using Python's standard `resource` module under Python 3.11:

- **Python Version:** Python 3.11 (CPython 3.11.15).
- **Peak RSS Memory:** **$\approx 96.4\text{ MB}$** steady-state across 100 consecutive multi-street simulations.
- **Official Memory Limit:** $1,000\text{ MB}$ (1 GB) — the bot consumes $\approx 9.6\%$ of the allowed budget.
- **CPU Threads:** Explicitly pinned to 1 core (`OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, `NUMEXPR_NUM_THREADS=1`).
- **File System:** Zero file write operations at runtime, zero subprocesses, zero network sockets.
- **Protocol Conformance:** Standard JSON output to stdout with explicit `flush=True`. Clean exit on `match_end`.
