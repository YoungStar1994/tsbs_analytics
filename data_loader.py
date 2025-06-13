import os
import re
import pandas as pd
import time
import signal
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading
import logging
import csv
import functools
import json

# 超时处理装饰器
def timeout(seconds, default_return=None):
    """函数执行超时装饰器"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            result = [default_return]
            is_timeout = [False]
            
            def handler(signum, frame):
                is_timeout[0] = True
                raise TimeoutError(f"Function {func.__name__} timed out after {seconds} seconds")
            
            # 设置信号处理器和闹钟
            original_handler = signal.signal(signal.SIGALRM, handler)
            signal.alarm(seconds)
            
            try:
                result[0] = func(*args, **kwargs)
            except TimeoutError as e:
                logging.warning(str(e))
            finally:
                # 恢复原始处理器和取消闹钟
                signal.signal(signal.SIGALRM, original_handler)
                signal.alarm(0)
            
            return result[0]
        return wrapper
    return decorator

# 配置日志格式，但不强制设置级别（让父级控制）
# 注意：不在这里配置日志处理器，避免与主应用的日志配置冲突
# 日志配置应该由主应用程序（app.py）统一管理

class TSBSDataLoader:
    def __init__(self, base_path):
        self.base_path = base_path
        self.df = pd.DataFrame()
        self.last_scan_time = time.time()
        self.lock = threading.Lock()
        self.known_dirs = set()
        self.required_columns = [
            'branch', 'query_type', 'scale', 'worker', 
            'min_ms', 'mean_ms', 'max_ms', 'med_ms'
        ]
        
        # 缓存机制
        self._options_cache = None
        self._options_cache_time = 0
        self._data_cache = {}
        self._cache_ttl = 300  # 5分钟缓存
        
        # 获取环境变量设置的超时时间（默认60秒，降低超时时间）
        self.data_load_timeout = int(os.environ.get('TSBS_DATA_LOAD_TIMEOUT', 60))
        logging.info(f"Initializing TSBSDataLoader for path: {base_path} with timeout: {self.data_load_timeout}s")
        
        # 创建空DataFrame以快速启动
        self.df = pd.DataFrame(columns=self.required_columns)
        
        # 异步加载数据，不阻塞启动
        self._start_async_initialization()
        logging.info("Data loader initialized successfully (async loading started)")
    
    def parse_directory_name(self, dir_name):
        """解析目录名提取元数据，增加容错处理"""
        try:
            # 更灵活的正则表达式，适应不同格式
            pattern = r'(\d{4})_(\d{2})(\d{2})_(\d{6})_(.*?)_scale(\d+)_cluster(\d+)_([a-zA-Z]+?\d*)_([a-zA-Z]+)_(wal\d+)_replica(\d+)_dop(\d+)'
            match = re.match(pattern, dir_name)
            if not match:
                # 尝试更宽松的匹配
                pattern = r'(\d{4})_(\d{2})(\d{2})_(\d{6})_(.*?)_scale(\d+)_cluster(\d+)_.+_dop(\d+)'
                match = re.match(pattern, dir_name)
                if not match:
                    logging.warning(f"Directory name pattern mismatch: {dir_name}")
                    return None
                
                return {
                    'year': int(match.group(1)),
                    'month': int(match.group(2)),
                    'day': int(match.group(3)),
                    'time': match.group(4),
                    'branch': match.group(5),
                    'scale': int(match.group(6)),
                    'cluster': int(match.group(7)),
                    'dop': int(match.group(8)),
                    'phase': match.group(9),  # 新增执行类型字段
                    'dir_name': dir_name,
                    'datetime': datetime.strptime(
                        f"{match.group(1)}{match.group(2)}{match.group(3)}_{match.group(4)}", 
                        '%Y%m%d_%H%M%S'
                    )
                }
                
            return {
                'year': int(match.group(1)),
                'month': int(match.group(2)),
                'day': int(match.group(3)),
                'time': match.group(4),
                'branch': match.group(5),
                'scale': int(match.group(6)),
                'cluster': int(match.group(7)),
                'test_type': match.group(8),
                'phase': match.group(9),
                'wal': match.group(10),
                'replica': int(match.group(11)),
                'dop': int(match.group(12)),
                'dir_name': dir_name,
                'datetime': datetime.strptime(
                    f"{match.group(1)}{match.group(2)}{match.group(3)}_{match.group(4)}", 
                    '%Y%m%d_%H%M%S'
                )
            }
        except Exception as e:
            logging.error(f"Error parsing directory name {dir_name}: {str(e)}")
            return None
    
    def load_existing_data_with_timeout(self):
        """使用超时机制加载现有数据"""
        @timeout(self.data_load_timeout, default_return=False)
        def load_with_timeout():
            self.load_existing_data()
            return True
        
        success = load_with_timeout()
        if not success:
            logging.warning(f"Data loading timed out after {self.data_load_timeout} seconds. Continuing with partial data.")
            # 确保至少有一个空的DataFrame
            if self.df is None or len(self.df.columns) == 0:
                self.df = pd.DataFrame(columns=self.required_columns)
                logging.warning("Created empty DataFrame with required columns.")
    
    def validate_dataframe(self, df):
        """验证数据框是否包含必需的列"""
        missing_cols = [col for col in self.required_columns if col not in df.columns]
        if missing_cols:
            logging.warning(f"Missing required columns: {', '.join(missing_cols)}")
            return False
            
        if df.empty:
            logging.warning("DataFrame is empty")
            return False
            
        return True
    
    def robust_csv_loader(self, csv_path):
        """强大的CSV加载器，处理各种格式问题"""
        # 尝试1: 使用Python csv模块手动解析
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                header = next(reader)
                data = list(reader)
            
            # 如果标题行只有一个元素，尝试分割
            if len(header) == 1:
                header = header[0].split(',')
                
            # 创建DataFrame
            df = pd.DataFrame(data, columns=header)
            return df
        except Exception as e:
            logging.warning(f"Manual CSV parsing failed: {str(e)}")
        
        # 尝试2: 使用pandas自动检测分隔符
        try:
            return pd.read_csv(csv_path, sep=None, engine='python', encoding='utf-8')
        except:
            pass
        
        # 尝试3: 使用不同编码
        encodings = ['utf-8', 'utf-8-sig', 'latin1', 'iso-8859-1']
        for encoding in encodings:
            try:
                return pd.read_csv(csv_path, sep=',', encoding=encoding)
            except:
                continue
        
        # 尝试4: 作为纯文本处理并分割
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 跳过空行
            lines = [line.strip() for line in lines if line.strip()]
            header = lines[0].split(',')
            data = [line.split(',') for line in lines[1:]]
            
            # 确保所有行长度相同
            max_cols = len(header)
            for i, row in enumerate(data):
                if len(row) < max_cols:
                    data[i] = row + [''] * (max_cols - len(row))
                elif len(row) > max_cols:
                    data[i] = row[:max_cols]
            
            return pd.DataFrame(data, columns=header)
        except Exception as e:
            logging.error(f"All CSV parsing methods failed: {str(e)}")
            return pd.DataFrame()
    
    def load_single_directory(self, dir_path):
        """加载单个目录的数据，增加健壮性处理"""
        dir_name = os.path.basename(dir_path)
        
        # 如果目录已经加载过，先移除旧数据
        if dir_name in self.known_dirs:
            logging.info(f"Directory already loaded, refreshing data: {dir_name}")
            with self.lock:
                self.df = self.df[self.df['dir_name'] != dir_name]
                self.known_dirs.discard(dir_name)
        
        meta = self.parse_directory_name(dir_name)
        if not meta:
            logging.warning(f"Skipping directory due to parse failure: {dir_name}")
            return
            
        csv_path = os.path.join(dir_path, 'query_result', 'TSBS_TEST_RESULT.csv')
        if not os.path.exists(csv_path):
            logging.warning(f"CSV file not found: {csv_path}")
            return
            
        try:
            # 使用强大的CSV加载器
            df_new = self.robust_csv_loader(csv_path)
            
            if df_new.empty:
                logging.warning(f"CSV file is empty or has no data rows: {csv_path}")
                return
                
            # 检查是否只有表头没有数据
            if len(df_new) == 0:
                logging.warning(f"CSV file has headers but no data: {csv_path}")
                return
                
            # 只在调试模式下输出详细列信息
            logging.debug(f"Loaded CSV from {csv_path}. Columns: {df_new.columns.tolist()}")
            
            # 标准化列名（移除空格和下划线）
            df_new.columns = df_new.columns.str.strip().str.replace(' ', '_').str.lower()
            
            # 重命名列以适应标准化
            column_mapping = {
                'query_type': 'query_type',
                'query-type': 'query_type',
                'querytype': 'query_type',
                'query': 'query_type',
                'min(ms)': 'min_ms',
                'mean(ms)': 'mean_ms',
                'max(ms)': 'max_ms',
                'med(ms)': 'med_ms',
                'worker': 'worker',
                'scale': 'scale',
                'query_count': 'query_count'
            }
            
            # 应用列名映射
            df_new.rename(columns=lambda x: column_mapping.get(x, x), inplace=True)
           
            
            # 只在调试模式下输出详细列信息  
            logging.debug(f"After renaming columns: {df_new.columns.tolist()}")
            
            # 添加元数据列
            for key, value in meta.items():
                df_new[key] = value
            
            # 新增：提取导入速度import_speed
            import_speed = None
            try:
                load_result_dir = os.path.join(dir_path, 'load_result')
                if os.path.isdir(load_result_dir):
                    for fname in os.listdir(load_result_dir):
                        if fname.endswith('.log'):
                            log_path = os.path.join(load_result_dir, fname)
                            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                                for line in f:
                                    m = re.search(r'actually rate ([\d.]+) rows/sec without ddl time', line)
                                    if m:
                                        import_speed = float(m.group(1))
                                        break
                        if import_speed is not None:
                            break
            except Exception as e:
                logging.warning(f"Error extracting import_speed from log: {str(e)}")
            df_new['import_speed'] = import_speed
            
            numeric_cols = ['min_ms', 'mean_ms', 'max_ms', 'med_ms', 'worker', 'query_count', 'scale', 'cluster', 'dop', 'replica', 'import_speed']
            for col in numeric_cols:
                if col in df_new.columns:
                    try:
                        df_new[col] = pd.to_numeric(df_new[col], errors='coerce')
                    except Exception as e:
                        logging.warning(f"Error converting column {col} to numeric: {str(e)}")
            # 验证数据
            if not self.validate_dataframe(df_new):
                logging.error(f"Validation failed for {csv_path}")
                # 尝试修复缺失列
                for col in self.required_columns:
                    if col not in df_new.columns:
                        df_new[col] = None
                        logging.warning(f"Added missing column: {col}")
                
                # 再次验证
                if not self.validate_dataframe(df_new):
                    logging.error(f"Validation still failed, skipping directory: {dir_name}")
                    return
                
            with self.lock:
                if not self.df.empty and not df_new.empty:
                    self.df = pd.concat([self.df, df_new], ignore_index=True)
                elif df_new.empty:
                    pass  # 不添加空数据
                else:
                    self.df = df_new.copy()
                self.known_dirs.add(dir_name)
                # 只在调试模式下输出详细加载信息
                logging.debug(f"Successfully loaded data from: {dir_name}")
                
        except Exception as e:
            logging.error(f"Error loading {csv_path}: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
    
    def load_existing_data(self):
        """加载所有现有数据，只加载符合条件的第一层目录"""
        if not os.path.exists(self.base_path):
            logging.error(f"Base path does not exist: {self.base_path}")
            return
        
        # 排除的目录名
        excluded_dirs = {'history', 'backup', 'temp', 'logs'}
        
        # 过滤目录列表，只包含符合命名规范且不在排除列表中的目录
        dir_list = []
        for d in os.listdir(self.base_path):
            if os.path.isdir(os.path.join(self.base_path, d)):
                # 检查是否在排除列表中
                if d in excluded_dirs:
                    logging.debug(f"Skipping excluded directory: {d}")
                    continue
                # 检查是否符合命名规范
                if re.match(r'\d{4}_\d{4}_\d{6}_.*', d):
                    dir_list.append(d)
                else:
                    logging.debug(f"Skipping directory with non-standard name: {d}")
        
        total = len(dir_list)
        
        # 只在有大量目录时才显示详细进度信息
        if total > 50:
            logging.debug(f"Found {total} directories to load")
        elif total > 0:
            logging.info(f"Found {total} valid directories to load")
        
        for i, dir_name in enumerate(dir_list):
            dir_path = os.path.join(self.base_path, dir_name)
            self.load_single_directory(dir_path)
            
            # 减少进度日志的频率：每处理50个目录才显示一次进度
            if total > 50 and ((i + 1) % 50 == 0 or (i + 1) == total):
                logging.debug(f"Loading progress: {i+1}/{total} directories processed")
        
        # 完成时输出总结信息
        if total > 0:
            logging.info(f"Data loading completed: {total} directories processed, {len(self.df)} records loaded")
    
    def remove_directory_data(self, dir_path):
        """移除被删除目录的数据"""
        dir_name = os.path.basename(dir_path)
        with self.lock:
            if dir_name in self.known_dirs:
                before_count = len(self.df)
                self.df = self.df[self.df['dir_name'] != dir_name]
                self.known_dirs.discard(dir_name)
                after_count = len(self.df)
                logging.info(f"Removed data for deleted directory: {dir_name}, rows removed: {before_count - after_count}")
            else:
                logging.info(f"Deleted directory not in known_dirs: {dir_name}")

    def start_file_monitor(self):
        """启动文件系统监控，只监控第一层目录中的TSBS_TEST_RESULT.csv文件"""
        if not os.path.exists(self.base_path):
            logging.error(f"Cannot start file monitor, path does not exist: {self.base_path}")
            return
            
        class CSVFileHandler(FileSystemEventHandler):
            def __init__(self, loader):
                self.loader = loader
            
            def on_created(self, event):
                if not event.is_directory and event.src_path.endswith('TSBS_TEST_RESULT.csv'):
                    # 等待文件完全写入
                    time.sleep(5)
                    logging.info(f"New CSV file detected: {event.src_path}")
                    # 获取包含该CSV文件的主目录（query_result的父目录）
                    dir_path = os.path.dirname(os.path.dirname(event.src_path))
                    self.loader.load_single_directory(dir_path)
            
            def on_modified(self, event):
                if not event.is_directory and event.src_path.endswith('TSBS_TEST_RESULT.csv'):
                    # CSV文件被修改时重新加载
                    time.sleep(2)
                    logging.info(f"CSV file modified: {event.src_path}")
                    dir_path = os.path.dirname(os.path.dirname(event.src_path))
                    # 先移除旧数据再重新加载
                    dir_name = os.path.basename(dir_path)
                    if dir_name in self.loader.known_dirs:
                        self.loader.remove_directory_data(dir_path)
                    self.loader.load_single_directory(dir_path)
            
            def on_deleted(self, event):
                if not event.is_directory and event.src_path.endswith('TSBS_TEST_RESULT.csv'):
                    logging.info(f"CSV file deleted: {event.src_path}")
                    # 获取包含该CSV文件的主目录并移除数据
                    dir_path = os.path.dirname(os.path.dirname(event.src_path))
                    self.loader.remove_directory_data(dir_path)
        
        try:
            event_handler = CSVFileHandler(self)
            
            # 尝试使用不同的 Observer 类型以避免 FSEvents 问题
            try:
                # 首先尝试使用 PollingObserver，它在所有平台上都更稳定
                from watchdog.observers.polling import PollingObserver
                observer = PollingObserver()
                logging.info("Using PollingObserver for file monitoring (more compatible)")
            except ImportError:
                try:
                    # 如果 PollingObserver 不可用，尝试使用 KqueueObserver (macOS/BSD)
                    from watchdog.observers.kqueue import KqueueObserver
                    observer = KqueueObserver()
                    logging.info("Using KqueueObserver for file monitoring")
                except ImportError:
                    # 最后使用默认 Observer，但增加错误处理
                    observer = Observer()
                    logging.info("Using default Observer for file monitoring")
            
            # 只监控第一层目录，不使用递归监控
            observer.schedule(event_handler, self.base_path, recursive=False)
            
            # 排除的目录名
            excluded_dirs = {'history', 'backup', 'temp', 'logs'}
            
            # 为每个符合条件的第一层目录添加监控（只监控query_result子目录，不递归）
            if os.path.exists(self.base_path):
                for item in os.listdir(self.base_path):
                    item_path = os.path.join(self.base_path, item)
                    if os.path.isdir(item_path):
                        # 只监控符合命名规范的目录
                        if re.match(r'\d{4}_\d{4}_\d{6}_.*', item) and item not in excluded_dirs:
                            # 只监控query_result子目录，而不是整个目录树
                            query_result_path = os.path.join(item_path, 'query_result')
                            if os.path.exists(query_result_path):
                                try:
                                    observer.schedule(event_handler, query_result_path, recursive=False)
                                    logging.debug(f"Added monitoring for query_result directory: {query_result_path}")
                                except Exception as e:
                                    logging.warning(f"Failed to monitor query_result directory {query_result_path}: {str(e)}")
            
            observer.start()
            observer_type = type(observer).__name__
            logging.info(f"File system monitoring started using {observer_type} (monitoring query_result directories only, no recursion)")
            
        except Exception as e:
            logging.error(f"Failed to start file monitor: {str(e)}")
            logging.warning("File monitoring disabled due to errors. Application will continue without real-time file updates.")
            # 不要抛出异常，让应用继续运行
    
    def start_cleanup_task(self):
        """启动定时数据清理任务"""
        def cleanup():
            while True:
                time.sleep(3600)  # 每小时清理一次
                self.clean_old_data()
                
        thread = threading.Thread(target=cleanup, daemon=True)
        thread.start()
        logging.info("Cleanup task started")
    
    def clean_old_data(self):
        """清理旧数据（保留最近30天）"""
        try:
            with self.lock:
                if not self.df.empty and 'datetime' in self.df.columns:
                    cutoff = datetime.now() - pd.DateOffset(days=30)
                    initial_count = len(self.df)
                    self.df = self.df[self.df['datetime'] >= cutoff]
                    removed = initial_count - len(self.df)
                    if removed > 0:
                        logging.info(f"Cleaned up {removed} old records")
                    
                    # 更新已知目录集
                    self.known_dirs = set(self.df['dir_name'].unique())
        except Exception as e:
            logging.error(f"Error during cleanup: {str(e)}")
    
    def get_data(self):
        """获取当前数据集（线程安全）"""
        with self.lock:
            # 确保返回标准化的列名
            if 'query_type' not in self.df.columns:
                # 尝试查找可能的列名变体
                possible_names = ['query_type', 'query type', 'query-type', 'querytype', 'query']
                for name in possible_names:
                    if name in self.df.columns:
                        self.df.rename(columns={name: 'query_type'}, inplace=True)
                        break
            
            # 确保时间列是datetime类型
            if 'datetime' in self.df.columns and not pd.api.types.is_datetime64_any_dtype(self.df['datetime']):
                try:
                    self.df['datetime'] = pd.to_datetime(self.df['datetime'])
                except:
                    pass
                    
            return self.df.copy()
    
    def get_options(self):
        """获取筛选选项，增加空数据保护和缓存"""
        # 检查缓存
        if (self._options_cache is not None and 
            self._is_cache_valid(self._options_cache_time)):
            return self._options_cache
        
        df = self.get_data()
        options = {'branches': [], 'query_types': [], 'scales': [], 'clusters': [], 'execution_types': [], 'workers': []}
        
        if df.empty:
            logging.warning("No data available for options")
            return options
            
        try:
            if 'branch' in df.columns:
                options['branches'] = sorted(df['branch'].astype(str).unique())
            
            if 'query_type' in df.columns:
                options['query_types'] = sorted(df['query_type'].astype(str).unique())
            
            if 'scale' in df.columns:
                options['scales'] = sorted(df['scale'].unique())
            
            if 'cluster' in df.columns:
                options['clusters'] = sorted(df['cluster'].unique())
                
            if 'phase' in df.columns:
                options['execution_types'] = sorted(df['phase'].astype(str).unique())
                
            if 'worker' in df.columns:
                options['workers'] = sorted(df['worker'].unique())
                
        except Exception as e:
            logging.error(f"Error getting options: {str(e)}")
        
        # 缓存结果
        self._options_cache = options
        self._options_cache_time = time.time()
        
        return options
            
    def _start_async_initialization(self):
        """启动异步初始化"""
        def async_init():
            try:
                # 延迟5秒启动，让主应用先启动
                time.sleep(5)
                # 直接调用加载数据，不使用timeout装饰器（避免signal问题）
                self.load_existing_data()
                # 启动文件监视器和清理任务
                threading.Thread(target=self.start_file_monitor, daemon=True).start()
                self.start_cleanup_task()
                logging.info("Async data loading completed")
            except Exception as e:
                logging.error(f"Async initialization failed: {str(e)}")
                import traceback
                logging.error(traceback.format_exc())
        
        threading.Thread(target=async_init, daemon=True).start()
    
    def _clear_cache(self):
        """清除缓存"""
        self._options_cache = None
        self._options_cache_time = 0
        self._data_cache.clear()
    
    def _is_cache_valid(self, cache_time):
        """检查缓存是否有效"""
        return time.time() - cache_time < self._cache_ttl
    
    def get_data_filtered(self, filters=None):
        """获取筛选后的数据（优化版本）"""
        if filters is None:
            filters = {}
        
        with self.lock:
            df = self.df.copy()
        
        if df.empty:
            return df
        
        # 应用筛选 - 使用更高效的筛选方式
        mask = pd.Series(True, index=df.index)
        
        if filters.get('branches'):
            mask &= df['branch'].astype(str).isin(filters['branches'])
        
        if filters.get('query_types') and 'query_type' in df.columns:
            mask &= df['query_type'].isin(filters['query_types'])
        
        if filters.get('scales'):
            try:
                scales = [int(s) for s in filters['scales']]
                mask &= df['scale'].isin(scales)
            except:
                pass
        
        if filters.get('clusters'):
            try:
                clusters = [int(c) for c in filters['clusters']]
                mask &= df['cluster'].isin(clusters)
            except:
                pass
        
        if filters.get('workers'):
            try:
                workers = [int(w) for w in filters['workers']]
                mask &= df['worker'].isin(workers)
            except:
                pass
        
        if filters.get('execution_types') and 'phase' in df.columns:
            mask &= df['phase'].astype(str).isin(filters['execution_types'])
        
        return df[mask]
# 修正基础路径配置 - 支持环境变量和多个路径
def get_data_path():
    """获取数据路径，支持环境变量配置"""
    # 尝试从环境变量获取数据路径
    env_path = os.environ.get('TSBS_DATA_PATH')
    if env_path:
        # 确保路径存在
        if not os.path.exists(env_path):
            try:
                os.makedirs(env_path, exist_ok=True)
                logging.info(f"Created data directory from environment variable: {env_path}")
            except Exception as e:
                logging.warning(f"Failed to create directory {env_path}: {str(e)}")
        
        if os.path.exists(env_path):
            logging.info(f"Using data path from environment variable: {env_path}")
            return env_path
    
    # 默认候选路径列表
    candidate_paths = [
        '/Users/yangxing/Desktop/tsbs_dist_server_gitee'
    ]
    
    for path in candidate_paths:
        if os.path.exists(path):
            logging.info(f"Using data path: {path}")
            return path
    
    # 如果都不存在，创建默认目录
    default_path = './data'
    try:
        os.makedirs(default_path, exist_ok=True)
        logging.warning(f"No existing data path found, created: {default_path}")
        return default_path
    except Exception as e:
        logging.error(f"Failed to create default data directory: {str(e)}")
        # 最后的备用方案 - 使用临时目录
        import tempfile
        tmp_dir = tempfile.mkdtemp(prefix="tsbs_data_")
        logging.error(f"Using temporary directory as fallback: {tmp_dir}")
        return tmp_dir

# 使用动态路径初始化
def init_loader():
    """安全地初始化数据加载器"""
    # 设置超时处理
    @timeout(10, default_return=None)
    def init_with_timeout():
        try:
            data_path = get_data_path()
            loader = TSBSDataLoader(data_path)
            logging.info(f"Data loader initialized successfully with path: {data_path}")
            return loader
        except Exception as e:
            logging.error(f"Failed to initialize data loader: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            return None
    
    # 尝试初始化
    loader = init_with_timeout()
    
    # 如果初始化失败，使用空的数据加载器
    if loader is None:
        logging.warning("Using fallback empty data loader")
        # 创建默认数据目录
        default_path = './data'
        try:
            os.makedirs(default_path, exist_ok=True)
        except:
            import tempfile
            default_path = tempfile.mkdtemp(prefix="tsbs_data_")
            logging.warning(f"Using temporary directory as fallback: {default_path}")
        
        loader = TSBSDataLoader(default_path)
    
    return loader

# 初始化全局加载器
loader = init_loader()
