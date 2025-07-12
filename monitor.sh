#!/bin/bash

# TSBS Analytics 监控脚本 - 用于检查应用健康状态

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

PID_FILE="$PROJECT_DIR/logs/app.pid"
LOG_FILE="$PROJECT_DIR/app.log"
ERROR_LOG_FILE="$PROJECT_DIR/app_error.log"
HEALTH_LOG="$PROJECT_DIR/health.log"

# 记录健康检查结果
log_health() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$HEALTH_LOG"
}

# 检查应用是否运行
check_process() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

# 检查端口是否监听
check_port() {
    if lsof -Pi :5001 -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0
    fi
    return 1
}

# 检查HTTP响应
check_http() {
    if command -v curl &> /dev/null; then
        if curl -s -o /dev/null -w "%{http_code}" http://localhost:5001/ | grep -q "200"; then
            return 0
        fi
    fi
    return 1
}

# 自动重启
auto_restart() {
    log_health "Application not responding, attempting restart..."
    echo "Application not responding, attempting restart..."
    
    # 停止应用
    ./stop.sh
    sleep 2
    
    # 启动应用
    ./start.sh
    sleep 5
    
    # 验证重启结果
    if check_process && check_port; then
        log_health "Application restarted successfully"
        echo "Application restarted successfully"
        return 0
    else
        log_health "Failed to restart application"
        echo "Failed to restart application"
        return 1
    fi
}

# 主监控逻辑
main() {
    local restart_needed=false
    
    # 检查进程
    if ! check_process; then
        log_health "Process not running"
        echo "Process not running"
        restart_needed=true
    fi
    
    # 检查端口
    if ! check_port; then
        log_health "Port 5001 not listening"
        echo "Port 5001 not listening"
        restart_needed=true
    fi
    
    # 检查HTTP响应（可选）
    if ! check_http; then
        log_health "HTTP health check failed"
        echo "HTTP health check failed"
        # 对于HTTP失败，我们可能不需要立即重启，只是记录
    fi
    
    # 如果需要重启
    if [ "$restart_needed" = true ]; then
        if [ "${1:-}" = "--auto-restart" ]; then
            auto_restart
        else
            echo "Use --auto-restart flag to automatically restart the application"
            exit 1
        fi
    else
        log_health "Application is healthy"
        echo "Application is healthy"
    fi
}

# 如果传入 --daemon 参数，则以守护进程方式运行
if [ "${1:-}" = "--daemon" ]; then
    while true; do
        main --auto-restart
        sleep 30  # 每30秒检查一次
    done
else
    main "$@"
fi
