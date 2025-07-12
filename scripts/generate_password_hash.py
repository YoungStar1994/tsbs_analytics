#!/usr/bin/env python3
"""
密码哈希生成工具
用于生成安全的密码哈希，可以用于更新 app.py 中的用户配置
"""

import hashlib
import getpass
import sys

def hash_password(password):
    """对密码进行SHA256哈希"""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def main():
    print("TSBS Analytics 密码哈希生成工具")
    print("=" * 40)
    
    try:
        # 获取密码输入
        password = getpass.getpass("请输入新密码: ")
        
        if not password:
            print("密码不能为空")
            sys.exit(1)
            
        if len(password) < 6:
            print("密码长度至少6位")
            sys.exit(1)
            
        # 生成哈希
        password_hash = hash_password(password)
        
        print("\n生成的密码哈希:")
        print("-" * 40)
        print(password_hash)
        print("-" * 40)
        
        print("\n使用方法:")
        print("1. 复制上面的哈希值")
        print("2. 在 app.py 中找到 USER_CONFIG 配置")
        print("3. 将对应用户的 'password_hash' 值替换为新的哈希值")
        print("4. 重启应用程序")
        
        print("\n示例配置:")
        print("USER_CONFIG = {")
        print("    'admin': {")
        print(f"        'password_hash': '{password_hash}',")
        print("        'role': 'admin'")
        print("    }")
        print("}")
        
    except KeyboardInterrupt:
        print("\n\n操作已取消")
        sys.exit(0)
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
