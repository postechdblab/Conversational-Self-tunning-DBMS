#!/usr/bin/env python3
"""
Monitor experiment progress in real-time.
Detects if experiments are stuck and provides progress estimates.
"""

import os
import json
import time
import sys
from pathlib import Path
from datetime import datetime, timedelta


def get_experiment_status(json_file, experiment_name):
    """
    Get status of an experiment from its history JSON file.
    """
    try:
        # Get file modification time
        mtime = os.path.getmtime(json_file)
        last_modified = datetime.fromtimestamp(mtime)
        time_since_update = datetime.now() - last_modified
        
        # Read the JSON file
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        # Count configurations
        if isinstance(data, dict) and 'data' in data:
            configs = data['data']
        elif isinstance(data, list):
            configs = data
        else:
            return None
        
        num_configs = len(configs)
        
        # Estimate completion based on max_runs (usually 200)
        max_runs = 200  # Default
        progress_pct = (num_configs / max_runs) * 100 if num_configs < max_runs else 100
        
        return {
            'name': experiment_name,
            'file': os.path.basename(json_file),
            'configs': num_configs,
            'max_runs': max_runs,
            'progress_pct': progress_pct,
            'last_update': last_modified,
            'time_since_update': time_since_update,
            'is_stuck': time_since_update.total_seconds() > 1800,  # 30 minutes
            'is_complete': num_configs >= max_runs
        }
    except Exception as e:
        return None


def format_timedelta(td):
    """Format timedelta to human readable string."""
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    
    if hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"


def main():
    # Get the project root directory
    script_dir = Path(__file__).parent.absolute()
    project_root = script_dir.parent
    repo_dir = project_root / "repo"
    
    if not repo_dir.exists():
        print(f"Error: Repository directory '{repo_dir}' does not exist!")
        return
    
    # Define experiments from machine runners
    experiments = [
        # Machine 1
        ('Twitter (Single)', 'history_oltpbench_twitter_smac.json'),
        ('Twitter (Ensemble)', 'history_oltpbench_twitter_ensemble.json'),
        ('TPC-C (Single)', 'history_oltpbench_tpcc.json'),
        ('TPC-C (Ensemble)', 'history_oltpbench_tpcc_ensemble.json'),
        ('YCSB (Single)', 'history_oltpbench_ycsb.json'),
        ('YCSB (Ensemble)', 'history_oltpbench_ycsb_ensemble.json'),
        ('Wikipedia (Single)', 'history_oltpbench_wikipedia.json'),
        ('Wikipedia (Ensemble)', 'history_oltpbench_wikipedia_ensemble.json'),
        # Machine 2
        ('TATP (Single)', 'history_oltpbench_tatp.json'),
        ('TATP (Ensemble)', 'history_oltpbench_tatp_ensemble.json'),
        ('Voter (Single)', 'history_oltpbench_voter.json'),
        ('Voter (Ensemble)', 'history_oltpbench_voter_ensemble.json'),
        ('TPC-H (Single)', 'history_tpch.json'),
        ('TPC-H (Ensemble)', 'history_tpch_ensemble.json'),
        ('JOB (Single)', 'history_job.json'),
        ('JOB (Ensemble)', 'history_job_ensemble.json'),
        # Machine 3
        ('Sysbench-RW (Single)', 'history_sysbench_rw.json'),
        ('Sysbench-RW (Ensemble)', 'history_sysbench_rw_ensemble.json'),
        ('Sysbench-WO (Single)', 'history_sysbench_wo.json'),
        ('Sysbench-WO (Ensemble)', 'history_sysbench_wo_ensemble.json'),
        ('Sysbench-RO (Single)', 'history_sysbench_ro.json'),
        ('Sysbench-RO (Ensemble)', 'history_sysbench_ro_ensemble.json'),
    ]
    
    # Check if running in watch mode
    watch_mode = '--watch' in sys.argv
    interval = 60  # seconds
    
    while True:
        # Clear screen in watch mode
        if watch_mode:
            os.system('clear' if os.name == 'posix' else 'cls')
        
        print("=" * 100)
        print(f"Experiment Progress Monitor - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 100)
        print()
        
        # Get status for all experiments
        statuses = []
        for exp_name, filename in experiments:
            file_path = repo_dir / filename
            if file_path.exists():
                status = get_experiment_status(file_path, exp_name)
                if status:
                    statuses.append(status)
        
        if not statuses:
            print("No experiments found!")
            return
        
        # Print active experiments
        print(f"{'Experiment':<30} {'Progress':>12} {'Configs':>10} {'Last Update':>18} {'Status':>15}")
        print("-" * 100)
        
        active = []
        completed = []
        stuck = []
        
        for status in sorted(statuses, key=lambda x: (-x['is_complete'], -x['configs'])):
            name = status['name']
            progress = f"{status['progress_pct']:.1f}%"
            configs = f"{status['configs']}/{status['max_runs']}"
            time_since = format_timedelta(status['time_since_update'])
            
            if status['is_complete']:
                status_str = "✅ Complete"
                completed.append(status)
            elif status['is_stuck']:
                status_str = "⚠️  STUCK"
                stuck.append(status)
            else:
                status_str = "🔄 Running"
                active.append(status)
            
            print(f"{name:<30} {progress:>12} {configs:>10} {time_since:>18} {status_str:>15}")
        
        # Summary
        print()
        print("=" * 100)
        print(f"Summary: {len(completed)} complete, {len(active)} running, {len(stuck)} stuck, "
              f"{len(experiments) - len(statuses)} not started")
        print("=" * 100)
        
        if stuck:
            print()
            print("⚠️  STUCK EXPERIMENTS (no update in >30 min):")
            for status in stuck:
                print(f"   - {status['name']}: Last update {format_timedelta(status['time_since_update'])} ago")
                print(f"     File: {status['file']}")
        
        if active:
            print()
            # Estimate completion time for active experiments
            print("📊 Active Experiments:")
            for status in active:
                if status['configs'] > 10:  # Need some data to estimate
                    # Simple linear extrapolation
                    remaining = status['max_runs'] - status['configs']
                    if remaining > 0:
                        avg_time_per_config = status['time_since_update'].total_seconds() / max(status['configs'], 1)
                        est_remaining_time = timedelta(seconds=avg_time_per_config * remaining)
                        print(f"   - {status['name']}: ~{format_timedelta(est_remaining_time)} remaining")
        
        print()
        
        if not watch_mode:
            break
        
        print(f"Refreshing in {interval}s... (Ctrl+C to stop)")
        try:
            time.sleep(interval)
        except KeyboardInterrupt:
            print("\n\nMonitoring stopped.")
            break


if __name__ == "__main__":
    if '--help' in sys.argv or '-h' in sys.argv:
        print("Usage: python monitor_progress.py [--watch]")
        print()
        print("Options:")
        print("  --watch    Continuously monitor and refresh every 60 seconds")
        print("  --help     Show this help message")
        sys.exit(0)
    
    main()

