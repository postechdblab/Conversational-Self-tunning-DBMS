#!/usr/bin/env python3
"""
Verification script for GP training changes in ensemble mode.

This script checks that:
1. Only the best optimizer result per iteration is marked as real
2. The other 3 results are marked as synthetic
3. GP training uses only the real observations
"""

import re
import sys


def analyze_log_file(log_file_path):
    """Analyze the log file to verify GP training behavior."""
    
    with open(log_file_path, 'r') as f:
        log_content = f.read()
    
    # Find all ensemble iterations
    ensemble_iterations = []
    current_iteration = {}
    
    for line in log_content.split('\n'):
        # Check for ensemble evaluation completion
        if '[Ensemble] Completed evaluation' in line:
            match = re.search(r'from (\w+), objs=\[([\d.]+)', line)
            if match:
                optimizer = match.group(1)
                obj_value = float(match.group(2))
                if 'evaluations' not in current_iteration:
                    current_iteration['evaluations'] = []
                current_iteration['evaluations'].append((optimizer, obj_value))
        
        # Check for best result selection
        elif '[Ensemble] Best result from' in line:
            match = re.search(r'from (\w+) with objective value ([\d.]+)', line)
            if match:
                current_iteration['best_optimizer'] = match.group(1)
                current_iteration['best_value'] = float(match.group(2))
        
        # Check for real/synthetic marking
        elif '[Ensemble] Adding' in line and 'result as' in line:
            match = re.search(r'Adding (\w+) result as (\w+) \(obj=([\d.]+)', line)
            if match:
                optimizer = match.group(1)
                result_type = match.group(2)
                obj_value = float(match.group(3))
                if 'markings' not in current_iteration:
                    current_iteration['markings'] = []
                current_iteration['markings'].append((optimizer, result_type, obj_value))
        
        # Check for GP training data size
        elif '[BO] Filtered' in line and 'real samples from' in line:
            match = re.search(r'Filtered (\d+) real samples from (\d+) total', line)
            if match:
                real_samples = int(match.group(1))
                total_samples = int(match.group(2))
                if 'gp_training' not in current_iteration:
                    current_iteration['gp_training'] = []
                current_iteration['gp_training'].append((real_samples, total_samples))
        
        # Check for iteration completion
        elif '[Ensemble] All 4 evaluations completed' in line:
            if current_iteration:
                ensemble_iterations.append(current_iteration.copy())
                current_iteration = {}
    
    return ensemble_iterations


def verify_iterations(iterations):
    """Verify that the GP training logic is correct."""
    
    print("=" * 80)
    print("GP TRAINING VERIFICATION REPORT")
    print("=" * 80)
    print()
    
    all_passed = True
    
    for i, iteration in enumerate(iterations, 1):
        print(f"Iteration {i}:")
        print("-" * 40)
        
        # Verify evaluations
        if 'evaluations' in iteration:
            print(f"  Evaluations: {len(iteration['evaluations'])} configurations")
            for optimizer, obj_value in iteration['evaluations']:
                print(f"    - {optimizer}: obj={obj_value}")
        
        # Verify best selection
        if 'best_optimizer' in iteration:
            print(f"  Best Optimizer: {iteration['best_optimizer']} (obj={iteration['best_value']})")
            
            # Check if best has minimum value
            if 'evaluations' in iteration:
                min_value = min(obj for _, obj in iteration['evaluations'])
                if abs(min_value - iteration['best_value']) > 1e-6:
                    print(f"    ❌ ERROR: Best value {iteration['best_value']} != minimum {min_value}")
                    all_passed = False
                else:
                    print(f"    ✓ Correctly identified best result")
        
        # Verify markings
        if 'markings' in iteration:
            print(f"  Markings:")
            real_count = 0
            synthetic_count = 0
            for optimizer, result_type, obj_value in iteration['markings']:
                symbol = "✓" if result_type == "REAL" else "○"
                print(f"    {symbol} {optimizer}: {result_type} (obj={obj_value})")
                if result_type == "REAL":
                    real_count += 1
                    if 'best_optimizer' in iteration and optimizer != iteration['best_optimizer']:
                        print(f"      ❌ ERROR: {optimizer} marked as REAL but not the best!")
                        all_passed = False
                elif result_type == "SYNTHETIC":
                    synthetic_count += 1
            
            # Verify counts
            if real_count != 1:
                print(f"    ❌ ERROR: Expected 1 REAL observation, got {real_count}")
                all_passed = False
            if synthetic_count != 3:
                print(f"    ❌ ERROR: Expected 3 SYNTHETIC observations, got {synthetic_count}")
                all_passed = False
            
            if real_count == 1 and synthetic_count == 3:
                print(f"    ✓ Correct marking: 1 REAL, 3 SYNTHETIC")
        
        # Verify GP training
        if 'gp_training' in iteration:
            for real_samples, total_samples in iteration['gp_training']:
                print(f"  GP Training: {real_samples} real / {total_samples} total samples")
                expected_real = i  # Should have i real samples after i iterations
                if real_samples != expected_real:
                    print(f"    ⚠ Warning: Expected ~{expected_real} real samples after {i} iterations")
                else:
                    print(f"    ✓ Correct number of real samples")
        
        print()
    
    print("=" * 80)
    if all_passed:
        print("✓ ALL CHECKS PASSED")
        print("GP training is correctly using only the best optimizer result per iteration.")
    else:
        print("❌ SOME CHECKS FAILED")
        print("Please review the errors above.")
    print("=" * 80)
    
    return all_passed


def main():
    if len(sys.argv) < 2:
        print("Usage: python verify_gp_training.py <log_file_path>")
        print("Example: python verify_gp_training.py logs/machine1_experiments.log")
        sys.exit(1)
    
    log_file = sys.argv[1]
    
    try:
        iterations = analyze_log_file(log_file)
        
        if not iterations:
            print("No ensemble iterations found in log file.")
            print("Make sure you're running with ensemble_mode=True")
            sys.exit(1)
        
        success = verify_iterations(iterations)
        sys.exit(0 if success else 1)
        
    except FileNotFoundError:
        print(f"Error: Log file '{log_file}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error analyzing log file: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

