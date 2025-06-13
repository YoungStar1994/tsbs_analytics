#!/bin/bash

# TSBS Analytics 后台启动脚本

# 设置项目目录
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# 设置PID文件路径
PID_FILE="$PROJECT_DIR/app.pid"
LOG_FILE="$PROJECT_DIR/logs/nohup.out"
ERROR_LOG_FILE="$PROJECT_DIR/logs/app_error.log"

# 检查是否已经在运行
if [ -f "$PID_FILE" ]; then
    if ps -p $(cat "$PID_FILE") > /dev/null 2>&1; then
        echo "Application is already running with PID $(cat $PID_FILE)"
        exit 1
    else
        echo "Removing stale PID file"
        rm -f "$PID_FILE"
    fi
fi

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "Python3 is not installed"
    exit 1
fi

# 检查依赖
echo "Checking dependencies..."
python3 -c "import flask, pandas" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Installing required dependencies..."
    pip3 install flask pandas
fi

# 创建日志目录
mkdir -p logs

# 启动应用
echo "Starting TSBS Analytics application..."
nohup python3 app.py > "$LOG_FILE" 2> "$ERROR_LOG_FILE" &

# 保存PID
echo $! > "$PID_FILE"

# 等待几秒检查启动状态
sleep 3

if ps -p $(cat "$PID_FILE") > /dev/null 2>&1; then
    echo "Application started successfully with PID $(cat $PID_FILE)"
    echo "Log file: $LOG_FILE"
    echo "Error log file: $ERROR_LOG_FILE"
    echo "Access the application at: http://localhost:5001"
else
    echo "Failed to start application"
    echo "Check error log: $ERROR_LOG_FILE"
    rm -f "$PID_FILE"
    exit 1
fi
