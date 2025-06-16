# TSBS Analytics 进程管理

## 快速使用

### 启动应用
```bash
./start.sh
```

### 停止应用
```bash
./stop.sh
```

### 重启应用
```bash
./restart.sh
```

### 查看状态
```bash
./status.sh
```

## 系统服务方式运行（可选）

如果你想要应用随系统启动，可以安装为系统服务：

### Linux 系统
```bash
# 复制服务文件
sudo cp tsbs-analytics.service /etc/systemd/system/

# 重新加载系统服务
sudo systemctl daemon-reload

# 启用服务（开机自启）
sudo systemctl enable tsbs-analytics

# 启动服务
sudo systemctl start tsbs-analytics

# 查看服务状态
sudo systemctl status tsbs-analytics

# 查看服务日志
sudo journalctl -u tsbs-analytics -f
```

### macOS 系统
```bash
# 创建 plist 文件
cat > com.tsbs.analytics.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.tsbs.analytics</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/yangxing/Downloads/tsbs_analytics/start.sh</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/yangxing/Downloads/tsbs_analytics</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/yangxing/Downloads/tsbs_analytics/logs/launchd.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/yangxing/Downloads/tsbs_analytics/logs/launchd_error.log</string>
</dict>
</plist>
EOF

# 复制到 LaunchAgents 目录
cp com.tsbs.analytics.plist ~/Library/LaunchAgents/

# 加载服务
launchctl load ~/Library/LaunchAgents/com.tsbs.analytics.plist

# 启动服务
launchctl start com.tsbs.analytics

# 查看服务状态
launchctl list | grep tsbs
```

## 日志文件

- `app.log` - 应用主日志
- `app_error.log` - 错误日志
- `app.pid` - 进程ID文件

## 监控和维护

### 查看实时日志
```bash
# 查看主日志
tail -f app.log

# 查看错误日志
tail -f app_error.log
```

### 清理日志
```bash
# 清理旧日志（保留最近1000行）
tail -1000 app.log > app.log.tmp && mv app.log.tmp app.log
tail -1000 app_error.log > app_error.log.tmp && mv app_error.log.tmp app_error.log
```

### 性能监控
```bash
# 查看应用资源使用情况
./status.sh

# 查看端口占用
lsof -i :5001

# 查看进程详情
ps aux | grep python3 | grep app.py
```

## 故障排除

### 常见问题

1. **端口被占用**
   ```bash
   # 查找占用端口的进程
   lsof -i :5001
   
   # 杀死占用进程
   kill -9 $(lsof -ti:5001)
   ```

2. **权限问题**
   ```bash
   # 添加执行权限
   chmod +x *.sh
   ```

3. **Python依赖问题**
   ```bash
   # 安装依赖
   pip3 install flask pandas
   ```

4. **数据加载问题**
   - 检查数据目录路径是否正确
   - 查看 `app_error.log` 获取详细错误信息

### 手动启动（调试模式）
```bash
# 前台运行用于调试
python3 app.py
```

## 配置修改

如需修改端口或其他配置，请编辑 `app.py` 文件的最后几行：

```python
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False)
```
