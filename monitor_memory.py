#!/usr/bin/env python3
"""
TSBS Analytics 内存监控脚本
用于监控应用的内存使用情况，帮助诊断内存泄漏问题
"""

import os
import sys
import time
import signal
import logging
from datetime import datetime

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/memory_monitor.log'),
        logging.StreamHandler()
    ]
)

class MemoryMonitor:
    def __init__(self, pid_file='logs/app.pid'):
        self.pid_file = pid_file
        self.running = True
        self.check_interval = 60  # 每分钟检查一次
        
        # 设置信号处理器
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """处理退出信号"""
        logging.info(f"Received signal {signum}, stopping monitor...")
        self.running = False
    
    def get_app_pid(self):
        """获取应用程序的PID"""
        try:
            if os.path.exists(self.pid_file):
                with open(self.pid_file, 'r') as f:
                    return int(f.read().strip())
            return None
        except Exception as e:
            logging.error(f"Error reading PID file: {e}")
            return None
    
    def get_memory_info(self, pid):
        """获取进程的内存使用信息"""
        try:
            import psutil
            process = psutil.Process(pid)
            memory_info = process.memory_info()
            memory_percent = process.memory_percent()
            
            return {
                'rss_mb': memory_info.rss / 1024 / 1024,  # 物理内存使用
                'vms_mb': memory_info.vms / 1024 / 1024,  # 虚拟内存使用
                'percent': memory_percent,
                'num_threads': process.num_threads(),
                'cpu_percent': process.cpu_percent(),
                'status': process.status()
            }
        except ImportError:
            # 如果没有psutil，使用基本的系统命令
            return self._get_memory_info_basic(pid)
        except Exception as e:
            logging.error(f"Error getting memory info: {e}")
            return None
    
    def _get_memory_info_basic(self, pid):
        """使用基本系统命令获取内存信息"""
        try:
            import subprocess
            
            # 在macOS上使用ps命令
            result = subprocess.run(
                ['ps', '-p', str(pid), '-o', 'rss,vsz,pcpu,state'],
                capture_output=True, text=True
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) >= 2:
                    values = lines[1].split()
                    return {
                        'rss_mb': float(values[0]) / 1024,  # KB to MB
                        'vms_mb': float(values[1]) / 1024,  # KB to MB
                        'cpu_percent': float(values[2]),
                        'status': values[3],
                        'num_threads': 'N/A',
                        'percent': 'N/A'
                    }
            return None
        except Exception as e:
            logging.error(f"Error getting basic memory info: {e}")
            return None
    
    def check_memory_thresholds(self, memory_info):
        """检查内存使用是否超过阈值"""
        alerts = []
        
        # 检查物理内存使用
        if memory_info['rss_mb'] > 1024:  # 超过1GB
            alerts.append(f"高内存使用: {memory_info['rss_mb']:.1f}MB")
        
        # 检查CPU使用率
        if isinstance(memory_info['cpu_percent'], (int, float)) and memory_info['cpu_percent'] > 80:
            alerts.append(f"高CPU使用: {memory_info['cpu_percent']:.1f}%")
        
        # 检查线程数
        if isinstance(memory_info['num_threads'], int) and memory_info['num_threads'] > 50:
            alerts.append(f"线程数过多: {memory_info['num_threads']}")
        
        return alerts
    
    def log_memory_status(self, pid, memory_info):
        """记录内存状态"""
        if memory_info:
            status_msg = (
                f"PID: {pid}, "
                f"内存: {memory_info['rss_mb']:.1f}MB, "
                f"虚拟内存: {memory_info['vms_mb']:.1f}MB, "
                f"CPU: {memory_info['cpu_percent']}%, "
                f"线程数: {memory_info['num_threads']}, "
                f"状态: {memory_info['status']}"
            )
            
            # 检查是否有警告
            alerts = self.check_memory_thresholds(memory_info)
            if alerts:
                logging.warning(f"内存警告 - {status_msg} - 警告: {'; '.join(alerts)}")
            else:
                logging.info(f"内存状态正常 - {status_msg}")
        else:
            logging.warning(f"无法获取PID {pid}的内存信息")
    
    def run(self):
        """运行监控循环"""
        logging.info("开始内存监控...")
        
        while self.running:
            try:
                pid = self.get_app_pid()
                
                if pid is None:
                    logging.warning("应用程序未运行或PID文件不存在")
                    time.sleep(self.check_interval)
                    continue
                
                # 检查进程是否还在运行
                try:
                    os.kill(pid, 0)  # 发送信号0检查进程是否存在
                except OSError:
                    logging.warning(f"进程 {pid} 不存在，可能已经停止")
                    time.sleep(self.check_interval)
                    continue
                
                # 获取内存信息
                memory_info = self.get_memory_info(pid)
                self.log_memory_status(pid, memory_info)
                
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                logging.error(f"监控循环出错: {e}")
                time.sleep(self.check_interval)
        
        logging.info("内存监控已停止")

def main():
    """主函数"""
    print("=== TSBS Analytics 内存监控 ===")
    print("监控应用程序的内存使用情况...")
    print("按 Ctrl+C 停止监控")
    print()
    
    # 创建日志目录
    os.makedirs('logs', exist_ok=True)
    
    # 检查是否安装了psutil
    try:
        import psutil
        print("✓ 使用psutil进行详细内存监控")
    except ImportError:
        print("⚠ 未安装psutil，使用基本内存监控")
        print("  建议运行: pip install psutil")
        print()
    
    # 启动监控
    monitor = MemoryMonitor()
    monitor.run()

if __name__ == "__main__":
    main() 