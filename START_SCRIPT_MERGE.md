# 启动脚本合并完成说明

## 概述
已成功将 `start_optimized.sh` 和 `start_secure.sh` 的功能合并到统一的 `start.sh` 脚本中。

## 新的启动脚本功能

### 1. 命令行参数支持
- `./start.sh` - 前台启动（默认模式）
- `./start.sh -d` 或 `./start.sh --daemon` - 后台启动
- `./start.sh -o` 或 `./start.sh --optimized` - 性能优化模式
- `./start.sh -h` 或 `./start.sh --help` - 显示帮助信息

### 2. 性能优化功能（来自 start_optimized.sh）
当使用 `--optimized` 参数时：
- `TSBS_DATA_LOAD_TIMEOUT=30` - 降低数据加载超时时间
- `OMP_NUM_THREADS=4` - 限制OpenMP线程数
- `PYTHONOPTIMIZE=1` - 启用Python优化

### 3. 安全检查功能（来自 start_secure.sh）
- 检查是否设置了自定义管理员密码
- 在前台模式下提供交互式密码确认
- 在后台模式下自动使用默认密码并给出警告
- 设置适当的文件权限保护敏感文件

### 4. 智能启动模式
- **前台模式**：等待应用启动并检查健康状态，按Ctrl+C停止
- **后台模式**：后台运行并创建PID文件，支持通过stop.sh停止

### 5. 全面的状态检查
- 检查是否已有实例在运行
- Python依赖检查
- 启动后的健康状态验证
- 详细的日志信息输出

## 基准值比较功能修复

### 问题解决
修复了表格中对比列显示"--"的问题：

1. **数据迭代问题**：修正了DataFrame行迭代的方式
2. **精度控制**：基准值比较结果现在保留两位小数
3. **错误处理**：增强了对无效数据的处理

### 基准值计算
- `calculate_performance_percentage()` - 用于导入速度等"越大越好"的指标
- `calculate_performance_percentage_reverse()` - 用于查询延迟等"越小越好"的指标
- 所有结果都使用 `round(result, 2)` 保留两位小数

## 使用建议

### 开发环境
```bash
./start.sh  # 前台启动，便于调试
```

### 生产环境
```bash
export ADMIN_PASSWORD='your_secure_password'
./start.sh --daemon --optimized  # 后台优化启动
```

### 快速测试
```bash
./start.sh --optimized  # 前台优化启动
```

## 文件清理建议
现在可以安全删除以下文件：
- `start_optimized.sh`
- `start_secure.sh`

因为它们的功能已经完全集成到新的 `start.sh` 中。

## 相关脚本
- `./stop.sh` - 停止应用
- `./restart.sh` - 重启应用
- `./status.sh` - 查看状态
