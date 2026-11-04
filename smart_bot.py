"""Stronger baseline bot: simple but solid strategy."""
import sys, json, random

RANKS = "23456789TJQKA"
SUITS = "shdc"
RANK_VALUE = {r: i for i, r in enumerate(RANKS)}

# Global state for tracking hole cards
_my_hole_cards = []

def hand_rank_3card(hole):
    """Rough strength of 3-card hand."""
    ranks = sorted([RANK_VALUE[c[0]] for c in hole], reverse=True)
    suits = [c[1] for c in hole]
    
    # Three of a kind
    if ranks[0] == ranks[2]:
        return 1000 + ranks[0]
    
    # Pair
    if ranks[0] == ranks[1] or ranks[1] == ranks[2]:
        pair_rank = ranks[1]
        kicker = ranks[0] if ranks[0] != pair_rank else ranks[2]
        return 500 + pair_rank * 13 + kicker
    
    # Flush draw (3 same suit)
    if suits[0] == suits[1] == suits[2]:
        return 300 + ranks[0] * 13 + ranks[1]
    
    # Straight draw
    if ranks[0] - ranks[2] <= 4 and len(set(ranks)) == 3:
        return 200 + ranks[0]
    
    # Two suited
    if suits[0] == suits[1] or suits[1] == suits[2] or suits[0] == suits[2]:
        return 100 + ranks[0] * 13 + ranks[1]
    
    # High cards
    return ranks[0] * 13 + ranks[1]

def choose_action(req):
    legal = req["legal_actions"]
    street = req["street"]
    hole = _my_hole_cards
    board = req["board"]
    pot = req["pot"]
    to_call = req["to_call"]
    my_stack = req["my_stack"]
    opp_stack = req["opp_stack"]
    raises_left = req.get("raises_left", 4)
    
    # Preflop: use 3-card hand strength
    if street == "preflop":
        strength = hand_rank_3card(hole)
        # Normalize to 0-1
        eq = min(1.0, strength / 1000.0)
        
        if to_call == 0:  # Button
            if eq > 0.55 and "raise" in legal:
                size = random.choice([0.5, 0.66, 0.75])
                target = req["opp_bet"] + int(size * (req["pot"] + req["to_call"]))
                amount = max(req["min_raise"], min(req["max_raise"], target))
                return {"type": "action", "action": "raise", "amount": amount}
            return {"type": "action", "action": "check"}
        else:  # BB
            if eq > 0.40:
                if eq > 0.65 and "raise" in legal and raises_left > 1:
                    size = random.choice([0.75, 1.0])
                    target = req["opp_bet"] + int(size * (req["pot"] + req["to_call"]))
                    amount = max(req["min_raise"], min(req["max_raise"], target))
                    return {"type": "action", "action": "raise", "amount": amount}
                return {"type": "action", "action": "call"}
            # Bluff 3-bet
            if eq > 0.30 and "raise" in legal and raises_left > 1 and random.random() < 0.1:
                target = req["opp_bet"] + int(0.75 * (req["pot"] + req["to_call"]))
                amount = max(req["min_raise"], min(req["max_raise"], target))
                return {"type": "action", "action": "raise", "amount": amount}
            return {"type": "action", "action": "fold"}
    
    # Postflop: simple equity estimate
    # Count made hands and draws
    all_cards = hole + board
    ranks = [RANK_VALUE[c[0]] for c in all_cards]
    suits = [c[1] for c in all_cards]
    
    # Simple made hand detection
    rank_counts = {}
    for r in ranks:
        rank_counts[r] = rank_counts.get(r, 0) + 1
    
    max_count = max(rank_counts.values())
    flush_draw = max(suits.count(s) for s in set(suits)) >= 4
    straight_draw = False
    unique_ranks = sorted(set(ranks))
    for i in range(len(unique_ranks) - 3):
        if unique_ranks[i+3] - unique_ranks[i] <= 4:
            straight_draw = True
            break
    
    # Estimate equity
    if max_count >= 3:
        eq = 0.8
    elif max_count == 2:
        if len([c for c in rank_counts.values() if c == 2]) >= 2:
            eq = 0.75  # Two pair
        else:
            eq = 0.55  # One pair
    elif flush_draw or straight_draw:
        eq = 0.35  # Draw
    else:
        eq = 0.25 + max(ranks) / 100.0  # High card
    
    pot_odds = to_call / (pot + to_call) if (pot + to_call) > 0 else 0
    
    if to_call == 0:
        # Betting
        if eq > 0.55 and "raise" in legal:
            size = 0.5 if eq < 0.7 else 0.75
            target = int(size * pot)
            amount = max(req["min_raise"], min(req["max_raise"], target))
            return {"type": "action", "action": "raise", "amount": amount}
        # Bluff
        if eq < 0.35 and "raise" in legal and random.random() < 0.2:
            target = int(0.5 * pot)
            amount = max(req["min_raise"], min(req["max_raise"], target))
            return {"type": "action", "action": "raise", "amount": amount}
        return {"type": "action", "action": "check"}
    else:
        # Facing bet
        if eq > pot_odds + 0.05:
            if eq > 0.7 and "raise" in legal and raises_left > 0 and random.random() < 0.3:
                target = req["opp_bet"] + int(0.75 * (pot + to_call))
                amount = max(req["min_raise"], min(req["max_raise"], target))
                return {"type": "action", "action": "raise", "amount": amount}
            return {"type": "action", "action": "call"}
        elif eq > pot_odds - 0.05:
            return {"type": "action", "action": "call"} if random.random() < 0.5 else {"type": "action", "action": "fold"}
        else:
            # Bluff raise
            if eq < 0.2 and "raise" in legal and raises_left > 0 and random.random() < 0.05:
                target = req["opp_bet"] + int(0.75 * (pot + to_call))
                amount = max(req["min_raise"], min(req["max_raise"], target))
                return {"type": "action", "action": "raise", "amount": amount}
            return {"type": "action", "action": "fold"}

def choose_discard(req):
    global _my_hole_cards
    hole = req["hole_cards"]
    _my_hole_cards = hole  # Update global
    board = req["board"]
    
    # Keep best 2 cards
    best_eq = -1
    best_discard = hole[0]
    
    for i in range(3):
        kept = [hole[j] for j in range(3) if j != i]
        # Simple evaluation of 2 cards + board
        ranks = sorted([RANK_VALUE[c[0]] for c in kept + board], reverse=True)
        suits = [c[1] for c in kept + board]
        
        rank_counts = {}
        for r in ranks:
            rank_counts[r] = rank_counts.get(r, 0) + 1
        max_count = max(rank_counts.values())
        
        score = max_count * 100 + ranks[0]
        if score > best_eq:
            best_eq = score
            best_discard = hole[i]
    
    return {"type": "discard", "card": best_discard}

def main():
    global _my_hole_cards
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        t = msg.get("type")
        reply = None
        if t == "new_hand":
            _my_hole_cards = msg.get("hole_cards", [])
        elif t == "discard_result":
            _my_hole_cards = msg.get("hole_cards", [])
        elif t == "action_request":
            reply = choose_action(msg)
        elif t == "discard_request":
            reply = choose_discard(msg)
        elif t == "match_end":
            break
        else:
            continue
        if reply:
            print(json.dumps(reply), flush=True)

if __name__ == "__main__":
    main()