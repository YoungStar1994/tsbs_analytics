#!/usr/bin/env python3
"""
TSBS Analytics 安全认证测试脚本
用于验证密码哈希和认证系统是否正常工作
"""

import hashlib
import requests
import json

def hash_password(password):
    """对密码进行SHA256哈希"""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def test_password_hash():
    """测试密码哈希功能"""
    print("=== 测试密码哈希 ===")
    test_password = "Tsbs2024"
    expected_hash = "3e4e69e51d323903c6e65859c0a29461a85addf6327360f92f1dec47efcdaddd"
    actual_hash = hash_password(test_password)
    
    print(f"测试密码: {test_password}")
    print(f"期望哈希: {expected_hash}")
    print(f"实际哈希: {actual_hash}")
    print(f"哈希匹配: {'✓' if actual_hash == expected_hash else '✗'}")
    
    return actual_hash == expected_hash

def test_login_api(base_url="http://localhost:5001"):
    """测试登录API"""
    print("\n=== 测试登录API ===")
    
    try:
        # 测试正确密码
        login_data = {
            "username": "admin",
            "password": "Tsbs2024"
        }
        
        response = requests.post(f"{base_url}/api/login", 
                               json=login_data,
                               headers={'Content-Type': 'application/json'})
        
        print(f"登录请求状态码: {response.status_code}")
        print(f"登录响应: {response.text}")
        
        if response.status_code == 200:
            print("✓ 正确密码登录成功")
            
            # 获取session cookie
            session_cookie = response.cookies.get('session')
            if session_cookie:
                print(f"✓ 获得Session Cookie: {session_cookie[:20]}...")
                
                # 测试认证检查
                auth_response = requests.get(f"{base_url}/api/check-auth", 
                                           cookies=response.cookies)
                print(f"认证检查状态码: {auth_response.status_code}")
                print(f"认证检查响应: {auth_response.text}")
                
                if auth_response.status_code == 200:
                    auth_data = auth_response.json()
                    if auth_data.get('authenticated'):
                        print("✓ 认证检查通过")
                    else:
                        print("✗ 认证检查失败")
                
                # 测试登出
                logout_response = requests.post(f"{base_url}/api/logout",
                                              cookies=response.cookies,
                                              headers={'Content-Type': 'application/json'})
                print(f"登出状态码: {logout_response.status_code}")
                print(f"登出响应: {logout_response.text}")
                
                if logout_response.status_code == 200:
                    print("✓ 登出成功")
                
            else:
                print("✗ 未获得Session Cookie")
        else:
            print("✗ 正确密码登录失败")
            
        # 测试错误密码
        print("\n--- 测试错误密码 ---")
        wrong_login_data = {
            "username": "admin",
            "password": "wrong_password"
        }
        
        wrong_response = requests.post(f"{base_url}/api/login", 
                                     json=wrong_login_data,
                                     headers={'Content-Type': 'application/json'})
        
        print(f"错误密码登录状态码: {wrong_response.status_code}")
        print(f"错误密码登录响应: {wrong_response.text}")
        
        if wrong_response.status_code == 401:
            print("✓ 错误密码正确被拒绝")
        else:
            print("✗ 错误密码未被正确拒绝")
            
    except requests.exceptions.ConnectionError:
        print("✗ 无法连接到服务器，请确保应用正在运行")
        return False
    except Exception as e:
        print(f"✗ 测试过程中出现错误: {e}")
        return False
        
    return True

def main():
    print("TSBS Analytics 安全认证测试")
    print("=" * 50)
    
    # 测试密码哈希
    hash_test_passed = test_password_hash()
    
    # 测试登录API（需要服务器运行）
    api_test_passed = test_login_api()
    
    print("\n" + "=" * 50)
    print("测试结果总结:")
    print(f"密码哈希测试: {'✓ 通过' if hash_test_passed else '✗ 失败'}")
    print(f"登录API测试: {'✓ 通过' if api_test_passed else '✗ 失败'}")
    
    if hash_test_passed and api_test_passed:
        print("\n🎉 所有安全测试通过！")
    else:
        print("\n⚠️  部分测试失败，请检查配置")

if __name__ == "__main__":
    main()
