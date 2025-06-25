#!/usr/bin/env python3
"""
Script to update baseline2 configuration with actual test data from a specified date range and branch.
This script is similar to update_baseline.py but saves data to baseline2_config.json instead.
The script processes all test results within the date range, removes min/max values for each metric,
and calculates the average of remaining values as baseline data.
Usage: python update_baseline2.py --start YYYY-MM-DD --end YYYY-MM-DD --branch BRANCH_NAME [--output OUTPUT_FILE]
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
                error_messages.append(f"Configuration {config_name}: Missing data for query type '{missing_type}'")
    
    is_valid = len(error_messages) == 0
    return is_valid, error_messages

def remove_outliers_keep_average(values):
    """Remove minimum and maximum values, then calculate average of remaining values.
    
    Args:
        values: List or array of numeric values
    
    Returns:
        float: Average of values after removing min and max, or original average if <= 2 values
    """
    values = [v for v in values if pd.notna(v) and v is not None]
    
    if len(values) <= 2:
        return sum(values) / len(values) if values else 0
    
    values.remove(min(values))
    values.remove(max(values))
    
    return sum(values) / len(values) if values else 0

def process_baseline_data(df):
    """Process data to create baseline configuration by removing outliers and averaging.
    
    Args:
        df (pandas.DataFrame): Input data with all test results
    
    Returns:
        dict: Baseline configuration dictionary
    """
    baseline_config = {}
    
    # Process by configuration group
    for config_tuple in df.groupby(['scale', 'cluster', 'phase', 'worker']).groups.keys():
        scale, cluster, phase, worker = config_tuple
        config_key = f"{scale}_{cluster}_{phase}_{worker}"
        
        # Get all data for this configuration
        config_data = df[
            (df['scale'] == scale) & 
            (df['cluster'] == cluster) & 
            (df['phase'] == phase) & 
            (df['worker'] == worker)
        ]
        
        print(f"Processing configuration: {config_key} ({len(config_data)} records)")
        
        baseline_config[config_key] = {}
        
        # Process import_speed
        import_speeds = config_data[config_data['import_speed'].notna()]['import_speed'].tolist()
        if import_speeds:
            baseline_config[config_key]['import_speed'] = remove_outliers_keep_average(import_speeds)
            print(f"  import_speed: {len(import_speeds)} values -> {baseline_config[config_key]['import_speed']:.2f}")
        
        # Process query types
        query_types = config_data['query_type'].dropna().unique()
        for query_type in sorted(query_types):
            query_data = config_data[config_data['query_type'] == query_type]
            mean_ms_values = query_data[query_data['mean_ms'].notna()]['mean_ms'].tolist()
            
            if mean_ms_values:
                # Convert query type to metric key format (consistent with frontend)
                import re
                metric_key = re.sub(r'[^a-zA-Z0-9_-]', '-', str(query_type)).lower().replace('_', '-')
                baseline_config[config_key][metric_key] = remove_outliers_keep_average(mean_ms_values)
                print(f"  {query_type} -> {metric_key}: {len(mean_ms_values)} values -> {baseline_config[config_key][metric_key]:.2f}")
    
    return baseline_config

def save_baseline_config(config, output_file='baseline2_config.json'):
    """Save baseline configuration to JSON file.
    
    Args:
        config (dict): Baseline configuration to save
        output_file (str): Output file path
    """
    # Create backup if file exists
    if os.path.exists(output_file):
        backup_file = f"{output_file}.backup"
        print(f"Creating backup: {backup_file}")
        with open(output_file, 'r', encoding='utf-8') as f:
            with open(backup_file, 'w', encoding='utf-8') as bf:
                bf.write(f.read())
    
    # Save new configuration
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    print(f"Baseline2 configuration saved to: {output_file}")

def print_summary(config):
    """Print summary of the baseline configuration.
    
    Args:
        config (dict): Baseline configuration
    """
    print("\n" + "="*60)
    print("BASELINE2 CONFIGURATION SUMMARY")
    print("="*60)
    
    print(f"Total configurations: {len(config)}")
    
    # Count metrics per configuration
    all_metrics = set()
    for config_data in config.values():
        all_metrics.update(config_data.keys())
    
    print(f"Unique metrics found: {len(all_metrics)}")
    print("Metrics:", sorted(all_metrics))
    
    # Show some sample configurations
    print("\nSample configurations:")
    for i, (config_key, config_data) in enumerate(config.items()):
        if i >= 3:  # Show only first 3
            break
        print(f"  {config_key}: {len(config_data)} metrics")
        for metric, value in list(config_data.items())[:3]:  # Show first 3 metrics
            print(f"    {metric}: {value:.2f}")
        if len(config_data) > 3:
            print(f"    ... and {len(config_data) - 3} more metrics")

def main():
    parser = argparse.ArgumentParser(description='Update baseline2 configuration from test data')
    parser.add_argument('--start', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--branch', required=True, help='Branch name to filter data')
    parser.add_argument('--output', default='baseline2_config.json', help='Output file (default: baseline2_config.json)')
    parser.add_argument('--force', action='store_true', help='Force update even with incomplete data')
    
    args = parser.parse_args()
    
    try:
        start_date = datetime.strptime(args.start, '%Y-%m-%d').date()
        end_date = datetime.strptime(args.end, '%Y-%m-%d').date()
    except ValueError as e:
        print(f"Error parsing dates: {e}")
        sys.exit(1)
    
    if start_date > end_date:
        print("Error: Start date must be before or equal to end date")
        sys.exit(1)
    
    print(f"Updating baseline2 configuration...")
    print(f"Date range: {start_date} to {end_date}")
    print(f"Branch: {args.branch}")
    print(f"Output file: {args.output}")
    
    # Load and filter data
    df = load_data_by_date_range_and_branch(start_date, end_date, args.branch)
    
    if df.empty:
        print("No data found for the specified criteria")
        sys.exit(1)
    
    # Validate data completeness
    is_valid, error_messages = validate_data_completeness(df)
    
    if not is_valid:
        print("\nData completeness validation failed:")
        for error in error_messages:
            print(f"  - {error}")
        
        if not args.force:
            print("\nUse --force to proceed with incomplete data")
            sys.exit(1)
        else:
            print("\nProceeding with incomplete data (--force specified)")
    else:
        print("Data completeness validation passed ✓")
    
    # Process data to create baseline configuration
    baseline_config = process_baseline_data(df)
    
    if not baseline_config:
        print("No baseline configuration generated")
        sys.exit(1)
    
    # Save configuration
    save_baseline_config(baseline_config, args.output)
    
    # Print summary
    print_summary(baseline_config)
    
    print(f"\nBaseline2 update completed successfully!")
    print(f"You can now use the second baseline values in the web interface.")

if __name__ == '__main__':
    main()
