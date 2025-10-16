#!/usr/bin/env python3
"""
Analyze experiment results from run_experiments_machine*.sh scripts.
Compare single-optimizer mode vs ensemble mode performance.
"""

import json
import os
import glob
from pathlib import Path
from collections import defaultdict

# Define experiments run by each machine based on the runner scripts
# Format: (display_name, single_task_id_pattern, ensemble_task_id_pattern)
MACHINE_EXPERIMENTS = {
    'machine1': [
        ('Twitter', 'oltpbench_twitter_smac', 'oltpbench_twitter_ensemble'),
        ('TPC-C', 'oltpbench_tpcc', 'oltpbench_tpcc_ensemble'),
        ('YCSB', 'oltpbench_ycsb', 'oltpbench_ycsb_ensemble'),
        ('Wikipedia', 'oltpbench_wikipedia', 'oltpbench_wikipedia_ensemble'),
    ],
    'machine2': [
        ('TATP', 'oltpbench_tatp', 'oltpbench_tatp_ensemble'),
        ('Voter', 'oltpbench_voter', 'oltpbench_voter_ensemble'),
        ('TPC-H', 'tpch', 'tpch_ensemble'),
        ('JOB', 'job', 'job_ensemble'),
    ],
    'machine3': [
        ('Sysbench-RW', 'sysbench_rw', 'sysbench_rw_ensemble'),
        ('Sysbench-WO', 'sysbench_wo', 'sysbench_wo_ensemble'),
        ('Sysbench-RO', 'sysbench_ro', 'sysbench_ro_ensemble'),
    ],
}

def extract_max_tps(json_file_path):
    """
    Extract maximum TPS from a history JSON file.
    
    Args:
        json_file_path: Path to the JSON file
        
    Returns:
        tuple: (max_tps, latency_at_max, qps_at_max, total_configs)
    """
    try:
        with open(json_file_path, 'r') as f:
            data = json.load(f)
        
        max_tps = None
        max_lat = None
        max_qps = None
        total_configs = 0
        
        # Handle different JSON structures
        if isinstance(data, dict):
            if 'data' in data:
                configs = data['data']
            else:
                configs = [data]
        elif isinstance(data, list):
            configs = data
        else:
            return None, None, None, 0
        
        for config in configs:
            total_configs += 1
            
            # Navigate through possible structures
            external_metrics = None
            
            if isinstance(config, dict):
                if 'external_metrics' in config:
                    external_metrics = config['external_metrics']
                elif 'data' in config and isinstance(config['data'], dict):
                    external_metrics = config['data'].get('external_metrics')
                elif 'perf' in config and isinstance(config['perf'], dict):
                    external_metrics = config['perf']
            
            if external_metrics and isinstance(external_metrics, dict):
                tps = external_metrics.get('tps')
                if tps is not None:
                    try:
                        tps_value = float(tps)
                        if tps_value > 0:  # Only consider positive TPS values
                            if max_tps is None or tps_value > max_tps:
                                max_tps = tps_value
                                max_lat = external_metrics.get('lat')
                                max_qps = external_metrics.get('qps')
                    except (ValueError, TypeError):
                        pass
        
        return max_tps, max_lat, max_qps, total_configs
        
    except Exception as e:
        print(f"Error processing {json_file_path}: {e}")
        return None, None, None, 0


def find_history_file(repo_dir, task_id_pattern):
    """
    Find history JSON file matching the task_id pattern.
    """
    pattern = f"history_{task_id_pattern}.json"
    matches = glob.glob(str(repo_dir / pattern))
    return matches[0] if matches else None


def main():
    # Get the project root directory
    script_dir = Path(__file__).parent.absolute()
    project_root = script_dir.parent
    repo_dir = project_root / "repo"
    
    print("=" * 100)
    print("Machine Experiment Results Analysis: Single-Optimizer vs Ensemble Mode")
    print("=" * 100)
    print()
    
    if not repo_dir.exists():
        print(f"Error: Repository directory '{repo_dir}' does not exist!")
        return
    
    # Store results by machine
    results_by_machine = defaultdict(list)
    
    # Process each machine
    for machine_num in ['machine1', 'machine2', 'machine3']:
        if machine_num not in MACHINE_EXPERIMENTS:
            continue
        
        for display_name, single_pattern, ensemble_pattern in MACHINE_EXPERIMENTS[machine_num]:
            single_file = find_history_file(repo_dir, single_pattern)
            ensemble_file = find_history_file(repo_dir, ensemble_pattern)
            
            single_tps = None
            single_lat = None
            single_configs = 0
            ensemble_tps = None
            ensemble_lat = None
            ensemble_configs = 0
            
            if single_file:
                single_tps, single_lat, single_qps, single_configs = extract_max_tps(single_file)
            
            if ensemble_file:
                ensemble_tps, ensemble_lat, ensemble_qps, ensemble_configs = extract_max_tps(ensemble_file)
            
            # Calculate improvement
            improvement = None
            if single_tps and ensemble_tps:
                improvement = ((ensemble_tps - single_tps) / single_tps) * 100
            
            results_by_machine[machine_num].append({
                'name': display_name,
                'single_file': os.path.basename(single_file) if single_file else None,
                'ensemble_file': os.path.basename(ensemble_file) if ensemble_file else None,
                'single_tps': single_tps,
                'single_lat': single_lat,
                'single_configs': single_configs,
                'ensemble_tps': ensemble_tps,
                'ensemble_lat': ensemble_lat,
                'ensemble_configs': ensemble_configs,
                'improvement': improvement,
            })
    
    # Print results by machine
    for machine_num in ['machine1', 'machine2', 'machine3']:
        if machine_num not in results_by_machine or not results_by_machine[machine_num]:
            continue
            
        print(f"\n{'=' * 100}")
        print(f"MACHINE {machine_num[-1].upper()}: {', '.join([exp[0] for exp in MACHINE_EXPERIMENTS[machine_num]])}")
        print(f"{'=' * 100}")
        print()
        print(f"{'Workload':<15} {'Single-Opt TPS':>18} {'Ensemble TPS':>18} {'Improvement':>15} {'Status':>15}")
        print("-" * 100)
        
        for result in results_by_machine[machine_num]:
            name = result['name']
            single_tps = result['single_tps']
            ensemble_tps = result['ensemble_tps']
            improvement = result['improvement']
            
            # Format values
            single_str = f"{single_tps:,.2f}" if single_tps else "N/A"
            ensemble_str = f"{ensemble_tps:,.2f}" if ensemble_tps else "N/A"
            
            if improvement is not None:
                improvement_str = f"{improvement:+.2f}%"
                if improvement > 0:
                    status = "✅ Better"
                elif improvement < -1:  # More than 1% worse
                    status = "⚠️  Worse"
                else:
                    status = "≈ Similar"
            else:
                improvement_str = "N/A"
                if single_tps is None and ensemble_tps is None:
                    status = "❌ Missing"
                else:
                    status = "⚠️  Incomplete"
            
            print(f"{name:<15} {single_str:>18} {ensemble_str:>18} {improvement_str:>15} {status:>15}")
            
            # Print latency info if both available
            if result['single_lat'] is not None and result['ensemble_lat'] is not None:
                single_lat_str = f"{result['single_lat']:.2f}ms"
                ensemble_lat_str = f"{result['ensemble_lat']:.2f}ms"
                lat_change = ((result['ensemble_lat'] - result['single_lat']) / result['single_lat']) * 100
                lat_change_str = f"({lat_change:+.1f}%)"
                print(f"  {'└─ Latency:':<13} {single_lat_str:>18} {ensemble_lat_str:>18} {lat_change_str:>15}")
    
    # Overall summary
    print(f"\n{'=' * 100}")
    print("OVERALL SUMMARY")
    print(f"{'=' * 100}")
    print()
    
    all_results = []
    for machine_results in results_by_machine.values():
        all_results.extend(machine_results)
    
    # Filter complete comparisons
    complete = [r for r in all_results if r['improvement'] is not None]
    
    if complete:
        better = [r for r in complete if r['improvement'] > 0]
        worse = [r for r in complete if r['improvement'] < -1]
        similar = [r for r in complete if -1 <= r['improvement'] <= 0]
        
        print(f"Total workloads compared: {len(complete)}")
        print(f"  ✅ Ensemble better:     {len(better):2d} ({len(better)/len(complete)*100:.1f}%)")
        print(f"  ⚠️  Ensemble worse:      {len(worse):2d} ({len(worse)/len(complete)*100:.1f}%)")
        print(f"  ≈  Similar performance: {len(similar):2d} ({len(similar)/len(complete)*100:.1f}%)")
        print()
        
        if better:
            avg_improvement = sum(r['improvement'] for r in better) / len(better)
            print(f"Average improvement when ensemble is better: {avg_improvement:+.2f}%")
            
            best = max(better, key=lambda r: r['improvement'])
            print(f"  Best improvement: {best['name']} ({best['improvement']:+.2f}%)")
            print(f"    Single: {best['single_tps']:,.2f} TPS → Ensemble: {best['ensemble_tps']:,.2f} TPS")
        
        if worse:
            print()
            avg_degradation = sum(r['improvement'] for r in worse) / len(worse)
            print(f"Average degradation when ensemble is worse: {avg_degradation:.2f}%")
            
            worst = min(worse, key=lambda r: r['improvement'])
            print(f"  Worst degradation: {worst['name']} ({worst['improvement']:+.2f}%)")
            print(f"    Single: {worst['single_tps']:,.2f} TPS → Ensemble: {worst['ensemble_tps']:,.2f} TPS")
        
        print()
        print("-" * 100)
        
    else:
        print("⚠️  No complete comparisons available.")
        print("\nAvailable data:")
        for result in all_results:
            if result['single_tps'] or result['ensemble_tps']:
                status = []
                if result['single_tps']:
                    status.append(f"Single: {result['single_tps']:,.2f} TPS")
                if result['ensemble_tps']:
                    status.append(f"Ensemble: {result['ensemble_tps']:,.2f} TPS")
                print(f"  {result['name']}: {', '.join(status)}")
    
    print()


if __name__ == "__main__":
    main()
