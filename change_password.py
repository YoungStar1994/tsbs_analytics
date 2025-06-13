#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
密码管理工具
用于安全地更改TSBS Analytics系统的管理员密码
"""

import getpass
import hashlib
import os
import sys
import re

def validate_password(password):
    """验证密码强度"""
    if len(password) < 8:
        return False, "密码长度至少需要8个字符"
    
    if not re.search(r'[A-Z]', password):
        return False, "密码必须包含至少一个大写字母"
    
    if not re.search(r'[a-z]', password):
        return False, "密码必须包含至少一个小写字母"
    
    if not re.search(r'\d', password):
        return False, "密码必须包含至少一个数字"
    
    return True, "密码符合要求"

def hash_password(password):
    """生成密码哈希"""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def main():
    print("=== TSBS Analytics 密码管理工具 ===")
    print()
    
    # 方式1：环境变量设置
    print("选择密码设置方式：")
    print("1. 设置环境变量 (推荐用于生产环境)")
    print("2. 交互式输入密码")
    print("3. 生成随机密码")
    
    choice = input("请选择 (1-3): ").strip()
    
    if choice == "1":
        print("\n=== 环境变量设置方式 ===")
        print("将以下命令添加到您的环境配置中：")
        print()
        
        while True:
            password = getpass.getpass("请输入新密码: ")
            if not password:
                print("密码不能为空")
                continue
                
            confirm_password = getpass.getpass("请确认密码: ")
            if password != confirm_password:
                print("两次输入的密码不一致，请重试")
                continue
                
            valid, message = validate_password(password)
            if not valid:
                print(f"密码不符合要求: {message}")
                continue
                
            break
        
        print(f"export ADMIN_PASSWORD='{password}'")
        print()
        print("然后重启应用程序以使新密码生效。")
        
    elif choice == "2":
        print("\n=== 交互式密码设置 ===")
        print("注意：此方式仅用于开发环境测试")
        
        while True:
            password = getpass.getpass("请输入新密码: ")
            if not password:
                print("密码不能为空")
                continue
                
            confirm_password = getpass.getpass("请确认密码: ")
            if password != confirm_password:
                print("两次输入的密码不一致，请重试")
                continue
                
            valid, message = validate_password(password)
            if not valid:
                print(f"密码不符合要求: {message}")
                continue
                
            break
        
        password_hash = hash_password(password)
        print(f"\n密码哈希值: {password_hash}")
        print("请将此哈希值更新到config.py文件中的用户配置。")
        
    elif choice == "3":
        import secrets
        import string
        
        print("\n=== 生成随机密码 ===")
        
        # 生成强密码
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        password = ''.join(secrets.choice(alphabet) for _ in range(16))
        
        # 确保包含各种字符类型
        while not (re.search(r'[A-Z]', password) and 
                   re.search(r'[a-z]', password) and 
                   re.search(r'\d', password)):
            password = ''.join(secrets.choice(alphabet) for _ in range(16))
        
        print(f"生成的随机密码: {password}")
        print(f"环境变量设置: export ADMIN_PASSWORD='{password}'")
        print()
        print("请妥善保存此密码！")
        
    else:
        print("无效选择")
        return
    
    print("\n=== 安全提醒 ===")
    print("1. 请立即删除终端历史中的密码记录")
    print("2. 确保只有授权人员能访问密码")
    print("3. 定期更换密码以提高安全性")
    print("4. 不要在代码中硬编码密码")

if __name__ == "__main__":
    main()
