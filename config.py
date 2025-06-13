# -*- coding: utf-8 -*-
"""
安全配置文件
包含用户认证和安全设置
"""
import hashlib
import secrets
import os
from datetime import timedelta

class SecurityConfig:
    # 生成或读取应用密钥
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY') or secrets.token_hex(32)
    
    # 会话配置
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)  # 8小时后自动登出
    SESSION_COOKIE_SECURE = False  # 开发环境使用HTTP，生产环境应改为True
    SESSION_COOKIE_HTTPONLY = True  # 防止XSS攻击
    SESSION_COOKIE_SAMESITE = 'Lax'  # CSRF保护
    
    # 密码策略
    MIN_PASSWORD_LENGTH = 8
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True  
    REQUIRE_DIGITS = True
    REQUIRE_SPECIAL_CHARS = False
    
    # 登录尝试限制
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION = timedelta(minutes=30)
    
    # 用户数据库（生产环境应使用真实数据库）
    @staticmethod
    def get_users():
        """获取用户数据，支持环境变量覆盖"""
        # 默认用户
        users = {
            'admin': {
                'password_hash': hashlib.sha256('Tsbs2024'.encode('utf-8')).hexdigest(),
                'role': 'admin',
                'name': '管理员',
                'failed_attempts': 0,
                'locked_until': None
            }
        }
        
        # 支持从环境变量读取自定义密码
        custom_password = os.environ.get('ADMIN_PASSWORD')
        if custom_password:
            users['admin']['password_hash'] = hashlib.sha256(custom_password.encode('utf-8')).hexdigest()
        
        return users
    
    @staticmethod
    def hash_password(password):
        """生成密码哈希"""
        return hashlib.sha256(password.encode('utf-8')).hexdigest()
    
    @staticmethod
    def verify_password(password, password_hash):
        """验证密码"""
        return hashlib.sha256(password.encode('utf-8')).hexdigest() == password_hash

# 审计日志配置
AUDIT_LOG_FILE = 'logs/audit.log'
SECURITY_LOG_FILE = 'logs/security.log'
