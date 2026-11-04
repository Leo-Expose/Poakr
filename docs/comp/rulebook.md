# Pokerbots Rulebook

**Submission deadline:** 15 November 2026, 23:59 IST

Values marked **(provisional)** may be adjusted after benchmarking; any change will be announced to all teams before the submission deadline.

## 1. Scope

**1.1** Pokerbots is an online competition in which a team’s Python bot plays a custom poker variant against other teams’ bots on an automated server.

**1.2** The game uses virtual chips only. There is no entry fee and no real-money play.

**1.3** These rules apply to all teams. The Problem Statement and the Protocol Specification, released by the organisers before the submission deadline, form part of this rulebook. If they conflict with this rulebook, this rulebook prevails, except for the variant rules (Section 4), where the Problem Statement prevails. The starter kit (including `engine.py`) is provided for local testing; if it differs from these documents, these documents prevail, and the organisers will announce a correction.

**1.4** Terms used:

- A **hand** is one deal played by two bots.
- A **leg** is a series of hands played by one freshly started pair of bot processes, in which every deal of the match appears exactly once.
- A **match** is two legs between the same two bots, played with the same deals.
- A **duplicate deal** is one deal played once in each leg, with the hole cards and seats swapped between the two bots.
- The **engine** is the organisers’ match software.

## 2. Eligibility

**2.1** Participation is open to participants from any college or city.

**2.2** Each team has exactly two members. Teams of one, or of three or more, are not accepted.

**2.3** A person may be a member of only one team.

## 3. Registration

**3.1** Registration requires a unique team name and, for both members, name, email, college and city.

**3.2** Both members must consent to these rules at registration.

**3.3** Email addresses are verified. A registration with an unverified email is not valid.

**3.4** Member 1 is the team’s point of contact and receives all official communication.

## 4. The Game

**4.1** The game is Discard Hold’em, a heads-up Texas Hold’em variant with two changed mechanics. Full rules and worked examples are in the Problem Statement.

**4.2** Matches are head-to-head between two bots.

**4.3** **Three hole cards.** Each player is dealt 3 hole cards instead of 2.

**4.4** **Simultaneous exposed discard.** After the flop betting round, if no player has folded, each player secretly chooses one hole card to discard. Both choices are made simultaneously. Both discarded cards are then revealed to both players and removed from play. This also happens when a player is all-in.

**4.5** At showdown, each player makes the best five-card hand from their remaining 2 hole cards and the 5 board cards, using standard hand rankings.

**4.6** **Betting.** No-limit. Small blind 1, big blind 2. Each player starts every hand with 200 chips (stacks reset every hand). The button posts the small blind, acts first preflop, and acts second on later streets. Seats alternate every hand.

**4.7** The minimum raise is the size of the previous bet or raise, and never less than 2 chips. There are at most 4 bets or raises per betting round, with the big blind counting as the first on preflop.

## 5. Bot Requirements

**5.1** Bots must be written in Python and run on Python 3.11.

**5.2** Only the standard library, NumPy and SciPy may be used. No packages may be installed at runtime.

**5.3** Each bot runs with 1 vCPU and 1 GB RAM. **(provisional)**

**5.4** Bots have no network access and run on a read-only filesystem. A bot may read files contained in its own submission, but may not write files, open sockets, start other processes, or attempt to leave its sandbox.

**5.5** Each bot has a cumulative time bank per leg, which is not reset between hands: 30 seconds per leg in Stage 1 (two legs of 200 hands), and 75 seconds per leg in Stage 2 (two legs of 500 hands). **(provisional)**

**5.6** Any single response must arrive within 5 seconds. A hard wall-clock kill applies to each leg: 90 seconds in Stage 1 and 225 seconds in Stage 2. **(provisional)**

**5.7** A bot has 5 seconds from launch at the start of each leg to start up. The clock for each request starts at the later of the moment the request is sent and 5 seconds after launch, so time before that point is not charged to the time bank, and the first reply may arrive up to 10 seconds after launch.

**5.8** Bots communicate only through the stdin/stdout protocol in the Protocol Specification. Output on stdout must contain only protocol messages. Output on stderr is captured, limited to 64 KB per leg, and never parsed.

**5.9** A bot is started fresh for each leg of each match. It may keep state between hands within a leg. No state carries over between legs or between matches, and a bot may not attempt to pass information from one leg to another. Randomness is allowed.

**5.10** A bot’s source must be a single `bot.py`, or a `.zip` file with `bot.py` at its top level, no larger than 5 MB.

**5.11** All limits apply identically to every bot, and all matches in a round run on equal machines.

## 6. Submission

**6.1** Each team submits one final bot on Unstop. A team may upload more than once before the deadline; only its last valid upload is entered.

**6.2** The submission deadline is 15 November 2026 at 23:59 IST, at which point code is frozen. Uploads after this time are not accepted.

**6.3** A team with no valid upload at the deadline is not entered into the tournament.

**6.4** If a fault in the organisers’ upload portal prevents uploads, the organisers will extend the deadline for all teams and announce it.

## 7. Tournament Structure

**7.1** Every match is played in two legs. Each leg contains every deal of the match exactly once. In the second leg each deal is played with the hole cards and seats swapped between the bots, against the same board, so that each duplicate deal is two hands. Each leg is played by freshly started bot processes, so no bot process ever plays both hands of a duplicate deal. All results are computed over both legs together.

**7.2** **Stage 1 (Swiss qualifier).** All valid bots play 6 rounds, or 7 to 8 rounds if more than 1000 teams submit; the number of rounds is announced before Round 1. Each round is a match of 200 duplicate deals (400 hands), played as two legs of 200 hands.

**7.3** Round 1 pairings are random. In later rounds, teams are ranked by match points, then by capped chips per hand (Section 8), then randomly, and are paired with the closest-ranked team they have not yet played, within the same match-point group where possible. No two teams are paired more than once.

**7.4** A bye is awarded when the number of teams is odd. It goes to the lowest-ranked team that has not yet had one, and counts as a win. A bye adds neither chips nor hands to the capped score.

**7.5** If fewer than 64 valid bots submit, Stage 1 is a full round robin instead of a Swiss. If 32 or fewer valid bots submit, Stage 1 is skipped.

**7.6** The top 32 teams after Stage 1 advance to Stage 2. Ties at the cut-off are resolved by Section 8.

**7.7** **Stage 2 (finals).** The top 32 play a full round robin of \(32 \choose 2 = 496\) matches, each of 500 duplicate deals (1000 hands), played as two legs of 500 hands.

**7.8** Scores are reset before Stage 2. The Stage 2 standings alone determine the final result and the prizes.

**7.9** Deals are generated from secret random seeds, which are published after the results.

## 8. Scoring and Tie-Breaks

**8.1** The bot with the greater net chips over a match (both legs together) wins it. Equal net chips is a draw.

**8.2** Match points are: win 1, draw 0.5, loss 0. Teams are ranked by total match points.

**8.3** Teams level on match points are ranked by capped chips per hand:

\[
\text{Score}_{\text{cap}}
=
\frac{\sum_m \operatorname{clip}(\Delta_m,-C,C)}
{\sum_m H_m}
\]

where \(\Delta_m\) is the net chips in match \(m\) (both legs), \(H_m\) is the number of hands in match \(m\) (both legs), and \(C\) is a fixed cap. The function \(\operatorname{clip}(x,-C,C)\) limits \(x\) to the range \([-C,C]\).

- \(C = 400\) chips in Stage 1 and \(C = 1000\) chips in Stage 2. **(provisional)**
- For a forfeited match, \(H_m\) is the number of hands scheduled for the match (400 in Stage 1, 1000 in Stage 2), not the number actually played.

**8.4** Teams still level after 8.3, for a prize position or the Stage 2 cut-off, play a replay: a match of 500 duplicate deals (two legs of 500 hands) with a fresh secret seed under the Stage 2 limits. If more than two teams are level, they play a round robin of replays. A drawn replay is repeated with a new seed.

**8.5** Teams level for a position that carries no prize and no qualification effect share that position.

## 9. Crashes, Timeouts and Illegal Actions

**9.1** A bot that crashes, exhausts its time bank, exceeds the per-response limit, or is stopped by the wall-clock kill forfeits the remainder of the match. A forfeit in either leg forfeits the whole match; if it happens in the first leg, the second leg is not played.

**9.2** A forfeited match is a loss for the forfeiting bot, with \(\Delta = -C\), and the opponent’s result for that match is set to \(\Delta = +C\). If both bots forfeit in the same hand, the match is a draw with \(\Delta = 0\) for both.

**9.3** An action that is not legal, or a message that cannot be parsed, is corrected to a check where checking is legal, and to a fold otherwise.

**9.4** An illegal discard, or a discard message whose card field is missing or not a valid card, is corrected to discarding the lowest-ranked of the three hole cards (2 is lowest, ace is highest). Among cards of equal rank, the one whose suit comes first in the order spades, hearts, diamonds, clubs is discarded. No reply at all is a timeout (9.1).

**9.5** If a match is disrupted by a fault of the organisers’ engine or hardware, it is replayed in full and the original result is void.

## 10. Conduct

**10.1** A bot must be the team’s own work. Copying code from other teams or from public bot repositories is prohibited, except for material supplied by the organisers. Standard libraries and published algorithms may be used.

**10.2** Collusion between teams, including signalling between bots, sharing code or strategy, and deliberately losing to benefit another team, is prohibited.

**10.3** Attempting to access the network, interfere with the server or other bots, or exploit the evaluation system is prohibited. This includes any attempt to identify the two hands of a duplicate deal or to carry information between legs. A team that finds a weakness must report it to the organisers and not use it.

**10.4** The code of prize-winning teams is reviewed before prizes are awarded. The organisers may review any team’s code and run similarity checks across submissions.

**10.5** A team found in breach of these rules is disqualified, loses any prize, and its results are removed.

**10.6** The organisers’ decision on the interpretation of these rules and on any dispute is final.

## 11. Prizes

**11.1** Prizes are awarded to the top three teams by the Stage 2 standings:

| Rank | Prize (Rs.) |
|---|---:|
| 1st | 20,000 |
| 2nd | 14,000 |
| 3rd | 8,000 |

## 12. Results and Amendments

**12.1** Results are published after Stage 2.

**12.2** The organisers may amend this rulebook to correct errors, update provisional values or deal with unforeseen situations. After the submission deadline, the game rules and bot limits may not change, except to fix an engine fault under 9.5.