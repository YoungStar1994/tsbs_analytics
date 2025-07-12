#!/usr/bin/env python3
"""
测试不同基准值类型的评分计算
验证Master、企业发版、开源发版基准值是否正确使用
"""

import requests
import json

def test_baseline_scoring():
    """测试不同基准值类型的评分计算"""
    
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
    
    print("登录成功，开始测试不同基准值类型的评分计算...")
    
    # 测试筛选条件
    test_filters = {
        "branches": ["master"],
        "scales": ["100"],
        "clusters": ["1"],
        "workers": ["1"],
        "execution_types": ["insert"],
        "start_date": "2025-01-01",
        "end_date": "2025-12-31"
    }
    
    baseline_types = ["master", "enterprise", "opensource"]
    
    for baseline_type in baseline_types:
        print(f"\n=== 测试基准值类型: {baseline_type} ===")
        
        # 设置基准值类型
        test_filters["baseline_type"] = baseline_type
        
        # 发送请求获取数据
        response = session.post(f"{base_url}/data", json=test_filters)
        
        if response.status_code == 200:
            try:
                data = response.json()
                table_data = data.get("table_data", [])
                
                if table_data:
                    print(f"获取到 {len(table_data)} 条数据")
                    
                    # 分析评分数据
                    import_speeds = []
                    import_scores = []
                    import_baselines = []
                    query_scores = []
                    
                    for row in table_data:
                        if row.get("import_speed") is not None:
                            import_speeds.append(row["import_speed"])
                        if row.get("import_speed_score") is not None:
                            import_scores.append(row["import_speed_score"])
                        if row.get("import_speed_baseline_pct") is not None:
                            import_baselines.append(row["import_speed_baseline_pct"])
                        if row.get("query_comprehensive_score") is not None:
                            query_scores.append(row["query_comprehensive_score"])
                    
                    # 显示统计信息
                    if import_speeds:
                        print(f"  导入速度范围: {min(import_speeds):.2f} - {max(import_speeds):.2f} rows/sec")
                    if import_scores:
                        print(f"  导入速度评分范围: {min(import_scores):.2f} - {max(import_scores):.2f}")
                    if import_baselines:
                        print(f"  导入速度基准对比范围: {min(import_baselines):.2f}% - {max(import_baselines):.2f}%")
                    if query_scores:
                        print(f"  查询综合评分范围: {min(query_scores):.2f} - {max(query_scores):.2f}")
                    
                    # 显示一些具体的评分示例
                    print(f"  前3条记录的评分详情:")
                    for i, row in enumerate(table_data[:3]):
                        print(f"    记录{i+1}: 导入速度={row.get('import_speed', 'N/A')}, "
                              f"导入评分={row.get('import_speed_score', 'N/A')}, "
                              f"基准对比={row.get('import_speed_baseline_pct', 'N/A')}%, "
                              f"查询评分={row.get('query_comprehensive_score', 'N/A')}")
                else:
                    print("  没有获取到数据")
                    
            except Exception as e:
                print(f"  解析响应数据失败: {e}")
        else:
            print(f"  请求失败: {response.status_code} - {response.text}")
    
    print("\n=== 基准值配置对比 ===")
    
    # 获取不同基准值配置进行对比
    endpoints = {
        "master": "/masters",
        "enterprise": "/enterprises", 
        "opensource": "/opensources"
    }
    
    for baseline_type, endpoint in endpoints.items():
        print(f"\n{baseline_type}基准值配置:")
        response = session.get(f"{base_url}{endpoint}")
        if response.status_code == 200:
            config = response.json()
            # 显示100_1_insert_1配置的导入速度
            key = "100_1_insert_1"
            if key in config:
                import_speed = config[key].get("import_speed", "N/A")
                print(f"  {key}.import_speed = {import_speed}")
            else:
                print(f"  未找到配置键: {key}")
        else:
            print(f"  获取{baseline_type}基准值失败: {response.status_code}")

if __name__ == "__main__":
    test_baseline_scoring() 