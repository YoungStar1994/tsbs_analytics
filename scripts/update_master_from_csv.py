#!/usr/bin/env python3
"""
Script to update master configuration from master.csv file.
Usage: python update_master_from_csv.py
"""

import pandas as pd
import json
import os

def parse_master_csv(csv_file_path):
    """Parse the master.csv file and extract configuration data."""
    # Read the CSV file
    df = pd.read_csv(csv_file_path)
    
    # Get the header information from the first column
    exec_type_row = df.iloc[0, 1:]  # First data row contains execution types
    cluster_row = df.iloc[1, 1:]    # Second data row contains cluster counts
    scale_row = df.iloc[2, 1:]      # Third data row contains scales
    worker_row = df.iloc[3, 1:]     # Fourth data row contains worker counts
    
    # Initialize the master configuration
    master_config = {}
    
    # Process each column (configuration)
    for col_idx in range(1, len(df.columns)):
        # Extract configuration parameters
        exec_type = exec_type_row.iloc[col_idx - 1] 
        cluster = int(cluster_row.iloc[col_idx - 1])
        scale = int(scale_row.iloc[col_idx - 1])
        worker = int(worker_row.iloc[col_idx - 1])
        
        # Create configuration key
        config_key = f"{scale}_{cluster}_{exec_type}_{worker}"
        
        # Initialize configuration if not exists
        if config_key not in master_config:
            master_config[config_key] = {}
        
        # Extract metric values for this configuration (starting from row 4)
        for row_idx in range(4, len(df)):
            metric_name = df.iloc[row_idx, 0]  # First column contains metric names
            metric_value = df.iloc[row_idx, col_idx]
            
            # Convert metric name to match configuration format
            if metric_name == 'import_speed':
                master_config[config_key]['import_speed'] = float(metric_value)
            else:
                # Convert underscores to hyphens for consistency
                config_metric_name = metric_name.replace('_', '-')
                master_config[config_key][config_metric_name] = float(metric_value)
    
    return master_config

def update_master_config(master_config, output_file='config/master_config.json'):
    """Update the master configuration file."""
    # Ensure config directory exists
    os.makedirs('config', exist_ok=True)
    
    # Backup existing file if it exists
    if os.path.exists(output_file):
        backup_file = f"{output_file}.backup_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}"
        os.rename(output_file, backup_file)
        print(f"Backed up existing master config to: {backup_file}")
    
    # Write the new configuration
    with open(output_file, 'w') as f:
        json.dump(master_config, f, indent=2, sort_keys=True)
    
    print(f"Updated master configuration written to: {output_file}")
    print(f"Total configurations: {len(master_config)}")
    
    # Show sample configuration
    if master_config:
        sample_key = list(master_config.keys())[0]
        print(f"\nSample configuration ({sample_key}):")
        for metric, value in sorted(master_config[sample_key].items()):
            print(f"  {metric}: {value}")

def main():
    """Main function."""
    csv_file = 'master.csv'
    
    if not os.path.exists(csv_file):
        print(f"Error: {csv_file} not found!")
        return
    
    print(f"Reading data from {csv_file}...")
    master_config = parse_master_csv(csv_file)
    
    print(f"Parsed {len(master_config)} configurations")
    
    # Show all configuration keys
    print("\nConfiguration keys found:")
    for key in sorted(master_config.keys()):
        print(f"  {key}")
    
    # Update the master configuration
    update_master_config(master_config)
    
    print("\nMaster configuration update completed!")

if __name__ == '__main__':
    main() 