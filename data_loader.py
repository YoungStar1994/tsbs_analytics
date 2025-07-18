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
import pickle
import tempfile
from typing import Optional, Dict, Any, List, Union
from concurrent.futures import ThreadPoolExecutor
import gc
import weakref

# 配置日志格式，但不强制设置级别（让父级控制）
if not logging.getLogger().handlers:
    logging.basicConfig(
        format='%(asctime)s - %(levelname)s - %(message)s',
    )

class TSBSDataLoader:
    def __init__(self, base_path: str) -> None:
        self.base_path = base_path
        self.df: pd.DataFrame = pd.DataFrame()  # 修复类型注解
        self.last_scan_time = time.time()
        self.lock = threading.RLock()  # 使用RLock避免死锁
        self._save_lock = threading.Lock()  # 在初始化时就创建保存锁
        self._save_pending = False  # 标记是否有待保存的数据
        self.known_dirs = set()
        self.required_columns = [
            'branch', 'query_type', 'scale', 'worker', 
            'min_ms', 'mean_ms', 'max_ms', 'med_ms'
        ]
        
        # 使用线程池管理异步任务，限制线程数量
        self._thread_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='tsbs-cache')
        
        # 设置持久化文件路径 - 使用临时目录避免权限问题
        temp_dir = tempfile.gettempdir()
        self.cache_file = os.path.join(temp_dir, '.tsbs_data_cache.pkl')
        self.metadata_file = os.path.join(temp_dir, '.tsbs_metadata.pkl')
        
        # 添加内存监控
        self._max_memory_mb = 1024  # 最大内存使用限制(MB)
        self._last_gc_time = time.time()
        
        logging.info(f"Initializing TSBSDataLoader for path: {base_path}")
        
        # 先尝试加载缓存数据
        if self.load_cached_data():
            logging.info("Loaded data from cache")
            # 检查是否有新的目录需要加载
            self.load_new_directories()
        else:
            logging.info("No cache found, loading all data")
            self.load_existing_data()
            
        self.start_file_monitor()
        logging.info("Data loader initialized successfully")
    
    def __del__(self):
        """析构函数，确保线程池正确关闭"""
        try:
            if hasattr(self, '_thread_pool'):
                self._thread_pool.shutdown(wait=False)
        except:
            pass
    
    def _check_memory_usage(self):
        """检查内存使用情况，必要时进行垃圾回收"""
        current_time = time.time()
        if current_time - self._last_gc_time > 300:  # 每5分钟检查一次
            try:
                import psutil
                process = psutil.Process()
                memory_mb = process.memory_info().rss / 1024 / 1024
                
                if memory_mb > self._max_memory_mb:
                    logging.warning(f"Memory usage high: {memory_mb:.1f}MB, running garbage collection")
                    gc.collect()
                    
                self._last_gc_time = current_time
            except ImportError:
                # 如果没有psutil，只做基本的垃圾回收
                if current_time - self._last_gc_time > 600:  # 10分钟
                    gc.collect()
                    self._last_gc_time = current_time
            except Exception as e:
                logging.warning(f"Memory check failed: {e}")
    
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
                    'phase': 'unknown',  # 宽松匹配中无法获取phase，设为unknown
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
            df = pd.DataFrame(data, columns=pd.Index(header))
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
            
            return pd.DataFrame(data, columns=pd.Index(header))
        except Exception as e:
            logging.error(f"All CSV parsing methods failed: {str(e)}")
            return pd.DataFrame()
    
    def load_single_directory(self, dir_path):
        """加载单个目录的数据，增加健壮性处理"""
        dir_name = os.path.basename(dir_path)
        
        # 防止重复加载同一目录
        with self.lock:
            if dir_name in self.known_dirs:
                logging.info(f"Directory already loaded, refreshing data: {dir_name}")
                # 先移除旧数据
                filtered_df = self.df[self.df['dir_name'] != dir_name]
                self.df = filtered_df.copy() if isinstance(filtered_df, pd.DataFrame) else pd.DataFrame()
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
                # 使用更高效的concat方式
                if not self.df.empty:
                    self.df = pd.concat([self.df, df_new], ignore_index=True, copy=False)
                else:
                    self.df = df_new.copy()
                
                self.known_dirs.add(dir_name)
                logging.debug(f"Successfully loaded data from: {dir_name}")
                
                # 标记需要保存缓存
                self._save_pending = True
                
                # 使用线程池异步保存缓存，避免创建过多线程
                self._thread_pool.submit(self._delayed_save_cache)
                
                # 检查内存使用
                self._check_memory_usage()
                
        except Exception as e:
            logging.error(f"Error loading {csv_path}: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
    
    def _delayed_save_cache(self):
        """延迟保存缓存，避免频繁保存"""
        time.sleep(1)  # 等待1秒，合并多个保存请求
        if self._save_pending:
            self.save_cache()
    
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
            # 使用线程池异步保存缓存
            self._thread_pool.submit(self.save_cache)
    
    def remove_directory_data(self, dir_path):
        """移除被删除目录的数据"""
        dir_name = os.path.basename(dir_path)
        with self.lock:
            if dir_name in self.known_dirs:
                before_count = len(self.df)
                filtered_df = self.df[self.df['dir_name'] != dir_name]
                self.df = filtered_df.copy() if isinstance(filtered_df, pd.DataFrame) else pd.DataFrame()
                self.known_dirs.discard(dir_name)
                after_count = len(self.df)
                logging.info(f"Removed data for deleted directory: {dir_name}, rows removed: {before_count - after_count}")
                # 使用线程池异步保存缓存
                self._thread_pool.submit(self.save_cache)
            else:
                logging.info(f"Deleted directory not in known_dirs: {dir_name}")

    def start_file_monitor(self):
        """启动文件系统监控，监控TSBS_TEST_RESULT.csv文件的生成和删除"""
        if not os.path.exists(self.base_path):
            logging.error(f"Cannot start file monitor, path does not exist: {self.base_path}")
            return
            
        class CSVFileHandler(FileSystemEventHandler):
            def __init__(self, loader):
                self.loader = weakref.ref(loader)  # 使用弱引用避免循环引用
                self._processing = set()  # 记录正在处理的文件，避免重复处理
            
            def on_created(self, event):
                loader = self.loader()
                if loader is None:
                    return
                    
                if not event.is_directory and str(event.src_path).endswith('TSBS_TEST_RESULT.csv'):
                    if event.src_path in self._processing:
                        return
                    self._processing.add(event.src_path)
                    
                    try:
                        # 等待文件完全写入
                        time.sleep(5)
                        logging.info(f"New CSV file detected: {event.src_path}")
                        # 获取包含该CSV文件的目录 - CSV文件一定在query_result子目录中
                        dir_path = os.path.dirname(os.path.dirname(event.src_path))  # 向上两级到主目录
                        loader.load_single_directory(dir_path)
                    finally:
                        self._processing.discard(event.src_path)
            
            def on_modified(self, event):
                loader = self.loader()
                if loader is None:
                    return
                    
                if not event.is_directory and str(event.src_path).endswith('TSBS_TEST_RESULT.csv'):
                    if event.src_path in self._processing:
                        return
                    self._processing.add(event.src_path)
                    
                    try:
                        # CSV文件被修改时重新加载
                        time.sleep(2)
                        logging.info(f"CSV file modified: {event.src_path}")
                        # CSV文件一定在query_result子目录中
                        dir_path = os.path.dirname(os.path.dirname(event.src_path))  # 向上两级到主目录
                        # 先移除旧数据再重新加载
                        dir_name = os.path.basename(dir_path)
                        if dir_name in loader.known_dirs:
                            loader.remove_directory_data(dir_path)
                        loader.load_single_directory(dir_path)
                    finally:
                        self._processing.discard(event.src_path)
            
            def on_deleted(self, event):
                loader = self.loader()
                if loader is None:
                    return
                    
                if not event.is_directory and str(event.src_path).endswith('TSBS_TEST_RESULT.csv'):
                    logging.info(f"CSV file deleted: {event.src_path}")
                    # 获取包含该CSV文件的目录并移除数据 - CSV文件一定在query_result子目录中
                    dir_path = os.path.dirname(os.path.dirname(event.src_path))  # 向上两级到主目录
                    loader.remove_directory_data(dir_path)
                elif event.is_directory:
                    # 目录被删除时也要移除数据
                    logging.info(f"Directory deleted: {event.src_path}")
                    loader.remove_directory_data(event.src_path)
        
        try:
            event_handler = CSVFileHandler(self)
            observer = Observer()
            # 递归监控，以便捕获深层目录中的CSV文件变化
            observer.schedule(event_handler, self.base_path, recursive=True)
            observer.start()
            logging.info("File system monitoring started (monitoring CSV files)")
        except Exception as e:
            logging.error(f"Failed to start file monitor: {str(e)}")
    
    def get_data(self):
        """获取当前数据集（线程安全）"""
        with self.lock:
            # 确保返回标准化的列名
            if 'query_type' not in self.df.columns:
                # 尝试查找可能的列名变体
                possible_names = ['query_type', 'query type', 'query-type', 'querytype', 'query']
                for name in possible_names:
                    if name in self.df.columns:
                        self.df = self.df.rename(columns={name: 'query_type'})
                        break
            
            # 确保时间列是datetime类型
            if 'datetime' in self.df.columns and not pd.api.types.is_datetime64_any_dtype(self.df['datetime']):
                try:
                    self.df['datetime'] = pd.to_datetime(self.df['datetime'])
                except:
                    pass
                    
            return self.df.copy()
    
    def get_options(self):
        """获取筛选选项，增加空数据保护和强制去重"""
        df = self.get_data()
        options = {'branches': [], 'query_types': [], 'scales': [], 'clusters': [], 'execution_types': [], 'workers': []}
        
        if df.empty:
            logging.warning("No data available for options")
            return options
            
        try:
            if 'branch' in df.columns:
                unique_branches = df['branch'].astype(str).unique()
                options['branches'] = sorted(list(set(unique_branches)))
            
            if 'query_type' in df.columns:
                unique_query_types = df['query_type'].astype(str).unique()
                options['query_types'] = sorted(list(set(unique_query_types)))
            
            if 'scale' in df.columns:
                unique_scales = df['scale'].dropna().unique()
                options['scales'] = sorted(list(set(unique_scales)))
            
            if 'cluster' in df.columns:
                unique_clusters = df['cluster'].dropna().unique()
                options['clusters'] = sorted(list(set(unique_clusters)))
                
            if 'phase' in df.columns:
                unique_phases = df['phase'].astype(str).unique()
                options['execution_types'] = sorted(list(set(unique_phases)))
                
            if 'worker' in df.columns:
                unique_workers = df['worker'].dropna().unique()
                options['workers'] = sorted(list(set(unique_workers)))
                
        except Exception as e:
            logging.error(f"Error getting options: {str(e)}")
            
        # 最终确保所有选项都已去重
        for key in options:
            if isinstance(options[key], list):
                options[key] = sorted(list(set(options[key])))
            
        return options
    
    def save_cache(self) -> None:
        """保存数据到缓存文件（线程安全，避免重复保存）"""
        # 如果已经有保存任务在运行，则跳过
        if not self._save_lock.acquire(blocking=False):
            logging.debug("Cache save already in progress, skipping")
            return
        
        try:
            self._save_pending = False  # 重置保存标记
            
            with self.lock:
                # 保存主数据
                with open(self.cache_file, 'wb') as f:
                    pickle.dump(self.df, f, protocol=pickle.HIGHEST_PROTOCOL)
                
                # 保存元数据
                metadata = {
                    'known_dirs': self.known_dirs,
                    'last_save_time': datetime.now(),
                    'total_records': len(self.df)
                }
                with open(self.metadata_file, 'wb') as f:
                    pickle.dump(metadata, f, protocol=pickle.HIGHEST_PROTOCOL)
                
                logging.debug(f"Cache saved: {len(self.df)} records")
        except Exception as e:
            logging.error(f"Error saving cache: {str(e)}")
        finally:
            self._save_lock.release()
    
    def load_cached_data(self) -> bool:
        """从缓存文件加载数据"""
        try:
            if not os.path.exists(self.cache_file) or not os.path.exists(self.metadata_file):
                return False
            
            # 检查缓存文件是否太旧（超过1天）
            cache_age = time.time() - os.path.getmtime(self.cache_file)
            if cache_age > 86400:  # 24小时
                logging.info("Cache file is too old, will reload all data")
                return False
            
            with self.lock:
                # 加载主数据
                with open(self.cache_file, 'rb') as f:
                    self.df = pickle.load(f)
                
                # 加载元数据
                with open(self.metadata_file, 'rb') as f:
                    metadata = pickle.load(f)
                    self.known_dirs = metadata.get('known_dirs', set())
                
                logging.info(f"Loaded {len(self.df)} records from cache")
                return True
                
        except Exception as e:
            logging.error(f"Error loading cache: {str(e)}")
            return False
    
    def load_new_directories(self) -> None:
        """只加载新的目录"""
        if not os.path.exists(self.base_path):
            return
            
        current_dirs = set(d for d in os.listdir(self.base_path) 
                          if os.path.isdir(os.path.join(self.base_path, d)))
        
        new_dirs = current_dirs - self.known_dirs
        
        if new_dirs:
            logging.info(f"Found {len(new_dirs)} new directories to load")
            for dir_name in new_dirs:
                dir_path = os.path.join(self.base_path, dir_name)
                self.load_single_directory(dir_path)
            
            # 使用线程池异步保存更新后的缓存
            self._thread_pool.submit(self.save_cache)
        else:
            logging.debug("No new directories found")
    
    def clear_cache(self):
        """清理缓存文件"""
        try:
            if os.path.exists(self.cache_file):
                os.remove(self.cache_file)
            if os.path.exists(self.metadata_file):
                os.remove(self.metadata_file)
            logging.info("Cache files cleared")
        except Exception as e:
            logging.error(f"Error clearing cache: {str(e)}")
    
    def get_cache_info(self):
        """获取缓存信息"""
        info = {
            'cache_exists': os.path.exists(self.cache_file),
            'cache_size': 0,
            'last_modified': None,
            'records_count': len(self.df)
        }
        
        if info['cache_exists']:
            try:
                info['cache_size'] = os.path.getsize(self.cache_file) / 1024 / 1024  # MB
                info['last_modified'] = datetime.fromtimestamp(os.path.getmtime(self.cache_file))
            except Exception as e:
                logging.error(f"Error getting cache info: {str(e)}")
        
        return info
    
    def force_data_reload(self):
        """强制重新加载所有数据"""
        logging.info("Starting forced data reload...")
        with self.lock:
            self.df = pd.DataFrame()
            self.known_dirs = set()
        self.load_existing_data()
        # 使用线程池异步保存缓存
        self._thread_pool.submit(self.save_cache)
        logging.info("Forced data reload completed")

# 修正基础路径为实际路径
loader = TSBSDataLoader('/Users/yangxing/Desktop/tsbs_dist_server_gitee')
