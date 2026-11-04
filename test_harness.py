#!/usr/bin/env python3
"""
Test Harness for Pokerbots - runs matches against smart_bot and reports results.
Usage: python3 test_harness.py [--seeds N] [--hands N] [--stage 1|2] [--verbose]
"""
import subprocess
import sys
import os
import argparse
import json
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed

def run_single_match(seed, stage=1, hands=40, verbose=False, no_time_limits=True):
    """Run a single match and return parsed result."""
    cmd = [
        sys.executable, 'engine_official.py',
        'bot.py', 'smart_bot.py',
        '--stage', str(stage),
        '--hands', str(hands),
        '--seed', str(seed),
    ]
    if no_time_limits:
        cmd.append('--no-time-limits')
    if verbose:
        cmd.append('--verbose')
    
    try:
        result = subprocess.run(
            cmd, 
            cwd=os.path.dirname(__file__), 
            capture_output=True, 
            text=True, 
            timeout=180
        )
        return {
            'seed': seed,
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
        }
    except subprocess.TimeoutExpired:
        return {'seed': seed, 'error': 'timeout'}
    except Exception as e:
        return {'seed': seed, 'error': str(e)}

def parse_match_result(output):
    """Parse match result from engine stdout."""
    lines = output.strip().split('\n')
    result = {
        'outcome': 'unknown',
        'capped_delta': None,
        'net_a': None,
        'net_b': None,
        'forfeit': None,
        'notices_a': 0,
        'notices_b': 0,
        'time_a': 0.0,
        'time_b': 0.0,
    }
    
    for line in lines:
        line = line.strip()
        if line.startswith('Result:'):
            result['outcome'] = line
            if 'A wins' in line:
                result['winner'] = 'A'
            elif 'B wins' in line:
                result['winner'] = 'B'
            elif 'draw' in line.lower():
                result['winner'] = 'draw'
        elif 'Capped delta:' in line:
            result['capped_delta'] = line
            # Parse: "Capped delta: A +205, B -205 (C = 400)"
            import re
            m = re.search(r'A\s+([+-]?\d+),\s*B\s+([+-]?\d+)', line)
            if m:
                result['net_a'] = int(m.group(1))
                result['net_b'] = int(m.group(2))
        elif 'forfeit' in line.lower():
            result['forfeit'] = line
            if 'A forfeited' in line or 'A crashed' in line:
                result['winner'] = 'B'
                result['forfeit_bot'] = 'A'
            elif 'B forfeited' in line or 'B crashed' in line:
                result['winner'] = 'A'
                result['forfeit_bot'] = 'B'
        elif 'time used' in line.lower() and 'notices' in line.lower():
            # Parse: "  A  bot.py                           net    +205   time used   0.00 s of 60 s   notices 0"
            parts = line.split()
            if len(parts) >= 6:
                try:
                    bot_name = parts[0]
                    net = int(parts[2])
                    time_used = float(parts[5])
                    notices = int(parts[8])
                    if bot_name == 'A':
                        result['net_a'] = net
                        result['time_a'] = time_used
                        result['notices_a'] = notices
                    elif bot_name == 'B':
                        result['net_b'] = net
                        result['time_b'] = time_used
                        result['notices_b'] = notices
                except (ValueError, IndexError):
                    pass
    return result

def run_test_suite(seeds, stage=1, hands=40, max_workers=4, verbose=False):
    """Run multiple matches and aggregate results."""
    print(f"Running {len(seeds)} matches (Stage {stage}, {hands} hands each)...")
    print(f"Seeds: {seeds}")
    print(f"Max workers: {max_workers}")
    print("=" * 70)
    
    results = []
    completed = 0
    
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_to_seed = {
            executor.submit(run_single_match, seed, stage, hands, verbose): seed 
            for seed in seeds
        }
        
        for future in as_completed(future_to_seed):
            seed = future_to_seed[future]
            completed += 1
            
            try:
                match_result = future.result()
            except Exception as e:
                print(f"  Seed {seed}: EXCEPTION - {e}")
                results.append({'seed': seed, 'error': str(e)})
                continue
            
            if 'error' in match_result:
                print(f"  Seed {seed}: ERROR - {match_result['error']}")
                results.append(match_result)
                continue
            
            parsed = parse_match_result(match_result['stdout'])
            parsed['seed'] = seed
            parsed['raw_stdout'] = match_result['stdout']
            parsed['stderr'] = match_result['stderr']
            results.append(parsed)
            
            # Print result
            outcome = parsed.get('outcome', 'unknown')
            winner = parsed.get('winner', '?')
            forfeit = parsed.get('forfeit')
            net_a = parsed.get('net_a')
            capped = parsed.get('capped_delta', '')
            
            if forfeit:
                status = f"FORFEIT ({forfeit})"
            elif winner:
                status = f"{winner} wins"
            else:
                status = outcome
            
            net_str = f" net_a={net_a}" if net_a is not None else ""
            print(f"  [{completed}/{len(seeds)}] Seed {seed}: {status}{net_str}")
            
            if verbose:
                print(f"    {capped}")
    
    return results

def print_summary(results):
    """Print aggregated summary."""
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    total = len(results)
    wins = sum(1 for r in results if r.get('winner') == 'A')
    losses = sum(1 for r in results if r.get('winner') == 'B')
    draws = sum(1 for r in results if r.get('winner') == 'draw')
    forfeits = sum(1 for r in results if r.get('forfeit'))
    errors = sum(1 for r in results if 'error' in r)
    completed = sum(1 for r in results if 'winner' in r or r.get('forfeit'))
    
    print(f"Total matches: {total}")
    print(f"Completed: {completed}")
    print(f"  Wins (A):   {wins}")
    print(f"  Losses (A): {losses}")
    print(f"  Draws:      {draws}")
    print(f"  Forfeits:   {forfeits}")
    print(f"  Errors:     {errors}")
    
    if completed > 0:
        win_rate = wins / completed * 100
        print(f"Win rate: {win_rate:.1f}%")
        
        # Average net chips (capped)
        nets = [r.get('net_a') for r in results if r.get('net_a') is not None]
        if nets:
            avg_net = sum(nets) / len(nets)
            print(f"Avg net chips (capped): {avg_net:.1f}")
            
        # Notices
        notices_a = [r.get('notices_a', 0) for r in results]
        notices_b = [r.get('notices_b', 0) for r in results]
        print(f"Total notices - A: {sum(notices_a)}, B: {sum(notices_b)}")
        
        # Time usage
        times_a = [r.get('time_a', 0) for r in results if r.get('time_a')]
        times_b = [r.get('time_b', 0) for r in results if r.get('time_b')]
        if times_a:
            print(f"Avg time - A: {sum(times_a)/len(times_a):.2f}s, B: {sum(times_b)/len(times_b):.2f}s")
    
    # Forfeit details
    forfeit_results = [r for r in results if r.get('forfeit')]
    if forfeit_results:
        print(f"\nForfeit details:")
        for r in forfeit_results:
            print(f"  Seed {r['seed']}: {r.get('forfeit', 'unknown')}")

def save_results(results, filename=None):
    """Save detailed results to JSON."""
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"test_results_{timestamp}.json"
    
    output = {
        'timestamp': datetime.now().isoformat(),
        'bot': 'bot.py',
        'opponent': 'smart_bot.py',
        'results': results
    }
    
    with open(filename, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\nDetailed results saved to {filename}")

def main():
    parser = argparse.ArgumentParser(description='Test harness for Pokerbots')
    parser.add_argument('--seeds', type=int, nargs='+', 
                       default=[12345, 23456, 34567, 45678, 56789, 67890, 78901, 89012],
                       help='Seeds to test')
    parser.add_argument('--stage', type=int, choices=[1, 2], default=1)
    parser.add_argument('--hands', type=int, default=40)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--verbose', action='store_true')
    parser.add_argument('--output', type=str, help='Output JSON file')
    args = parser.parse_args()
    
    # Run tests
    results = run_test_suite(
        seeds=args.seeds,
        stage=args.stage,
        hands=args.hands,
        max_workers=args.workers,
        verbose=args.verbose
    )
    
    # Print summary
    print_summary(results)
    
    # Save results
    if args.output:
        save_results(results, args.output)
    else:
        save_results(results)

if __name__ == '__main__':
    main()