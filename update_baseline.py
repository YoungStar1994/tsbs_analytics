#!/usr/bin/env python3
"""
Script to update baseline configuration with actual test data from a specified date and branch.
Usage: python update_baseline.py --date YYYY-MM-DD --branch BRANCH_NAME [--output OUTPUT_FILE]
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

def load_data_by_date_and_branch(target_date, branch_name):
    """Load and process data for the specified date and branch.
    
    Args:
        target_date (date): The target date to filter data
        branch_name (str): The branch name to filter data
    
    Returns:
        pandas.DataFrame: Filtered data for the specified date and branch
    """
    # Get data from the data loader
    df = loader.get_data()
    
    if df.empty:
        print("No data available from data loader")
        return pd.DataFrame()
    
    print(f"Total records loaded: {len(df)}")
    
    # Filter for specified date and branch
    filtered_data = df[
        (df['datetime'].dt.date == target_date) & 
        (df['branch'] == branch_name)
    ]
    
    print(f"Loaded {len(filtered_data)} records from {target_date} {branch_name} branch")
    return filtered_data

def create_config_key(row):
    """Create configuration key in format scale_cluster_phase_worker"""
    return f"{row['scale']}_{row['cluster']}_{row['phase']}_{row['worker']}"

def process_baseline_data(df):
    """Process the data and create baseline configuration."""
    baselines = {}
    
    # Group by configuration (scale, cluster, phase, worker)
    for config_key, config_group in df.groupby(['scale', 'cluster', 'phase', 'worker']):
        scale, cluster, phase, worker = config_key
        key = f"{scale}_{cluster}_{phase}_{worker}"
        
        print(f"Processing configuration: {key}")
        
        # Initialize baseline for this configuration
        baseline = {}
        
        # Get import_speed (use the first available value since it should be the same for the config)
        import_speed_data = config_group[config_group['import_speed'].notna()]
        if not import_speed_data.empty:
            baseline['import_speed'] = float(import_speed_data['import_speed'].iloc[0])
        else:
            baseline['import_speed'] = 300  # fallback
        
        # Process query types and their mean_ms values
        for _, row in config_group.iterrows():
            query_type = row['query_type']
            mean_ms = row['mean_ms']
            
            if pd.notna(mean_ms) and pd.notna(query_type):
                # Convert query type to use hyphens consistently (matching app.py logic)
                import re
                metric_key = re.sub(r'[^a-zA-Z0-9_-]', '-', str(query_type)).lower().replace('_', '-')
                baseline[metric_key] = float(mean_ms)
        
        baselines[key] = baseline
    
    return baselines

def update_baseline_config(new_baselines, output_file=None):
    """Update the baseline configuration file with new data.
    
    Args:
        new_baselines (dict): New baseline data to update
        output_file (str, optional): Output file path. If None, uses default location.
    
    Returns:
        dict: Updated configuration
    """
    if output_file is None:
        baseline_file = '/Users/yangxing/Downloads/tsbs_analytics/baseline_config.json'
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
        description='Update baseline configuration with test data from specified date and branch',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python update_baseline.py --date 2025-06-03 --branch master
  python update_baseline.py --date 2025-06-10 --branch feature-branch --output custom_baseline.json
  python update_baseline.py -d 2025-06-03 -b master --list-available
        """
    )
    
    parser.add_argument(
        '--date', '-d',
        type=str,
        required=True,
        help='Target date in YYYY-MM-DD format (e.g., 2025-06-03)'
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
        print(f"  {row[0]} - {row['branch']}: {row['count']} records")

def main():
    """Main function to update baseline configuration."""
    args = parse_arguments()
    
    # 如果用户指定了详细输出，则启用详细日志
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        print("Verbose mode enabled - showing data loading progress...")
    
    # Validate and parse date
    try:
        target_date = datetime.strptime(args.date, '%Y-%m-%d').date()
    except ValueError:
        print(f"Error: Invalid date format '{args.date}'. Use YYYY-MM-DD format.")
        sys.exit(1)
    
    # List available data if requested
    if args.list_available:
        list_available_data()
        return
    
    print(f"Starting baseline configuration update for {target_date} on '{args.branch}' branch...")
    
    # Load data for specified date and branch
    df = load_data_by_date_and_branch(target_date, args.branch)
    
    if df.empty:
        print(f"No data found for {target_date} {args.branch} branch!")
        print("Use --list-available to see available dates and branches.")
        return
    
    # Show data summary
    print(f"\nData summary:")
    print(f"Configurations available: {df.groupby(['scale', 'cluster', 'phase', 'worker']).ngroups}")
    print(f"Query types available: {df['query_type'].nunique()}")
    print(f"Query types: {sorted(df['query_type'].unique())}")
    
    # Process the data into baseline format
    baselines = process_baseline_data(df)
    
    print(f"\nProcessed {len(baselines)} configurations")
    
    if args.dry_run:
        print("\nDry run mode - showing what would be updated:")
        for config_key, baseline_data in baselines.items():
            print(f"Configuration: {config_key}")
            for metric, value in baseline_data.items():
                print(f"  {metric}: {value}")
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
