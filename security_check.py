#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
安全检查工具
用于评估TSBS Analytics系统的安全状态
"""

import os
import sys
import hashlib
import re
from datetime import datetime

class SecurityChecker:
    def __init__(self):
        self.issues = []
        self.warnings = []
        self.info = []
        
    def check_password_security(self):
        """检查密码安全性"""
        print("=== 密码安全检查 ===")
        
        # 检查是否使用环境变量
        if os.environ.get('ADMIN_PASSWORD'):
            self.info.append("✓ 使用环境变量存储密码")
            password = os.environ.get('ADMIN_PASSWORD')
            
            # 检查密码强度
            if len(password) < 8:
                self.issues.append("✗ 密码长度不足8位")
            else:
                self.info.append("✓ 密码长度符合要求")
                
            if not re.search(r'[A-Z]', password):
                self.warnings.append("⚠ 密码缺少大写字母")
            else:
                self.info.append("✓ 密码包含大写字母")
                
            if not re.search(r'[a-z]', password):
                self.warnings.append("⚠ 密码缺少小写字母")
            else:
                self.info.append("✓ 密码包含小写字母")
                
            if not re.search(r'\d', password):
                self.warnings.append("⚠ 密码缺少数字")
            else:
                self.info.append("✓ 密码包含数字")
                
            if password == 'Tsbs2024':
                self.issues.append("✗ 使用默认密码，存在安全风险")
            else:
                self.info.append("✓ 未使用默认密码")
        else:
            self.warnings.append("⚠ 未设置环境变量密码，使用默认密码")
            self.issues.append("✗ 默认密码存在安全风险")
    
    def check_file_permissions(self):
        """检查文件权限"""
        print("\n=== 文件权限检查 ===")
        
        sensitive_files = [
            'app.py',
            'config.py', 
            'baseline_config.json',
            'logs/security.log',
            'logs/app.log'
        ]
        
        for file_path in sensitive_files:
            if os.path.exists(file_path):
                stat = os.stat(file_path)
                mode = oct(stat.st_mode)[-3:]
                
                if mode == '644' or mode == '600':
                    self.info.append(f"✓ {file_path} 权限设置合适 ({mode})")
                elif mode == '777' or mode == '666':
                    self.issues.append(f"✗ {file_path} 权限过于宽松 ({mode})")
                else:
                    self.warnings.append(f"⚠ {file_path} 权限需要检查 ({mode})")
    
    def check_log_files(self):
        """检查日志文件"""
        print("\n=== 日志文件检查 ===")
        
        log_files = [
            'logs/app.log',
            'logs/security.log', 
            'logs/app_error.log'
        ]
        
        for log_file in log_files:
            if os.path.exists(log_file):
                size = os.path.getsize(log_file)
                if size > 100 * 1024 * 1024:  # 100MB
                    self.warnings.append(f"⚠ {log_file} 文件过大 ({size/1024/1024:.1f}MB)")
                else:
                    self.info.append(f"✓ {log_file} 文件大小正常 ({size/1024:.1f}KB)")
            else:
                self.warnings.append(f"⚠ {log_file} 文件不存在")
    
    def check_https_config(self):
        """检查HTTPS配置"""
        print("\n=== HTTPS配置检查 ===")
        
        # 检查是否配置了SSL证书
        if os.path.exists('cert.pem') and os.path.exists('key.pem'):
            self.info.append("✓ 发现SSL证书文件")
        else:
            self.warnings.append("⚠ 未发现SSL证书，建议在生产环境使用HTTPS")
    
    def check_session_config(self):
        """检查会话配置"""
        print("\n=== 会话安全检查 ===")
        
        try:
            from config import SecurityConfig
            
            if hasattr(SecurityConfig, 'SESSION_COOKIE_SECURE'):
                if SecurityConfig.SESSION_COOKIE_SECURE:
                    self.info.append("✓ 会话Cookie设置为安全模式")
                else:
                    self.warnings.append("⚠ 会话Cookie未设置安全模式")
            
            if hasattr(SecurityConfig, 'SESSION_COOKIE_HTTPONLY'):
                if SecurityConfig.SESSION_COOKIE_HTTPONLY:
                    self.info.append("✓ 会话Cookie设置为HttpOnly")
                else:
                    self.warnings.append("⚠ 会话Cookie未设置HttpOnly")
                    
        except ImportError:
            self.warnings.append("⚠ 无法检查安全配置")
    
    def generate_report(self):
        """生成安全报告"""
        print("\n" + "="*50)
        print("         安全检查报告")
        print("="*50)
        
        if self.issues:
            print(f"\n🚨 严重问题 ({len(self.issues)}项)")
            for issue in self.issues:
                print(f"  {issue}")
        
        if self.warnings:
            print(f"\n⚠️  警告 ({len(self.warnings)}项)")
            for warning in self.warnings:
                print(f"  {warning}")
                
        if self.info:
            print(f"\n✅ 正常项目 ({len(self.info)}项)")
            for info in self.info:
                print(f"  {info}")
        
        print(f"\n📊 总结:")
        print(f"  - 严重问题: {len(self.issues)}项")
        print(f"  - 警告: {len(self.warnings)}项") 
        print(f"  - 正常: {len(self.info)}项")
        
        if self.issues:
            print(f"\n🔧 建议:")
            print("  1. 立即修复所有严重问题")
            print("  2. 使用 python3 change_password.py 更改默认密码")
            print("  3. 在生产环境中启用HTTPS")
            print("  4. 定期检查日志文件")
        
        return len(self.issues) == 0

def main():
    print("TSBS Analytics 安全检查工具")
    print(f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    checker = SecurityChecker()
    
    # 执行各项检查
    checker.check_password_security()
    checker.check_file_permissions()
    checker.check_log_files()
    checker.check_https_config()
    checker.check_session_config()
    
    # 生成报告
    is_secure = checker.generate_report()
    
    if not is_secure:
        print(f"\n⚠️  系统存在安全风险，建议立即处理！")
        sys.exit(1)
    else:
        print(f"\n✅ 系统安全状态良好")
        sys.exit(0)

if __name__ == "__main__":
    main()
