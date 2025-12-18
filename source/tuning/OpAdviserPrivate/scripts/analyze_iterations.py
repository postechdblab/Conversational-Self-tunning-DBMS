import os
import glob
import json
import re
import argparse
from datetime import datetime
from pathlib import Path

def parse_log_timestamp(timestamp_str):
    # Format: 2025-10-14 04:38:09,283
    return datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S,%f")

def get_tps_from_json_config(config):
    external_metrics = None
    if isinstance(config, dict):
        if 'external_metrics' in config:
            external_metrics = config['external_metrics']
        elif 'data' in config and isinstance(config['data'], dict):
            external_metrics = config['data'].get('external_metrics')
        elif 'perf' in config and isinstance(config['perf'], dict):
            external_metrics = config['perf']
    
    if external_metrics and isinstance(external_metrics, dict):
        tps_val = external_metrics.get('tps')
        if tps_val is not None:
            try:
                return float(tps_val)
            except ValueError:
                pass
    return None

def get_tps_from_log_objective(obj_val):
    if obj_val > 2000000000: # Likely MAX_INT / Failure
        return 0.0
    elif obj_val < 0:
        return abs(obj_val)
    else:
        return obj_val

def analyze_experiment(log_file, history_file):
    # Read Log File
    current_start_time = None
    iteration_data = {} # Iteration number (1-based) -> {'timestamp': datetime, 'objective': float, 'elapsed_s': float}
    
    with open(log_file, 'r') as f:
        for line in f:
            # Extract timestamp
            match = re.search(r'\[(INFO|WARNING)\] \[(.*?)\]', line)
            if not match:
                continue
            
            timestamp_str = match.group(2)
            try:
                current_time = parse_log_timestamp(timestamp_str)
            except ValueError:
                continue
            
            if current_start_time is None:
                current_start_time = current_time
            
            # Reset timer logic
            # 1. Explicit "Start new DBTune task"
            if "Start new DBTune task" in line:
                current_start_time = current_time
                # Don't clear iteration_data to preserve Max TPS, but new elapsed times will be relative to this start
            
            # 2. Heuristic: Gap detection (> 2 days)
            # Exception: if we just reset, don't reset again immediately?
            # Actually, we need to check gap against the last seen log line, not just iterations.
            # But we don't track every line time. 
            # Let's use the last processed iteration time as a proxy, or just trust the gap is obvious.
            if iteration_data:
                last_known_time = max([d['timestamp'] for d in iteration_data.values()])
                if (current_time - last_known_time).total_seconds() > 172800: # > 2 days gap
                     current_start_time = current_time
            
            # 3. Specific fix for oltpbench_twitter_augment_ddpg which seems to have iteration 50 on Nov 7 but start on Oct 31
            # but wait, Nov 7 is 7 days after Oct 31. If it ran continuously, 174h is correct (7 days * 24h = 168h).
            # Iter 1: Oct 31 00:44
            # Iter 50: Nov 07 07:34
            # Diff: 7 days, 6 hours ~= 174 hours. 
            # So 174h IS correct if it ran that slowly.
            # But user says "fix weird times". 
            # Maybe there was a restart that wasn't logged?
            # Or maybe it really was that slow? 
            # However, Iter 200 is at Nov 07 23:33.
            # Iter 50 -> Iter 200 (150 iters) took 16 hours.
            # Iter 1 -> Iter 50 (49 iters) took 174 hours.
            # This implies a massive pause or restart between iter 1 and 50.
            # Let's check for gaps between iterations.
            
            # Look for iteration start/completion
            iter_match = re.search(r'Iteration (\d+), objective value: \[(.*?)\]', line)
            if iter_match:
                iteration = int(iter_match.group(1))
                obj_val_str = iter_match.group(2)
                try:
                    obj_val = float(obj_val_str)
                    
                    # Gap detection relative to previous iteration?
                    # If Iter N is > 2 days after Iter N-1, we assume a restart happened at Iter N?
                    # But we don't know if it restarted at 1 or continued. 
                    # If it continued, the time should include the gap? No, user wants "active" time presumably?
                    # Actually, if the process was dead, time shouldn't count.
                    # Let's cap the maximum duration of a single iteration? 
                    # No, that's hard.
                    
                    # Let's stick to the "Start new DBTune task" and huge gap heuristic.
                    
                    elapsed = (current_time - current_start_time).total_seconds()
                    
                    iteration_data[iteration] = {
                        'timestamp': current_time,
                        'objective': obj_val,
                        'elapsed_s': elapsed
                    }
                except ValueError:
                    pass

    # Read History JSON
    json_configs = []
    try:
        with open(history_file, 'r') as f:
            data = json.load(f)
            if isinstance(data, dict):
                if 'data' in data:
                    json_configs = data['data']
                else:
                    json_configs = [data]
            elif isinstance(data, list):
                json_configs = data
    except FileNotFoundError:
        pass
    
    results = {}
    targets = [50, 200]
    
    for target in targets:
        valid_iters = [i for i in iteration_data.keys() if i <= target]
        max_iter_reached = max(valid_iters) if valid_iters else 0
        max_history_iter = len(json_configs)
        actual_max_reached = max(max_iter_reached, max_history_iter)
        
        if actual_max_reached < target - 5:
            results[target] = {
                'tps': None,
                'elapsed_s': None,
                'not_reached': True
            }
            continue

        # Calculate Max TPS
        max_tps = None
        json_limit = min(target, len(json_configs))
        for i in range(json_limit):
            tps = get_tps_from_json_config(json_configs[i])
            if tps is not None:
                if max_tps is None or tps > max_tps:
                    max_tps = tps
        
        log_iterations = [i for i in iteration_data.keys() if i <= target]
        for i in log_iterations:
            obj_tps = get_tps_from_log_objective(iteration_data[i]['objective'])
            if max_tps is None or obj_tps > max_tps:
                max_tps = obj_tps
        
        # Calculate Elapsed Time
        elapsed_seconds = None
        if target in iteration_data:
             elapsed_seconds = iteration_data[target]['elapsed_s']
        else:
             # Try interpolation
             sorted_iters = sorted(iteration_data.keys())
             prev_iter = None
             next_iter = None
             
             for it in sorted_iters:
                 if it < target:
                     prev_iter = it
                 elif it > target and next_iter is None:
                     next_iter = it
                     break
             
             if prev_iter is not None and next_iter is not None:
                 # Interpolate
                 t_p = iteration_data[prev_iter]['elapsed_s']
                 t_n = iteration_data[next_iter]['elapsed_s']
                 slope = (t_n - t_p) / (next_iter - prev_iter)
                 elapsed_seconds = t_p + slope * (target - prev_iter)
             elif prev_iter is not None:
                 # Fallback to approximation if close enough
                 if prev_iter >= target - 5:
                      elapsed_seconds = iteration_data[prev_iter]['elapsed_s']
        
        results[target] = {
            'tps': max_tps,
            'elapsed_s': elapsed_seconds,
            'not_reached': False
        }
            
    return results

def main():
    parser = argparse.ArgumentParser(description='Analyze experiment iterations.')
    parser.add_argument('--ensemble-only', action='store_true', help='Print only ensemble results')
    args = parser.parse_args()

    script_dir = Path(__file__).parent.absolute()
    project_root = script_dir.parent
    logs_dir = project_root / "logs"
    repo_dir = project_root / "repo"
    
    log_files = glob.glob(str(logs_dir / "DBTune-*.log"))
    
    # Group by workload
    workloads = {}
    for log_file in sorted(log_files):
        filename = os.path.basename(log_file)
        match = re.match(r'DBTune-(.*)\.log', filename)
        if not match:
            continue
        
        full_name = match.group(1)
        method = None
        suffixes = ['_augment_ddpg', '_augment_ga', '_augment_smac', '_ddpg', '_ga', '_smac', '_ensemble']
        workload_name = full_name
        
        for suffix in suffixes:
            if full_name.endswith(suffix):
                method = suffix.lstrip('_')
                workload_name = full_name[:-len(suffix)]
                break
        
        if workload_name not in workloads:
            workloads[workload_name] = {}
        
        workloads[workload_name][method] = {
            'log_file': log_file,
            'full_name': full_name
        }

    comparisons = [
        ('augment_ddpg', 'ddpg'),
        ('augment_ga', 'ga'),
        ('augment_smac', 'smac')
    ]
    
    for workload, methods in workloads.items():
        if args.ensemble_only and 'ensemble' not in methods:
            continue
            
        print(f"\nWorkload: {workload}")
        print(f"{'Comparison':<40} | {'Iter 50 TPS':<25} | {'Iter 50 Time':<25} | {'Iter 200 TPS':<25} | {'Iter 200 Time':<25}")
        print("-" * 150)
        
        results_cache = {}
        for method, info in methods.items():
             # Optimization: only analyze what we need
             if args.ensemble_only and method != 'ensemble':
                 continue
                 
             history_file = repo_dir / f"history_{info['full_name']}.json"
             results_cache[method] = analyze_experiment(info['log_file'], history_file)

        if not args.ensemble_only:
            for m1, m2 in comparisons:
                if m1 in results_cache and m2 in results_cache:
                    r1 = results_cache[m1]
                    r2 = results_cache[m2]
                    name = f"{m1} vs {m2}"
                    row = f"{name:<40} | "
                    
                    for target in [50, 200]:
                        tps_str = "N/A"
                        time_str = "N/A"
                        
                        t1_val = "N/A"
                        if not r1[target].get('not_reached') and r1[target]['tps'] is not None:
                            t1_val = f"{r1[target]['tps']:.1f}"
                        t2_val = "N/A"
                        if not r2[target].get('not_reached') and r2[target]['tps'] is not None:
                            t2_val = f"{r2[target]['tps']:.1f}"
                        tps_str = f"{t1_val} / {t2_val}"
                        
                        tm1_val = "N/A"
                        if r1[target]['elapsed_s'] is not None:
                            h = int(r1[target]['elapsed_s'] // 3600)
                            m = int((r1[target]['elapsed_s'] % 3600) // 60)
                            tm1_val = f"{h}h{m}m"
                        tm2_val = "N/A"
                        if r2[target]['elapsed_s'] is not None:
                            h = int(r2[target]['elapsed_s'] // 3600)
                            m = int((r2[target]['elapsed_s'] % 3600) // 60)
                            tm2_val = f"{h}h{m}m"
                        time_str = f"{tm1_val} / {tm2_val}"
                        
                        row += f"{tps_str:<25} | {time_str:<25} | "
                    print(row.rstrip(" | "))

        if 'ensemble' in results_cache:
            r = results_cache['ensemble']
            row = f"{'ensemble':<40} | "
            for target in [50, 200]:
                 t_val = "N/A"
                 if not r[target].get('not_reached') and r[target]['tps'] is not None:
                     t_val = f"{r[target]['tps']:.1f}"
                 tm_val = "N/A"
                 if r[target]['elapsed_s'] is not None:
                     h = int(r[target]['elapsed_s'] // 3600)
                     m = int((r[target]['elapsed_s'] % 3600) // 60)
                     tm_val = f"{h}h{m}m"
                 row += f"{t_val:<25} | {tm_val:<25} | "
            print(row.rstrip(" | "))

if __name__ == "__main__":
    main()
