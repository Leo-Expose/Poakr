# Pokerbots Problem Statement: Discard Hold’em

**Submission deadline:** 15 November 2026, 23:59 IST

This Problem Statement is part of the Pokerbots Rulebook. It gives the complete rules of Discard Hold’em with worked examples. The message interface is defined in the Protocol Specification; eligibility, tournament structure, and scoring are defined in the Rulebook. Values marked **provisional** may be adjusted after benchmarking. Corrections or clarifications are announced to all teams.

## 1. The Task

Write a bot in Python 3.11 that plays Discard Hold’em, a heads-up (two-player) no-limit Texas Hold’em variant, against other teams’ bots. Each match is played in two legs of several hundred hands. Your bot is started fresh for each leg and communicates with the organisers’ engine through stdin and stdout. The bot that wins more chips over a match (both legs together) wins that match.

Discard Hold’em differs from standard Texas Hold’em in exactly two ways:

1. **Three hole cards.** Each player is dealt 3 hole cards instead of 2.
2. **Simultaneous exposed discard.** After the flop betting round, if no player has folded, each player secretly chooses one of their hole cards to discard. Both choices are made at the same time. Then both discarded cards are revealed to both players and removed from play. Each player plays the rest of the hand with 2 hole cards.

| Item | Value |
|---|---|
| Players | 2 (heads-up) |
| Betting | No-limit |
| Blinds | Small blind 1, big blind 2 |
| Starting stack | 200 chips per player, reset every hand |
| Hole cards | 3, then 2 after the discard |
| Bets or raises per round | At most 4 (the big blind counts as the first preflop) |
| Showdown hand | Best 5 cards from 2 hole cards and 5 board cards |

## 2. Cards

### 2.1. Deck and notation

A standard 52-card deck is used: 13 ranks (`2 3 4 5 6 7 8 9 T J Q K A`) in 4 suits (spades `s`, hearts `h`, diamonds `d`, clubs `c`). In the protocol, a card is a two-character string such as `As`, `Td`, or `2c`. In this document, the same cards are printed as A♠, T♢, and 2♣.

The ace is the highest rank, except in the straight A–2–3–4–5 (Section 6).

### 2.2. The deal

For each deal, the engine shuffles a full deck using a secret random seed (Rulebook 7.9) and fixes, before any action:

- 3 hole cards for each seat; and
- the 5 board cards (3 flop, 1 turn, 1 river).

The board does not depend on any player’s action or discard. A discarded card was in a player’s hand, so it could never have appeared on the board.

### 2.3. Duplicate deals

Every deal is played twice, once in each of the two legs of a match (Rulebook 7.1). In the second leg, the hole cards and the seats are swapped between the bots: the bot that held one set of hole cards in the first leg holds the other set, in the other seat, against the same board.

A fresh bot process plays each leg, so no bot ever plays both hands of a duplicate deal. Bots are not told which hands are duplicates of each other. Results are computed over both legs, so the luck of the cards largely cancels out.

## 3. Structure of a Hand

1. **Blinds.** The button posts the small blind (1); the other player posts the big blind (2). Seats alternate every hand.
2. **Deal.** Each player receives 3 hole cards, face down.
3. **Preflop betting.** The button acts first.
4. **Flop.** Three board cards are revealed.
5. **Flop betting.** The big blind acts first.
6. **Discard.** If no player has folded, both players discard one hole card simultaneously; both discards are revealed (Section 5).
7. **Turn.** One board card is revealed, followed by betting; the big blind acts first.
8. **River.** One board card is revealed, followed by betting; the big blind acts first.
9. **Showdown.** If no player has folded, the better hand wins the pot.

If a player folds at any point, the hand ends immediately and the other player wins the pot. No further cards are revealed. If the fold happens before the flop betting ends, there is no discard.

## 4. Betting

### 4.1. Stacks and blinds

Each player starts every hand with 200 chips; stacks do not carry over between hands. The blinds count as chips committed on the preflop street.

### 4.2. Order of action

Preflop, the button (small blind) acts first and the big blind acts second. On the flop, turn, and river, the big blind acts first and the button acts second.

### 4.3. Actions

| Action | When it is legal and what it does |
|---|---|
| `fold` | Only when facing a bet (`to_call > 0`). Gives up the hand and the pot. |
| `check` | Only when not facing a bet (`to_call = 0`). Passes without committing chips. |
| `call` | Only when facing a bet. Commits enough chips to match the opponent’s bet. |
| `raise` | Opens the betting or raises an existing bet, to a total amount between `min_raise` and `max_raise`. An opening bet is also sent as `raise`. |

### 4.4. “To” amounts

All raise amounts are totals for the current street, not increments. If you have committed 2 on this street and raise to 10, you add 8 chips, and your street total becomes 10.

### 4.5. Minimum raise

The minimum raise-to amount is:

\[
\text{min\_raise} = \text{opp\_bet} + \max(s, 2),
\]

where \(s\) is the size of the last bet or raise on this street. If nobody has bet on the street, the minimum opening bet is 2. Preflop, the big blind counts as the first raise (\(s = 2\)), so the first preflop minimum is \(2 + 2 = 4\).

For example, if the button raises preflop from 2 to 6, the raise size is \(s = 4\), and the big blind’s minimum re-raise is to \(6 + 4 = 10\).

### 4.6. Maximum raise and all-in

The maximum raise-to amount is the all-in amount, the most a player can have committed on the street. Both players start each hand with 200 chips, and every completed street leaves both players equally committed, so the all-in amount is always the same for both players.

If the all-in amount is below the usual minimum raise, the all-in is still legal: `min_raise = max_raise`, and only that amount may be raised to. A player facing an all-in can only call or fold.

### 4.7. Raise cap

At most 4 bets or raises are allowed per betting round. Preflop, the big blind counts as the first, so at most 3 voluntary raises can follow it. On later streets, the opening bet counts as the first. When the cap is reached, raise is no longer legal and the remaining player may only call or fold.

### 4.8. End of a betting round

A betting round ends when both players have acted and have committed equal amounts on the street, or when a player folds. In particular:

- If both players check, the round ends.
- Preflop, if the button only calls the big blind, the big blind still has the option to check (ending the round) or raise.
- A call of a bet or raise ends the round, except the button’s preflop call of the big blind, after which the big blind still has its option.

### 4.9. All-in hands

Once a player is all-in and the other has called, no further betting takes place. The remaining board cards are revealed, the discard still happens after the flop, and the hand goes to showdown. No action requests are sent for streets with no betting.

## 5. The Discard

- **When:** After the flop betting round ends, if no player has folded. This includes hands in which one or both players are all-in.
- **Simultaneous:** Both players receive the discard request at the same time. Neither player sees the other’s choice before committing to their own.
- **Exposed:** After both discards are in, both discarded cards are revealed to both players. Each player’s remaining 2 hole cards stay hidden until showdown.
- **Removed from play:** A discarded card cannot be used at showdown. The board is already fixed, so discards do not change the turn or river cards.
- **Default discard:** If a bot’s discard is illegal, or its card field is missing or unparsable, the engine discards the lowest-ranked of its three hole cards (2 lowest, ace highest). Among cards of equal rank, the one whose suit comes first in the order spades, hearts, diamonds, clubs is discarded. Sending no reply at all is a timeout and forfeits the match.

The discard is a strategic decision. The best two cards to keep depend on the flop (pairs, straight and flush draws, kickers). Your own discard is public, and it tells the opponent something about what you chose to keep.

## 6. Showdown

At showdown, each player makes the best possible five-card hand from any combination of their 2 remaining hole cards and the 5 board cards, using both, one, or none of their hole cards. A player whose best five cards are the board itself is said to “play the board.”

### 6.1. Hand rankings

From highest to lowest:

| Rank | Hand | Description | Example |
|---:|---|---|---|
| 1 | Straight flush | Five consecutive ranks, same suit | 9♡ 8♡ 7♡ 6♡ 5♡ |
| 2 | Four of a kind | Four cards of one rank | Q♠ Q♡ Q♢ Q♣ 4♠ |
| 3 | Full house | Three of one rank and two of another | 7♠ 7♡ 7♢ K♣ K♠ |
| 4 | Flush | Five cards of the same suit | A♢ J♢ 8♢ 6♢ 2♢ |
| 5 | Straight | Five consecutive ranks | T♠ 9♢ 8♡ 7♣ 6♠ |
| 6 | Three of a kind | Three cards of one rank | 5♠ 5♡ 5♣ K♢ 9♠ |
| 7 | Two pair | Two cards of one rank and two of another | J♠ J♣ 4♡ 4♢ A♠ |
| 8 | One pair | Two cards of one rank | 8♠ 8♢ A♡ T♣ 3♠ |
| 9 | High card | None of the above | A♣ Q♢ 9♡ 6♠ 3♣ |

The ace may be used low only in the straight A♠ 2♢ 3♡ 4♣ 5♠ (the lowest straight). Straights do not wrap around: Q–K–A–2–3 is not a straight.

### 6.2. Ties

Hands of the same category are compared by the ranks that make them, then by kickers, in the usual way. For example, two players with a pair of aces are compared by their three highest remaining cards in order. Suits never break ties.

If both best hands are equal, the pot is split. At showdown, both players have always committed the same number of chips, so a split pot returns each player’s chips exactly and both players’ net result is 0.

## 7. Chips, Matches, and Scoring

- **Net chips per hand:** The winner of a hand wins the chips the loser committed. After a fold, the folding player loses exactly what they had committed. After a showdown, the loser loses their full commitment. A split pot gives net 0.
- **Match:** A match is two legs between two bots, each leg containing every deal once: 200 deals per leg (400 hands in total) in Stage 1 and 500 deals per leg (1000 hands in total) in Stage 2. A fresh bot process plays each leg.
- **Winning a match:** The bot with greater net chips over the match (both legs together) wins. Equal net chips is a draw. Match points: win 1, draw 0.5, loss 0.
- **Tie-break:** Teams level on match points are ranked by capped chips per hand:

\[
\text{Score}_{\text{cap}}
=
\frac{\sum_m \operatorname{clip}(\Delta_m, -C, C)}
     {\sum_m H_m},
\]

where \(\Delta_m\) is the net chips in match \(m\), \(H_m\) is the number of hands in it (both legs; for a forfeited match, the number of hands scheduled), and \(C = 400\) in Stage 1, \(C = 1000\) in Stage 2 (**provisional**).

- **Forfeit:** A bot that crashes, exhausts its time bank, exceeds the per-response limit, or is killed by the wall-clock limit in either leg forfeits the rest of the match (the second leg is not played): a loss with \(\Delta = -C\), and the opponent’s result is set to \(\Delta = +C\).

The full tournament structure and tie-break rules are in Sections 7 and 8 of the Rulebook.

## 8. Worked Examples

In all examples, player A is on the button and player B is the big blind. The “Pot” column shows the total pot after each action.

### 8.1. Example 1: A complete hand to showdown

A holds Q♡ J♡ 4♣. B holds 9♠ 9♢ K♣. The board will be T♡ 9♡ 2♣ / 3♠ / 5♡.

| Street | Actor | Action | Pot | Notes |
|---|---|---|---:|---|
| Preflop | A | Posts small blind 1 | 1 | |
|  | B | Posts big blind 2 | 3 | Counts as the first raise |
|  | A | Raise to 6 | 8 | `min_raise` 4, `max_raise` 200 |
|  | B | Call (to 6) | 12 | Preflop betting ends |
| Flop T♡ 9♡ 2♣ | B | Check | 12 | Big blind acts first after the flop |
|  | A | Bet to 8 | 20 | Sent as `raise`, amount 8; minimum is 2 |
|  | B | Raise to 24 | 44 | Minimum was \(8 + \max(8, 2) = 16\) |
|  | A | Call (to 24) | 60 | Flop betting ends; each has 170 behind |
| Discard | A | Discards 4♣ | 60 | Keeps Q♡ J♡: flush and straight draws |
|  | B | Discards K♣ | 60 | Keeps 9♠ 9♢: three nines |
| Turn 3♠ | B | Bet to 40 | 100 | |
|  | A | Call (to 40) | 140 | Each has 130 behind |
| River 5♡ | B | Check | 140 | |
|  | A | Bet to 70 | 210 | |
|  | B | Call (to 70) | 280 | |

After the discards, A receives:

```json
{"type":"discard_result","hand_id":7,"my_discard":"4c","opp_discard":"Kc","hole_cards":["Qh","Jh"]}
```

B’s discard of a king tells A that B kept two cards it valued more than a king on this flop.

**Showdown:** A’s best hand is Q♡ J♡ T♡ 9♡ 5♡, a queen-high flush. B’s best hand is 9♠ 9♢ 9♡ T♡ 5♡, three of a kind. The flush wins.

**Chip check:** Each player committed \(6 + 24 + 40 + 70 = 140\). A wins B’s 140: net +140 for A, −140 for B.

In the other leg of the match, the bot that played A’s cards here receives 9♠ 9♢ K♣ in the big-blind seat, and the board is again T♡ 9♡ 2♣ 3♠ 5♡. That hand is played by a freshly started bot process, which has no memory of this one.

### 8.2. Example 2: Minimum raises and the raise cap

A preflop raising war:

| Actor | Action | To | Raise size \(s\) | Next `min_raise` | Next `raises_left` |
|---|---|---:|---:|---:|---:|
| B | Posts big blind | 2 | 2 | 4 | 3 |
| A | Raise | 6 | 4 | 10 | 2 |
| B | Re-raise | 18 | 12 | 30 | 1 |
| A | Raise | 50 | 32 | — | 0 |

Four bets or raises have now been made (the big blind and three raises), so the cap is reached. B’s `legal_actions` are `["fold","call"]`. If B calls, the pot is 100 and each player has 150 behind for the flop.

### 8.3. Example 3: All-in before the flop; the discard still happens

A holds A♠ A♢ 5♣. B holds K♡ K♠ Q♢.

1. Preflop, A raises to 200, which is `max_raise`, so A is all-in. B can only fold or call, and B calls. The pot is 400.
2. The flop 7♣ K♢ 2♡ is revealed. There is no betting, since both players are all-in.
3. Both players still receive a discard request. A discards 5♣; B discards Q♢.
4. The turn 9♠ and the river A♣ are revealed with no betting.
5. At showdown, A has three aces and B has three kings. Three aces wins: net +200 for A, −200 for B.

### 8.4. Example 4: A fold before the discard

1. Preflop, A calls (to 2). B checks, using the big blind’s option. The pot is 4.
2. On the flop, B bets to 4 (pot 8), and A folds.
3. The hand ends with no discard. A’s `hand_result` lists all 3 of A’s hole cards, and `opp_hole_cards` and `opp_discard` are null.
4. A committed 2 and loses it: net −2 for A, +2 for B.

### 8.5. Example 5: Kickers and a split pot

**Kicker.** The board is A♡ K♢ 8♣ 5♠ 2♡. A keeps A♣ Q♠ and B keeps A♢ J♠. Both have a pair of aces with a king. A’s hand (A–A–K–Q–8) beats B’s (A–A–K–J–8) on the fourth card.

**Split pot.** The board is T♠ J♠ Q♢ K♡ A♣, an ace-high straight. A keeps 9♣ 9♢ and B keeps 4♣ 4♡. Neither pair improves on the straight, so both players play the board. The pot is split and both players’ net is 0.

### 8.6. Example 6: Corrections by the engine

- **Illegal discard.** A bot holding 7♢ 7♠ A♣ replies `{"type":"discard","card":"Kh"}`. K♡ is not one of its cards, so the engine discards the lowest rank. Both sevens qualify, and spades comes before diamonds, so 7♠ is discarded. The bot receives:

  ```json
  {"type":"notice","code":"illegal_discard","applied":"7s"}
  ```

- **Illegal raise.** With `to_call = 0` and `min_raise = 2`, a bot replies with a raise to 1. Checking is legal, so the action is corrected to check.
- **Illegal check.** Facing a bet, a bot replies check. Checking is not legal, so the action is corrected to fold.
- **Stray output.** A debug print on stdout while a request is outstanding is read as the bot’s reply. It is malformed, so it is corrected like an illegal action, and the bot’s real reply that follows is ignored. A bot that prints a debug line on every turn will therefore check or fold every time. Use stderr for debugging.

## 9. What Your Bot Must Do

- Read engine messages from stdin, one JSON object per line, and answer every `action_request` and `discard_request` with exactly one flushed line on stdout.
- Ignore message types and fields it does not recognise.
- Choose legal actions and legal raise amounts, and choose which hole card to discard.
- Stay within the time limits for every leg, never crash, and exit after `match_end`, which is sent at the end of each leg.

| Limit | Value |
|---|---|
| Language | Python 3.11; standard library, numpy, and scipy only |
| Source | Single `bot.py`, or a `.zip` with `bot.py` at the top level; at most 5 MB |
| Match format | Two legs per match; a fresh bot process for each leg |
| Time bank | 30 s per leg in Stage 1, 75 s per leg in Stage 2 (**provisional**) |
| Per reply | 5 s (**provisional**) |
| Start-up | 5 s at the start of each leg; time before 5 s after launch is not charged |
| Wall-clock kill | 90 s per leg (Stage 1), 225 s per leg (Stage 2) (**provisional**) |
| Resources | 1 vCPU, 1 GB RAM, no network, read-only filesystem (**provisional**) |
| State | Kept only within a leg; none between legs or matches; randomness allowed |

The message formats, legality rules, and error handling are in the Protocol Specification. Test your bot with the starter kit’s local match runner for a full Stage 1 match (two legs of 200 hands) before uploading.

## 10. Precedence and Corrections

On the rules of the game, this Problem Statement prevails over Section 4 of the Rulebook. On everything else, the Rulebook prevails (Rulebook 1.3). Corrections and clarifications are announced to all teams. After the submission deadline, the game rules do not change, except to fix an engine fault (Rulebook 9.5 and 12.2).