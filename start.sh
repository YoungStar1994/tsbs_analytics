#!/bin/bash

# TSBS Analytics 统一启动脚本
# 集成了安全检查和性能优化功能
#
# 使用方法:
#   ./start.sh                # 前台启动 (默认)
#   ./start.sh -d             # 后台启动 (daemon模式)
#   ./start.sh --daemon       # 后台启动 (daemon模式)
#   ./start.sh --optimized    # 性能优化模式启动

echo "=== TSBS Analytics 启动脚本 ==="
echo

# 解析命令行参数
DAEMON_MODE=false
OPTIMIZED_MODE=false

for arg in "$@"; do
    case $arg in
        --daemon|-d)
            DAEMON_MODE=true
            shift
            ;;
        --optimized|-o)
            OPTIMIZED_MODE=true
            shift
            ;;
        --help|-h)
            echo "使用方法:"
            echo "  $0                # 前台启动"
            echo "  $0 -d|--daemon    # 后台启动"
            echo "  $0 -o|--optimized # 性能优化模式"
            echo "  $0 -h|--help      # 显示帮助"
            exit 0
            ;;
        *)
            echo "未知参数: $arg"
            echo "使用 $0 --help 查看帮助"
            exit 1
            ;;
    esac
done

# 性能优化设置
if [ "$OPTIMIZED_MODE" = true ]; then
    echo "🚀 启用性能优化模式"
    export TSBS_DATA_LOAD_TIMEOUT=30  # 降低超时时间到30秒
    export OMP_NUM_THREADS=4  # 限制OpenMP线程数
    export PYTHONOPTIMIZE=1   # 启用Python优化
    echo "✓ 性能优化配置完成"
else
    export TSBS_DATA_LOAD_TIMEOUT=60  # 标准超时时间
fi

# 通用环境变量设置
export FLASK_ENV=production
export FLASK_DEBUG=false
export PYTHONUNBUFFERED=1

# 检查是否已有实例在运行
PID_FILE="app.pid"
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p $PID > /dev/null 2>&1; then
        echo "⚠️  应用已在运行 (PID: $PID)"
        echo "如需重启，请先运行: ./stop.sh"
        exit 1
    else
        echo "发现过期的PID文件，正在清理..."
        rm -f "$PID_FILE"
    fi
fi

# 安全检查：检查是否设置了自定义密码
if [ -z "$ADMIN_PASSWORD" ]; then
    echo "⚠️  警告: 未设置 ADMIN_PASSWORD 环境变量"
    echo "   系统将使用默认密码，这在生产环境中是不安全的"
    echo
    echo "建议设置自定义密码:"
    echo "   export ADMIN_PASSWORD='your_secure_password'"
    echo "   或运行: python3 change_password.py"
    echo
    
    # 检查是否在非交互式环境中运行
    if [ -t 0 ] && [ "$DAEMON_MODE" = false ]; then
        read -p "是否继续使用默认密码? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "启动已取消"
            exit 1
        fi
    else
        echo "后台模式或非交互式环境，自动使用默认密码"
    fi
else
    echo "✓ 检测到自定义密码配置"
fi

# 检查Python依赖
echo "检查Python依赖..."
python3 -c "import flask, pandas" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "✗ Python依赖检查失败"
    echo "请运行: pip install flask pandas"
    exit 1
fi
echo "✓ Python依赖检查通过"

# 创建日志目录
mkdir -p logs

# 设置文件权限（安全措施）
chmod 600 baseline_config.json 2>/dev/null || true
chmod 600 logs/*.log 2>/dev/null || true

echo "✓ 安全配置完成"
echo

# 显示启动信息
echo "启动 TSBS Analytics..."
echo "启动时间: $(date)"
echo "访问地址: http://localhost:5001"

if [ "$DAEMON_MODE" = true ]; then
    echo "模式: 后台启动"
else
    echo "模式: 前台启动 (按 Ctrl+C 停止服务)"
fi

if [ "$OPTIMIZED_MODE" = true ]; then
    echo "优化: 性能优化模式已启用"
fi
echo

# 启动应用
if [ "$DAEMON_MODE" = true ]; then
    # 后台启动，将输出重定向到日志文件
    nohup python3 app.py > logs/app_startup.log 2>&1 &
    APP_PID=$!
    # 将PID写入文件以便后续管理
    echo $APP_PID > "$PID_FILE"
    
    echo "应用已启动 (PID: $APP_PID)"
    echo "启动日志: logs/app_startup.log"
    echo "应用日志: logs/app.log"
    
    # 等待几秒确认启动状态
    echo "等待应用启动..."
    sleep 5
    
    # 检查进程是否还在运行
    if ps -p $APP_PID > /dev/null 2>&1; then
        echo "✓ 应用启动成功"
        echo "访问地址: http://localhost:5001"
        echo "查看日志: tail -f logs/app.log"
        echo "停止应用: ./stop.sh"
        echo "查看状态: ./status.sh"
    else
        echo "✗ 应用启动失败，请检查日志文件"
        rm -f "$PID_FILE"
        exit 1
    fi
else
    # 前台启动
    echo "正在启动应用..."
    python3 app.py &
    APP_PID=$!
    
    # 等待应用启动
    echo "正在检查应用状态..."
    for i in {1..15}; do
        if curl -s http://localhost:5001/login.html > /dev/null 2>&1; then
            echo "✓ TSBS Analytics 启动成功！"
            echo
            echo "应用信息:"
            echo "  - 访问地址: http://localhost:5001"
            echo "  - 进程ID: $APP_PID"
            echo "  - 日志文件: logs/app.log, logs/app_error.log"
            echo
            echo "按 Ctrl+C 停止服务"
            
            # 等待进程结束
            wait $APP_PID
            echo "应用已停止"
            exit 0
        fi
        echo "等待应用启动... ($i/15)"
        sleep 2
    done
    
    echo "❌ 应用启动超时，请检查日志文件"
    kill $APP_PID 2>/dev/null
    exit 1
fi
