from flask import Flask, render_template, request, jsonify, redirect, url_for
from data_loader import loader
from datetime import datetime
import pandas as pd
import logging
import json
import os
import signal
import sys
import atexit

# 配置日志 - 支持文件输出
def setup_logging():
    """设置日志配置"""
    log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # 创建文件处理器
    file_handler = logging.FileHandler('app.log', encoding='utf-8')
    file_handler.setFormatter(log_formatter)
    file_handler.setLevel(logging.INFO)
    
    # 创建错误文件处理器
    error_handler = logging.FileHandler('app_error.log', encoding='utf-8')
    error_handler.setFormatter(log_formatter)
    error_handler.setLevel(logging.ERROR)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)
    console_handler.setLevel(logging.INFO)
    
    # 配置根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(error_handler)
    root_logger.addHandler(console_handler)

setup_logging()

app = Flask(__name__)

# 基准值配置文件路径
BASELINE_CONFIG_FILE = 'baseline_config.json'
PID_FILE = 'app.pid'

def write_pid_file():
    """写入PID文件"""
    try:
        with open(PID_FILE, 'w') as f:
            f.write(str(os.getpid()))
        logging.info(f"PID file written: {PID_FILE} (PID: {os.getpid()})")
    except Exception as e:
        logging.error(f"Failed to write PID file: {e}")

def remove_pid_file():
    """删除PID文件"""
    try:
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
            logging.info(f"PID file removed: {PID_FILE}")
    except Exception as e:
        logging.error(f"Failed to remove PID file: {e}")

def signal_handler(signum, frame):
    """信号处理器"""
    logging.info(f"Received signal {signum}, shutting down gracefully...")
    remove_pid_file()
    sys.exit(0)

# 注册信号处理器
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# 注册退出处理器
atexit.register(remove_pid_file)

def convert_to_beijing_time(dt):
    """原始时间已经是北京时间，直接返回"""
    if pd.isna(dt):
        return None
    if isinstance(dt, str):
        try:
            dt = pd.to_datetime(dt)
        except:
            return dt
    return dt

def format_datetime_for_display(dt):
    """格式化日期时间用于显示（原始时间已经是北京时间）"""
    if pd.isna(dt) or dt is None:
        return None
    if isinstance(dt, str):
        try:
            dt = pd.to_datetime(dt)
        except:
            return str(dt)
    return dt.strftime('%Y-%m-%d %H:%M:%S')

def format_datetime_for_chart(dt):
    """格式化日期时间用于图表（年月日时分，原始时间已经是北京时间）"""
    if pd.isna(dt) or dt is None:
        return None
    if isinstance(dt, str):
        try:
            dt = pd.to_datetime(dt)
        except:
            return str(dt)
    return dt.strftime('%Y-%m-%d %H:%M')

@app.route('/')
def index():
    """主页面展示筛选表单，增加错误处理"""
    try:
        options = loader.get_options()
        return render_template('index.html', 
                               branches=options['branches'],
                               query_types=options['query_types'],
                               scales=options['scales'],
                               clusters=options['clusters'],
			       execution_types=options['execution_types'])
    except Exception as e:
        logging.error(f"Error in index route: {str(e)}")
        return render_template('error.html', message="系统初始化失败，请检查日志"), 500

@app.route('/login.html')
def login():
    """登录页面路由"""
    return render_template('login.html')

@app.route('/data', methods=['POST'])
def get_data():
    """处理数据筛选请求，增加健壮性处理"""
    try:
        filters = request.json
        
        # 获取当前数据集
        df = loader.get_data()
        
        if df.empty:
            return jsonify({
                'table_data': [],
                'chart_data': {}
            })
        
        # 应用筛选条件
        filtered = df.copy()
        
        # 标准化列名
        if 'query_type' not in filtered.columns and 'query type' in filtered.columns:
            filtered.rename(columns={'query type': 'query_type'}, inplace=True)
        
        # 应用筛选
        if filters.get('branches'):
            filtered = filtered[filtered['branch'].astype(str).isin(filters['branches'])]
        
        if filters.get('start_date'):
            try:
                start_date = datetime.strptime(filters['start_date'], '%Y-%m-%d')
                filtered = filtered[filtered['datetime'] >= start_date]
            except:
                pass
        
        if filters.get('end_date'):
            try:
                end_date = datetime.strptime(filters['end_date'], '%Y-%m-%d')
                next_day = end_date + pd.Timedelta(days=1)
                filtered = filtered[filtered['datetime'] <= next_day]
            except:
                pass
        
        if filters.get('scales'):
            try:
                scales = [int(s) for s in filters['scales']]
                filtered = filtered[filtered['scale'].isin(scales)]
            except:
                pass
            
        if filters.get('clusters'):
            try:
                clusters = [int(c) for c in filters['clusters']]
                filtered = filtered[filtered['cluster'].isin(clusters)]
            except:
                pass
            
        if filters.get('query_types'):
            if 'query_type' in filtered.columns:
                filtered = filtered[filtered['query_type'].isin(filters['query_types'])]
            
        if filters.get('workers'):
            try:
                workers = [int(w) for w in filters['workers']]
                filtered = filtered[filtered['worker'].isin(workers)]
            except:
                pass
        if filters.get('execution_types'):
            if 'phase' in filtered.columns:
                filtered = filtered[filtered['phase'].astype(str).isin(filters['execution_types'])]
        
        # 转换时间为北京时间用于表格显示
        table_data = filtered.head(1000).copy()
        if 'datetime' in table_data.columns:
            table_data['datetime'] = table_data['datetime'].apply(format_datetime_for_display)
        
        # 添加基准值对比
        baselines = load_baseline_config()
        if baselines:
            for idx, row in table_data.iterrows():
                baseline_key = f"{row.get('scale', '')}_{row.get('cluster', '')}_{row.get('phase', '')}_{row.get('worker', '')}"
                if baseline_key in baselines:
                    baseline_data = baselines[baseline_key]
                    
                    # 导入速度对比
                    if 'import_speed' in baseline_data and row.get('import_speed') is not None:
                        baseline_import = baseline_data['import_speed']
                        if baseline_import and baseline_import > 0:
                            actual_import = row.get('import_speed', 0)
                            percentage = calculate_performance_percentage(actual_import, baseline_import)
                            if percentage is not None:
                                table_data.at[idx, 'import_speed_baseline_pct'] = round(percentage, 2)
                                # 调试日志
                                logging.debug(f"Import speed comparison - Baseline: {baseline_import}, Actual: {actual_import}, Percentage: {percentage}%")
                    
                    # 查询类型对比 - 使用实际的查询类型
                    query_type = row.get('query_type', '')
                    if query_type and 'mean_ms' in row:
                        # 将查询类型名称转换为metric key格式（Python正则表达式）
                        import re
                        metric_key = re.sub(r'[^a-zA-Z0-9_-]', '-', str(query_type)).lower().replace('_', '-')
                        if metric_key in baseline_data:
                            baseline_value = baseline_data[metric_key]
                            if baseline_value and baseline_value > 0:
                                actual_value = row.get('mean_ms', 0)
                                # 对于延迟，值越小越好，所以计算反向百分比
                                percentage = calculate_performance_percentage_reverse(actual_value, baseline_value)
                                if percentage is not None:
                                    table_data.at[idx, 'mean_ms_baseline_pct'] = round(percentage, 2)
                                    # 调试日志
                                    logging.debug(f"Query {query_type} comparison - Baseline: {baseline_value}ms, Actual: {actual_value}ms, Percentage: {percentage}%")
                else:
                    # 调试日志：未找到基准配置
                    logging.debug(f"No baseline found for key: {baseline_key}")
        
        # 返回数据
        return jsonify({
            'table_data': table_data.replace({pd.NaT: None}).to_dict(orient='records'),
            'chart_data': prepare_chart_data(filtered, filters.get('metric', 'mean_ms'))
        })
    except Exception as e:
        logging.error(f"Error in data route: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/options', methods=['GET'])
def get_options():
    try:
        options = loader.get_options()
        
        # 确保所有选项都是可JSON序列化的
        options['scales'] = [int(scale) for scale in options['scales']]
        options['clusters'] = [int(cluster) for cluster in options['clusters']]
        options['workers'] = [int(worker) for worker in options['workers']]
        options['branches'] = [str(branch) for branch in options['branches']]
        options['query_types'] = [str(qtype) for qtype in options['query_types']]
        options['execution_types'] = [str(etype) for etype in options['execution_types']]
        
        return jsonify(options)
    except Exception as e:
        logging.error(f"Error in options route: {str(e)}")
        return jsonify({"error": str(e)}), 500

def prepare_chart_data(df, metric):
    """准备图表需要的数据结构，增加空数据保护，支持import_speed"""
    if df.empty or metric not in df.columns:
        return {}
    try:
        if 'query_type' not in df.columns and 'query type' in df.columns:
            df.rename(columns={'query type': 'query_type'}, inplace=True)
        # 对于import_speed，按分支、查询类型、时间取均值（或最大值）
        if metric == 'import_speed':
            grouped = df.groupby(['branch', 'query_type', 'datetime'])[metric].max().reset_index()
        else:
            grouped = df.groupby(['branch', 'query_type', 'datetime'])[metric].mean().reset_index()
        chart_data = {}
        for (branch, query_type), group in grouped.groupby(['branch', 'query_type']):
            key = f"{branch}_{query_type}"
            chart_data[key] = {
                'name': f"{branch} - {query_type}",
                'type': 'line',
                'data': [
                    [format_datetime_for_chart(row['datetime']), row[metric]]
                    for _, row in group.iterrows()
                ]
            }
        return chart_data
    except Exception as e:
        logging.error(f"Error preparing chart data: {str(e)}")
        return {}

def load_baseline_config():
    """加载基准值配置"""
    if os.path.exists(BASELINE_CONFIG_FILE):
        try:
            with open(BASELINE_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"加载基准值配置失败: {e}")
    return {}

def save_baseline_config(config):
    """保存基准值配置"""
    try:
        with open(BASELINE_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logging.error(f"保存基准值配置失败: {e}")
        return False

def calculate_performance_percentage(actual_value, baseline_value):
    """计算性能百分比变化"""
    if not baseline_value or baseline_value == 0:
        return None
    return ((actual_value - baseline_value) / baseline_value) * 100

def calculate_performance_percentage_reverse(actual_value, baseline_value):
    """计算性能百分比变化（对于延迟等越小越好的指标）"""
    if not baseline_value or baseline_value == 0:
        return None
    # 对于延迟，值越小越好，所以用基准值减去实际值
    return ((baseline_value - actual_value) / baseline_value) * 100

@app.route('/baseline')
def baseline():
    """基准值配置页面"""
    return render_template('baseline.html')

@app.route('/baselines', methods=['GET'])
def get_baselines():
    """获取基准值配置"""
    try:
        baselines = load_baseline_config()
        return jsonify(baselines)
    except Exception as e:
        logging.error(f"获取基准值失败: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/baselines', methods=['POST'])
def save_baselines():
    """保存基准值配置"""
    try:
        baselines = request.json
        if save_baseline_config(baselines):
            return jsonify({"message": "基准值保存成功"})
        else:
            return jsonify({"error": "保存失败"}), 500
    except Exception as e:
        logging.error(f"保存基准值失败: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    try:
        # 写入PID文件
        write_pid_file()
        
        logging.info("Starting TSBS Analytics application...")
        logging.info(f"PID: {os.getpid()}")
        logging.info("Application will be available at http://0.0.0.0:5001")
        
        app.run(host='0.0.0.0', port=5001, debug=False, threaded=True)
    except Exception as e:
        logging.error(f"Failed to start application: {e}")
        remove_pid_file()
        sys.exit(1)

