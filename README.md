# Discard Hold'em bot

Python 3.11 bot for the Pokerbots Discard Hold'em tournament (heads-up Texas
Hold'em with 3 hole cards and a simultaneous, exposed discard after the flop).

**Submission:** `bot.py` (single file, ~58 KB, standard library + NumPy only).
SHA-256: `d25e9724a0d5dc098b128047d95446ba98886707a851f251a190a0312005b155`

## Design (as implemented in `bot.py`)

- Embedded preflop strength table (no file I/O at runtime).
- Monte-Carlo equity for the flop/turn, exact enumeration on the river and, when
  time allows, on the turn.
- Discard chosen by simulating post-discard equity for each of the three cards.
- Opponent range weighted by their observed betting; opponent aggression is
  measured within the current leg only.
- Time manager: CPU-speed calibration, reserve of the time bank, and a safe
  fallback action, so a slow machine degrades quality instead of forfeiting.
- Defensive protocol handling: only legal replies, clean exit on bad input.

## Rules compliance

- Standard library + NumPy only; no file writes, network or subprocesses.
- State is kept only within a leg. Nothing is carried between legs, and nothing
  tries to identify the two hands of a duplicate deal (Rulebook 5.9, 10.3).

## Local results

See `RESULTS.md`. These are small local samples, not a prediction of the
tournament result.
