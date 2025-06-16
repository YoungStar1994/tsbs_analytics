import os
import re
import pandas as pd
import time
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading
import logging
import csv

# 配置日志格式，但不强制设置级别（让父级控制）
if not logging.getLogger().handlers:
    logging.basicConfig(
        format='%(asctime)s - %(levelname)s - %(message)s',
    )

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
        
        logging.info(f"Initializing TSBSDataLoader for path: {base_path}")
        self.load_existing_data()
        self.start_file_monitor()
        self.start_cleanup_task()
        logging.info("Data loader initialized successfully")
    
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
                logging.error(f"Failed to load CSV: {csv_path}")
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
                self.df = pd.concat([self.df, df_new], ignore_index=True)
                self.known_dirs.add(dir_name)
                # 只在调试模式下输出详细加载信息
                logging.debug(f"Successfully loaded data from: {dir_name}")
                
        except Exception as e:
            logging.error(f"Error loading {csv_path}: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
    
    def load_existing_data(self):
        """加载所有现有数据，增加进度日志"""
        if not os.path.exists(self.base_path):
            logging.error(f"Base path does not exist: {self.base_path}")
            return
            
        dir_list = [d for d in os.listdir(self.base_path) 
                   if os.path.isdir(os.path.join(self.base_path, d))]
        total = len(dir_list)
        
        # 只在有大量目录时才显示详细进度信息
        if total > 50:
            logging.debug(f"Found {total} directories to load")
        
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
        """启动文件系统监控，监控TSBS_TEST_RESULT.csv文件的生成和删除"""
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
                    # 获取包含该CSV文件的目录
                    dir_path = os.path.dirname(os.path.dirname(event.src_path))  # 向上两级到主目录
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
                    # 获取包含该CSV文件的目录并移除数据
                    dir_path = os.path.dirname(os.path.dirname(event.src_path))
                    self.loader.remove_directory_data(dir_path)
                elif event.is_directory:
                    # 目录被删除时也要移除数据
                    logging.info(f"Directory deleted: {event.src_path}")
                    self.loader.remove_directory_data(event.src_path)
        
        try:
            event_handler = CSVFileHandler(self)
            observer = Observer()
            # 递归监控，以便捕获深层目录中的CSV文件变化
            observer.schedule(event_handler, self.base_path, recursive=True)
            observer.start()
            logging.info("File system monitoring started (monitoring CSV files)")
        except Exception as e:
            logging.error(f"Failed to start file monitor: {str(e)}")
    
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
        """获取筛选选项，增加空数据保护"""
        df = self.get_data()
        options = {'branches': [], 'query_types': [], 'scales': [], 'clusters': [], 'execution_types': [], 'workers': []}  # 新增 execution_types 和 workers
        
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
            
        return options

# 修正基础路径为实际路径
loader = TSBSDataLoader('/data1/reports/tsbs_dist_server_gitee')
