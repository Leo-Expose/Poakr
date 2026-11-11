# Local results (single machine, 1 shared core, Python 3.12)

All matches are 400 hands (2 legs x 200) using the supplied engine.
Numbers are net chips for `bot.py`; zero notices and zero forfeits in every run.

## Versus the lab's opponent zoo (seed 41)

| Opponent | bot.py | PRISM (alternative bot) |
|---|---|---|
| station | +10,958 | +15,460 |
| loose   | +9,192  | +12,534 |
| solid   | +6,607  | +13,271 |
| aggro   | +5,845  | +10,444 |
| tight   | +3,693  | +11,272 |
| maniac  | +3,226  | +6,251 |
| nit     | +2,160  | +8,950 |
| shover  | +904    | +377 |

Extra seeds for the closest opponents (bot.py): shover +3,257 / +2,625 / +4,437,
maniac +4,143 / +2,627 / +4,191. All wins.

## Head-to-head

PRISM vs bot.py, 5 seeds: -3,066 / -3,606 / -3,382 / -2,013 / -6,075 for PRISM.
bot.py was therefore kept as the submission.

## Other checks

- vs random bot, seed 1: +8,737.
- Time used: about 16-32 s over both legs of a Stage 1 match (bank is 30 s per leg).
- `fuzz.py`: 8/8 protocol tests passed. Parses under Python 3.11 grammar.

## Caveats

One seed per matchup for most rows; same-seed reruns vary because sampling scales
with measured time. The zoo is a self-made opponent set and may not resemble the
real field. Python 3.11 execution and the official hardware speed were not tested.
