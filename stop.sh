#!/bin/bash

# TSBS Analytics 停止脚本

# 设置项目目录
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# 设置PID文件路径
PID_FILE="$PROJECT_DIR/app.pid"

# 检查PID文件是否存在
if [ ! -f "$PID_FILE" ]; then
    echo "PID file not found. Application may not be running."
    # 尝试通过端口杀死进程
    echo "Trying to find process by port 5001..."
    PID=$(lsof -ti:5001)
    if [ ! -z "$PID" ]; then
        echo "Found process $PID listening on port 5001"
        kill -TERM $PID
        sleep 2
        if ps -p $PID > /dev/null 2>&1; then
            echo "Process still running, forcing kill..."
            kill -KILL $PID
        fi
        echo "Process stopped"
    else
        echo "No process found listening on port 5001"
    fi
    exit 0
fi

# 读取PID
PID=$(cat "$PID_FILE")

# 检查进程是否存在
if ! ps -p $PID > /dev/null 2>&1; then
    echo "Process with PID $PID is not running"
    rm -f "$PID_FILE"
    exit 0
fi

# 优雅停止
echo "Stopping application with PID $PID..."
kill -TERM $PID

# 等待进程停止
for i in {1..10}; do
    if ! ps -p $PID > /dev/null 2>&1; then
        echo "Application stopped successfully"
        rm -f "$PID_FILE"
        exit 0
    fi
    echo "Waiting for process to stop... ($i/10)"
    sleep 1
done

# 强制停止
echo "Force stopping application..."
kill -KILL $PID
sleep 1

if ! ps -p $PID > /dev/null 2>&1; then
    echo "Application force stopped"
    rm -f "$PID_FILE"
else
    echo "Failed to stop application"
    exit 1
fi
