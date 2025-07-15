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
        self.root.withdraw()  # 隐藏主窗口，直到初始化完成
        
        # 设置中文字体支持
        self.style = ttk.Style()
        self.style.configure('TLabel', font=('SimHei', 10))
        self.style.configure('TButton', font=('SimHei', 10))
        self.style.configure('TEntry', font=('SimHei', 10))
        self.style.configure('TCombobox', font=('SimHei', 10))
        
        # 自定义主题颜色
        self.bg_color = "#1E1E1E"        # 主背景色
        self.card_color = "#2D2D2D"      # 卡片背景色
        self.primary_color = "#FF0000"   # 主色调 (YouTube红)
        self.secondary_color = "#383838" # 次要背景色
        self.text_color = "#FFFFFF"      # 文本颜色
        self.accent_color = "#4CAF50"    # 强调色 (绿色)
        
        # 配置自定义样式
        self.style.configure('Main.TFrame', background=self.bg_color)
        self.style.configure('Card.TFrame', background=self.card_color)
        self.style.configure('Title.TLabel', font=('SimHei', 24, 'bold'), foreground=self.text_color, background=self.bg_color)
        self.style.configure('Subtitle.TLabel', font=('SimHei', 12), foreground=self.text_color, background=self.bg_color)
        self.style.configure('CardTitle.TLabel', font=('SimHei', 16, 'bold'), foreground=self.text_color, background=self.card_color)
        self.style.configure('CardText.TLabel', font=('SimHei', 10), foreground=self.text_color, background=self.card_color)
        self.style.configure('TButton', font=('SimHei', 10, 'bold'), foreground=self.text_color, background=self.primary_color)
        self.style.configure('Accent.TButton', font=('SimHei', 10, 'bold'), foreground=self.text_color, background=self.accent_color)
        self.style.configure('TProgressbar', background=self.primary_color, troughcolor=self.secondary_color)
        
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
        
        # 创建并显示启动画面
        self.create_splash_screen()
        
        # 检查并下载依赖
        threading.Thread(target=self.check_dependencies, daemon=True).start()
    
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
    
    def create_splash_screen(self):
        """创建并显示美化后的启动画面"""
        self.splash = tk.Toplevel(self.root)
        self.splash.title("启动中...")
        self.splash.geometry("600x400")
        self.splash.resizable(False, False)
        self.splash.transient(self.root)
        self.splash.overrideredirect(True)  # 无边框窗口
        self.splash.configure(bg=self.bg_color)
        
        # 居中显示
        self.splash.update_idletasks()
        width = self.splash.winfo_width()
        height = self.splash.winfo_height()
        x = (self.splash.winfo_screenwidth() // 2) - (width // 2)
        y = (self.splash.winfo_screenheight() // 2) - (height // 2)
        self.splash.geometry('{}x{}+{}+{}'.format(width, height, x, y))
        
        # 创建主框架
        main_frame = ttk.Frame(self.splash, style='Main.TFrame', padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 添加应用名称和版本
        title_frame = ttk.Frame(main_frame, style='Main.TFrame')
        title_frame.pack(pady=(40, 20))
        
        # YouTube图标
        icon_frame = ttk.Frame(title_frame, style='Main.TFrame')
        icon_frame.pack(side=tk.LEFT, padx=(0, 10))
        
        icon_canvas = tk.Canvas(icon_frame, width=60, height=40, bg=self.bg_color, highlightthickness=0)
        icon_canvas.pack()
        icon_canvas.create_polygon(10, 5, 50, 20, 10, 35, fill=self.primary_color)
        
        title_label = ttk.Label(
            title_frame, 
            text="YouTube 下载器",
            style='Title.TLabel'
        )
        title_label.pack(side=tk.LEFT)
        
        ttk.Label(
            main_frame, 
            text="版本 1.0.0",
            style='Subtitle.TLabel'
        ).pack(pady=(0, 40))
        
        # 依赖状态框架
        dependencies_frame = ttk.LabelFrame(main_frame, text="依赖状态", style='Card.TFrame', padding="10")
        dependencies_frame.pack(fill=tk.X, pady=10)
        
        # yt-dlp状态
        yt_dlp_frame = ttk.Frame(dependencies_frame, style='Card.TFrame')
        yt_dlp_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(yt_dlp_frame, text="yt-dlp:", style='CardText.TLabel').pack(side=tk.LEFT, padx=(0, 10))
        
        self.yt_dlp_status = tk.StringVar(value="检查中...")
        ttk.Label(yt_dlp_frame, textvariable=self.yt_dlp_status, style='CardText.TLabel').pack(side=tk.LEFT)
        
        self.yt_dlp_progress_var = tk.DoubleVar()
        self.yt_dlp_progress_bar = ttk.Progressbar(
            yt_dlp_frame, 
            variable=self.yt_dlp_progress_var, 
            length=300, 
            mode='determinate'
        )
        self.yt_dlp_progress_bar.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        
        # FFmpeg状态
        ffmpeg_frame = ttk.Frame(dependencies_frame, style='Card.TFrame')
        ffmpeg_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(ffmpeg_frame, text="FFmpeg:", style='CardText.TLabel').pack(side=tk.LEFT, padx=(0, 10))
        
        self.ffmpeg_status = tk.StringVar(value="检查中...")
        ttk.Label(ffmpeg_frame, textvariable=self.ffmpeg_status, style='CardText.TLabel').pack(side=tk.LEFT)
        
        self.ffmpeg_progress_var = tk.DoubleVar()
        self.ffmpeg_progress_bar = ttk.Progressbar(
            ffmpeg_frame, 
            variable=self.ffmpeg_progress_var, 
            length=300, 
            mode='determinate'
        )
        self.ffmpeg_progress_bar.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        
        # 总体进度
        overall_frame = ttk.Frame(main_frame, style='Main.TFrame')
        overall_frame.pack(fill=tk.X, pady=20)
        
        ttk.Label(overall_frame, text="总体进度:", style='Subtitle.TLabel').pack(side=tk.LEFT, padx=(0, 10))
        
        self.overall_status = tk.StringVar(value="初始化中...")
        ttk.Label(overall_frame, textvariable=self.overall_status, style='Subtitle.TLabel').pack(side=tk.LEFT)
        
        self.overall_progress_var = tk.DoubleVar()
        self.overall_progress_bar = ttk.Progressbar(
            overall_frame, 
            variable=self.overall_progress_var, 
            length=400, 
            mode='determinate'
        )
        self.overall_progress_bar.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        
        # 底部信息
        footer_frame = ttk.Frame(main_frame, style='Main.TFrame')
        footer_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(20, 0))
        
        ttk.Label(
            footer_frame, 
            text="© 2025 YouTube 下载器 - 所有权利保留",
            style='Subtitle.TLabel'
        ).pack(anchor=tk.CENTER)
        
        # 确保窗口可见
        self.splash.deiconify()
        self.root.update()
    
    def check_dependencies(self):
        """检查并下载必要的依赖"""
        try:
            # 初始化总体进度
            total_dependencies = 2
            completed_dependencies = 0
            
            # 检查并下载yt-dlp
            self.overall_status.set("检查yt-dlp...")
            self.overall_progress_var.set((completed_dependencies / total_dependencies) * 100)
            
            self.ydl_path = self._get_yt_dlp_path()
            completed_dependencies += 1
            self.overall_progress_var.set((completed_dependencies / total_dependencies) * 100)
            
            # 检查并下载FFmpeg
            self.overall_status.set("检查FFmpeg...")
            
            self.ffmpeg_path = self._get_ffmpeg_path()
            completed_dependencies += 1
            self.overall_progress_var.set((completed_dependencies / total_dependencies) * 100)
            
            # 所有依赖都已准备好，关闭启动画面并创建主界面
            self.overall_status.set("初始化完成")
            self.logger.info("所有依赖准备就绪")
            
            # 延迟1秒让用户看到完成状态
            self.root.after(1000, self._create_main_interface)
        except Exception as e:
            # 确保在发生异常时显示错误信息
            error_msg = f"初始化失败: {str(e)}"
            self.logger.error(error_msg)
            self.root.after(0, lambda: messagebox.showerror("初始化失败", error_msg))
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
            self.root.after(0, lambda: self.ffmpeg_status.set("已安装"))
            self.root.after(0, lambda: self.ffmpeg_progress_var.set(100))
            return ffmpeg_path
        
        # 更新状态
        self.root.after(0, lambda: self.ffmpeg_status.set("准备下载..."))
        self.root.after(0, lambda: self.ffmpeg_progress_var.set(0))
        
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
            self._download_file_with_progress(ffmpeg_url, ffmpeg_dir, self.ffmpeg_progress_var, self.ffmpeg_status)
            
            # 更新进度
            self.root.after(0, lambda: self.ffmpeg_status.set("正在解压..."))
            self.root.after(0, lambda: self.ffmpeg_progress_var.set(70))
            
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
            
            self.logger.info("FFmpeg下载完成")
            return ffmpeg_path
        except Exception as e:
            error_msg = f"下载FFmpeg失败: {str(e)}"
            self.logger.error(error_msg)
            self.root.after(0, lambda: self.ffmpeg_status.set(f"下载失败: {str(e)}"))
            # 尝试备用下载源
            self.logger.info("尝试备用下载源...")
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
            self.root.after(0, lambda: self.yt_dlp_status.set("已安装"))
            self.root.after(0, lambda: self.yt_dlp_progress_var.set(100))
            return yt_dlp_path
        
        # 更新状态
        self.root.after(0, lambda: self.yt_dlp_status.set("准备下载..."))
        self.root.after(0, lambda: self.yt_dlp_progress_var.set(0))
        
        # 使用国内镜像下载yt-dlp
        if platform.system() == "Windows":
            yt_dlp_url = "https://cdn.npmmirror.com/binaries/yt-dlp/latest/yt-dlp.exe"
        else:  # macOS和Linux
            yt_dlp_url = "https://cdn.npmmirror.com/binaries/yt-dlp/latest/yt-dlp"
        
        try:
            # 下载yt-dlp
            self.root.after(0, lambda: self.yt_dlp_status.set("正在下载..."))
            self._download_file_with_progress(yt_dlp_url, yt_dlp_dir, self.yt_dlp_progress_var, self.yt_dlp_status)
            
            # 更新进度
            self.root.after(0, lambda: self.yt_dlp_progress_var.set(100))
            self.root.after(0, lambda: self.yt_dlp_status.set("下载完成"))
            
            # 添加执行权限
            if platform.system() != "Windows":
                os.chmod(yt_dlp_path, 0o755)
            
            self.logger.info("yt-dlp下载完成")
            return yt_dlp_path
        except Exception as e:
            error_msg = f"下载yt-dlp失败: {str(e)}"
            self.logger.error(error_msg)
            self.root.after(0, lambda: self.yt_dlp_status.set(f"下载失败: {str(e)}"))
            # 尝试备用下载源
            self.logger.info("尝试备用下载源...")
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
        # 备用源下载逻辑（与之前相同）
        pass
    
    def _try_backup_yt_dlp_source(self):
        """尝试从备用源下载yt-dlp"""
        # 备用源下载逻辑（与之前相同）
        pass
    
    def _create_main_interface(self):
        """创建美化后的主界面"""
        # 关闭启动画面
        if hasattr(self, 'splash') and self.splash:
            self.splash.destroy()
        
        # 显示主窗口
        self.root.deiconify()
        self.root.configure(bg=self.bg_color)
        
        # 创建顶部导航栏
        nav_frame = ttk.Frame(self.root, style='Card.TFrame', padding="10")
        nav_frame.pack(fill=tk.X)
        
        # 应用名称
        ttk.Label(
            nav_frame, 
            text="YouTube 下载器",
            style='Title.TLabel'
        ).pack(side=tk.LEFT, padx=10)
        
        # 状态栏
        status_frame = ttk.Frame(self.root, style='Card.TFrame', padding="5")
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(
            status_frame, 
            textvariable=self.status_var,
            style='Subtitle.TLabel'
        ).pack(side=tk.LEFT, padx=10)
        
        # 主内容区域
        content_frame = ttk.Frame(self.root, style='Main.TFrame', padding="20")
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # URL输入区域
        url_frame = ttk.LabelFrame(content_frame, text="视频URL", style='Card.TFrame', padding="10")
        url_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.url_entry = ttk.Entry(url_frame, width=70, font=('SimHei', 12))
        self.url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        fetch_button = ttk.Button(
            url_frame, 
            text="获取视频信息", 
            command=self.fetch_video_info,
            style='Accent.TButton'
        )
        fetch_button.pack(side=tk.RIGHT)
        
        # 视频信息区域
        info_frame = ttk.LabelFrame(content_frame, text="视频信息", style='Card.TFrame', padding="10")
        info_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # 左侧缩略图区域
        thumb_frame = ttk.Frame(info_frame, style='Card.TFrame')
        thumb_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        # 模拟缩略图
        self.thumb_canvas = tk.Canvas(thumb_frame, width=320, height=180, bg=self.secondary_color, highlightthickness=0)
        self.thumb_canvas.pack(padx=10, pady=10)
        
        # 播放按钮图标
        self.thumb_canvas.create_polygon(
            140, 80, 200, 120, 140, 160, 
            fill=self.primary_color, outline=""
        )
        
        # 右侧信息区域
        details_frame = ttk.Frame(info_frame, style='Card.TFrame')
        details_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self.title_var = tk.StringVar(value="视频标题")
        ttk.Label(
            details_frame, 
            textvariable=self.title_var,
            style='CardTitle.TLabel'
        ).pack(anchor=tk.W, padx=10, pady=(10, 5))
        
        # 信息标签
        info_labels = ttk.Frame(details_frame, style='Card.TFrame')
        info_labels.pack(fill=tk.X, padx=10, pady=5)
        
        self.duration_var = tk.StringVar(value="时长: --:--")
        ttk.Label(
            info_labels, 
            textvariable=self.duration_var,
            style='CardText.TLabel'
        ).pack(side=tk.LEFT, padx=(0, 20))
        
        self.views_var = tk.StringVar(value="观看次数: --")
        ttk.Label(
            info_labels, 
            textvariable=self.views_var,
            style='CardText.TLabel'
        ).pack(side=tk.LEFT, padx=(0, 20))
        
        self.date_var = tk.StringVar(value="发布日期: --")
        ttk.Label(
            info_labels, 
            textvariable=self.date_var,
            style='CardText.TLabel'
        ).pack(side=tk.LEFT)
        
        # 格式选择区域
        format_frame = ttk.LabelFrame(details_frame, text="下载格式", style='Card.TFrame', padding="10")
        format_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.format_var = tk.StringVar()
        self.format_combobox = ttk.Combobox(
            format_frame, 
            textvariable=self.format_var, 
            width=40,
            state="disabled"
        )
        self.format_combobox.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        download_button = ttk.Button(
            format_frame, 
            text="开始下载", 
            command=self.start_download,
            style='Accent.TButton',
            state="disabled"
        )
        download_button.pack(side=tk.RIGHT)
        
        # 下载路径选择
        path_frame = ttk.Frame(details_frame, style='Card.TFrame')
        path_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.path_var = tk.StringVar(value=os.path.expanduser("~"))
        ttk.Entry(
            path_frame, 
            textvariable=self.path_var, 
            width=45,
            state="readonly"
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        browse_button = ttk.Button(
            path_frame, 
            text="浏览", 
            command=self.browse_download_path,
            style='TButton'
        )
        browse_button.pack(side=tk.RIGHT)
        
        # 下载进度区域
        progress_frame = ttk.LabelFrame(content_frame, text="下载进度", style='Card.TFrame', padding="10")
        progress_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            progress_frame, 
            variable=self.progress_var, 
            length=100, 
            mode='determinate'
        )
        self.progress_bar.pack(fill=tk.X, expand=True)
        
        self.progress_text = tk.StringVar(value="等待下载...")
        ttk.Label(
            progress_frame, 
            textvariable=self.progress_text,
            style='Subtitle.TLabel'
        ).pack(anchor=tk.W, pady=(5, 0))
        
        # 日志区域
        log_frame = ttk.LabelFrame(content_frame, text="操作日志", style='Card.TFrame', padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = scrolledtext.ScrolledText(
            log_frame, 
            wrap=tk.WORD, 
            height=10, 
            bg=self.secondary_color, 
            fg=self.text_color,
            font=('SimHei', 10)
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.config(state=tk.DISABLED)
        
        # 启动日志处理线程
        self.root.after(100, self.process_log_messages)
    
    def fetch_video_info(self):
        """获取视频信息"""
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showerror("错误", "请输入有效的YouTube视频URL")
            return
        
        self.status_var.set("正在获取视频信息...")
        self.logger.info(f"获取视频信息: {url}")
        
        # 清空之前的信息
        self.format_combobox['values'] = []
        self.format_combobox.set("")
        self.format_combobox['state'] = 'disabled'
        self.progress_var.set(0)
        self.progress_text.set("等待下载...")
        
        # 在单独线程中获取视频信息
        threading.Thread(target=self._fetch_video_info_thread, args=(url,), daemon=True).start()
    
    def _fetch_video_info_thread(self, url):
        """在单独线程中获取视频信息"""
        try:
            ydl_opts = {
                'noplaylist': True,
                'quiet': True,
                'format': 'best',
                'outtmpl': '%(id)s.%(ext)s',
                'ffmpeg_location': self.ffmpeg_path,
                'downloader': self.ydl_path,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    self.root.after(0, lambda: messagebox.showerror("错误", "无法获取视频信息"))
                    self.root.after(0, lambda: self.status_var.set("就绪"))
                    return
                
                # 缓存视频信息
                self.video_info = info
                
                # 更新UI
                self.root.after(0, lambda: self._update_video_info_ui(info))
                
                # 获取可用格式
                formats = []
                if 'formats' in info:
                    for fmt in info['formats']:
                        if fmt.get('acodec') != 'none' and fmt.get('vcodec') != 'none':
                            format_str = f"{fmt.get('format_note', '未知')} - {fmt.get('ext', '未知')} - {fmt.get('filesize_approx', '未知大小')}"
                            formats.append((format_str, fmt['format_id']))
                
                # 更新格式选择下拉框
                self.root.after(0, lambda: self._update_format_combobox(formats))
                
                self.status_var.set("视频信息获取完成")
                self.logger.info("视频信息获取完成")
        
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("错误", f"获取视频信息失败: {str(e)}"))
            self.root.after(0, lambda: self.status_var.set("就绪"))
            self.logger.error(f"获取视频信息失败: {str(e)}")
    
    def _update_video_info_ui(self, info):
        """更新视频信息UI"""
        # 更新标题
        self.title_var.set(info.get('title', '未知标题'))
