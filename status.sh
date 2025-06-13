#!/bin/bash

# TSBS Analytics 状态检查脚本

# 设置项目目录
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# 设置PID文件路径
PID_FILE="$PROJECT_DIR/app.pid"
LOG_FILE="$PROJECT_DIR/logs/app.log"
ERROR_LOG_FILE="$PROJECT_DIR/logs/app_error.log"

echo "=== TSBS Analytics Status ==="

# 检查PID文件
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    echo "PID file exists: $PID"
    
    # 检查进程是否运行
    if ps -p $PID > /dev/null 2>&1; then
        echo "Status: RUNNING (PID: $PID)"
        
        # 检查端口
        if lsof -Pi :5001 -sTCP:LISTEN -t >/dev/null; then
            echo "Port 5001: LISTENING"
            echo "Application URL: http://localhost:5001"
        else
            echo "Port 5001: NOT LISTENING"
        fi
        
        # 显示进程信息
        echo "Process info:"
        ps -p $PID -o pid,ppid,user,start,time,command
        
        # 显示内存使用
        echo "Memory usage:"
        ps -p $PID -o pid,rss,vsz,%mem,command
        
    else
        echo "Status: NOT RUNNING (stale PID file)"
        echo "Removing stale PID file..."
        rm -f "$PID_FILE"
    fi
else
    echo "PID file: NOT FOUND"
    
    # 检查是否有进程在监听端口5001
    PID=$(lsof -ti:5001)
    if [ ! -z "$PID" ]; then
        echo "Status: UNKNOWN (process $PID listening on port 5001)"
        echo "Process info:"
        ps -p $PID -o pid,ppid,user,start,time,command
    else
        echo "Status: NOT RUNNING"
    fi
fi

echo ""
echo "=== Log Files ==="
if [ -f "$LOG_FILE" ]; then
    echo "Main log: $LOG_FILE ($(wc -l < "$LOG_FILE") lines)"
    echo "Last 5 lines:"
    tail -5 "$LOG_FILE"
else
    echo "Main log: NOT FOUND"
fi

echo ""
if [ -f "$ERROR_LOG_FILE" ]; then
    echo "Error log: $ERROR_LOG_FILE ($(wc -l < "$ERROR_LOG_FILE") lines)"
    if [ -s "$ERROR_LOG_FILE" ]; then
        echo "Last 5 error lines:"
        tail -5 "$ERROR_LOG_FILE"
    else
        echo "No errors logged"
    fi
else
    echo "Error log: NOT FOUND"
fi

echo ""
echo "=== Disk Usage ==="
du -sh "$PROJECT_DIR"

echo ""
echo "=== Available Commands ==="
echo "Start:   ./start.sh"
echo "Stop:    ./stop.sh"
echo "Restart: ./restart.sh"
echo "Status:  ./status.sh"
