import sys, json

RANKS = "23456789TJQKA"

def choose_action(req):
    legal = req["legal_actions"]
    # Replace with your strategy. This one checks if free, else calls.
    if "check" in legal:
        return {"type": "action", "action": "check"}
    if "call" in legal:
        return {"type": "action", "action": "call"}
    return {"type": "action", "action": "fold"}

def choose_discard(req):
    # Replace with your strategy. This one discards the lowest rank.
    cards = req["hole_cards"]
    worst = min(cards, key=lambda c: RANKS.index(c[0]))
    return {"type": "discard", "card": worst}

def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        t = msg.get("type")
        if t == "action_request":
            reply = choose_action(msg)
        elif t == "discard_request":
            reply = choose_discard(msg)
        elif t == "match_end":
            break
        else:
            # init, new_hand, discard_result, hand_result, notice:
            # update your own state here; no reply is sent.
            continue
        print(json.dumps(reply), flush=True)

if __name__ == "__main__":
    main()
