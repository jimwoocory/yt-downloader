import yt_dlp
import sys
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
from tkinter import ttk, scrolledtext
import threading
import logging
import queue
from urllib.parse import urlparse
import os
from datetime import datetime
import json
import subprocess
import platform
import tempfile
import requests

class QueueHandler(logging.Handler):
    """日志处理器，将日志消息放入队列"""
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue
    
    def emit(self, record):
        self.log_queue.put((record.levelname, self.format(record)))

class YouTubeDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("YouTube 下载器")
        self.root.geometry("1000x800")
        self.root.minsize(900, 750)
        
        # 设置中文字体支持 - 修复字体设置问题，使用更兼容的方式
        default_font = tk.font.nametofont("TkDefaultFont")
        default_font.configure(family="SimHei", size=10)
        
        fixed_font = tk.font.nametofont("TkFixedFont")
        fixed_font.configure(family="SimHei", size=10)
        
        # 应用字体设置到所有控件
        self.style = ttk.Style()
        self.style.configure(".", font=default_font)
        
        # 创建下载任务队列和结果队列
        self.download_queue = queue.Queue()
        self.result_queue = queue.Queue()
        
        # 下载任务列表和控制变量
        self.download_tasks = []
        self.current_task_index = 0
        self.total_tasks = 0
        self.abort_all_tasks = False
        
        # 视频信息缓存
        self.video_info = {}
        
        # 可用格式信息
        self.available_formats = {}
        
        # 配置日志
        self.setup_logging()
        
        # 工具目录
        self.tool_dir = os.path.join(os.path.expanduser("~"), ".youtube_downloader")
        os.makedirs(self.tool_dir, exist_ok=True)
        
        # 立即显示启动提示窗口
        self.show_startup_message()
        
        # 检查并下载依赖
        self.check_dependencies()
    
    def show_startup_message(self):
        """显示启动提示窗口"""
        self.startup_window = tk.Toplevel(self.root)
        self.startup_window.title("初始化")
        self.startup_window.geometry("400x200")
        self.startup_window.resizable(False, False)
        self.startup_window.transient(self.root)
        self.startup_window.grab_set()
        
        # 居中显示
        self.startup_window.update_idletasks()
        width = self.startup_window.winfo_width()
        height = self.startup_window.winfo_height()
        x = (self.startup_window.winfo_screenwidth() // 2) - (width // 2)
        y = (self.startup_window.winfo_screenheight() // 2) - (height // 2)
        self.startup_window.geometry('{}x{}+{}+{}'.format(width, height, x, y))
        
        # 添加提示信息
        ttk.Label(
            self.startup_window, 
            text="YouTube下载器正在初始化...",
            font=('SimHei', 14)
        ).pack(pady=20)
        
        ttk.Label(
            self.startup_window, 
            text="首次启动需要下载必要的依赖文件，请耐心等待",
            font=('SimHei', 10)
        ).pack(pady=10)
        
        # 添加进度条
        self.startup_progress_var = tk.DoubleVar()
        self.startup_progress_bar = ttk.Progressbar(
            self.startup_window, 
            variable=self.startup_progress_var, 
            length=300, 
            mode='indeterminate'
        )
        self.startup_progress_bar.pack(pady=10)
        self.startup_progress_bar.start()
        
        # 添加状态标签
        self.startup_status = tk.StringVar(value="准备下载依赖...")
        ttk.Label(
            self.startup_window, 
            textvariable=self.startup_status,
            font=('SimHei', 10)
        ).pack(pady=10)
        
        # 确保窗口可见
        self.startup_window.deiconify()
        self.root.update()
    
    def setup_logging(self):
        """配置日志系统，将日志输出到GUI"""
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        # 创建日志处理器，将日志输出到GUI
        self.log_handler = QueueHandler(self.result_queue)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        self.log_handler.setFormatter(formatter)
        self.logger.addHandler(self.log_handler)
        
        # 添加控制台日志输出，便于调试
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
    
    def check_dependencies(self):
        """检查并下载必要的依赖"""
        # 创建依赖检查窗口
        self.dependency_window = tk.Toplevel(self.root)
        self.dependency_window.title("初始化")
        self.dependency_window.geometry("500x300")
        self.dependency_window.resizable(False, False)
        self.dependency_window.transient(self.root)
        self.dependency_window.grab_set()
        
        # 居中显示
        self.dependency_window.update_idletasks()
        width = self.dependency_window.winfo_width()
        height = self.dependency_window.winfo_height()
        x = (self.dependency_window.winfo_screenwidth() // 2) - (width // 2)
        y = (self.dependency_window.winfo_screenheight() // 2) - (height // 2)
        self.dependency_window.geometry('{}x{}+{}+{}'.format(width, height, x, y))
        
        # 添加提示信息
        ttk.Label(
            self.dependency_window, 
            text="正在下载重要依赖文件:",
            font=('SimHei', 12)
        ).pack(pady=10)
        
        # 创建依赖项的框架
        self.dependencies_frame = ttk.Frame(self.dependency_window)
        self.dependencies_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # yt-dlp依赖项
        yt_dlp_frame = ttk.Frame(self.dependencies_frame)
        yt_dlp_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(yt_dlp_frame, text="yt-dlp:", font=('SimHei', 10)).pack(side=tk.LEFT, padx=(0, 10))
        
        self.yt_dlp_status = tk.StringVar(value="等待中")
        ttk.Label(yt_dlp_frame, textvariable=self.yt_dlp_status, font=('SimHei', 10)).pack(side=tk.LEFT, padx=(0, 10))
        
        self.yt_dlp_progress_var = tk.DoubleVar()
        self.yt_dlp_progress_bar = ttk.Progressbar(
            yt_dlp_frame, 
            variable=self.yt_dlp_progress_var, 
            length=300, 
            mode='determinate'
        )
        self.yt_dlp_progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # FFmpeg依赖项
        ffmpeg_frame = ttk.Frame(self.dependencies_frame)
        ffmpeg_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(ffmpeg_frame, text="FFmpeg:", font=('SimHei', 10)).pack(side=tk.LEFT, padx=(0, 10))
        
        self.ffmpeg_status = tk.StringVar(value="等待中")
        ttk.Label(ffmpeg_frame, textvariable=self.ffmpeg_status, font=('SimHei', 10)).pack(side=tk.LEFT, padx=(0, 10))
        
        self.ffmpeg_progress_var = tk.DoubleVar()
        self.ffmpeg_progress_bar = ttk.Progressbar(
            ffmpeg_frame, 
            variable=self.ffmpeg_progress_var, 
            length=300, 
            mode='determinate'
        )
        self.ffmpeg_progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # 总体进度
        overall_frame = ttk.Frame(self.dependency_window)
        overall_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(overall_frame, text="总体进度:", font=('SimHei', 10)).pack(side=tk.LEFT, padx=(0, 10))
        
        self.overall_status = tk.StringVar(value="准备下载...")
        ttk.Label(overall_frame, textvariable=self.overall_status, font=('SimHei', 10)).pack(side=tk.LEFT, padx=(0, 10))
        
        self.overall_progress_var = tk.DoubleVar()
        self.overall_progress_bar = ttk.Progressbar(
            overall_frame, 
            variable=self.overall_progress_var, 
            length=300, 
            mode='determinate'
        )
        self.overall_progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # 添加日志文本框
        self.dependency_log_text = scrolledtext.ScrolledText(self.dependency_window, wrap=tk.WORD, height=5)
        self.dependency_log_text.pack(fill=tk.X, padx=10, pady=5)
        self.dependency_log_text.config(state=tk.DISABLED)
        
        # 关闭启动窗口
        if hasattr(self, 'startup_window') and self.startup_window:
            self.startup_window.destroy()
        
        # 确保窗口可见
        self.dependency_window.deiconify()
        self.root.update()
        
        # 启动依赖检查线程
        self.logger.info("开始检查依赖...")
        self.update_dependency_log("开始检查依赖...")
        threading.Thread(target=self._check_dependencies_thread, daemon=True).start()
    
    def update_dependency_log(self, message):
        """更新依赖窗口中的日志文本"""
        self.dependency_log_text.config(state=tk.NORMAL)
        self.dependency_log_text.insert(tk.END, message + "\n")
        self.dependency_log_text.see(tk.END)
        self.dependency_log_text.config(state=tk.DISABLED)
    
    def _check_dependencies_thread(self):
        """在单独线程中检查并下载依赖"""
        try:
            # 初始化总体进度
            total_dependencies = 2
            completed_dependencies = 0
            
            # 检查并下载yt-dlp
            self.root.after(0, lambda: self.overall_status.set("检查yt-dlp..."))
            self.root.after(0, lambda: self.yt_dlp_status.set("检查中..."))
            self.root.after(0, lambda: self.overall_progress_var.set((completed_dependencies / total_dependencies) * 100))
            
            self.ydl_path = self._get_yt_dlp_path()
            completed_dependencies += 1
            self.root.after(0, lambda: self.overall_progress_var.set((completed_dependencies / total_dependencies) * 100))
            
            # 检查并下载FFmpeg
            self.root.after(0, lambda: self.overall_status.set("检查FFmpeg..."))
            self.root.after(0, lambda: self.ffmpeg_status.set("检查中..."))
            
            self.ffmpeg_path = self._get_ffmpeg_path()
            completed_dependencies += 1
            self.root.after(0, lambda: self.overall_progress_var.set((completed_dependencies / total_dependencies) * 100))
            
            # 所有依赖都已准备好，关闭依赖窗口并创建主界面
            self.root.after(0, lambda: self.overall_status.set("初始化完成"))
            self.root.after(0, lambda: self.yt_dlp_status.set("已完成"))
            self.root.after(0, lambda: self.ffmpeg_status.set("已完成"))
            self.logger.info("所有依赖准备就绪")
            self.update_dependency_log("所有依赖准备就绪")
            
            # 延迟1秒让用户看到完成状态
            self.root.after(1000, self._create_main_interface)
        except Exception as e:
            # 确保在发生异常时显示错误信息
            error_msg = f"初始化失败: {str(e)}"
            self.logger.error(error_msg)
            self.update_dependency_log(error_msg)
            self.root.after(0, lambda: messagebox.showerror("初始化失败", error_msg))
            # 关闭依赖窗口
            self.root.after(0, self.dependency_window.destroy)
            # 退出应用
            self.root.after(0, self.root.destroy)
    
    def _get_ffmpeg_path(self):
        """自动检测或下载FFmpeg二进制文件"""
        ffmpeg_dir = os.path.join(self.tool_dir, "ffmpeg")
        os.makedirs(ffmpeg_dir, exist_ok=True)
        
        # 根据操作系统确定FFmpeg文件路径
        if platform.system() == "Windows":
            ffmpeg_exe = "ffmpeg.exe"
            ffplay_exe = "ffplay.exe"
            ffprobe_exe = "ffprobe.exe"
        else:  # macOS和Linux
            ffmpeg_exe = "ffmpeg"
            ffplay_exe = "ffplay"
            ffprobe_exe = "ffprobe"
        
        ffmpeg_path = os.path.join(ffmpeg_dir, ffmpeg_exe)
        ffplay_path = os.path.join(ffmpeg_dir, ffplay_exe)
        ffprobe_path = os.path.join(ffmpeg_dir, ffprobe_exe)
        
        # 检查所有三个文件是否存在
        if all(os.path.exists(path) for path in [ffmpeg_path, ffplay_path, ffprobe_path]):
            self.logger.info("找到已安装的FFmpeg")
            self.update_dependency_log("找到已安装的FFmpeg")
            self.root.after(0, lambda: self.ffmpeg_status.set("已安装"))
            self.root.after(0, lambda: self.ffmpeg_progress_var.set(100))
            return ffmpeg_path
        
        # 更新状态
        self.root.after(0, lambda: self.ffmpeg_status.set("准备下载..."))
        self.root.after(0, lambda: self.ffmpeg_progress_var.set(0))
        self.update_dependency_log("准备下载FFmpeg...")
        
        # 使用国内镜像下载FFmpeg
        if platform.system() == "Windows":
            ffmpeg_url = "https://cdn.npmmirror.com/binaries/ffmpeg/latest/ffmpeg-win64-latest.zip"
        elif platform.system() == "Darwin":  # macOS
            ffmpeg_url = "https://cdn.npmmirror.com/binaries/ffmpeg/latest/ffmpeg-osx-x64-latest.zip"
        else:  # Linux
            ffmpeg_url = "https://cdn.npmmirror.com/binaries/ffmpeg/latest/ffmpeg-linux-x64-latest.zip"
        
        try:
            # 下载FFmpeg
            self.root.after(0, lambda: self.ffmpeg_status.set("正在下载..."))
            self.update_dependency_log(f"从 {ffmpeg_url} 下载FFmpeg...")
            self._download_file_with_progress(ffmpeg_url, ffmpeg_dir, self.ffmpeg_progress_var, self.ffmpeg_status)
            
            # 更新进度
            self.root.after(0, lambda: self.ffmpeg_status.set("正在解压..."))
            self.root.after(0, lambda: self.ffmpeg_progress_var.set(70))
            self.update_dependency_log("正在解压FFmpeg...")
            
            # 解压文件
            filename = os.path.basename(urlparse(ffmpeg_url).path)
            download_path = os.path.join(ffmpeg_dir, filename)
            
            if filename.endswith('.zip'):
                import zipfile
                with zipfile.ZipFile(download_path, 'r') as zip_ref:
                    # 查找包含ffmpeg的目录
                    namelist = zip_ref.namelist()
                    ffmpeg_found = False
                    ffplay_found = False
                    ffprobe_found = False
                    
                    # 首先查找根目录中的文件
                    for name in namelist:
                        if name.endswith(ffmpeg_exe) and not ffmpeg_found:
                            zip_ref.extract(name, ffmpeg_dir)
                            os.rename(os.path.join(ffmpeg_dir, name), ffmpeg_path)
                            ffmpeg_found = True
                        elif name.endswith(ffplay_exe) and not ffplay_found:
                            zip_ref.extract(name, ffmpeg_dir)
                            os.rename(os.path.join(ffmpeg_dir, name), ffplay_path)
                            ffplay_found = True
                        elif name.endswith(ffprobe_exe) and not ffprobe_found:
                            zip_ref.extract(name, ffmpeg_dir)
                            os.rename(os.path.join(ffmpeg_dir, name), ffprobe_path)
                            ffprobe_found = True
                    
                    # 如果在根目录中找不到，则在子目录中查找
                    if not (ffmpeg_found and ffplay_found and ffprobe_found):
                        for name in namelist:
                            if '/' in name or '\\' in name:  # 子目录中的文件
                                dir_name = os.path.dirname(name)
                                if name.endswith(ffmpeg_exe) and not ffmpeg_found:
                                    zip_ref.extract(name, ffmpeg_dir)
                                    os.rename(os.path.join(ffmpeg_dir, name), ffmpeg_path)
                                    ffmpeg_found = True
                                elif name.endswith(ffplay_exe) and not ffplay_found:
                                    zip_ref.extract(name, ffmpeg_dir)
                                    os.rename(os.path.join(ffmpeg_dir, name), ffplay_path)
                                    ffplay_found = True
                                elif name.endswith(ffprobe_exe) and not ffprobe_found:
                                    zip_ref.extract(name, ffmpeg_dir)
                                    os.rename(os.path.join(ffmpeg_dir, name), ffprobe_path)
                                    ffprobe_found = True
            elif filename.endswith(('.tar.gz', '.tar.xz')):
                import tarfile
                with tarfile.open(download_path, 'r') as tar_ref:
                    # 查找包含ffmpeg的目录
                    namelist = tar_ref.getnames()
                    ffmpeg_found = False
                    ffplay_found = False
                    ffprobe_found = False
                    
                    # 首先查找根目录中的文件
                    for name in namelist:
                        if name.endswith(ffmpeg_exe) and not ffmpeg_found:
                            tar_ref.extract(name, ffmpeg_dir)
                            os.rename(os.path.join(ffmpeg_dir, name), ffmpeg_path)
                            ffmpeg_found = True
                        elif name.endswith(ffplay_exe) and not ffplay_found:
                            tar_ref.extract(name, ffmpeg_dir)
                            os.rename(os.path.join(ffmpeg_dir, name), ffplay_path)
                            ffplay_found = True
                        elif name.endswith(ffprobe_exe) and not ffprobe_found:
                            tar_ref.extract(name, ffmpeg_dir)
                            os.rename(os.path.join(ffmpeg_dir, name), ffprobe_path)
                            ffprobe_found = True
                    
                    # 如果在根目录中找不到，则在子目录中查找
                    if not (ffmpeg_found and ffplay_found and ffprobe_found):
                        for name in namelist:
                            if '/' in name or '\\' in name:  # 子目录中的文件
                                dir_name = os.path.dirname(name)
                                if name.endswith(ffmpeg_exe) and not ffmpeg_found:
                                    tar_ref.extract(name, ffmpeg_dir)
                                    os.rename(os.path.join(ffmpeg_dir, name), ffmpeg_path)
                                    ffmpeg_found = True
                                elif name.endswith(ffplay_exe) and not ffplay_found:
                                    tar_ref.extract(name, ffmpeg_dir)
                                    os.rename(os.path.join(ffmpeg_dir, name), ffplay_path)
                                    ffplay_found = True
                                elif name.endswith(ffprobe_exe) and not ffprobe_found:
                                    tar_ref.extract(name, ffmpeg_dir)
                                    os.rename(os.path.join(ffmpeg_dir, name), ffprobe_path)
                                    ffprobe_found = True
            
            # 清理下载的压缩文件
            if os.path.exists(download_path):
                os.remove(download_path)
            
            # 添加执行权限
            for file_path in [ffmpeg_path, ffplay_path, ffprobe_path]:
                if os.path.exists(file_path) and platform.system() != "Windows":
                    os.chmod(file_path, 0o755)
            
            # 更新进度
            self.root.after(0, lambda: self.ffmpeg_progress_var.set(100))
            self.root.after(0, lambda: self.ffmpeg_status.set("下载完成"))
            self.update_dependency_log("FFmpeg下载完成")
            
            self.logger.info("FFmpeg下载完成")
            return ffmpeg_path
        except Exception as e:
            error_msg = f"下载FFmpeg失败: {str(e)}"
            self.logger.error(error_msg)
            self.update_dependency_log(error_msg)
            self.root.after(0, lambda: self.ffmpeg_status.set(f"下载失败: {str(e)}"))
            # 尝试备用下载源
            self.logger.info("尝试备用下载源...")
            self.update_dependency_log("尝试备用下载源...")
            self.root.after(0, lambda: self.ffmpeg_status.set("尝试备用源..."))
            self._try_backup_ffmpeg_source()
            raise
    
    def _get_yt_dlp_path(self):
        """自动检测或下载yt-dlp二进制文件"""
        yt_dlp_dir = os.path.join(self.tool_dir, "yt-dlp")
        os.makedirs(yt_dlp_dir, exist_ok=True)
        
        # 根据操作系统确定yt-dlp文件路径
        if platform.system() == "Windows":
            yt_dlp_exe = "yt-dlp.exe"
        else:  # macOS和Linux
            yt_dlp_exe = "yt-dlp"
        
        yt_dlp_path = os.path.join(yt_dlp_dir, yt_dlp_exe)
        
        # 检查文件是否存在
        if os.path.exists(yt_dlp_path):
            self.logger.info("找到已安装的yt-dlp")
            self.update_dependency_log("找到已安装的yt-dlp")
            self.root.after(0, lambda: self.yt_dlp_status.set("已安装"))
            self.root.after(0, lambda: self.yt_dlp_progress_var.set(100))
            return yt_dlp_path
        
        # 更新状态
        self.root.after(0, lambda: self.yt_dlp_status.set("准备下载..."))
        self.root.after(0, lambda: self.yt_dlp_progress_var.set(0))
        self.update_dependency_log("准备下载yt-dlp...")
        
        # 使用国内镜像下载yt-dlp
        if platform.system() == "Windows":
            yt_dlp_url = "https://cdn.npmmirror.com/binaries/yt-dlp/latest/yt-dlp.exe"
        else:  # macOS和Linux
            yt_dlp_url = "https://cdn.npmmirror.com/binaries/yt-dlp/latest/yt-dlp"
        
        try:
            # 下载yt-dlp
            self.root.after(0, lambda: self.yt_dlp_status.set("正在下载..."))
            self.update_dependency_log(f"从 {yt_dlp_url} 下载yt-dlp...")
            self._download_file_with_progress(yt_dlp_url, yt_dlp_dir, self.yt_dlp_progress_var, self.yt_dlp_status)
            
            # 更新进度
            self.root.after(0, lambda: self.yt_dlp_progress_var.set(100))
            self.root.after(0, lambda: self.yt_dlp_status.set("下载完成"))
            self.update_dependency_log("yt-dlp下载完成")
            
            # 添加执行权限
            if platform.system() != "Windows":
                os.chmod(yt_dlp_path, 0o755)
            
            self.logger.info("yt-dlp下载完成")
            return yt_dlp_path
        except Exception as e:
            error_msg = f"下载yt-dlp失败: {str(e)}"
            self.logger.error(error_msg)
            self.update_dependency_log(error_msg)
            self.root.after(0, lambda: self.yt_dlp_status.set(f"下载失败: {str(e)}"))
            # 尝试备用下载源
            self.logger.info("尝试备用下载源...")
            self.update_dependency_log("尝试备用下载源...")
            self.root.after(0, lambda: self.yt_dlp_status.set("尝试备用源..."))
            self._try_backup_yt_dlp_source()
            raise
    
    def _download_file_with_progress(self, url, target_dir, progress_var, status_var):
        """下载文件并显示进度"""
        filename = os.path.basename(urlparse(url).path)
        target_path = os.path.join(target_dir, filename)
        
        try:
            # 尝试使用requests下载
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            block_size = 8192
            downloaded_size = 0
            
            with open(target_path, 'wb') as f:
                for data in response.iter_content(block_size):
                    if self.abort_all_tasks:
                        raise Exception("下载已取消")
                    
                    downloaded_size += len(data)
                    f.write(data)
                    
                    # 更新进度条
                    progress = (downloaded_size / total_size) * 100
                    self.root.after(0, lambda p=progress: progress_var.set(p))
                    self.root.after(0, lambda s=f"下载中: {progress:.1f}%": status_var.set(s))
        
        except Exception as e:
            # 清理不完整的下载
            if os.path.exists(target_path):
                os.remove(target_path)
            raise
    
    def _try_backup_ffmpeg_source(self):
        """尝试从备用源下载FFmpeg"""
        ffmpeg_dir = os.path.join(self.tool_dir, "ffmpeg")
        os.makedirs(ffmpeg_dir, exist_ok=True)
        
        # 根据操作系统确定FFmpeg文件路径
        if platform.system() == "Windows":
            ffmpeg_exe = "ffmpeg.exe"
            ffplay_exe = "ffplay.exe"
            ffprobe_exe = "ffprobe.exe"
        else:  # macOS和Linux
            ffmpeg_exe = "ffmpeg"
            ffplay_exe = "ffplay"
            ffprobe_exe = "ffprobe"
        
        ffmpeg_path = os.path.join(ffmpeg_dir, ffmpeg_exe)
        ffplay_path = os.path.join(ffmpeg_dir, ffplay_exe)
        ffprobe_path = os.path.join(ffmpeg_dir, ffprobe_exe)
        
        # 使用备用国内镜像
        if platform.system() == "Windows":
            ffmpeg_url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
        elif platform.system() == "Darwin":  # macOS
            ffmpeg_url = "https://evermeet.cx/ffmpeg/ffmpeg-latest.zip"
        else:  # Linux
            ffmpeg_url = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
        
        try:
            # 下载FFmpeg
            self.root.after(0, lambda: self.ffmpeg_status.set("正在从备用源下载FFmpeg..."))
            self.root.after(0, lambda: self.ffmpeg_progress_var.set(0))
            self._download_file_with_progress(ffmpeg_url, ffmpeg_dir, self.ffmpeg_progress_var, self.ffmpeg_status)
            
            # 更新进度
            self.root.after(0, lambda: self.ffmpeg_status.set("正在解压FFmpeg..."))
            self.root.after(0, lambda: self.ffmpeg_progress_var.set(70))
            
            # 解压文件 (与之前相同的解压逻辑)
            filename = os.path.basename(urlparse(ffmpeg_url).path)
            download_path = os.path.join(ffmpeg_dir, filename)
            
            if filename.endswith('.zip'):
                import zipfile
                with zipfile.ZipFile(download_path, 'r') as zip_ref:
                    # 查找包含ffmpeg的目录
                    namelist = zip_ref.namelist()
                    ffmpeg_found = False
                    ffplay_found = False
                    ffprobe_found = False
                    
                    # 首先查找根目录中的文件
                    for name in namelist:
                        if name.endswith(ffmpeg_exe) and not ffmpeg_found:
                            zip_ref.extract(name, ffmpeg_dir)
                            os.rename(os.path.join(ffmpeg_dir, name), ffmpeg_path)
                            ffmpeg_found = True
                        elif name.endswith(ffplay_exe) and not ffplay_found:
                            zip_ref.extract(name, ffmpeg_dir)
                            os.rename(os.path.join(ffmpeg_dir, name), ffplay_path)
                            ffplay_found = True
                        elif name.endswith(ffprobe_exe) and not ffprobe_found:
                            zip_ref.extract(name, ffmpeg_dir)
                            os.rename(os.path.join(ffmpeg_dir, name), ffprobe_path)
                            ffprobe_found = True
                    
                    # 如果在根目录中找不到，则在子目录中查找
                    if not (ffmpeg_found and ffplay_found and ffprobe_found):
                        for name in namelist:
                            if '/' in name or '\\' in name:  # 子目录中的文件
                                dir_name = os.path.dirname(name)
                                if name.endswith(ffmpeg_exe) and not ffmpeg_found:
                                    zip_ref.extract(name, ffmpeg_dir)
                                    os.rename(os.path.join(ffmpeg_dir, name), ffmpeg_path)
                                    ffmpeg_found = True
                                elif name.endswith(ffplay_exe) and not ffplay_found:
                                    zip_ref.extract(name, ffmpeg_dir)
                                    os.rename(os.path.join(ffmpeg_dir, name), ffplay_path)
                                    ffplay_found = True
                                elif name.endswith(ffprobe_exe) and not ffprobe_found:
                                    zip_ref.extract(name, ffmpeg_dir)
                                    os.rename(os.path.join(ffmpeg_dir, name), ffprobe_path)
                                    ffprobe_found = True
            
            elif filename.endswith(('.tar.gz', '.tar.xz')):
                import tarfile
                with tarfile.open(download_path, 'r') as tar_ref:
                    # 查找包含ffmpeg的目录
                    namelist = tar_ref.getnames()
                    ffmpeg_found = False
                    ffplay_found = False
                    ffprobe_found = False
                    
                    # 首先查找根目录中的文件
                    for name in namelist:
                        if name.endswith(ffmpeg_exe) and not ffmpeg_found:
                            tar_ref.extract(name, ffmpeg_dir)
                            os.rename(os.path.join(ffmpeg_dir, name), ffmpeg_path)
                            ffmpeg_found = True
                        elif name.endswith(ffplay_exe) and not ffplay_found:
                            tar_ref.extract(name, ffmpeg_dir)
                            os.rename(os.path.join(ffmpeg_dir, name), ffplay_path)
                            ffplay_found = True
                        elif name.endswith(ffprobe_exe) and not ffprobe_found:
                            tar_ref.extract(name, ffmpeg_dir)
                            os.rename(os.path.join(ffmpeg_dir, name), ffprobe_path)
                            ffprobe_found = True
                    
                    # 如果在根目录中找不到，则在子目录中查找
                    if not (ffmpeg_found and ffplay_found and ffprobe_found):
                        for name in namelist:
                            if '/' in name or '\\' in name:  # 子目录中的文件
                                dir_name = os.path.dirname(name)
                                if name.endswith(ffmpeg_exe) and not ffmpeg_found:
                                    tar_ref.extract(name, ffmpeg_dir)
                                    os.rename(os.path.join(ffmpeg_dir, name), ffmpeg_path)
                                    ffmpeg_found = True
                                elif name.endswith(ffplay_exe) and not ffplay_found:
                                    tar_ref.extract(name, ffmpeg_dir)
                                    os.rename(os.path.join(ffmpeg_dir, name), ffplay_path)
                                    ffplay_found = True
                                elif name.endswith(ffprobe_exe) and not ffprobe_found:
                                    tar_ref.extract(name, ffmpeg_dir)
                                    os.rename(os.path.join(ffmpeg_dir, name), ffprobe_path)
                                    ffprobe_found = True
            
            # 清理下载的压缩文件
            if os.path.exists(download_path):
                os.remove(download_path)
            
            # 添加执行权限
            for file_path in [ffmpeg_path, ffplay_path, ffprobe_path]:
                if os.path.exists(file_path) and platform.system() != "Windows":
                    os.chmod(file_path, 0o755)
            
            # 更新进度
            self.root.after(0, lambda: self.ffmpeg_progress_var.set(100))
            self.root.after(0, lambda: self.ffmpeg_status.set("下载完成"))
            
            self.logger.info("FFmpeg从备用源下载完成")
            return ffmpeg_path
        except Exception as e:
            self.logger.error(f"从备用源下载FFmpeg失败: {str(e)}")
            raise
    
    def _try_backup_yt_dlp_source(self):
        """尝试从备用源下载yt-dlp"""
        yt_dlp_dir = os.path.join(self.tool_dir, "yt-dlp")
        os.makedirs(yt_dlp_dir, exist_ok=True)
        
        # 根据操作系统确定yt-dlp文件路径
        if platform.system() == "Windows":
            yt_dlp_exe = "yt-dlp.exe"
        else:  # macOS和Linux
            yt_dlp_exe = "yt-dlp"
        
        yt_dlp_path = os.path.join(yt_dlp_dir, yt_dlp_exe)
        
        # 使用备用源
        if platform.system() == "Windows":
            yt_dlp_url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
        else:  # macOS和Linux
            yt_dlp_url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp"
        
        try:
            # 下载yt-dlp
            self.root.after(0, lambda: self.yt_dlp_status.set("正在从备用源下载yt-dlp..."))
            self.root.after(0, lambda: self.yt_dlp_progress_var.set(0))
            self._download_file_with_progress(yt_dlp_url, yt_dlp_dir, self.yt_dlp_progress_var, self.yt_dlp_status)
            
            # 更新进度
            self.root.after(0, lambda: self.yt_dlp_progress_var.set(100))
            self.root.after(0, lambda: self.yt_dlp_status.set("下载完成"))
            
            # 添加执行权限
            if platform.system() != "Windows":
                os.chmod(yt_dlp_path, 0o755)
            
            self.logger.info("yt-dlp从备用源下载完成")
            return yt_dlp_path
        except Exception as e:
            self.logger.error(f"从备用源下载yt-dlp失败: {str(e)}")
            raise
    
    def _create_main_interface(self):
        """创建主界面"""
        # 关闭依赖窗口
        if hasattr(self, 'dependency_window') and self.dependency_window:
            self.dependency_window.destroy()
        
        # 创建主界面
        # URL输入和代理设置
        url_frame = ttk.LabelFrame(self.root, text="视频URL和代理设置", padding="10 10 10 10")
        url_frame.pack(fill=tk.X, pady=5, ipady=5)
        
        url_input_frame = ttk.Frame(url_frame)
        url_input_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(url_input_frame, text="视频URL:").grid(row=0, column=0, sticky=tk.W, pady=5, padx=5)
        self.url_entry = ttk.Entry(url_input_frame, width=70)
        self.url_entry.grid(row=0, column=1, sticky=tk.W, pady=5, padx=5)
        self.url_entry.insert(0, "https://www.youtube.com/watch?v=")
        
        ttk.Button(url_input_frame, text="获取信息", command=self.fetch_video_info).grid(row=0, column=2, padx=5)
        
        # 批量下载支持
        ttk.Label(url_frame, text="或批量输入URLs (每行一个):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.urls_text = scrolledtext.ScrolledText(url_frame, wrap=tk.WORD, height=3)
        self.urls_text.grid(row=1, column=0, columnspan=3, sticky="ew", padx=5, pady=5)
        
        proxy_frame = ttk.Frame(url_frame)
        proxy_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(proxy_frame, text="代理 (例如: http://127.0.0.1:7897):").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.proxy_entry = ttk.Entry(proxy_frame, width=50)
        self.proxy_entry.grid(row=0, column=1, sticky=tk.W, pady=5, padx=5)
        self.proxy_entry.insert(0, "http://127.0.0.1:7897")
        
        # 视频信息预览
        info_frame = ttk.LabelFrame(self.root, text="视频信息预览", padding="10 10 10 10")
        info_frame.pack(fill=tk.X, pady=5, ipady=5)
        
        self.title_var = tk.StringVar(value="标题: ")
        self.duration_var = tk.StringVar(value="时长: ")
        self.views_var = tk.StringVar(value="观看次数: ")
        self.uploader_var = tk.StringVar(value="上传者: ")
        
        # 美化信息显示
        info_display_frame = ttk.Frame(info_frame)
        info_display_frame.pack(fill=tk.X, expand=True)
        
        ttk.Label(info_display_frame, textvariable=self.title_var).grid(row=0, column=0, sticky=tk.W, pady=2, padx=5)
        ttk.Label(info_display_frame, textvariable=self.duration_var).grid(row=0, column=1, sticky=tk.W, pady=2, padx=20)
        ttk.Label(info_display_frame, textvariable=self.views_var).grid(row=0, column=2, sticky=tk.W, pady=2, padx=20)
        ttk.Label(info_display_frame, textvariable=self.uploader_var).grid(row=0, column=3, sticky=tk.W, pady=2, padx=20)
        
        # 下载选项
        options_frame = ttk.LabelFrame(self.root, text="下载选项", padding="10 10 10 10")
        options_frame.pack(fill=tk.X, pady=5, ipady=5)
        
        # 保存路径设置
        save_path_frame = ttk.Frame(options_frame)
        save_path_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(save_path_frame, text="保存路径:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.save_path_var = tk.StringVar(value=r"D:\Users\Jimwoo\Downloads")
        ttk.Entry(save_path_frame, textvariable=self.save_path_var, width=50).grid(row=0, column=1, sticky=tk.W, padx=(0, 5))
        ttk.Button(save_path_frame, text="浏览...", command=self.browse_save_path).grid(row=0, column=2, sticky=tk.W)
        
        # 下载格式选择
        format_frame = ttk.Frame(options_frame)
        format_frame.pack(fill=tk.X, pady=5)
        
        # 视频格式选择
        video_format_frame = ttk.Frame(format_frame)
        video_format_frame.pack(fill=tk.X, pady=2)
        
        ttk.Label(video_format_frame, text="视频格式:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.video_format_var = tk.StringVar()
        self.video_format_combobox = ttk.Combobox(video_format_frame, textvariable=self.video_format_var, width=40, state="disabled")
        self.video_format_combobox.grid(row=0, column=1, sticky=tk.W, padx=5)
        
        # 音频格式选择
        audio_format_frame = ttk.Frame(format_frame)
        audio_format_frame.pack(fill=tk.X, pady=2)
        
        ttk.Label(audio_format_frame, text="音频格式:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.audio_format_var = tk.StringVar()
        self.audio_format_combobox = ttk.Combobox(audio_format_frame, textvariable=self.audio_format_var, width=40, state="disabled")
        self.audio_format_combobox.grid(row=0, column=1, sticky=tk.W, padx=5)
        
        # 自定义格式ID输入
        custom_format_frame = ttk.Frame(options_frame)
        custom_format_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(custom_format_frame, text="自定义格式ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.custom_format_var = tk.StringVar()
        ttk.Entry(custom_format_frame, textvariable=self.custom_format_var, width=15).
