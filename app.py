from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_file
from data_loader import loader
from datetime import datetime
import pandas as pd
from pandas import DataFrame
import logging
import json
import os
import signal
import sys
import atexit
import hashlib
import secrets
from functools import wraps
import io
import zipfile
from typing import Optional, Dict, Any, List

# 配置日志 - 支持文件输出
def setup_logging():
    """设置日志配置"""
    log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # 创建文件处理器
    file_handler = logging.FileHandler('logs/app.log', encoding='utf-8')
    file_handler.setFormatter(log_formatter)
    file_handler.setLevel(logging.INFO)
    
    # 创建错误文件处理器
    error_handler = logging.FileHandler('logs/app_error.log', encoding='utf-8')
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

# 设置密钥用于session加密
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# 用户配置 - 使用哈希密码存储
USER_CONFIG = {
    'admin': {
        'password_hash': '3e4e69e51d323903c6e65859c0a29461a85addf6327360f92f1dec47efcdaddd',  # 'Tsbs2024' 的SHA256哈希
        'role': 'admin'
    }
}

def hash_password(password):
    """对密码进行SHA256哈希"""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def verify_password(password, password_hash):
    """验证密码"""
    return hash_password(password) == password_hash

def login_required(f):
    """登录验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            return jsonify({'error': '需要登录'}), 401
        return f(*args, **kwargs)
    return decorated_function

# 基准值配置文件路径
MASTER_CONFIG_FILE = 'config/master_config.json'
ENTERPRISE_CONFIG_FILE = 'config/enterprise_config.json'  # 企业发版基准值配置文件
OPENSOURCE_CONFIG_FILE = 'config/opensource_config.json'  # 开源发版基准值配置文件
PID_FILE = 'logs/app.pid'

def write_pid_file():
    """写入PID文件"""
    try:
        os.makedirs(os.path.dirname(PID_FILE), exist_ok=True)
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
        # 检查是否已登录
        if not session.get('user_id'):
            return redirect(url_for('login'))
            
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
@app.route('/login')
def login():
    """登录页面路由"""
    return render_template('login.html')

@app.route('/api/login', methods=['POST'])
def api_login():
    """API登录接口"""
    try:
        data = request.json or {}
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return jsonify({'error': '用户名和密码不能为空'}), 400
            
        user = USER_CONFIG.get(username)
        if user and verify_password(password, user['password_hash']):
            session['user_id'] = username
            session['role'] = user['role']
            logging.info(f"User {username} logged in successfully")
            return jsonify({'success': True, 'message': '登录成功'})
        else:
            logging.warning(f"Failed login attempt for user: {username}")
            return jsonify({'error': '用户名或密码错误'}), 401
            
    except Exception as e:
        logging.error(f"Login error: {str(e)}")
        return jsonify({'error': '登录失败，请重试'}), 500

@app.route('/api/logout', methods=['POST'])
def api_logout():
    """API登出接口"""
    user_id = session.get('user_id')
    session.clear()
    if user_id:
        logging.info(f"User {user_id} logged out")
    return jsonify({'success': True, 'message': '已成功登出'})

@app.route('/api/check-auth', methods=['GET'])
def check_auth():
    """检查登录状态"""
    if session.get('user_id'):
        return jsonify({
            'authenticated': True,
            'user': session.get('user_id'),
            'role': session.get('role')
        })
    else:
        return jsonify({'authenticated': False})

@app.route('/data', methods=['POST'])
@login_required
def get_data():
    """处理数据筛选请求，增加健壮性处理"""
    try:
        filters = request.json or {}
        
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
                filtered = filtered[filtered['scale'].isin(scales)]  # type: ignore
            except:
                pass
            
        if filters.get('clusters'):
            try:
                clusters = [int(c) for c in filters['clusters']]
                filtered = filtered[filtered['cluster'].isin(clusters)]  # type: ignore
            except:
                pass
            
        if filters.get('query_types'):
            if 'query_type' in filtered.columns:  # type: ignore
                filtered = filtered[filtered['query_type'].isin(filters['query_types'])]  # type: ignore
            
        if filters.get('workers'):
            try:
                workers = [int(w) for w in filters['workers']]
                filtered = filtered[filtered['worker'].isin(workers)]  # type: ignore
            except:
                pass
        if filters.get('execution_types'):
            if 'phase' in filtered.columns:  # type: ignore
                filtered = filtered[filtered['phase'].astype(str).isin(filters['execution_types'])]  # type: ignore
        
        # 转换时间为北京时间用于表格显示
        table_data = filtered.copy()
        if 'datetime' in table_data.columns:  # type: ignore
            table_data['datetime'] = table_data['datetime'].apply(format_datetime_for_display)  # type: ignore
        
        # 添加基准值对比
        baseline_type = filters.get('baseline_type', 'master')
        if baseline_type == 'enterprise':
            baselines = load_enterprise_config()
            logging.info(f"Using enterprise baseline with {len(baselines)} configurations")
        elif baseline_type == 'opensource':
            baselines = load_opensource_config()
            logging.info(f"Using opensource baseline with {len(baselines)} configurations")
        else:
            baselines = load_master_config()
            logging.info(f"Using master baseline with {len(baselines)} configurations")
            
        if baselines:
            for idx, row in table_data.iterrows():  # type: ignore
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
                                table_data.at[idx, 'import_speed_baseline_pct'] = round(percentage, 2)  # type: ignore
                                # 调试日志
                                logging.info(f"Import speed comparison - Baseline: {baseline_import}, Actual: {actual_import}, Percentage: {percentage}%")
                    
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
                                    table_data.at[idx, 'mean_ms_baseline_pct'] = round(percentage, 2)  # type: ignore
                                    # 调试日志
                                    logging.info(f"Query {query_type} comparison - Baseline: {baseline_value}ms, Actual: {actual_value}ms, Percentage: {percentage}%")
                else:
                    # 调试日志：未找到基准配置
                    logging.info(f"No baseline found for key: {baseline_key}")
        
        # 返回数据
        return jsonify({
            'table_data': table_data.replace({pd.NaT: None}).to_dict(orient='records'),  # type: ignore
            'chart_data': prepare_chart_data(filtered, filters.get('metric', 'mean_ms'))
        })
    except Exception as e:
        logging.error(f"Error in data route: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/options', methods=['GET'])
@login_required
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

def load_master_config():
    """加载Master基准值配置"""
    if os.path.exists(MASTER_CONFIG_FILE):
        try:
            with open(MASTER_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"加载Master基准值配置失败: {e}")
    return {}

def save_master_config(config):
    """保存Master基准值配置"""
    try:
        with open(MASTER_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logging.error(f"保存Master基准值配置失败: {e}")
        return False



def load_enterprise_config():
    """加载企业发版基准值配置"""
    if os.path.exists(ENTERPRISE_CONFIG_FILE):
        try:
            with open(ENTERPRISE_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"加载企业发版基准值配置失败: {e}")
    return {}

def save_enterprise_config(config):
    """保存企业发版基准值配置"""
    try:
        with open(ENTERPRISE_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logging.error(f"保存企业发版基准值配置失败: {e}")
        return False

def load_opensource_config():
    """加载开源发版基准值配置"""
    if os.path.exists(OPENSOURCE_CONFIG_FILE):
        try:
            with open(OPENSOURCE_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"加载开源发版基准值配置失败: {e}")
    return {}

def save_opensource_config(config):
    """保存开源发版基准值配置"""
    try:
        with open(OPENSOURCE_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logging.error(f"保存开源发版基准值配置失败: {e}")
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

@app.route('/master')
@login_required
def master():
    """基准值配置页面"""
    return render_template('master.html')

@app.route('/masters', methods=['GET'])
@login_required
def get_masters():
    """获取Master基准值配置"""
    try:
        baselines = load_master_config()
        return jsonify(baselines)
    except Exception as e:
        logging.error(f"获取Master基准值失败: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/masters', methods=['POST'])
@login_required
def save_masters():
    """保存Master基准值配置"""
    try:
        baselines = request.json
        if save_master_config(baselines):
            return jsonify({"message": "Master基准值保存成功"})
        else:
            return jsonify({"error": "保存失败"}), 500
    except Exception as e:
        logging.error(f"保存Master基准值失败: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/opensource')
@login_required
def opensource_page():
    """开源发版基准值配置页面"""
    return render_template('opensource.html')

@app.route('/opensources', methods=['GET'])
@login_required
def get_opensource_config():
    """获取开源发版基准值配置"""
    try:
        baselines = load_opensource_config()
        return jsonify(baselines)
    except Exception as e:
        logging.error(f"获取开源发版基准值失败: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/opensources', methods=['POST'])
@login_required
def save_opensource_config_api():
    """保存开源发版基准值配置"""
    try:
        baselines = request.json
        if save_opensource_config(baselines):
            return jsonify({"message": "开源发版基准值保存成功"})
        else:
            return jsonify({"error": "保存失败"}), 500
    except Exception as e:
        logging.error(f"保存开源发版基准值失败: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/enterprise')
@login_required
def enterprise_page():
    """企业发版基准值配置页面"""
    return render_template('enterprise.html')

@app.route('/enterprises', methods=['GET'])
@login_required
def get_enterprise_config():
    """获取企业发版基准值配置"""
    try:
        baselines = load_enterprise_config()
        return jsonify(baselines)
    except Exception as e:
        logging.error(f"获取企业发版基准值失败: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/enterprises', methods=['POST'])
@login_required
def save_enterprise_config_api():
    """保存企业发版基准值配置"""
    try:
        baselines = request.json
        if save_enterprise_config(baselines):
            return jsonify({"message": "企业发版基准值保存成功"})
        else:
            return jsonify({"error": "保存失败"}), 500
    except Exception as e:
        logging.error(f"保存企业发版基准值失败: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/export-csv', methods=['POST'])
@login_required
def export_csv():
    """导出筛选结果为Excel文件 - 每个表格作为一个sheet页"""
    try:
        request_data = request.json or {}
        export_data = request_data.get('export_data', {})
        baseline_type = request_data.get('baseline_type', 'master')
        
        if not export_data:
            return jsonify({'error': '没有数据可导出'}), 400
        
        # 创建内存中的Excel文件
        memory_file = io.BytesIO()
        
        # 使用pandas的ExcelWriter创建多sheet的Excel文件
        with pd.ExcelWriter(memory_file, engine='openpyxl', mode='w') as writer:  # type: ignore
            for table_key, table_info in export_data.items():
                metadata = table_info['metadata']
                data_rows = table_info['data']
                
                if not data_rows:
                    continue
                
                # 收集所有查询类型
                all_query_types = set()
                for row in data_rows:
                    all_query_types.update(row.get('queries', {}).keys())
                all_query_types = sorted(list(all_query_types))
                
                # 准备DataFrame数据
                df_data = []
                
                for row in data_rows:
                    row_data = {
                        '时间': format_datetime_for_display(row.get('datetime')),
                        '分支': row.get('branch', ''),
                        '执行类型': row.get('phase', ''),
                        '规模': row.get('scale', ''),
                        '集群': row.get('cluster', ''),
                        '工作线程': row.get('worker', ''),
                        '导入速度(rows/sec)': row.get('import_speed', '') if row.get('import_speed') is not None else '',
                        '导入速度对比(%)': f"{row.get('import_speed_baseline_pct', '')}%" if row.get('import_speed_baseline_pct') is not None else ''
                    }
                    
                    # 为每个查询类型添加平均延迟和对比数据
                    queries = row.get('queries', {})
                    for qt in all_query_types:
                        if qt in queries:
                            query_data = queries[qt]
                            row_data[f'{qt}_平均延迟(ms)'] = query_data.get('mean_ms', '')
                            row_data[f'{qt}_对比(%)'] = f"{query_data.get('mean_ms_baseline_pct', '')}%" if query_data.get('mean_ms_baseline_pct') is not None else ''
                        else:
                            row_data[f'{qt}_平均延迟(ms)'] = ''
                            row_data[f'{qt}_对比(%)'] = ''
                    
                    df_data.append(row_data)
                
                # 创建DataFrame
                df = pd.DataFrame(df_data)
                
                # 生成sheet名称（Excel限制sheet名称长度为31字符）
                sheet_name = f"{metadata['branch']}_规模{metadata['scale']}_集群{metadata['cluster']}_工作线程{metadata['worker']}"
                if metadata.get('phase'):
                    sheet_name += f"_{metadata['phase']}"
                
                # 确保sheet名称不超过31字符且不包含非法字符
                import re
                sheet_name = re.sub(r'[\\/*?[\]:]+', '_', sheet_name)  # 替换Excel不允许的字符
                if len(sheet_name) > 31:
                    sheet_name = sheet_name[:28] + "..."
                
                # 写入Excel sheet
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                
                # 获取工作表对象以进行格式化
                worksheet = writer.sheets[sheet_name]
                
                # 自动调整列宽
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)  # 最大宽度限制为50
                    worksheet.column_dimensions[column_letter].width = adjusted_width
        
        memory_file.seek(0)
        
        # 生成下载文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        baseline_name = "企业发版基准值" if baseline_type == 'enterprise' else "开源发版基准值" if baseline_type == 'opensource' else "Master基准值"
        download_name = f'TSBS分析数据导出_{baseline_name}_{timestamp}.xlsx'
        
        return send_file(
            memory_file,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=download_name
        )
        
    except Exception as e:
        logging.error(f"Excel导出失败: {str(e)}")
        return jsonify({'error': f'导出失败: {str(e)}'}), 500



@app.route('/api/upload-enterprise-csv', methods=['POST'])
@login_required
def upload_enterprise_csv():
    """上传企业版CSV文件并更新配置"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': '没有选择文件'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '没有选择文件'}), 400
        
        if not file.filename or not file.filename.endswith('.csv'):
            return jsonify({'error': '请上传CSV格式的文件'}), 400
        
        # 读取CSV文件
        csv_content = file.read().decode('utf-8')
        df = pd.read_csv(io.StringIO(csv_content))
        
        # 解析CSV并生成配置
        enterprise_config = parse_enterprise_csv_from_dataframe(df)
        
        # 保存配置
        save_enterprise_config(enterprise_config)
        
        return jsonify({
            'success': True,
            'message': f'企业版配置更新成功，共处理 {len(enterprise_config)} 个配置项',
            'config_count': len(enterprise_config),
            'sample_keys': list(enterprise_config.keys())[:5]  # 显示前5个配置键
        })
        
    except Exception as e:
        logging.error(f"Upload enterprise CSV error: {str(e)}")
        return jsonify({'error': f'处理文件失败: {str(e)}'}), 500

@app.route('/api/upload-opensource-csv', methods=['POST'])
@login_required
def upload_opensource_csv():
    """上传开源版CSV文件并更新配置"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': '没有选择文件'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '没有选择文件'}), 400
        
        if not file.filename or not file.filename.endswith('.csv'):
            return jsonify({'error': '请上传CSV格式的文件'}), 400
        
        # 读取CSV文件
        csv_content = file.read().decode('utf-8')
        df = pd.read_csv(io.StringIO(csv_content))
        
        # 解析CSV并生成配置
        opensource_config = parse_opensource_csv_from_dataframe(df)
        
        # 保存配置
        save_opensource_config(opensource_config)  # 保存到opensource_config.json
        
        return jsonify({
            'success': True,
            'message': f'开源版配置更新成功，共处理 {len(opensource_config)} 个配置项',
            'config_count': len(opensource_config),
            'sample_keys': list(opensource_config.keys())[:5]  # 显示前5个配置键
        })
        
    except Exception as e:
        logging.error(f"Upload opensource CSV error: {str(e)}")
        return jsonify({'error': f'处理文件失败: {str(e)}'}), 500

def parse_enterprise_csv_from_dataframe(df):
    """从DataFrame解析企业版CSV数据"""
    # 获取头部信息
    exec_type_row = df.iloc[0, 1:]  # 第一行数据包含执行类型
    cluster_row = df.iloc[1, 1:]    # 第二行数据包含集群数量
    scale_row = df.iloc[2, 1:]      # 第三行数据包含规模
    worker_row = df.iloc[3, 1:]     # 第四行数据包含工作节点数量
    
    # 初始化企业版配置
    enterprise_config = {}
    
    # 处理每一列（配置）
    for col_idx in range(1, len(df.columns)):
        # 提取配置参数
        exec_type = exec_type_row.iloc[col_idx - 1] 
        cluster = int(cluster_row.iloc[col_idx - 1])
        scale = int(scale_row.iloc[col_idx - 1])
        worker = int(worker_row.iloc[col_idx - 1])
        
        # 创建配置键
        config_key = f"{scale}_{cluster}_{exec_type}_{worker}"
        
        # 初始化配置（如果不存在）
        if config_key not in enterprise_config:
            enterprise_config[config_key] = {}
        
        # 提取此配置的指标值（从第4行开始）
        for row_idx in range(4, len(df)):
            metric_name = df.iloc[row_idx, 0]  # 第一列包含指标名称
            metric_value = df.iloc[row_idx, col_idx]
            
            # 转换指标名称以匹配配置格式
            if metric_name == 'import_speed':
                enterprise_config[config_key]['import_speed'] = float(metric_value)
            else:
                # 将下划线转换为连字符以保持一致性
                config_metric_name = metric_name.replace('_', '-')
                enterprise_config[config_key][config_metric_name] = float(metric_value)
    
    return enterprise_config

def parse_opensource_csv_from_dataframe(df):
    """从DataFrame解析开源版CSV数据"""
    # 获取头部信息
    exec_type_row = df.iloc[0, 1:]  # 第一行数据包含执行类型
    cluster_row = df.iloc[1, 1:]    # 第二行数据包含集群数量
    scale_row = df.iloc[2, 1:]      # 第三行数据包含规模
    worker_row = df.iloc[3, 1:]     # 第四行数据包含工作节点数量
    
    # 初始化开源版配置
    opensource_config = {}
    
    # 处理每一列（配置）
    for col_idx in range(1, len(df.columns)):
        # 提取配置参数
        exec_type = exec_type_row.iloc[col_idx - 1] 
        cluster = int(cluster_row.iloc[col_idx - 1])
        scale = int(scale_row.iloc[col_idx - 1])
        worker = int(worker_row.iloc[col_idx - 1])
        
        # 创建配置键
        config_key = f"{scale}_{cluster}_{exec_type}_{worker}"
        
        # 初始化配置（如果不存在）
        if config_key not in opensource_config:
            opensource_config[config_key] = {}
        
        # 提取此配置的指标值（从第4行开始）
        for row_idx in range(4, len(df)):
            metric_name = df.iloc[row_idx, 0]  # 第一列包含指标名称
            metric_value = df.iloc[row_idx, col_idx]
            
            # 转换指标名称以匹配配置格式
            if metric_name == 'import_speed':
                opensource_config[config_key]['import_speed'] = float(metric_value)
            else:
                # 将下划线转换为连字符以保持一致性
                config_metric_name = metric_name.replace('_', '-')
                opensource_config[config_key][config_metric_name] = float(metric_value)
    
    return opensource_config

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

