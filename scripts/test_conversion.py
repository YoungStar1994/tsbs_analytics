#!/usr/bin/env python3
"""
Test script to verify underscore to hyphen conversion logic
"""
import re
import json

def test_conversion_logic():
    """Test the conversion logic used in app.py and baseline.html"""
    
    # Test query types that should be converted
    test_query_types = [
        'single_groupby_1_1_1',
        'single_groupby_5_8_1', 
        'double_groupby_1',
        'cpu_max_all_1',
        'import_speed',
        'high_cpu_all',
        'groupby_orderby_limit'
    ]
    
    print("Testing conversion logic:")
    print("-" * 50)
    
    for query_type in test_query_types:
        # Python logic from app.py
        python_converted = re.sub(r'[^a-zA-Z0-9_-]', '-', str(query_type)).lower().replace('_', '-')
        
        # JavaScript equivalent logic from baseline.html
        js_converted = query_type.replace('_', '-').lower()
        
        print(f"Original: {query_type}")
        print(f"Python:   {python_converted}")
        print(f"JS:       {js_converted}")
        print(f"Match:    {python_converted == js_converted}")
        print("-" * 30)

def check_baseline_config():
    """Check if baseline_config.json has consistent naming"""
    
    try:
        with open('baseline_config.json', 'r') as f:
            config = json.load(f)
        
        print("\nChecking baseline_config.json:")
        print("-" * 50)
        
        underscore_count = 0
        hyphen_count = 0
        
        for config_key, config_data in config.items():
            for metric_key in config_data.keys():
                if '_' in metric_key and metric_key != 'import_speed':  # import_speed is exception
                    underscore_count += 1
                    print(f"Found underscore in {config_key}: {metric_key}")
                elif '-' in metric_key:
                    hyphen_count += 1
        
        print(f"\nSummary:")
        print(f"Metrics with underscores (excluding import_speed): {underscore_count}")
        print(f"Metrics with hyphens: {hyphen_count}")
        
        if underscore_count == 0:
            print("✅ All metrics (except import_speed) use hyphens!")
        else:
            print("❌ Some metrics still use underscores")
            
    except FileNotFoundError:
        print("❌ baseline_config.json not found")
    except json.JSONDecodeError:
        print("❌ Error parsing baseline_config.json")

if __name__ == "__main__":
    test_conversion_logic()
    check_baseline_config()
