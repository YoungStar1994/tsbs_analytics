# 🚀 TSBS Analytics

> 时间序列基准测试数据分析平台 - 安全增强版

## 📋 项目概述

TSBS Analytics是一个用于分析时间序列数据库基准测试结果的Web应用程序。本版本在原有功能基础上大幅增强了安全性，提供企业级的安全保护。

## ⚡ 快速开始

### 🚀 一键启动（最简单）
```bash
# 后台启动，无需交互
./quick_start.sh
```
- **访问地址**: http://localhost:5001
- **默认账号**: admin / Tsbs2024

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

## 🛡️ 安全特性

### 核心安全功能
- ✅ **后端认证系统** - 替代不安全的前端验证
- ✅ **密码哈希存储** - SHA256加密，支持环境变量
- ✅ **会话管理** - 8小时自动过期，安全Cookie配置
- ✅ **登录保护** - 5次失败尝试后锁定30分钟
- ✅ **审计日志** - 完整的安全事件记录
- ✅ **路由保护** - 所有敏感页面需要登录验证

### 安全工具
- **密码管理**: `python3 change_password.py`
- **安全检查**: `python3 security_check.py`  
- **安全启动**: `./start_secure.sh`

## 📚 文档指南

| 文档 | 用途 | 目标用户 |
|------|------|---------|
| [安全使用指南](SECURITY_GUIDE.md) | 详细的安全配置和使用说明 | 管理员、运维 |
| [部署检查清单](DEPLOYMENT_CHECKLIST.md) | 生产部署前的安全检查 | 部署工程师 |
| [安全策略](SECURITY_POLICY.md) | 企业级安全策略文档 | 安全团队、管理层 |
| [安全改进摘要](SECURITY_SUMMARY.md) | 安全改进概览和对比 | 所有用户 |

## ⚠️ 重要安全提醒

### 🚨 立即执行（生产环境）
1. **更改默认密码**
   ```bash
   export ADMIN_PASSWORD='YourSecurePassword123!'
   ```

2. **运行安全检查**
   ```bash
   python3 security_check.py
   ```

3. **启用HTTPS**
   ```bash
   # 配置SSL证书和反向代理
   ```

### 🔍 安全验证
```bash
# 验证密码保护
curl -X POST http://localhost:5000/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"wrong"}'
# 应返回401错误

# 验证路由保护  
curl http://localhost:5000/
# 未登录应跳转到登录页
```

## 🏗️ 系统架构

### 技术栈
- **后端**: Flask (Python)
- **前端**: HTML + JavaScript + CSS
- **数据处理**: Pandas
- **认证**: Flask Session
- **安全**: 自定义安全中间件

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

## 📊 功能特性

### 数据分析功能
- 📈 **性能数据可视化** - 多维度图表展示
- 🔧 **灵活筛选** - 按分支、规模、查询类型等筛选
- 📋 **基准值管理** - 配置和管理性能基准
- 📊 **统计分析** - 平均值、百分位数等统计指标

### 用户界面
- 🎨 **现代化设计** - 响应式、美观的用户界面
- 🔐 **安全登录** - 安全的用户认证系统
- 🚀 **快速操作** - 直观的操作流程
- 📱 **移动友好** - 支持移动设备访问

## 🔧 开发指南

### 开发环境设置
```bash
# 1. 克隆项目
git clone <repository-url>
cd tsbs_analytics

# 2. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 3. 安装依赖
pip install flask pandas

# 4. 设置开发密码
export ADMIN_PASSWORD='DevPassword123!'

# 5. 启动开发服务器
python3 app.py
```

### 代码贡献
1. 遵循安全编码规范
2. 所有PR需要通过安全检查
3. 更新相关文档
4. 添加适当的测试

## 🚀 部署指南

### 生产环境部署
1. **系统要求**
   - Python 3.7+
   - 2GB+ RAM
   - 10GB+ 磁盘空间

2. **部署步骤**
   ```bash
   # 1. 准备环境
   sudo apt update && sudo apt install python3 python3-pip nginx

   # 2. 配置应用
   git clone <repository-url>
   cd tsbs_analytics
   pip install -r requirements.txt

   # 3. 安全配置
   export ADMIN_PASSWORD='ProductionPassword123!'
   python3 security_check.py

   # 4. 配置服务
   sudo cp tsbs-analytics.service /etc/systemd/system/
   sudo systemctl enable tsbs-analytics
   sudo systemctl start tsbs-analytics

   # 5. 配置Nginx反向代理
   # (参考SECURITY_GUIDE.md中的配置)
   ```

3. **部署检查**
   ```bash
   # 使用部署检查清单
   python3 security_check.py
   systemctl status tsbs-analytics
   curl -k https://yourdomain.com/login.html
   ```

## 📋 系统要求

### 最低要求
- **OS**: Linux/macOS/Windows
- **Python**: 3.7+
- **RAM**: 1GB
- **磁盘**: 5GB

### 推荐配置
- **OS**: Ubuntu 20.04+ / CentOS 8+
- **Python**: 3.9+
- **RAM**: 4GB+
- **磁盘**: 20GB+
- **网络**: 稳定的互联网连接

## 🔒 安全最佳实践

### 生产环境必须
- [ ] 更改默认密码
- [ ] 启用HTTPS
- [ ] 配置防火墙
- [ ] 设置监控告警
- [ ] 定期安全检查

### 日常维护
- [ ] 监控安全日志
- [ ] 定期更新系统
- [ ] 备份重要配置
- [ ] 审查访问模式

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

## 📞 技术支持

### 获取帮助
- **文档**: 查看相关安全文档
- **日志**: 检查 `logs/app_error.log` 和 `logs/security.log`
- **工具**: 使用 `security_check.py` 诊断问题

### 报告问题
如发现bug或安全问题，请提供：
- 详细的错误描述
- 系统环境信息
- 相关日志内容
- 复现步骤

## 📜 更新日志

### v2.0.0 (2024-06-13) - 安全增强版
- 🔐 实现完整的后端认证系统
- 🔑 添加密码安全管理功能
- 📊 集成安全审计日志
- 🛡️ 强化会话安全机制
- 🔧 提供安全管理工具
- 📚 完善安全文档体系

### v1.x.x (历史版本)
- 基础数据分析功能
- 前端界面实现
- 数据可视化组件

## 📄 许可证

本项目遵循 [MIT License](LICENSE) 开源协议。

## 🤝 贡献指南

欢迎贡献代码！请注意：
1. 所有贡献必须通过安全审查
2. 遵循项目的安全编码规范
3. 更新相关文档
4. 添加适当的测试覆盖

---

## ⚡ 快速链接

- 🔐 [安全使用指南](SECURITY_GUIDE.md) - 必读安全文档
- 📋 [部署检查清单](DEPLOYMENT_CHECKLIST.md) - 生产部署指南
- 🛡️ [安全策略](SECURITY_POLICY.md) - 企业安全策略
- 📊 [安全改进摘要](SECURITY_SUMMARY.md) - 安全改进概览

---

**⚠️ 安全提醒**: 在生产环境使用前，请务必阅读安全文档并完成所有安全配置！
