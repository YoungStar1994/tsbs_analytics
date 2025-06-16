#!/bin/bash

# TSBS Analytics 重启脚本

# 设置项目目录
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "Restarting TSBS Analytics application..."

# 停止应用
echo "Stopping application..."
./stop.sh

# 等待一秒
sleep 1

# 启动应用
echo "Starting application..."
./start.sh
