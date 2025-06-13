# TSBS Analytics 启动指南

## 启动方式

### 1. 前台启动（默认）
```bash
./start_secure.sh
```
- 应用程序在前台运行
- 可以直接看到实时日志输出
- 按 Ctrl+C 停止服务
- 适合开发和调试

### 2. 后台启动（推荐生产环境）
```bash
./start_secure.sh --daemon
# 或者
./start_secure.sh -d
```
- 应用程序在后台运行
- 不占用终端
- 日志输出到文件
- 适合生产环境

## 管理命令

### 查看状态
```bash
./status.sh
```
显示应用程序运行状态、内存使用、日志信息等

### 停止服务
```bash
./stop.sh
```
安全停止应用程序

### 重启服务
```bash
./restart.sh
```
重启应用程序（保留配置）

## 日志文件

- `logs/app.log` - 主要应用日志
- `logs/app_error.log` - 错误日志
- `logs/app_startup.log` - 启动日志（后台模式时）
- `logs/security.log` - 安全审计日志

## 访问应用

启动成功后，在浏览器中访问：
```
http://localhost:5001
```

默认登录信息：
- 用户名: admin
- 密码: Tsbs2024

## 安全建议

### 生产环境部署
1. 设置自定义密码：
   ```bash
   export ADMIN_PASSWORD='your_secure_password'
   ./start_secure.sh --daemon
   ```

2. 或使用密码修改工具：
   ```bash
   python3 change_password.py
   ```

3. 确保日志文件权限正确：
   ```bash
   chmod 600 logs/*.log
   ```

## 故障排除

### 端口被占用
```bash
# 查看端口占用
lsof -i :5001

# 强制停止
./stop.sh
```

### 查看详细错误
```bash
# 查看错误日志
tail -f logs/app_error.log

# 查看主日志
tail -f logs/app.log
```

### 重置应用
```bash
./stop.sh
rm -f app.pid
./start_secure.sh --daemon
```
