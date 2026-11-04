#!/usr/bin/env python3
"""
Test harness for running matches against smart_bot.
"""
import subprocess
import sys
import os

def run_match(bot_a, bot_b, stage=1, hands=40, seed=None, no_time_limits=True):
    """Run a match and return results."""
    cmd = [
        sys.executable, 'engine_official.py',
        bot_a, bot_b,
        '--stage', str(stage),
        '--hands', str(hands),
    ]
    if seed:
        cmd.extend(['--seed', str(seed)])
    if no_time_limits:
        cmd.append('--no-time-limits')
    
    result = subprocess.run(cmd, cwd=os.path.dirname(__file__), capture_output=True, text=True, timeout=120)
    return result

def parse_result(output):
    """Parse match result from engine output."""
    lines = output.strip().split('\n')
    result = {}
    for line in lines:
        if 'Result:' in line:
            result['outcome'] = line.strip()
        elif 'Capped delta:' in line:
            result['capped'] = line.strip()
        elif 'forfeit' in line.lower():
            result['forfeit'] = line.strip()
    return result

def main():
    seeds = [12345, 23456, 34567, 45678, 56789, 67890, 78901, 89012]
    wins = 0
    losses = 0
    forfeits = 0
    
    print(f"Testing bot.py vs smart_bot.py over {len(seeds)} seeds...")
    print("=" * 60)
    
    for seed in seeds:
        print(f"\nSeed {seed}: ", end='', flush=True)
        result = run_match('bot.py', 'smart_bot.py', stage=1, hands=40, seed=seed)
        parsed = parse_result(result.stdout)
        
        if 'forfeit' in parsed and 'bot.py' in parsed.get('forfeit', ''):
            print("FORFEIT (our bot crashed)")
            forfeits += 1
        elif 'forfeit' in parsed and 'smart_bot.py' in parsed.get('forfeit', ''):
            print("WIN (opponent forfeited)")
            wins += 1
        elif 'Result: A wins' in parsed.get('outcome', ''):
            print("WIN")
            wins += 1
        elif 'Result: B wins' in parsed.get('outcome', ''):
            print("LOSS")
            losses += 1
        elif 'draw' in parsed.get('outcome', '').lower():
            print("DRAW")
        else:
            print(f"UNKNOWN: {parsed}")
        
        if 'capped' in parsed:
            print(f"  {parsed['capped']}")
    
    print("\n" + "=" * 60)
    print(f"Results: {wins} wins, {losses} losses, {forfeits} forfeits")
    print(f"Win rate: {wins/(wins+losses)*100:.1f}%" if (wins+losses) > 0 else "N/A")

if __name__ == '__main__':
    main()