#!/usr/bin/env python3
"""
Analyze experiment results from run_experiments_machine*.sh scripts.
Compare performance across all optimizer variants (SMAC, DDPG, GA), ensemble, and augment modes.
"""

import json
import os
import glob
from pathlib import Path
from collections import defaultdict

# Define experiments run by each machine based on the runner scripts
# Format: (display_name, workload_base)
MACHINE_EXPERIMENTS = {
    'machine1': [
        ('Twitter', 'oltpbench_twitter'),
        ('TPC-C', 'oltpbench_tpcc'),
        ('YCSB', 'oltpbench_ycsb'),
        ('Wikipedia', 'oltpbench_wikipedia'),
    ],
    'machine2': [
        ('TATP', 'oltpbench_tatp'),
        ('Voter', 'oltpbench_voter'),
        ('TPC-H', 'tpch'),
        ('JOB', 'job'),
    ],
    'machine3': [
        ('Sysbench-RW', 'sbrw'),
        ('Sysbench-WO', 'sbwrite'),
        ('Sysbench-RO', 'sbread'),
    ],
}

# Define all experiment types
EXPERIMENT_TYPES = {
    'single_smac': {'display': 'SMAC', 'pattern': '_smac'},
    'single_ddpg': {'display': 'DDPG', 'pattern': '_ddpg'},
    'single_ga': {'display': 'GA', 'pattern': '_ga'},
    'ensemble': {'display': 'Ensemble', 'pattern': '_ensemble'},
    'augment_smac': {'display': 'Augment+SMAC', 'pattern': '_augment_smac'},
    'augment_ddpg': {'display': 'Augment+DDPG', 'pattern': '_augment_ddpg'},
    'augment_ga': {'display': 'Augment+GA', 'pattern': '_augment_ga'},
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
    
    print("=" * 150)
    print("Machine Experiment Results Analysis: All Optimizers Comparison (SMAC, DDPG, GA, Ensemble, Augment)")
    print("=" * 150)
    print()
    
    if not repo_dir.exists():
        print(f"Error: Repository directory '{repo_dir}' does not exist!")
        return
    
    # Store results by machine and workload
    results_by_machine = defaultdict(list)
    
    # Process each machine
    for machine_num in ['machine1', 'machine2', 'machine3']:
        if machine_num not in MACHINE_EXPERIMENTS:
            continue
        
        for display_name, workload_base in MACHINE_EXPERIMENTS[machine_num]:
            workload_results = {'name': display_name, 'workload_base': workload_base}
            
            # Process each experiment type
            for exp_type, exp_info in EXPERIMENT_TYPES.items():
                pattern = workload_base + exp_info['pattern']
                file_path = find_history_file(repo_dir, pattern)
                
                if file_path:
                    tps, lat, qps, total_configs = extract_max_tps(file_path)
                    workload_results[exp_type] = {
                        'tps': tps,
                        'latency': lat,
                        'qps': qps,
                        'total_configs': total_configs,
                        'file': os.path.basename(file_path),
                        'exists': True
                    }
                else:
                    workload_results[exp_type] = {
                        'tps': None,
                        'latency': None,
                        'qps': None,
                        'total_configs': 0,
                        'file': None,
                        'exists': False
                    }
            
            results_by_machine[machine_num].append(workload_results)
    
    # Print detailed results by machine
    for machine_num in ['machine1', 'machine2', 'machine3']:
        if machine_num not in results_by_machine or not results_by_machine[machine_num]:
            continue
        
        print(f"\n{'=' * 150}")
        print(f"MACHINE {machine_num[-1].upper()}: {', '.join([exp['name'] for exp in results_by_machine[machine_num]])}")
        print(f"{'=' * 150}")
        
        for result in results_by_machine[machine_num]:
            workload_name = result['name']
            print(f"\n📊 {workload_name}")
            print("-" * 150)
            
            # Print header
            header = f"{'Type':<20}"
            for exp_type, exp_info in EXPERIMENT_TYPES.items():
                header += f"{exp_info['display']:>18}"
            header += f"{'Best':>18}"
            print(header)
            print("-" * 150)
            
            # Get TPS values for all types
            tps_values = {}
            for exp_type, exp_info in EXPERIMENT_TYPES.items():
                tps_values[exp_type] = result[exp_type]['tps']
            
            # Find best TPS
            best_tps = max([v for v in tps_values.values() if v is not None], default=None)
            
            # Print TPS row
            row = f"{'TPS':<20}"
            for exp_type, exp_info in EXPERIMENT_TYPES.items():
                tps = tps_values[exp_type]
                if tps is not None:
                    if tps == best_tps:
                        row += f"{tps:>17,.2f}★"
                    else:
                        row += f"{tps:>18,.2f}"
                else:
                    row += f"{'N/A':>18}"
            
            best_type = None
            if best_tps:
                best_type = [k for k, v in tps_values.items() if v == best_tps][0]
                best_display = EXPERIMENT_TYPES[best_type]['display']
                row += f"{best_display:>18}"
            else:
                row += f"{'N/A':>18}"
            
            print(row)
            
            # Print latency row
            row = f"{'Latency (ms)':<20}"
            for exp_type, exp_info in EXPERIMENT_TYPES.items():
                lat = result[exp_type]['latency']
                if lat is not None:
                    row += f"{lat:>18,.2f}"
                else:
                    row += f"{'N/A':>18}"
            row += " " * 18  # Skip best column
            print(row)
            
            # Print config count row
            row = f"{'Configs':<20}"
            for exp_type, exp_info in EXPERIMENT_TYPES.items():
                count = result[exp_type]['total_configs']
                row += f"{count:>18d}"
            row += " " * 18  # Skip best column
            print(row)
            
            # Print file status
            row = f"{'Status':<20}"
            for exp_type, exp_info in EXPERIMENT_TYPES.items():
                exists = result[exp_type]['exists']
                if exists:
                    row += f"{'✅':>18}"
                else:
                    row += f"{'❌':>18}"
            row += " " * 18  # Skip best column
            print(row)
    
    # Overall summary
    print(f"\n{'=' * 150}")
    print("OVERALL SUMMARY")
    print(f"{'=' * 150}")
    print()
    
    # Collect all results
    all_results = []
    for machine_results in results_by_machine.values():
        all_results.extend(machine_results)
    
    # Calculate statistics for each experiment type
    print("Win Counts (Best TPS per workload):")
    print("-" * 150)
    
    wins = defaultdict(int)
    for result in all_results:
        best_tps = None
        best_type = None
        
        for exp_type in EXPERIMENT_TYPES.keys():
            tps = result[exp_type]['tps']
            if tps is not None:
                if best_tps is None or tps > best_tps:
                    best_tps = tps
                    best_type = exp_type
        
        if best_type:
            wins[best_type] += 1
    
    # Print win counts
    for exp_type, exp_info in EXPERIMENT_TYPES.items():
        count = wins[exp_type]
        percentage = (count / len(all_results)) * 100 if all_results else 0
        bar = "█" * int(percentage / 2)
        print(f"{exp_info['display']:<20} {count:>3d} wins ({percentage:>5.1f}%) {bar}")
    
    print()
    print("-" * 150)
    
    # Calculate average TPS by type
    print("\nAverage TPS by Experiment Type:")
    print("-" * 150)
    
    avg_tps_by_type = defaultdict(list)
    for result in all_results:
        for exp_type in EXPERIMENT_TYPES.keys():
            tps = result[exp_type]['tps']
            if tps is not None:
                avg_tps_by_type[exp_type].append(tps)
    
    for exp_type, exp_info in EXPERIMENT_TYPES.items():
        tps_list = avg_tps_by_type[exp_type]
        if tps_list:
            avg_tps = sum(tps_list) / len(tps_list)
            print(f"{exp_info['display']:<20} {avg_tps:>18,.2f} TPS (from {len(tps_list)} workloads)")
        else:
            print(f"{exp_info['display']:<20} {'N/A':>18}")
    
    print()
    print("-" * 150)
    
    # Count missing data
    print("\nData Availability:")
    print("-" * 150)
    
    for exp_type, exp_info in EXPERIMENT_TYPES.items():
        total_workloads = len(all_results)
        existing = sum(1 for r in all_results if r[exp_type]['exists'])
        missing = total_workloads - existing
        percentage = (existing / total_workloads) * 100 if total_workloads > 0 else 0
        print(f"{exp_info['display']:<20} {existing:>3d}/{total_workloads} available ({percentage:>5.1f}%)")
    
    print()
    print("=" * 150)
    print("Analysis complete!")
    print("=" * 150)
    print()


if __name__ == "__main__":
    main()
