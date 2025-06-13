# TSBS Analytics 性能优化配置

## 环境变量配置
# 数据加载超时时间（秒）
TSBS_DATA_LOAD_TIMEOUT=30

# 数据路径（可选，如果不设置会使用默认路径）
# TSBS_DATA_PATH=/path/to/your/data

## Python运行时优化
# 启用字节码优化
PYTHONOPTIMIZE=1

# 禁用调试模式
FLASK_ENV=production

# 确保输出不缓冲
PYTHONUNBUFFERED=1

# 限制OpenMP线程数（避免CPU过载）
OMP_NUM_THREADS=4

## Flask应用配置
# 服务器配置
FLASK_HOST=0.0.0.0
FLASK_PORT=5001
FLASK_DEBUG=False
FLASK_THREADED=True

## 日志配置
# 日志级别 (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO

## 缓存配置
# 选项缓存时间（秒）
OPTIONS_CACHE_TTL=300

# 数据缓存时间（秒）
DATA_CACHE_TTL=300

# 最大缓存条目数
MAX_CACHE_ENTRIES=20

## 性能调优建议

### 1. 数据库优化
# - 确保数据目录在SSD上
# - 定期清理旧数据
# - 使用合适的目录结构

### 2. 系统优化
# - 增加系统内存
# - 使用较新版本的Python (3.9+)
# - 安装优化版本的pandas和numpy

### 3. 网络优化
# - 使用CDN加载前端资源
# - 启用gzip压缩
# - 减少HTTP请求数量

### 4. 应用优化
# - 启用缓存机制
# - 使用异步加载
# - 限制单次返回的数据量

## 故障排除

### 启动慢的原因及解决方案：
1. 数据量过大：
   - 减少TSBS_DATA_LOAD_TIMEOUT
   - 使用异步加载（已启用）
   - 清理旧数据

2. 文件监控问题：
   - 检查文件系统权限
   - 减少监控的目录数量

3. 依赖库问题：
   - 更新到最新版本的pandas
   - 检查watchdog库兼容性

### 筛选慢的原因及解决方案：
1. 数据量大：
   - 启用缓存（已启用）
   - 使用索引优化
   - 限制返回结果数量

2. 前端渲染慢：
   - 使用虚拟滚动
   - 分页显示
   - 减少DOM操作

3. 网络延迟：
   - 使用本地部署
   - 优化JSON传输
   - 启用压缩

## 监控命令

# 查看应用状态
./status.sh

# 查看实时日志
tail -f logs/app.log

# 查看性能指标
top -p $(cat app.pid)

# 查看内存使用
ps aux | grep python
