# Benchmark Results & Validation Logs

All tests run on local hardware with single-core pinning under **native Python 3.11.15** using the official starter-kit engine (`Starter_Kit/engine.py`).  
Every match follows official tournament rules: duplicate deals, seat swaps in Leg 2, 200 starting chips per hand, blinds 1 and 2, and official time limits.

---

## 1. Threat Counter & Max Harvesting Edition vs Previous Build (Head-to-Head Duplicate Series)

Matches are 400 hands each (2 legs $\times$ 200 deals with swapped seats).  
Comparison between the finalized Max Harvesting Champion Edition (`bot.py`) and `bot_champion_v1.py`:

| Match Seed | Stage | Hands | Final `bot.py` | Previous Build | Result | Capped Delta | Notices |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Seed 42** | Stage 1 | 400 | **$+908$** | $-908$ | **Final Wins** | **$+400$ (Max)** | **0** |
| **Seed 123** | Stage 1 | 400 | **$+455$** | $-455$ | **Final Wins** | **$+400$ (Max)** | **0** |
| **Seed 777** | Stage 1 | 400 | **$+105$** | $-105$ | **Final Wins** | $+105$ | **0** |
| **Seed 2024** | Stage 1 | 400 | **$+430$** | $-430$ | **Final Wins** | **$+400$ (Max)** | **0** |
| **TOTAL** | — | **1,600 Hands** | **$+1,898$ Net Chips** | **$-1,898$ Net Chips** | **Final Wins 4–0** | **$+1,305$ Cap Score** | **0** |

**Takeaway:** The final edition achieved a dominant **4–0 sweep** and a staggering **$+1,898$ net chip margin** over our earlier champion candidate, proving that accelerated chip harvesting and GTO defense directly translate into maximum capped tournament points.

---

## 2. Starter Kit Engine Official Benchmarks (Post-Optimization)

### Stage 1 Qualifier Benchmark (400 hands vs `random_bot.py`)
- **Deal Seed:** `249269332`
- **Result:** **`bot.py` Wins**
- **Net Chips:** $+4,423$ chips
- **Capped Delta:** $+400$ (Maximum possible cap)
- **Time Used:** **$20.42\text{ s}$ total across both legs** (Bank: $30.0\text{ s}$ per leg)
- **Engine Notices / Errors:** **0 notices**, **0 forfeits**

### Stage 2 Finals Benchmark (1,000 hands vs `random_bot.py`)
- **Deal Seed:** `822630635`
- **Result:** **`bot.py` Wins**
- **Net Chips:** $+16,535$ chips
- **Capped Delta:** $+1000$ (Maximum possible cap)
- **Time Used:** $77.93\text{ s}$ total across both legs (Bank: $75.0\text{ s}$ per leg)
- **Engine Notices / Errors:** **0 notices**, **0 forfeits**

---

## 3. Hardware & Sandboxing Verification

- **CPython Version:** `3.11.15` verified.
- **RAM Footprint:** Reduced from previous peaks down to **$63.1\text{ MB}$ RSS peak** across 100+ consecutive multi-street simulations (Limit: $1,000\text{ MB} / 1\text{ GB}$).
- **Evaluator Speed:** $\approx 36.8\text{ ms}$ for $40,000$ 7-card evaluations via `int16`/`int8` dot products (26% faster).
- **CPU Threads:** Explicitly pinned to 1 core (`OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, `NUMEXPR_NUM_THREADS=1`).
- **File System:** Clean memory-only execution; zero read/write operations outside Python package imports.
- **Protocol Conformance:** Standard JSON output to stdout with explicit `flush=True`. Clean exit on `match_end`.
