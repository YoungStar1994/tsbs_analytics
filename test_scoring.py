#!/usr/bin/env python3
"""
TSBS 性能评分系统测试脚本
测试评分体系的各种场景
"""

import requests
import json

def test_scoring_scenarios():
    """测试不同的评分场景"""
    
    base_url = "http://localhost:5001"
    
    # 先登录
    login_data = {
        "username": "admin",
        "password": "Tsbs2024"
    }
    
    session = requests.Session()
    login_response = session.post(f"{base_url}/api/login", json=login_data)
    
    if login_response.status_code != 200:
        print("登录失败")
        return
    
    print("登录成功，开始测试评分功能...")
    
    # 测试场景1：性能完全符合基准值（应该得100分）
    print("\n=== 测试场景1：性能完全符合基准值 ===")
    scenario1 = {
        "actual_mean": 50.0,
        "actual_median": 45.0,
        "actual_std": 10.0,
        "actual_range": 40.0,
        "baseline_mean": 50.0,
        "baseline_median": 45.0,
        "baseline_std": 10.0,
        "baseline_range": 40.0,
        "actual_import_speed": 1600000,
        "baseline_import_speed": 1600000
    }
    
    response = session.post(f"{base_url}/api/test-scoring", json=scenario1)
    if response.status_code == 200:
        result = response.json()
        print(f"综合得分: {result['score_info']['comprehensive_score']}")
        print(f"导入速度得分: {result['import_speed_test']['import_score']}")
        print(f"详细得分: {result['score_info']['detail_scores']}")
    else:
        print(f"测试失败: {response.text}")
    
    # 测试场景2：性能略好于基准值（应该得100分）
    print("\n=== 测试场景2：性能略好于基准值 ===")
    scenario2 = {
        "actual_mean": 45.0,  # 比基准值低5ms（好）
        "actual_median": 42.0,  # 比基准值低3ms（好）
        "actual_std": 9.0,  # 比基准值低1（好）
        "actual_range": 35.0,  # 比基准值低5（好）
        "baseline_mean": 50.0,
        "baseline_median": 45.0,
        "baseline_std": 10.0,
        "baseline_range": 40.0,
        "actual_import_speed": 1700000,  # 比基准值高（好）
        "baseline_import_speed": 1600000
    }
    
    response = session.post(f"{base_url}/api/test-scoring", json=scenario2)
    if response.status_code == 200:
        result = response.json()
        print(f"综合得分: {result['score_info']['comprehensive_score']}")
        print(f"导入速度得分: {result['import_speed_test']['import_score']}")
        print(f"详细得分: {result['score_info']['detail_scores']}")
        print(f"偏差率: {result['score_info']['deviation_rates']}")
    else:
        print(f"测试失败: {response.text}")
    
    # 测试场景3：性能略差于基准值（偏差率在10%以内）
    print("\n=== 测试场景3：性能略差于基准值（偏差率在10%以内） ===")
    scenario3 = {
        "actual_mean": 54.0,  # 比基准值高8%（差）
        "actual_median": 48.0,  # 比基准值高6.7%（差）
        "actual_std": 10.8,  # 比基准值高8%（差）
        "actual_range": 43.0,  # 比基准值高7.5%（差）
        "baseline_mean": 50.0,
        "baseline_median": 45.0,
        "baseline_std": 10.0,
        "baseline_range": 40.0,
        "actual_import_speed": 1500000,  # 比基准值低6.25%（差）
        "baseline_import_speed": 1600000
    }
    
    response = session.post(f"{base_url}/api/test-scoring", json=scenario3)
    if response.status_code == 200:
        result = response.json()
        print(f"综合得分: {result['score_info']['comprehensive_score']}")
        print(f"导入速度得分: {result['import_speed_test']['import_score']}")
        print(f"详细得分: {result['score_info']['detail_scores']}")
        print(f"偏差率: {result['score_info']['deviation_rates']}")
    else:
        print(f"测试失败: {response.text}")
    
    # 测试场景4：性能明显差于基准值（偏差率超过10%）
    print("\n=== 测试场景4：性能明显差于基准值（偏差率超过10%） ===")
    scenario4 = {
        "actual_mean": 60.0,  # 比基准值高20%（差）
        "actual_median": 54.0,  # 比基准值高20%（差）
        "actual_std": 13.0,  # 比基准值高30%（差）
        "actual_range": 50.0,  # 比基准值高25%（差）
        "baseline_mean": 50.0,
        "baseline_median": 45.0,
        "baseline_std": 10.0,
        "baseline_range": 40.0,
        "actual_import_speed": 1200000,  # 比基准值低25%（差）
        "baseline_import_speed": 1600000
    }
    
    response = session.post(f"{base_url}/api/test-scoring", json=scenario4)
    if response.status_code == 200:
        result = response.json()
        print(f"综合得分: {result['score_info']['comprehensive_score']}")
        print(f"导入速度得分: {result['import_speed_test']['import_score']}")
        print(f"详细得分: {result['score_info']['detail_scores']}")
        print(f"偏差率: {result['score_info']['deviation_rates']}")
    else:
        print(f"测试失败: {response.text}")

if __name__ == "__main__":
    test_scoring_scenarios() 