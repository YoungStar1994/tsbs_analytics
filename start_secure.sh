#!/bin/bash

# TSBS Analytics 安全启动脚本
# 这个脚本演示了如何安全地启动应用程序
#
# 使用方法:
#   ./start_secure.sh         # 前台启动 (默认)
#   ./start_secure.sh -d      # 后台启动 (daemon模式)
#   ./start_secure.sh --daemon # 后台启动 (daemon模式)

echo "=== TSBS Analytics 安全启动脚本 ==="
echo

# 检查是否设置了自定义密码
if [ -z "$ADMIN_PASSWORD" ]; then
    echo "⚠️  警告: 未设置 ADMIN_PASSWORD 环境变量"
    echo "   系统将使用默认密码，这在生产环境中是不安全的"
    echo
    echo "建议设置自定义密码:"
    echo "   export ADMIN_PASSWORD='your_secure_password'"
    echo "   或运行: python3 change_password.py"
    echo
    
    # 检查是否在非交互式环境中运行
    if [ -t 0 ]; then
        read -p "是否继续使用默认密码? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "启动已取消"
            exit 1
        fi
    else
        echo "非交互式模式，自动使用默认密码"
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

# 设置安全的Flask环境变量
export FLASK_ENV=production
export FLASK_DEBUG=false

# 添加数据加载超时设置 - 避免加载过程无限等待
export TSBS_DATA_LOAD_TIMEOUT=60


# 创建日志目录
mkdir -p logs

# 设置文件权限
chmod 600 baseline_config.json 2>/dev/null || true
chmod 600 logs/*.log 2>/dev/null || true

echo "✓ 安全配置完成"
echo

# 检查是否需要后台启动
DAEMON_MODE=false
if [ "$1" = "--daemon" ] || [ "$1" = "-d" ]; then
    DAEMON_MODE=true
fi

# 启动应用
echo "启动 TSBS Analytics..."
echo "访问地址: http://localhost:5001"

if [ "$DAEMON_MODE" = true ]; then
    echo "后台启动模式"
else
    echo "前台启动模式 (按 Ctrl+C 停止服务)"
fi
echo

# 启动Flask应用
if [ "$DAEMON_MODE" = true ]; then
    # 后台启动，将输出重定向到日志文件
    nohup python3 app.py >> logs/app_startup.log 2>&1 &
    APP_PID=$!
    # 将PID写入文件以便后续管理
    echo $APP_PID > app.pid
else
    # 前台启动
    python3 app.py &
    APP_PID=$!
fi

EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "❌ 应用启动失败 (退出码: $EXIT_CODE)"
    echo "请检查日志文件获取详细错误信息 (logs/app.log, logs/app_error.log)"
    exit $EXIT_CODE
fi

echo "应用启动中... (PID: $APP_PID)"

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
        
        if [ "$DAEMON_MODE" = true ]; then
            echo "  - 启动日志: logs/app_startup.log"
            echo
            echo "✓ 应用已在后台运行"
            echo "使用 './stop.sh' 停止服务"
            echo "使用 './status.sh' 查看状态"
            exit 0
        else
            echo
            echo "按 Ctrl+C 停止服务"
            
            # 等待进程结束
            wait $APP_PID
            echo "应用已停止"
            exit 0
        fi
    fi
    echo "等待应用启动... ($i/15)"
    sleep 2
done

echo "❌ 应用启动超时，请检查日志文件"
kill $APP_PID 2>/dev/null
if [ "$DAEMON_MODE" = true ]; then
    rm -f app.pid
fi
exit 1
