#!/usr/bin/env python3
"""
Script to update baseline configuration with actual test data from a specified date range and branch.
The script processes all test results within the date range, removes min/max values for each metric,
and calculates the average of remaining values as baseline data.
Usage: python update_baseline.py --start YYYY-MM-DD --end YYYY-MM-DD --branch BRANCH_NAME [--output OUTPUT_FILE]
"""

import pandas as pd
import json
from datetime import datetime, date
import sys
import os
import argparse
import logging

# 配置日志级别 - 减少详细输出
logging.getLogger().setLevel(logging.WARNING)  # 只显示警告和错误
logging.getLogger('data_loader').setLevel(logging.WARNING)

# Add the current directory to path to import data_loader
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from data_loader import loader

def load_data_by_date_range_and_branch(start_date, end_date, branch_name):
    """Load and process data for the specified date range and branch.
    
    Args:
        start_date (date): The start date to filter data
        end_date (date): The end date to filter data (inclusive)
        branch_name (str): The branch name to filter data
    
    Returns:
        pandas.DataFrame: Filtered data for the specified date range and branch
    """
    # Get data from the data loader
    df = loader.get_data()
    
    if df.empty:
        print("No data available from data loader")
        return pd.DataFrame()
    
    print(f"Total records loaded: {len(df)}")
    
    # Filter for specified date range and branch
    filtered_data = df[
        (df['datetime'].dt.date >= start_date) & 
        (df['datetime'].dt.date <= end_date) &
        (df['branch'] == branch_name)
    ]
    
    print(f"Loaded {len(filtered_data)} records from {start_date} to {end_date} for {branch_name} branch")
    return filtered_data

def create_config_key(row):
    """Create configuration key in format scale_cluster_phase_worker"""
    return f"{row['scale']}_{row['cluster']}_{row['phase']}_{row['worker']}"

def validate_data_completeness(df):
    """Validate that all configurations have complete data for all metrics.
    
    Args:
        df (pandas.DataFrame): The filtered data to validate
    
    Returns:
        tuple: (is_valid, error_messages)
    """
    error_messages = []
    
    # Get unique configurations and query types
    configurations = df.groupby(['scale', 'cluster', 'phase', 'worker']).groups.keys()
    all_query_types = df['query_type'].dropna().unique()
    
    print(f"Validating data completeness...")
    print(f"Found {len(configurations)} configurations and {len(all_query_types)} query types")
    
    # Check each configuration
    for config_key in configurations:
        scale, cluster, phase, worker = config_key
        config_name = f"{scale}_{cluster}_{phase}_{worker}"
        
        # Get data for this configuration
        config_data = df[
            (df['scale'] == scale) & 
            (df['cluster'] == cluster) & 
            (df['phase'] == phase) & 
            (df['worker'] == worker)
        ]
        
        # Check import_speed data
        import_speed_data = config_data[config_data['import_speed'].notna()]
        if import_speed_data.empty:
            error_messages.append(f"Configuration {config_name}: Missing import_speed data")
        
        # Check query type data
        config_query_types = config_data['query_type'].dropna().unique()
        missing_query_types = set(all_query_types) - set(config_query_types)
        
        if missing_query_types:
            for missing_type in sorted(missing_query_types):
                error_messages.append(f"Configuration {config_name}: Missing query_type '{missing_type}' data")
        
        # Check for query types with missing mean_ms values
        for query_type in config_query_types:
            query_data = config_data[
                (config_data['query_type'] == query_type) & 
                (config_data['mean_ms'].notna())
            ]
            if query_data.empty:
                error_messages.append(f"Configuration {config_name}: Query type '{query_type}' has no valid mean_ms values")
    
    # Additional validation: Check if we have sufficient data points for trimmed mean
    insufficient_data = []
    for config_key in configurations:
        scale, cluster, phase, worker = config_key
        config_name = f"{scale}_{cluster}_{phase}_{worker}"
        
        config_data = df[
            (df['scale'] == scale) & 
            (df['cluster'] == cluster) & 
            (df['phase'] == phase) & 
            (df['worker'] == worker)
        ]
        
        # Check import_speed data points
        import_speed_count = len(config_data[config_data['import_speed'].notna()])
        if import_speed_count == 0:
            insufficient_data.append(f"Configuration {config_name}: No import_speed data points")
        elif import_speed_count == 1:
            print(f"Warning: Configuration {config_name}: Only 1 import_speed data point (no trimming possible)")
        
        # Check query type data points
        for query_type in config_data['query_type'].dropna().unique():
            query_count = len(config_data[
                (config_data['query_type'] == query_type) & 
                (config_data['mean_ms'].notna())
            ])
            if query_count == 0:
                insufficient_data.append(f"Configuration {config_name}: No data points for query_type '{query_type}'")
            elif query_count == 1:
                print(f"Warning: Configuration {config_name}: Only 1 data point for query_type '{query_type}' (no trimming possible)")
    
    error_messages.extend(insufficient_data)
    
    return len(error_messages) == 0, error_messages

def calculate_trimmed_mean(values, metric_name=None, config_name=None, verbose=False):
    """Calculate mean after removing min and max values.
    
    Args:
        values: List or Series of numeric values
        metric_name: Name of the metric for debugging
        config_name: Name of the configuration for debugging
        verbose: Whether to print detailed calculation steps
    
    Returns:
        tuple: (trimmed_mean, calculation_details)
    """
    values_list = list(values) if hasattr(values, '__iter__') else [values]
    
    if len(values_list) <= 2:
        # If we have 2 or fewer values, return the mean without trimming
        mean_val = sum(values_list) / len(values_list) if len(values_list) > 0 else 0.0
        details = {
            'original_values': values_list,
            'count': len(values_list),
            'method': 'simple_mean' if len(values_list) <= 2 else 'no_data',
            'removed_values': [],
            'used_values': values_list,
            'result': mean_val
        }
        
        if verbose and metric_name and config_name:
            print(f"    {config_name}.{metric_name}: {values_list} -> Simple mean (≤2 values): {mean_val:.4f}")
        
        return mean_val, details
    
    # Remove min and max values
    values_sorted = sorted(values_list)
    min_val = values_sorted[0]
    max_val = values_sorted[-1]
    trimmed_values = values_sorted[1:-1]  # Remove first (min) and last (max)
    
    result = sum(trimmed_values) / len(trimmed_values) if trimmed_values else 0.0
    
    details = {
        'original_values': values_list,
        'sorted_values': values_sorted,
        'count': len(values_list),
        'method': 'trimmed_mean',
        'removed_min': min_val,
        'removed_max': max_val,
        'removed_values': [min_val, max_val],
        'used_values': trimmed_values,
        'result': result
    }
    
    if verbose and metric_name and config_name:
        print(f"    {config_name}.{metric_name}:")
        print(f"      Original: {values_list}")
        print(f"      Sorted: {values_sorted}")
        print(f"      Removed min: {min_val}, max: {max_val}")
        print(f"      Used for calculation: {trimmed_values}")
        print(f"      Trimmed mean: {result:.4f}")
    
    return result, details

def process_baseline_data(df, verbose=False):
    """Process the data and create baseline configuration using trimmed mean."""
    baselines = {}
    calculation_logs = {}
    
    # Group by configuration (scale, cluster, phase, worker)
    for config_key, config_group in df.groupby(['scale', 'cluster', 'phase', 'worker']):
        scale, cluster, phase, worker = config_key
        key = f"{scale}_{cluster}_{phase}_{worker}"
        
        print(f"Processing configuration: {key}")
        
        # Initialize baseline for this configuration
        baseline = {}
        calculation_logs[key] = {}
        
        # Get import_speed values and calculate trimmed mean
        import_speed_data = config_group[config_group['import_speed'].notna()]['import_speed']
        if not import_speed_data.empty:
            baseline['import_speed'], calc_details = calculate_trimmed_mean(
                import_speed_data, 'import_speed', key, verbose
            )
            calculation_logs[key]['import_speed'] = calc_details
            print(f"  import_speed: {len(import_speed_data)} values -> {baseline['import_speed']:.2f}")
        else:
            baseline['import_speed'] = 300  # fallback
            calculation_logs[key]['import_speed'] = {'method': 'fallback', 'result': 300}
        
        # Process query types and their mean_ms values
        query_metrics = {}
        for _, row in config_group.iterrows():
            query_type = row['query_type']
            mean_ms = row['mean_ms']
            
            if pd.notna(mean_ms) and pd.notna(query_type):
                # Convert query type to use hyphens consistently (matching app.py logic)
                import re
                metric_key = re.sub(r'[^a-zA-Z0-9_-]', '-', str(query_type)).lower().replace('_', '-')
                
                if metric_key not in query_metrics:
                    query_metrics[metric_key] = []
                query_metrics[metric_key].append(float(mean_ms))
        
        # Calculate trimmed mean for each query metric
        for metric_key, values in query_metrics.items():
            baseline[metric_key], calc_details = calculate_trimmed_mean(
                values, metric_key, key, verbose
            )
            calculation_logs[key][metric_key] = calc_details
            print(f"  {metric_key}: {len(values)} values -> {baseline[metric_key]:.2f}")
        
        baselines[key] = baseline
    
    return baselines, calculation_logs

def update_baseline_config(new_baselines, output_file=None):
    """Update the baseline configuration file with new data.
    
    Args:
        new_baselines (dict): New baseline data to update
        output_file (str, optional): Output file path. If None, uses default location.
    
    Returns:
        dict: Updated configuration
    """
    if output_file is None:
        baseline_file = './baseline_config.json'
    else:
        baseline_file = output_file
    
    # Load existing configuration
    try:
        with open(baseline_file, 'r') as f:
            existing_config = json.load(f)
    except FileNotFoundError:
        print(f"Baseline file {baseline_file} not found, creating new one")
        existing_config = {}
    
    # Update with new baselines
    updated_count = 0
    for config_key, baseline_data in new_baselines.items():
        if config_key in existing_config:
            # Update existing configuration
            for metric, value in baseline_data.items():
                if metric in existing_config[config_key]:
                    old_value = existing_config[config_key][metric]
                    existing_config[config_key][metric] = value
                    print(f"Updated {config_key}.{metric}: {old_value} -> {value}")
                    updated_count += 1
                else:
                    existing_config[config_key][metric] = value
                    print(f"Added {config_key}.{metric}: {value}")
                    updated_count += 1
        else:
            # Add new configuration
            existing_config[config_key] = baseline_data
            print(f"Added new configuration: {config_key}")
            updated_count += len(baseline_data)
    
    # Create backup of original file
    if os.path.exists(baseline_file):
        backup_file = baseline_file + '.backup'
        with open(backup_file, 'w') as f:
            json.dump(json.load(open(baseline_file, 'r')), f, indent=2)
        print(f"Created backup: {backup_file}")
    
    # Write updated configuration
    with open(baseline_file, 'w') as f:
        json.dump(existing_config, f, indent=2)
    
    print(f"Updated baseline configuration with {updated_count} values")
    return existing_config

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Update baseline configuration with test data from specified date range and branch',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python update_baseline.py --start 2025-06-01 --end 2025-06-03 --branch master
  python update_baseline.py --start 2025-06-05 --end 2025-06-10 --branch feature-branch --output custom_baseline.json
  python update_baseline.py -s 2025-06-01 -e 2025-06-03 -b master --list-available
        """
    )
    
    parser.add_argument(
        '--start', '-s',
        type=str,
        required=True,
        help='Start date in YYYY-MM-DD format (e.g., 2025-06-01)'
    )
    
    parser.add_argument(
        '--end', '-e',
        type=str,
        required=True,
        help='End date in YYYY-MM-DD format (e.g., 2025-06-03)'
    )
    
    parser.add_argument(
        '--branch', '-b',
        type=str,
        required=True,
        help='Branch name to filter data (e.g., master, feature-branch)'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        help='Output baseline configuration file path (default: baseline_config.json)'
    )
    
    parser.add_argument(
        '--list-available',
        action='store_true',
        help='List available dates and branches in the data'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be updated without making changes'
    )
    
    parser.add_argument(
        '--verbose-calc',
        action='store_true',
        help='Show detailed calculation steps for trimmed mean'
    )
    
    parser.add_argument(
        '--export-calc-log',
        type=str,
        help='Export detailed calculation log to JSON file'
    )
    
    parser.add_argument(
        '--skip-validation',
        action='store_true',
        help='Skip data completeness validation (use with caution)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output (show data loading progress)'
    )
    
    return parser.parse_args()

def list_available_data():
    """List available dates and branches in the data."""
    print("Loading data to check available dates and branches...")
    df = loader.get_data()
    
    if df.empty:
        print("No data available from data loader")
        return
    
    print(f"Total records: {len(df)}")
    print("\nAvailable dates:")
    dates = sorted(df['datetime'].dt.date.unique())
    for d in dates:
        print(f"  {d}")
    
    print("\nAvailable branches:")
    branches = sorted(df['branch'].unique())
    for branch in branches:
        print(f"  {branch}")
    
    print("\nDate-Branch combinations:")
    combinations = df.groupby([df['datetime'].dt.date, 'branch']).size().reset_index(name='count')
    for _, row in combinations.iterrows():
        date_val = row.iloc[0]  # Use iloc for positional access
        branch_val = row['branch']
        count_val = row['count']
        print(f"  {date_val} - {branch_val}: {count_val} records")

def main():
    """Main function to update baseline configuration."""
    args = parse_arguments()
    
    # 如果用户指定了详细输出，则启用详细日志
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        print("Verbose mode enabled - showing data loading progress...")
    
    # Validate and parse dates
    try:
        start_date = datetime.strptime(args.start, '%Y-%m-%d').date()
        end_date = datetime.strptime(args.end, '%Y-%m-%d').date()
    except ValueError as e:
        print(f"Error: Invalid date format. Use YYYY-MM-DD format. {e}")
        sys.exit(1)
    
    # Validate date range
    if start_date > end_date:
        print("Error: Start date must be before or equal to end date.")
        sys.exit(1)
    
    # List available data if requested
    if args.list_available:
        list_available_data()
        return
    
    print(f"Starting baseline configuration update for {start_date} to {end_date} on '{args.branch}' branch...")
    print("Using trimmed mean (removing min/max values) for each metric...")
    
    # Load data for specified date range and branch
    df = load_data_by_date_range_and_branch(start_date, end_date, args.branch)
    
    if df.empty:
        print(f"No data found for {start_date} to {end_date} on {args.branch} branch!")
        print("Use --list-available to see available dates and branches.")
        return
    
    # Show date distribution
    print(f"\nData distribution by date:")
    date_counts = df['datetime'].dt.date.value_counts().sort_index()
    for d, count in date_counts.items():
        print(f"  {d}: {count} records")
    
    # Show data summary
    print(f"\nData summary:")
    print(f"Total records: {len(df)}")
    print(f"Date range: {df['datetime'].dt.date.min()} to {df['datetime'].dt.date.max()}")
    print(f"Configurations available: {df.groupby(['scale', 'cluster', 'phase', 'worker']).ngroups}")
    print(f"Query types available: {df['query_type'].nunique()}")
    print(f"Query types: {sorted(df['query_type'].unique())}")
    
    # Validate data completeness
    if not args.skip_validation:
        print(f"\n" + "="*50)
        print("VALIDATING DATA COMPLETENESS")
        print("="*50)
        
        is_valid, error_messages = validate_data_completeness(df)
        
        if not is_valid:
            print(f"\n❌ DATA VALIDATION FAILED!")
            print(f"Found {len(error_messages)} issues:")
            print("-" * 40)
            
            for i, error in enumerate(error_messages, 1):
                print(f"{i}. {error}")
            
            print("-" * 40)
            print("Please check the data source and ensure all configurations have complete data.")
            print("Use --skip-validation flag to bypass this check (not recommended).")
            print("Execution terminated to prevent incomplete baseline generation.")
            sys.exit(1)
        
        print("✅ Data validation passed - all configurations have complete data")
    else:
        print("\n⚠️  Data validation skipped (--skip-validation flag used)")
    
    # Process the data into baseline format
    baselines, calculation_logs = process_baseline_data(df, args.verbose_calc)
    
    # Export calculation log if requested
    if args.export_calc_log:
        try:
            with open(args.export_calc_log, 'w') as f:
                json.dump(calculation_logs, f, indent=2, default=str)
            print(f"Calculation log exported to: {args.export_calc_log}")
        except Exception as e:
            print(f"Failed to export calculation log: {e}")
    
    print(f"\nProcessed {len(baselines)} configurations")
    
    if args.dry_run:
        print("\nDry run mode - showing what would be updated:")
        for config_key, baseline_data in baselines.items():
            print(f"Configuration: {config_key}")
            for metric, value in baseline_data.items():
                print(f"  {metric}: {value:.2f}")
        print("\nNo changes made (dry run mode)")
        return
    
    # Update the baseline configuration
    updated_config = update_baseline_config(baselines, args.output)
    
    print(f"\nBaseline configuration update completed!")
    print(f"Updated configurations: {list(baselines.keys())}")
    
    if args.output:
        print(f"Configuration saved to: {args.output}")
    else:
        print("Configuration saved to: baseline_config.json")

if __name__ == '__main__':
    main()
