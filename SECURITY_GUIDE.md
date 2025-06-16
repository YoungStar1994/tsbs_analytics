# TSBS Analytics 安全配置指南

## 密码安全改进

### 已实施的安全措施

1. **移除明文密码存储**
   - 前端 JavaScript 中不再包含明文密码
   - 使用 SHA256 哈希存储密码
   - 实现基于 Session 的安全认证

2. **后端安全认证**
   - 添加了 Flask Session 管理
   - 实现了 `@login_required` 装饰器保护敏感路由
   - 所有 API 接口都需要身份验证

3. **安全的登录流程**
   - 使用 HTTPS API 接口进行登录验证
   - 服务器端验证用户凭据
   - Session 自动过期管理

### 如何更改密码

1. **使用密码哈希生成工具**：
   ```bash
   cd /Users/yangxing/Downloads/tsbs_analytics
   python3 generate_password_hash.py
   ```

2. **手动生成哈希**（可选）：
   ```python
   import hashlib
   password = "your_new_password"
   hash_value = hashlib.sha256(password.encode('utf-8')).hexdigest()
   print(hash_value)
   ```

3. **更新配置**：
   - 编辑 `app.py` 文件
   - 找到 `USER_CONFIG` 字典
   - 替换 `password_hash` 值为新生成的哈希值
   - 重启应用程序

### 当前用户配置

```python
USER_CONFIG = {
    'admin': {
        'password_hash': '3e4e69e51d323903c6e65859c0a29461a85addf6327360f92f1dec47efcdaddd',  # 'Tsbs2024'
        'role': 'admin'
    }
}
```

### 安全建议

1. **定期更换密码**
   - 建议每3-6个月更换一次密码
   - 使用强密码（至少8位，包含大小写字母、数字和特殊字符）

2. **环境变量配置**
   - 可以考虑将密码哈希存储在环境变量中
   - 设置安全的 SECRET_KEY 环境变量

3. **HTTPS 部署**
   - 生产环境建议使用 HTTPS
   - 配置反向代理（如 Nginx）启用 SSL

4. **Session 安全**
   - Session 密钥已使用随机生成
   - 可通过环境变量 `SECRET_KEY` 自定义

### 环境变量设置示例

```bash
# 设置应用密钥
export SECRET_KEY="your-very-secure-secret-key-here"

# 可选：通过环境变量设置密码哈希
export ADMIN_PASSWORD_HASH="your-password-hash-here"
```

### 故障排除

1. **无法登录**
   - 检查密码哈希是否正确生成
   - 确认 app.py 中的配置已更新
   - 检查应用日志 `app.log` 和 `app_error.log`

2. **Session 问题**
   - 清除浏览器缓存和 Cookie
   - 重启应用程序
   - 检查 SECRET_KEY 配置

### 安全检查清单

- [ ] 已移除所有明文密码
- [ ] 使用哈希存储密码
- [ ] 所有敏感路由都有认证保护
- [ ] 设置了安全的 SESSION 密钥
- [ ] 定期更换密码
- [ ] 生产环境使用 HTTPS
- [ ] 监控登录日志

### 日志记录

应用会记录以下安全相关事件：
- 成功登录：`User {username} logged in successfully`
- 失败登录：`Failed login attempt for user: {username}`
- 用户登出：`User {username} logged out`

检查日志文件：
```bash
tail -f app.log | grep -E "(logged in|logged out|Failed login)"
```
