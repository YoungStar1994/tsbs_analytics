# 🚀 TSBS Analytics

> 时间序列基准测试数据分析平台 - 安全增强版

## 📋 项目概述

TSBS Analytics是一个用于分析时间序列数据库基准测试结果的Web应用程序。本版本在原有功能基础上大幅增强了安全性，提供企业级的安全保护。

## ⚡ 快速开始


### 🔐 安全启动（推荐生产环境）
```bash
# 前台启动（可看到实时日志）
./start_secure.sh

# 后台启动（不占用终端）
./start_secure.sh --daemon
```

### 📊 管理命令
```bash
./status.sh   # 查看运行状态
./stop.sh     # 停止服务
./restart.sh  # 重启服务
```

### 📱 访问应用
- **登录页面**: http://localhost:5001/login.html
- **主界面**: http://localhost:5001/ (需要登录)
- **基准配置**: http://localhost:5001/baseline (需要登录)

## ⚠️ 重要安全提醒

### 🚨 立即执行（生产环境）
1. **更改默认密码**
   ```bash
   export ADMIN_PASSWORD='YourSecurePassword123!'
   ```

### 目录结构
```
tsbs_analytics/
├── app.py                    # 主应用程序
├── config.py                 # 安全配置
├── data_loader.py           # 数据加载器
├── change_password.py       # 密码管理工具
├── security_check.py        # 安全检查工具
├── start_secure.sh          # 安全启动脚本
├── templates/               # HTML模板
│   ├── login.html          # 安全登录页面
│   ├── index.html          # 主界面
│   └── baseline.html       # 基准配置
├── logs/                    # 日志目录
│   ├── app.log             # 主要应用日志
│   ├── app_error.log       # 错误日志
│   ├── security.log        # 安全审计日志
│   └── *.log              # 其他日志文件
```

## 🐛 故障排除

### 常见问题
1. **无法启动**
   ```bash
   # 检查端口占用
   netstat -tlnp | grep 5000
   # 检查Python版本
   python3 --version
   ```

2. **登录失败**
   ```bash
   # 检查密码配置
   echo $ADMIN_PASSWORD
   # 查看安全日志
   tail -20 logs/security.log
   ```

3. **权限错误**
   ```bash
   # 修复文件权限
   chmod 600 baseline_config.json
   chmod 644 app.py
   ```