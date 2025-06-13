from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from data_loader import loader
from datetime import datetime, timedelta
import pandas as pd
import logging
import json
import os
import signal
import sys
import atexit
import hashlib
import secrets
from functools import wraps
from config import SecurityConfig
import time

# 配置日志 - 支持文件输出
def setup_logging():
    """设置日志配置"""
    # 获取根日志器
    root_logger = logging.getLogger()
    
    # 如果已经配置过处理器，直接返回
    if root_logger.handlers:
        return
    
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
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(error_handler)
    root_logger.addHandler(console_handler)
    
    # 配置 Werkzeug 日志器，减少 HTTP 400 错误的噪音
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.setLevel(logging.WARNING)
    
    # 添加自定义的 Werkzeug 过滤器
    class WerkzeugFilter(logging.Filter):
        def filter(self, record):
            # 过滤掉包含二进制数据的 HTTP 400 错误
            if record.levelno == logging.ERROR and 'Bad request version' in record.getMessage():
                # 将这些错误降级为警告，并简化消息
                record.levelno = logging.WARNING
                record.levelname = 'WARNING'
                record.msg = f"Filtered non-HTTP request from {record.getMessage().split()[0]}"
            return True
    
    werkzeug_logger.addFilter(WerkzeugFilter())

setup_logging()

app = Flask(__name__)
app.config.from_object(SecurityConfig)
app.secret_key = SecurityConfig.SECRET_KEY

# 确保session配置正确应用
app.permanent_session_lifetime = SecurityConfig.PERMANENT_SESSION_LIFETIME
app.config['SESSION_COOKIE_SECURE'] = SecurityConfig.SESSION_COOKIE_SECURE
app.config['SESSION_COOKIE_HTTPONLY'] = SecurityConfig.SESSION_COOKIE_HTTPONLY
app.config['SESSION_COOKIE_SAMESITE'] = SecurityConfig.SESSION_COOKIE_SAMESITE

# 添加错误处理器
@app.errorhandler(400)
def bad_request(error):
    """处理400错误，通常是非HTTP请求"""
    client_ip = request.environ.get('REMOTE_ADDR', 'unknown')
    user_agent = request.environ.get('HTTP_USER_AGENT', 'unknown')
    
    # 记录详细的错误信息但不记录二进制数据
    logging.warning(f"Bad request from {client_ip}, User-Agent: {user_agent}")
    
    # 返回简单的错误响应
    return "Bad Request", 400

@app.errorhandler(500)
def internal_error(error):
    """处理500内部错误"""
    logging.error(f"Internal server error: {str(error)}")
    return "Internal Server Error", 500

# 添加请求前处理器，过滤可疑请求
@app.before_request
def filter_suspicious_requests():
    """过滤可疑的非HTTP请求"""
    try:
        # 检查请求是否是有效的HTTP请求
        if not hasattr(request, 'method') or not request.method:
            return "Bad Request", 400
            
        # 检查User-Agent，过滤明显的非浏览器请求
        user_agent = request.headers.get('User-Agent', '').lower()
        
        # 记录一些基本的请求信息用于调试
        if request.path not in ['/favicon.ico']:  # 忽略favicon请求
            logging.debug(f"Request: {request.method} {request.path} from {request.remote_addr}")
            
    except Exception as e:
        logging.warning(f"Request filtering error: {str(e)}")
        return "Bad Request", 400

# 安全审计日志
def setup_security_logging():
    """设置安全审计日志"""
    security_logger = logging.getLogger('security')
    
    # 如果已经配置过处理器，直接返回
    if security_logger.handlers:
        return security_logger
    
    security_handler = logging.FileHandler('logs/security.log', encoding='utf-8')
    security_formatter = logging.Formatter('%(asctime)s - SECURITY - %(message)s')
    security_handler.setFormatter(security_formatter)
    security_logger.addHandler(security_handler)
    security_logger.setLevel(logging.INFO)
    return security_logger

security_logger = setup_security_logging()

# 登录尝试跟踪
login_attempts = {}

def is_user_locked(username):
    """检查用户是否被锁定"""
    if username not in login_attempts:
        return False
    
    attempt_data = login_attempts[username]
    if attempt_data['locked_until'] and datetime.now() < attempt_data['locked_until']:
        return True
    
    # 锁定时间过期，重置计数
    if attempt_data['locked_until'] and datetime.now() >= attempt_data['locked_until']:
        login_attempts[username] = {'count': 0, 'locked_until': None}
    
    return False

def record_login_attempt(username, success=False, ip_address=None):
    """记录登录尝试"""
    if username not in login_attempts:
        login_attempts[username] = {'count': 0, 'locked_until': None}
    
    if success:
        # 成功登录，重置计数
        login_attempts[username] = {'count': 0, 'locked_until': None}
        security_logger.info(f"Successful login: {username} from {ip_address}")
    else:
        # 失败登录，增加计数
        login_attempts[username]['count'] += 1
        security_logger.warning(f"Failed login attempt: {username} from {ip_address}, attempt #{login_attempts[username]['count']}")
        
        # 检查是否需要锁定
        if login_attempts[username]['count'] >= SecurityConfig.MAX_LOGIN_ATTEMPTS:
            login_attempts[username]['locked_until'] = datetime.now() + SecurityConfig.LOCKOUT_DURATION
            security_logger.warning(f"User locked due to too many failed attempts: {username}")

def require_login(f):
    """登录验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            if request.is_json:
                return jsonify({'error': 'Authentication required', 'redirect': '/login.html'}), 401
            return redirect('/login.html')
        return f(*args, **kwargs)
    return decorated_function

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
@require_login
def index():
    """主页面展示筛选表单，增加错误处理"""
    try:
        options = loader.get_options()
        # 检查options是否为空或不完整
        if not options or not all(key in options for key in ['branches', 'query_types', 'scales', 'clusters', 'execution_types']):
            logging.warning("Incomplete options data returned from loader, using empty defaults")
            # 提供默认的空选项
            options = {
                'branches': [],
                'query_types': [],
                'scales': [],
                'clusters': [],
                'execution_types': []
            }
        
        return render_template('index.html', 
                               branches=options.get('branches', []),
                               query_types=options.get('query_types', []),
                               scales=options.get('scales', []),
                               clusters=options.get('clusters', []),
                               execution_types=options.get('execution_types', []))
    except Exception as e:
        logging.error(f"Error in index route: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        return render_template('error.html', message="系统初始化失败，请检查日志"), 500

@app.route('/login.html')
def login():
    """登录页面路由"""
    return render_template('login.html')

@app.route('/debug_login.html')
def debug_login():
    """调试登录页面路由"""
    import os
    debug_file = os.path.join(os.path.dirname(__file__), 'debug_login.html')
    try:
        with open(debug_file, 'r', encoding='utf-8') as f:
            content = f.read()
        from flask import Response
        return Response(content, mimetype='text/html')
    except Exception as e:
        return f"Debug page error: {e}", 500

@app.route('/simple_login_test.html')
def simple_login_test():
    """简单登录测试页面"""
    import os
    test_file = os.path.join(os.path.dirname(__file__), 'simple_login_test.html')
    try:
        with open(test_file, 'r', encoding='utf-8') as f:
            content = f.read()
        return content, 200, {'Content-Type': 'text/html; charset=utf-8'}
    except Exception as e:
        return f"Test page error: {e}", 500

@app.route('/api/login', methods=['POST'])
def api_login():
    """登录API"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR', 'unknown'))
        
        if not username or not password:
            return jsonify({'success': False, 'message': '用户名和密码不能为空'}), 400
        
        # 检查用户是否被锁定
        if is_user_locked(username):
            security_logger.warning(f"Login attempt for locked user: {username} from {client_ip}")
            return jsonify({'success': False, 'message': '账户已被锁定，请稍后再试'}), 429
        
        # 获取用户数据
        users = SecurityConfig.get_users()
        user = users.get(username)
        
        if user and SecurityConfig.verify_password(password, user['password_hash']):
            session.permanent = True
            session['logged_in'] = True
            session['username'] = username
            session['role'] = user['role']
            session['name'] = user.get('name', username)
            
            record_login_attempt(username, success=True, ip_address=client_ip)
            logging.info(f"User {username} logged in successfully from {client_ip}")
            return jsonify({'success': True, 'message': '登录成功'})
        else:
            record_login_attempt(username, success=False, ip_address=client_ip)
            logging.warning(f"Failed login attempt for user: {username} from {client_ip}")
            return jsonify({'success': False, 'message': '用户名或密码错误'}), 401
            
    except Exception as e:
        logging.error(f"Login error: {str(e)}")
        return jsonify({'success': False, 'message': '系统错误'}), 500

@app.route('/api/logout', methods=['POST'])
def api_logout():
    """登出API"""
    username = session.get('username', 'unknown')
    client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR', 'unknown'))
    session.clear()
    security_logger.info(f"User {username} logged out from {client_ip}")
    logging.info(f"User {username} logged out")
    return jsonify({'success': True, 'message': '登出成功'})

@app.route('/api/check-auth')
def check_auth():
    """检查认证状态"""
    if session.get('logged_in'):
        return jsonify({'authenticated': True, 'username': session.get('username')})
    return jsonify({'authenticated': False}), 401

@app.route('/data', methods=['POST'])
@require_login
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
@require_login
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
@require_login
def baseline():
    """基准值配置页面"""
    return render_template('baseline.html')

@app.route('/baselines', methods=['GET'])
@require_login
def get_baselines():
    """获取基准值配置"""
    try:
        baselines = load_baseline_config()
        return jsonify(baselines)
    except Exception as e:
        logging.error(f"获取基准值失败: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/baselines', methods=['POST'])
@require_login
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
        # 禁用Flask/Werkzeug的重复日志输出
        werkzeug_logger = logging.getLogger('werkzeug')
        werkzeug_logger.setLevel(logging.ERROR)  # 只显示错误信息
        
        # 写入PID文件
        write_pid_file()
        
        logging.info("Starting TSBS Analytics application...")
        logging.info(f"PID: {os.getpid()}")
        logging.info("Application will be available at http://0.0.0.0:5001")
        
        # 启动Flask应用 - 移除复杂的启动监控，因为它可能导致启动挂起
        # Flask的app.run()会阻塞直到服务器关闭，这是正常行为
        app.run(host='0.0.0.0', port=5001, debug=False, threaded=True)
    except Exception as e:
        logging.error(f"Failed to start application: {e}")
        remove_pid_file()
        sys.exit(1)

