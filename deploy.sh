#!/bin/bash

# TSBS Analytics 一键部署脚本

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "=== TSBS Analytics 一键部署 ==="
echo "项目目录: $PROJECT_DIR"

# 检查Python环境
echo "检查Python环境..."
if ! command -v python3 &> /dev/null; then
    echo "错误: Python3 未安装"
    echo "请先安装Python3: https://www.python.org/downloads/"
    exit 1
fi

echo "Python版本: $(python3 --version)"

# 检查pip
if ! command -v pip3 &> /dev/null; then
    echo "错误: pip3 未安装"
    exit 1
fi

# 安装依赖
echo "安装Python依赖..."
pip3 install flask pandas || {
    echo "错误: 依赖安装失败"
    exit 1
}

# 设置脚本权限
echo "设置脚本权限..."
chmod +x *.sh

# 创建必要的目录
echo "创建目录结构..."
mkdir -p logs

# 停止现有实例（如果有）
echo "停止现有实例..."
if [ -f "stop.sh" ]; then
    ./stop.sh
fi

# 启动应用
echo "启动应用..."
./start.sh

# 等待启动
echo "等待应用启动..."
sleep 5

# 检查状态
echo "检查应用状态..."
./status.sh

echo ""
echo "=== 部署完成 ==="
echo "应用地址: http://localhost:5001"
echo ""
echo "常用命令:"
echo "  启动应用: ./start.sh"
echo "  停止应用: ./stop.sh"
echo "  重启应用: ./restart.sh"
echo "  查看状态: ./status.sh"
echo "  监控应用: ./monitor.sh"
echo ""
echo "日志文件:"
echo "  主日志: logs/app.log"
echo "  错误日志: logs/app_error.log"
echo "  健康日志: logs/health.log"
