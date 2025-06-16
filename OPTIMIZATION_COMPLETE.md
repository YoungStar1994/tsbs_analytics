# TSBS Analytics 后台运行优化完成

## 🎉 优化内容

经过优化，TSBS Analytics 现在支持完善的后台运行方式，包括：

### ✅ 核心改进

1. **完善的进程管理**
   - PID 文件管理
   - 优雅的启动/停止
   - 信号处理机制
   - 自动清理

2. **丰富的日志系统**
   - 分离的主日志和错误日志
   - 文件日志 + 控制台输出
   - 健康检查日志
   - 日志轮转支持

3. **多种运行模式**
   - 开发模式（Flask 内置服务器）
   - 生产模式（Gunicorn WSGI 服务器）
   - 系统服务模式

4. **监控和健康检查**
   - 进程状态监控
   - 端口监听检查
   - HTTP 健康检查
   - 自动重启功能

## 🚀 使用方法

### 快速开始
```bash
# 一键部署（推荐新用户）
./deploy.sh

# 或者使用管理脚本
./manage.sh deploy
```

### 基本操作
```bash
# 启动应用（开发模式）
./manage.sh start

# 启动应用（生产模式）
./manage.sh start prod

# 停止应用
./manage.sh stop

# 重启应用
./manage.sh restart

# 查看状态
./manage.sh status
```

### 日志管理
```bash
# 查看主日志
./manage.sh logs

# 查看错误日志
./manage.sh logs error

# 查看访问日志（生产模式）
./manage.sh logs access

# 查看健康检查日志
./manage.sh logs health
```

### 监控和维护
```bash
# 一次性健康检查
./monitor.sh

# 持续监控（自动重启）
./monitor.sh --auto-restart

# 或使用管理脚本
./manage.sh monitor

# 清理日志和临时文件
./manage.sh clean
```

## 📁 文件说明

### 核心脚本
- `manage.sh` - 主管理脚本（推荐使用）
- `start.sh` - 开发模式启动脚本
- `start_gunicorn.sh` - 生产模式启动脚本
- `stop.sh` - 停止脚本
- `restart.sh` - 重启脚本
- `status.sh` - 状态检查脚本
- `monitor.sh` - 监控脚本
- `deploy.sh` - 一键部署脚本

### 配置文件
- `gunicorn.conf.py` - Gunicorn 生产环境配置
- `tsbs-analytics.service` - 系统服务配置

### 日志文件
- `app.log` - 主日志
- `app_error.log` - 错误日志
- `health.log` - 健康检查日志
- `logs/gunicorn_access.log` - 访问日志（生产模式）
- `logs/gunicorn_error.log` - Gunicorn 错误日志

### 进程文件
- `app.pid` - 开发模式进程ID
- `gunicorn.pid` - 生产模式进程ID

## 🔧 高级配置

### 系统服务（开机自启）

#### Linux 系统
```bash
# 安装系统服务
sudo cp tsbs-analytics.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable tsbs-analytics
sudo systemctl start tsbs-analytics
```

#### macOS 系统
```bash
# 创建 LaunchAgent
cp com.tsbs.analytics.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.tsbs.analytics.plist
```

### 性能调优

#### 生产环境配置
编辑 `gunicorn.conf.py`：
```python
# Worker 数量（CPU 核心数 * 2 + 1）
workers = multiprocessing.cpu_count() * 2 + 1

# 连接数限制
worker_connections = 1000

# 超时设置
timeout = 120

# 内存限制
max_requests = 1000
```

#### 监控频率
编辑 `monitor.sh`：
```bash
# 修改监控间隔（默认30秒）
sleep 30
```

## 📊 监控和告警

### 实时监控
```bash
# 查看实时日志
tail -f app.log

# 查看实时错误日志
tail -f app_error.log

# 查看系统资源使用
./status.sh
```

### 性能指标
- 内存使用量
- CPU 使用率
- 响应时间
- 错误率
- 活跃连接数

## 🛠️ 故障排除

### 常见问题

1. **端口占用**
   ```bash
   ./manage.sh stop  # 强制停止所有相关进程
   ```

2. **权限问题**
   ```bash
   chmod +x *.sh
   ```

3. **依赖缺失**
   ```bash
   pip3 install flask pandas gunicorn
   ```

4. **数据加载失败**
   ```bash
   ./manage.sh logs error  # 查看详细错误信息
   ```

### 调试模式
```bash
# 前台运行用于调试
python3 app.py
```

## 🎯 最佳实践

1. **生产环境使用 Gunicorn**
   ```bash
   ./manage.sh start prod
   ```

2. **定期监控健康状态**
   ```bash
   # 添加到 crontab
   */5 * * * * /path/to/tsbs_analytics/monitor.sh >/dev/null 2>&1
   ```

3. **日志轮转**
   ```bash
   # 定期清理日志
   ./manage.sh clean
   ```

4. **备份重要配置**
   - `baseline_config.json`
   - 自定义配置文件

## 📞 技术支持

如果遇到问题，请：

1. 查看日志文件获取详细错误信息
2. 检查系统资源使用情况
3. 确认网络端口没有被占用
4. 验证 Python 环境和依赖包

---

**现在你的 TSBS Analytics 应用已经完全支持后台运行！** 🎉

使用 `./manage.sh help` 查看所有可用命令。
