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
        
        # 设置中文字体支持
        self.style = ttk.Style()
        self.style.configure('TLabel', font=('SimHei', 10))
        self.style.configure('TButton', font=('SimHei', 10))
        self.style.configure('TEntry', font=('SimHei', 10))
        self.style.configure('TCombobox', font=('SimHei', 10))
        
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
        
        # 检查并下载依赖
        self.check_dependencies()
    
    def setup_logging(self):
        """配置日志系统，将日志输出到GUI"""
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        # 创建日志处理器，将日志输出到GUI
        self.log_handler = QueueHandler(self.result_queue)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        self.log_handler.setFormatter(formatter)
        self.logger.addHandler(self.log_handler)
    
    def check_dependencies(self):
        """检查并下载必要的依赖"""
        # 创建依赖检查窗口
        self.dependency_window = tk.Toplevel(self.root)
        self.dependency_window.title("初始化")
        self.dependency_window.geometry("400x200")
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
            text="正在下载重要依赖文件yt-dlp和FFmpeg组件！",
            font=('SimHei', 12)
        ).pack(pady=20)
        
        # 添加进度条
        self.dependency_progress_var = tk.DoubleVar()
        self.dependency_progress_bar = ttk.Progressbar(
            self.dependency_window, 
            variable=self.dependency_progress_var, 
            length=300, 
            mode='determinate'
        )
        self.dependency_progress_bar.pack(pady=10)
        
        # 添加状态标签
        self.dependency_status = tk.StringVar(value="准备下载...")
        ttk.Label(
            self.dependency_window, 
            textvariable=self.dependency_status,
            font=('SimHei', 10)
        ).pack(pady=10)
        
        # 确保窗口可见
        self.dependency_window.deiconify()
        self.root.update()
        
        # 启动依赖检查线程
        threading.Thread(target=self._check_dependencies_thread, daemon=True).start()
    
    def _check_dependencies_thread(self):
        """在单独线程中检查并下载依赖"""
        try:
            # 检查并下载yt-dlp
            self.ydl_path = self._get_yt_dlp_path()
            
            # 检查并下载FFmpeg
            self.ffmpeg_path = self._get_ffmpeg_path()
            
            # 所有依赖都已准备好，关闭依赖窗口并创建主界面
            self.root.after(0, self._create_main_interface)
        except Exception as e:
            # 确保在发生异常时显示错误信息
            self.logger.error(f"初始化失败: {str(e)}")
            self.root.after(0, lambda: messagebox.showerror("初始化失败", f"下载依赖失败: {str(e)}"))
            # 关闭依赖窗口
            self.root.after(0, self.dependency_window.destroy)
            # 退出应用
            self.root.after(0, self.root.destroy)
    
    def _create_main_interface(self):
        """创建主界面"""
        self.dependency_window.destroy()
        
        # 创建界面
        self.create_widgets()
        
        # 加载下载历史
        self.load_download_history()
        
        # 启动队列处理线程
        self.processing_thread = threading.Thread(target=self.process_queue, daemon=True)
        self.processing_thread.start()
        
        # 启动结果处理
        self.root.after(100, self.process_results)
        
        # 用于终止下载的变量
        self.ydl_instance = None
        self.is_downloading = False
        self.download_threads = {}  # 跟踪所有下载线程
    
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
            return ffmpeg_path
        
        # 更新状态
        self.root.after(0, lambda: self.dependency_status.set("准备下载FFmpeg..."))
        self.root.after(0, lambda: self.dependency_progress_var.set(0))
        
        # 使用国内镜像下载FFmpeg
        if platform.system() == "Windows":
            ffmpeg_url = "https://cdn.npmmirror.com/binaries/ffmpeg/latest/ffmpeg-win64-latest.zip"
        elif platform.system() == "Darwin":  # macOS
            ffmpeg_url = "https://cdn.npmmirror.com/binaries/ffmpeg/latest/ffmpeg-osx-x64-latest.zip"
        else:  # Linux
            ffmpeg_url = "https://cdn.npmmirror.com/binaries/ffmpeg/latest/ffmpeg-linux-x64-latest.zip"
        
        try:
            # 下载FFmpeg
            self.root.after(0, lambda: self.dependency_status.set("正在下载FFmpeg..."))
            self._download_file_with_progress(ffmpeg_url, ffmpeg_dir)
            
            # 更新进度
            self.root.after(0, lambda: self.dependency_progress_var.set(70))
            self.root.after(0, lambda: self.dependency_status.set("正在解压FFmpeg..."))
            
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
            self.root.after(0, lambda: self.dependency_progress_var.set(100))
            self.root.after(0, lambda: self.dependency_status.set("FFmpeg下载完成"))
            
            self.logger.info("FFmpeg下载完成")
            return ffmpeg_path
        except Exception as e:
            self.logger.error(f"下载FFmpeg失败: {str(e)}")
            # 尝试备用下载源
            self.logger.info("尝试备用下载源...")
            self._try_backup_ffmpeg_source()
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
            self.root.after(0, lambda: self.dependency_status.set("正在从备用源下载FFmpeg..."))
            self.root.after(0, lambda: self.dependency_progress_var.set(0))
            self._download_file_with_progress(ffmpeg_url, ffmpeg_dir)
            
            # 更新进度
            self.root.after(0, lambda: self.dependency_progress_var.set(70))
            self.root.after(0, lambda: self.dependency_status.set("正在解压FFmpeg..."))
            
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
                    
                    # 解压逻辑... (与之前相同)
                    
            elif filename.endswith(('.tar.gz', '.tar.xz')):
                import tarfile
                with tarfile.open(download_path, 'r') as tar_ref:
                    # 查找包含ffmpeg的目录
                    namelist = tar_ref.getnames()
                    ffmpeg_found = False
                    ffplay_found = False
                    ffprobe_found = False
                    
                    # 解压逻辑... (与之前相同)
            
            # 清理下载的压缩文件
            if os.path.exists(download_path):
                os.remove(download_path)
            
            # 添加执行权限
            for file_path in [ffmpeg_path, ffplay_path, ffprobe_path]:
                if os.path.exists(file_path) and platform.system() != "Windows":
                    os.chmod(file_path, 0o755)
            
            # 更新进度
            self.root.after(0, lambda: self.dependency_progress_var.set(100))
            self.root.after(0, lambda: self.dependency_status.set("FFmpeg下载完成"))
            
            self.logger.info("FFmpeg从备用源下载完成")
            return ffmpeg_path
        except Exception as e:
            self.logger.error(f"从备用源下载FFmpeg失败: {str(e)}")
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
            return yt_dlp_path
        
        # 更新状态
        self.root.after(0, lambda: self.dependency_status.set("准备下载yt-dlp..."))
        self.root.after(0, lambda: self.dependency_progress_var.set(0))
        
        # 使用国内镜像下载yt-dlp
        if platform.system() == "Windows":
            yt_dlp_url = "https://cdn.npmmirror.com/binaries/yt-dlp/latest/yt-dlp.exe"
        else:  # macOS和Linux
            yt_dlp_url = "https://cdn.npmmirror.com/binaries/yt-dlp/latest/yt-dlp"
        
        try:
            # 下载yt-dlp
            self.root.after(0, lambda: self.dependency_status.set("正在下载yt-dlp..."))
            self._download_file_with_progress(yt_dlp_url, yt_dlp_dir)
            
            # 更新进度
            self.root.after(0, lambda: self.dependency_progress_var.set(100))
            self.root.after(0, lambda: self.dependency_status.set("yt-dlp下载完成"))
            
            # 添加执行权限
            if platform.system() != "Windows":
                os.chmod(yt_dlp_path, 0o755)
            
            self.logger.info("yt-dlp下载完成")
            return yt_dlp_path
        except Exception as e:
            self.logger.error(f"下载yt-dlp失败: {str(e)}")
            # 尝试备用下载源
            self.logger.info("尝试备用下载源...")
            self._try_backup_yt_dlp_source()
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
            self.root.after(0, lambda: self.dependency_status.set("正在从备用源下载yt-dlp..."))
            self.root.after(0, lambda: self.dependency_progress_var.set(0))
            self._download_file_with_progress(yt_dlp_url, yt_dlp_dir)
            
            # 更新进度
            self.root.after(0, lambda: self.dependency_progress_var.set(100))
            self.root.after(0, lambda: self.dependency_status.set("yt-dlp下载完成"))
            
            # 添加执行权限
            if platform.system() != "Windows":
                os.chmod(yt_dlp_path, 0o755)
            
            self.logger.info("yt-dlp从备用源下载完成")
            return yt_dlp_path
        except Exception as e:
            self.logger.error(f"从备用源下载yt-dlp失败: {str(e)}")
            raise
    
    def _download_file_with_progress(self, url, target_dir):
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
                    self.root.after(0, lambda p=progress: self.dependency_progress_var.set(p))
        
        except Exception as e:
            # 清理不完整的下载
            if os.path.exists(target_path):
                os.remove(target_path)
            raise
    
    def create_widgets(self):
        """创建GUI界面组件"""
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # URL和代理设置
        url_frame = ttk.LabelFrame(main_frame, text="视频信息", padding=10)
        url_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(url_frame, text="YouTube 链接:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.url_entry = ttk.Entry(url_frame, width=60)
        self.url_entry.grid(row=0, column=1, sticky=tk.W, pady=5, padx=5)
        self.url_entry.insert(0, "https://www.youtube.com/watch?v=")
        
        ttk.Button(url_frame, text="获取信息", command=self.fetch_video_info).grid(row=0, column=2, padx=5)
        
        # 批量下载支持
        ttk.Label(url_frame, text="或批量输入URLs (每行一个):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.urls_text = scrolledtext.ScrolledText(url_frame, wrap=tk.WORD, height=3)
        self.urls_text.grid(row=1, column=1, sticky=tk.W, pady=5, padx=5)
        
        ttk.Label(url_frame, text="代理地址 (可选):").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.proxy_entry = ttk.Entry(url_frame, width=60)
        self.proxy_entry.grid(row=2, column=1, sticky=tk.W, pady=5, padx=5)
        self.proxy_entry.insert(0, "http://127.0.0.1:7897")
        
        # 视频信息预览
        info_frame = ttk.LabelFrame(main_frame, text="视频信息预览", padding=10)
        info_frame.pack(fill=tk.X, pady=5)
        
        self.title_var = tk.StringVar(value="标题: ")
        self.duration_var = tk.StringVar(value="时长: ")
        self.views_var = tk.StringVar(value="观看次数: ")
        self.uploader_var = tk.StringVar(value="上传者: ")
        
        ttk.Label(info_frame, textvariable=self.title_var).grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Label(info_frame, textvariable=self.duration_var).grid(row=0, column=1, sticky=tk.W, pady=2, padx=20)
        ttk.Label(info_frame, textvariable=self.views_var).grid(row=0, column=2, sticky=tk.W, pady=2, padx=20)
        ttk.Label(info_frame, textvariable=self.uploader_var).grid(row=0, column=3, sticky=tk.W, pady=2, padx=20)
        
        # 下载选项
        options_frame = ttk.LabelFrame(main_frame, text="下载选项", padding=10)
        options_frame.pack(fill=tk.X, pady=5)
        
        # 保存路径
        ttk.Label(options_frame, text="保存路径:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.save_path_var = tk.StringVar(value=".")
        save_path_frame = ttk.Frame(options_frame)
        save_path_frame.grid(row=0, column=1, sticky=tk.W, pady=5)
        
        ttk.Entry(save_path_frame, textvariable=self.save_path_var, width=50).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(save_path_frame, text="浏览...", command=self.browse_save_path).pack(side=tk.LEFT)
        
        # 下载格式预设 - 分开视频和音频选项
        ttk.Label(options_frame, text="视频格式:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.video_format_var = tk.StringVar(value="bestvideo")
        self.video_format_manual = tk.StringVar()
        
        video_frame = ttk.Frame(options_frame)
        video_frame.grid(row=1, column=1, sticky=tk.W, pady=5)
        
        # 视频格式下拉菜单
        self.video_format_combo = ttk.Combobox(video_frame, textvariable=self.video_format_var, width=30)
        self.video_format_combo['values'] = [
            ("自动选择", "bestvideo"),
            ("最高质量视频", "bestvideo"),
            ("720p 视频", "best[height<=720]"),
            ("480p 视频", "best[height<=480]"),
            ("360p 视频", "best[height<=360]"),
            ("无视频", "none")
        ]
        self.video_format_combo.current(0)
        self.video_format_combo.pack(side=tk.LEFT, padx=(0, 5))
        
        # 手动输入格式ID
        ttk.Label(video_frame, text="手动ID:").pack(side=tk.LEFT, padx=(5, 0))
        ttk.Entry(video_frame, textvariable=self.video_format_manual, width=10).pack(side=tk.LEFT)
        
        ttk.Label(options_frame, text="音频格式:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.audio_format_var = tk.StringVar(value="bestaudio")
        self.audio_format_manual = tk.StringVar()
        
        audio_frame = ttk.Frame(options_frame)
        audio_frame.grid(row=2, column=1, sticky=tk.W, pady=5)
        
        # 音频格式下拉菜单
        self.audio_format_combo = ttk.Combobox(audio_frame, textvariable=self.audio_format_var, width=30)
        self.audio_format_combo['values'] = [
            ("自动选择", "bestaudio"),
            ("最高质量音频", "bestaudio"),
            ("MP3 音频", "bestaudio"),
            ("无音频", "none")
        ]
        self.audio_format_combo.current(0)
        self.audio_format_combo.pack(side=tk.LEFT, padx=(0, 5))
        
        # 手动输入格式ID
        ttk.Label(audio_frame, text="手动ID:").pack(side=tk.LEFT, padx=(5, 0))
        ttk.Entry(audio_frame, textvariable=self.audio_format_manual, width=10).pack(side=tk.LEFT)
        
        # 字幕选项
        self.subtitle_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="下载字幕", variable=self.subtitle_var).grid(row=2, column=2, sticky=tk.W, pady=5)
        
        # 多线程下载
        ttk.Label(options_frame, text="多线程数:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.threads_var = tk.StringVar(value="4")
        ttk.Combobox(options_frame, textvariable=self.threads_var, values=["1", "2", "4", "8", "16"], width=5).grid(row=3, column=1, sticky=tk.W, pady=5, padx=5)
        
        # 转码选项
        self.transcode_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="下载后转码", variable=self.transcode_var).grid(row=3, column=2, sticky=tk.W, pady=5)
        
        self.transcode_format = tk.StringVar(value="mp4")
        ttk.Combobox(options_frame, textvariable=self.transcode_format, values=["mp4", "mkv", "avi", "mov", "webm"], width=10).grid(row=3, column=3, sticky=tk.W, pady=5, padx=5)
        
        # 按钮
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="查询格式", command=self.query_formats, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="开始下载", command=self.start_download, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="终止下载", command=self.stop_download, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="清空日志", command=self.clear_logs, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="查看历史", command=self.show_history, width=15).pack(side=tk.LEFT, padx=5)
        
        # 下载进度条
        progress_frame = ttk.LabelFrame(main_frame, text="下载进度", padding=10)
        progress_frame.pack(fill=tk.X, pady=5)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, length=100, mode='determinate')
        self.progress_bar.pack(fill=tk.X, expand=True)
        
        self.progress_label = ttk.Label(progress_frame, text="准备就绪")
        self.progress_label.pack(anchor=tk.W, pady=2)
        
        # 信息窗口日志
        log_frame = ttk.LabelFrame(main_frame, text="信息窗口日志", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=10)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.config(state=tk.DISABLED)
        
        self.log_text.tag_configure("error", foreground="red")
        self.log_text.tag_configure("success", foreground="green")
        self.log_text.tag_configure("info", foreground="black")
        self.log_text.tag_configure("progress", foreground="blue")
    
    def browse_save_path(self):
        """浏览并选择保存路径"""
        directory = filedialog.askdirectory(title="选择保存路径")
        if directory:
            self.save_path_var.set(directory)
    
    def validate_url(self, url):
        """验证URL格式"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except ValueError:
            return False
    
    def fetch_video_info(self):
        """获取视频信息并预览"""
        url = self.url_entry.get().strip()
        proxy = self.proxy_entry.get().strip() or None
        
        if not self.validate_url(url):
            messagebox.showerror("错误", "请输入有效的 YouTube 链接")
            return
            
        self.logger.info(f"获取视频信息: {url}")
        
        def _fetch():
            try:
                ydl_opts = {
                    'socket_timeout': 10,
                    'proxy': proxy,
                    'quiet': True
                }
                
                # 如果指定了yt-dlp路径，则使用它
                if self.ydl_path:
                    os.environ['YT_DLP_PATH'] = self.ydl_path
                    self.logger.info(f"使用yt-dlp路径: {self.ydl_path}")
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info_dict = ydl.extract_info(url, download=False)
                    
                    title = info_dict.get('title', '未知标题')
                    duration = info_dict.get('duration', 0)
                    views = info_dict.get('view_count', 0)
                    uploader = info_dict.get('uploader', '未知上传者')
                    
                    # 格式化时长
                    duration_str = "未知"
                    if duration:
                        hours, remainder = divmod(int(duration), 3600)
                        minutes, seconds = divmod(remainder, 60)
                        if hours > 0:
                            duration_str = f"{hours}小时{minutes}分{seconds}秒"
                        else:
                            duration_str = f"{minutes}分{seconds}秒"
                    
                    # 格式化观看次数
                    views_str = f"{views:,}"
                    
                    self.title_var.set(f"标题: {title}")
                    self.duration_var.set(f"时长: {duration_str}")
                    self.views_var.set(f"观看次数: {views_str}")
                    self.uploader_var.set(f"上传者: {uploader}")
                    
                    # 保存视频信息
                    self.video_info[url] = info_dict
                    
                    self.result_queue.put(("success", f"成功获取视频信息: {title}"))
            except Exception as e:
                self.result_queue.put(("error", f"获取视频信息失败: {str(e)}"))
        
        # 在单独线程中获取信息
        threading.Thread(target=_fetch, daemon=True).start()
    
    def query_formats(self):
        """查询视频格式"""
        url = self.url_entry.get().strip()
        proxy = self.proxy_entry.get().strip() or None
        
        if not self.validate_url(url):
            messagebox.showerror("错误", "请输入有效的 YouTube 链接")
            return
            
        self.logger.info(f"查询视频格式: {url}")
        
        def _query():
            try:
                ydl_opts = {
                    'socket_timeout': 10,
                    'proxy': proxy,
                    'quiet': True
                }
                
                # 如果指定了yt-dlp路径，则使用它
                if self.ydl_path:
                    os.environ['YT_DLP_PATH'] = self.ydl_path
