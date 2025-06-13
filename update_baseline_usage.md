# update_baseline.py 使用指南

这个脚本已经被修改为通用脚本，可以指定使用哪天的某个分支结果来更新基线配置。

## 基本用法

### 1. 更新特定日期和分支的基线配置
```bash
python update_baseline.py --date 2025-06-03 --branch master
```

### 2. 使用简短参数
```bash
python update_baseline.py -d 2025-06-03 -b master
```

### 3. 指定输出文件
```bash
python update_baseline.py --date 2025-06-10 --branch feature-branch --output custom_baseline.json
```

### 4. 查看可用的日期和分支
```bash
python update_baseline.py --date 2025-06-03 --branch master --list-available
```

### 5. 干运行模式（查看会更新什么但不实际修改）
```bash
python update_baseline.py --date 2025-06-03 --branch master --dry-run
```

## 参数说明

- `--date, -d`: 必需，目标日期，格式为 YYYY-MM-DD
- `--branch, -b`: 必需，分支名称
- `--output, -o`: 可选，输出基线配置文件路径（默认：baseline_config.json）
- `--list-available`: 可选，列出数据中可用的日期和分支
- `--dry-run`: 可选，干运行模式，显示会更新什么但不实际修改文件

## 主要改进

1. **命令行参数支持**: 使用 argparse 支持命令行参数
2. **灵活的日期选择**: 可以指定任意日期，不再硬编码为 6月3日
3. **分支选择**: 可以指定任意分支，不再硬编码为 master
4. **输出文件选择**: 可以指定输出文件路径
5. **数据探索**: 可以列出可用的日期和分支
6. **干运行模式**: 可以预览会进行的更改
7. **错误处理**: 更好的错误处理和用户友好的错误信息
8. **备份功能**: 自动创建配置文件备份

## 示例场景

### 场景1：检查可用数据
```bash
python update_baseline.py -d 2025-06-03 -b master --list-available
```

### 场景2：测试特定分支的性能基线
```bash
python update_baseline.py -d 2025-06-10 -b feature-optimization --output optimization_baseline.json
```

### 场景3：安全预览更改
```bash
python update_baseline.py -d 2025-06-03 -b master --dry-run
```

### 场景4：正式更新基线
```bash
python update_baseline.py -d 2025-06-03 -b master
```
