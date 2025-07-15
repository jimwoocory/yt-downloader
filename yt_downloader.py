import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, scrolledtext
import threading
import logging
import queue
import os
from datetime import datetime
import requests
import json
import re

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
        
        # API配置（使用公开的视频解析API）
        self.api_base_url = "https://api.baomitu.com/api/video_parse/"  # 视频解析API
        self.api_timeout = 30  # API请求超时时间（秒）
        
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
        
        # 创建队列
        self.result_queue = queue.Queue()
        
        # 视频信息缓存
        self.video_info = {}
        self.available_formats = []
        
        # 工具目录
        self.tool_dir = os.path.join(os.path.expanduser("~"), ".youtube_downloader")
        os.makedirs(self.tool_dir, exist_ok=True)
        
        # 创建日志文件
        self._create_log_file()
        
        # 配置日志
        self.setup_logging()
        
        # 捕获所有未处理的异常
        sys.excepthook = self._handle_exception
        
        try:
            # 创建并显示启动画面
            self.create_splash_screen()
            
            # 显示启动画面后直接进入主界面（无需依赖检查）
            self.root.after(1500, self._create_main_interface)
        except Exception as e:
            self.logger.error(f"初始化界面失败: {str(e)}")
            self._show_fatal_error(f"初始化界面失败: {str(e)}")
    
    def _create_log_file(self):
        """创建日志文件"""
        try:
            now = datetime.now()
            log_filename = now.strftime("youtube_downloader_%Y%m%d_%H%M%S.log")
            self.log_file_path = os.path.join(self.tool_dir, log_filename)
        except Exception as e:
            self.log_file_path = os.path.join(os.path.expanduser("~"), "youtube_downloader.log")
            self.logger.error(f"创建日志文件失败，使用默认路径: {self.log_file_path}")
    
    def setup_logging(self):
        """配置日志系统"""
        try:
            self.logger = logging.getLogger(__name__)
            self.logger.setLevel(logging.DEBUG)
            
            # 文件日志
            file_handler = logging.FileHandler(self.log_file_path, encoding='utf-8')
            file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)
            
            # GUI日志
            self.log_handler = QueueHandler(self.result_queue)
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            self.log_handler.setFormatter(formatter)
            self.logger.addHandler(self.log_handler)
            
            # 控制台日志
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
            
            self.logger.info("日志系统初始化完成")
        except Exception as e:
            try:
                error_log_path = os.path.join(self.tool_dir, "error_log.txt")
                with open(error_log_path, 'w', encoding='utf-8') as f:
                    f.write(f"配置日志系统失败: {str(e)}\n")
            except:
                pass
    
    def _handle_exception(self, exc_type, exc_value, exc_traceback):
        """处理未捕获的异常"""
        if issubclass(exc_type, KeyboardInterrupt):
            self.root.destroy()
            return
        
        error_msg = f"未处理的异常: {exc_type.__name__}, {str(exc_value)}"
        self.logger.error(error_msg, exc_info=(exc_type, exc_value, exc_traceback))
        
        if hasattr(self, 'log_text'):
            self.root.after(0, lambda: self._show_error_dialog(error_msg))
        else:
            self.root.after(0, lambda: self._show_fatal_error(error_msg))
    
    def _show_error_dialog(self, message):
        """显示错误对话框"""
        if hasattr(self, 'log_text') and self.log_text:
            self.log_text.config(state=tk.NORMAL)
            self.log_text.insert(tk.END, f"错误: {message}\n", "ERROR")
            self.log_text.config(state=tk.DISABLED)
        
        messagebox.showerror("错误", message)
    
    def _show_fatal_error(self, message):
        """显示严重错误并退出程序"""
        if hasattr(self, 'splash') and self.splash:
            self.splash.destroy()
        
        messagebox.showerror("严重错误", f"{message}\n\n日志文件: {self.log_file_path}")
        self.root.destroy()
    
    def create_splash_screen(self):
        """创建启动画面"""
        try:
            self.splash = tk.Toplevel(self.root)
            self.splash.title("启动中...")
            self.splash.geometry("600x400")
            self.splash.resizable(False, False)
            self.splash.transient(self.root)
            self.splash.overrideredirect(True)
            self.splash.configure(bg=self.bg_color)
            
            # 居中显示
            self.splash.update_idletasks()
            width = self.splash.winfo_width()
            height = self.splash.winfo_height()
            x = (self.splash.winfo_screenwidth() // 2) - (width // 2)
            y = (self.splash.winfo_screenheight() // 2) - (height // 2)
            self.splash.geometry('{}x{}+{}+{}'.format(width, height, x, y))
            
            # 主框架
            main_frame = ttk.Frame(self.splash, style='Main.TFrame', padding="20")
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # 应用图标和名称
            title_frame = ttk.Frame(main_frame, style='Main.TFrame')
            title_frame.pack(pady=(60, 20))
            
            icon_frame = ttk.Frame(title_frame, style='Main.TFrame')
            icon_frame.pack(side=tk.LEFT, padx=(0, 10))
            
            icon_canvas = tk.Canvas(icon_frame, width=60, height=40, bg=self.bg_color, highlightthickness=0)
            icon_canvas.pack()
            icon_canvas.create_polygon(10, 5, 50, 20, 10, 35, fill=self.primary_color)
            
            ttk.Label(
                title_frame, 
                text="YouTube 下载器",
                style='Title.TLabel'
            ).pack(side=tk.LEFT)
            
            ttk.Label(
                main_frame, 
                text="API版 - 无需本地依赖",
                style='Subtitle.TLabel'
            ).pack(pady=(0, 60))
            
            # 加载进度
            self.loading_progress = tk.DoubleVar(value=0)
            progress_frame = ttk.Frame(main_frame, style='Main.TFrame')
            progress_frame.pack(fill=tk.X, pady=20)
            
            ttk.Label(progress_frame, text="加载中...", style='Subtitle.TLabel').pack(side=tk.LEFT, padx=(0, 10))
            
            progress_bar = ttk.Progressbar(
                progress_frame, 
                variable=self.loading_progress, 
                length=400, 
                mode='determinate'
            )
            progress_bar.pack(side=tk.RIGHT, fill=tk.X, expand=True)
            
            # 底部信息
            ttk.Label(
                main_frame, 
                text="© 2025 YouTube 下载器",
                style='Subtitle.TLabel'
            ).pack(side=tk.BOTTOM, pady=20)
            
            # 模拟加载进度
            self._update_loading_progress()
            
            self.splash.deiconify()
            self.root.update()
        except Exception as e:
            self.logger.error(f"创建启动画面失败: {str(e)}")
            raise
    
    def _update_loading_progress(self):
        """更新启动进度"""
        current = self.loading_progress.get()
        if current < 100:
            self.loading_progress.set(current + 1)
            self.root.after(20, self._update_loading_progress)
        else:
            # 加载完成
            self.root.after(500, self._create_main_interface)
    
    def _create_main_interface(self):
        """创建主界面"""
        try:
            # 关闭启动画面
            if hasattr(self, 'splash') and self.splash:
                self.splash.destroy()
            
            # 显示主窗口
            self.root.deiconify()
            self.root.configure(bg=self.bg_color)
            
            # 顶部导航栏
            nav_frame = ttk.Frame(self.root, style='Card.TFrame', padding="10")
            nav_frame.pack(fill=tk.X)
            
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
            
            # 视频信息标签
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
            
            # 配置日志标签颜色
            self.log_text.tag_config('ERROR', foreground='#FF5252')  # 红色
            self.log_text.tag_config('WARNING', foreground='#FFD740')  # 黄色
            self.log_text.tag_config('INFO', foreground='#4CAF50')  # 绿色
            
            self.log_text.config(state=tk.DISABLED)
            
            # 启动日志处理线程
            self.root.after(100, self.process_log_messages)
            
            self.logger.info("主界面初始化完成")
        except Exception as e:
            self.logger.error(f"创建主界面失败: {str(e)}")
            self._show_fatal_error(f"创建主界面失败: {str(e)}")
    
    def process_log_messages(self):
        """处理日志消息，更新日志UI"""
        while not self.result_queue.empty():
            try:
                level, msg = self.result_queue.get_nowait()
                
                self.log_text.config(state=tk.NORMAL)
                self.log_text.insert(tk.END, f"{msg}\n", level)
                self.log_text.config(state=tk.DISABLED)
                
                self.log_text.see(tk.END)
            except queue.Empty:
                pass
            except Exception as e:
                self.logger.error(f"处理日志消息失败: {str(e)}")
        
        self.root.after(100, self.process_log_messages)
    
    def browse_download_path(self):
        """浏览并选择下载路径"""
        directory = filedialog.askdirectory(initialdir=self.path_var.get())
        if directory:
            self.path_var.set(directory)
            self.logger.info(f"下载路径已设置为: {directory}")
    
    def fetch_video_info(self):
        """获取视频信息"""
        url = self.url_entry.get().strip()
        if not url:
            self._show_error_dialog("请输入YouTube视频URL")
            return
        
        # 验证URL格式
        if not self._is_valid_youtube_url(url):
            self._show_error_dialog("请输入有效的YouTube视频URL")
            return
        
        self.status_var.set("正在获取视频信息...")
        self.progress_var.set(0)
        self.progress_text.set("正在获取视频信息...")
        
        # 禁用按钮防止重复点击
        self.url_entry.config(state="disabled")
        ttk.Button(
            self.url_entry.master, 
            text="获取视频信息", 
            command=self.fetch_video_info,
            style='Accent.TButton',
            state="disabled"
        ).pack(side=tk.RIGHT)
        
        # 在单独线程中获取视频信息
        threading.Thread(target=self._fetch_video_info_thread, args=(url,), daemon=True).start()
    
    def _is_valid_youtube_url(self, url):
        """验证是否为有效的YouTube URL"""
        youtube_regex = (
            r'(https?://)?(www\.)?'
            r'(youtube|youtu|youtube-nocookie)\.(com|be)/'
            r'(watch\?v=|embed/|v/|shorts/|.+?\?v=)?([^&=%\?]{11})'
        )
        return re.match(youtube_regex, url) is not None
    
    def _fetch_video_info_thread(self, url):
        """在单独线程中获取视频信息"""
        try:
            self.logger.info(f"开始获取视频信息: {url}")
            
            # 准备API请求参数
            params = {
                'url': url,
                'type': 'json'
            }
            
            # 发送API请求
            response = requests.get(self.api_base_url, params=params, timeout=self.api_timeout)
            response.raise_for_status()
            
            # 解析JSON响应
            data = response.json()
            
            # 检查API返回状态
            if data.get('code') != 200 or data.get('status') != 'success':
                error_msg = data.get('msg', '获取视频信息失败')
                self.logger.error(f"API请求失败: {error_msg}")
                self.root.after(0, lambda: self._show_error_dialog(f"获取视频信息失败: {error_msg}"))
                self.root.after(0, lambda: self._reset_ui_state())
                return
            
            # 提取视频信息
            video_info = data.get('data', {})
            
            if not video_info:
                self.logger.error("未获取到视频信息")
                self.root.after(0, lambda: self._show_error_dialog("未获取到视频信息"))
                self.root.after(0, lambda: self._reset_ui_state())
                return
            
            # 缓存视频信息
            self.video_info = video_info
            
            # 更新UI
            self.root.after(0, lambda: self._update_video_info_ui())
            
            self.logger.info(f"成功获取视频信息: {video_info.get('title', '未知标题')}")
        except Exception as e:
            self.logger.error(f"获取视频信息失败: {str(e)}")
            self.root.after(0, lambda: self._show_error_dialog(f"获取视频信息失败: {str(e)}"))
            self.root.after(0, lambda: self._reset_ui_state())
    
    def _update_video_info_ui(self):
        """更新视频信息UI"""
        # 更新标题
        title = self.video_info.get('title', '未知标题')
        self.title_var.set(title)
        
        # 更新时长
        duration = self.video_info.get('duration', '未知')
        self.duration_var.set(f"时长: {duration}")
        
        # 更新观看次数
        views = self.video_info.get('views', '未知')
        self.views_var.set(f"观看次数: {views}")
        
        # 更新发布日期
        pub_date = self.video_info.get('pub_date', '未知')
        self.date_var.set(f"发布日期: {pub_date}")
        
        # 更新可用格式
        formats = self.video_info.get('formats', [])
        self.available_formats = formats
        
        # 准备格式选项
        format_options = []
        for fmt in formats:
            quality = fmt.get('quality', '未知质量')
            ext = fmt.get('ext', '未知格式')
            size = fmt.get('size', '未知大小')
            format_options.append(f"{quality} ({ext}, {size})")
        
        # 更新格式选择下拉框
        self.format_combobox['values'] = format_options
        if format_options:
            self.format_combobox.current(0)
            self.format_combobox.config(state="readonly")
            ttk.Button(
                self.format_combobox.master, 
                text="开始下载", 
                command=self.start_download,
                style='Accent.TButton',
                state="normal"
            ).pack(side=tk.RIGHT)
        
        # 更新缩略图
        thumb_url = self.video_info.get('thumb', '')
        if thumb_url:
            self._update_thumbnail(thumb_url)
        
        self.status_var.set("就绪")
        self.progress_text.set("等待下载...")
        
        # 恢复URL输入框
        self.url_entry.config(state="normal")
    
    def _update_thumbnail(self, thumb_url):
        """更新视频缩略图"""
        # 由于无法直接加载网络图片，我们创建一个简单的缩略图占位符
        self.thumb_canvas.delete("all")
        self.thumb_canvas.create_rectangle(0, 0, 320, 180, fill=self.secondary_color)
        
        # 添加视频标题
        title = self.video_info.get('title', '视频缩略图')
        # 限制标题长度
        if len(title) > 40:
            title = title[:40] + "..."
        
        self.thumb_canvas.create_text(160, 90, text=title, fill=self.text_color, font=('SimHei', 12))
        
        # 添加播放按钮
        self.thumb_canvas.create_polygon(
            140, 80, 200, 120, 140, 160, 
            fill=self.primary_color, outline=""
        )
    
    def _reset_ui_state(self):
        """重置UI状态"""
        self.status_var.set("就绪")
        self.progress_var.set(0)
        self.progress_text.set("等待下载...")
        
        self.url_entry.config(state="normal")
        ttk.Button(
            self.url_entry.master, 
            text="获取视频信息", 
            command=self.fetch_video_info,
            style='Accent.TButton',
            state="normal"
        ).pack(side=tk.RIGHT)
        
        self.format_combobox['values'] = []
        self.format_combobox.set("")
        self.format_combobox.config(state="disabled")
        
        ttk.Button(
            self.format_combobox.master, 
            text="开始下载", 
            command=self.start_download,
            style='Accent.TButton',
            state="disabled"
        ).pack(side=tk.RIGHT)
    
    def start_download(self):
        """开始下载视频"""
        if not self.video_info:
            self._show_error_dialog("请先获取视频信息")
            return
        
        # 获取选中的格式
        selected_format_index = self.format_combobox.current()
        if selected_format_index < 0 or selected_format_index >= len(self.available_formats):
            self._show_error_dialog("请选择下载格式")
            return
        
        selected_format = self.available_formats[selected_format_index]
        download_url = selected_format.get('url', '')
        
        if not download_url:
            self._show_error_dialog("无法获取下载链接")
            return
        
        # 获取下载路径
        download_path = self.path_var.get()
        if not download_path or not os.path.exists(download_path):
            self._show_error_dialog("请选择有效的下载路径")
            return
        
        # 生成文件名
        title = self.video_info.get('title', 'video')
        # 替换不合法的文件名字符
        safe_title = re.sub(r'[\\/*?:"<>|]', '_', title)
        ext = selected_format.get('ext', 'mp4')
        filename = f"{safe_title}.{ext}"
        full_path = os.path.join(download_path, filename)
        
        # 更新UI状态
        self.status_var.set("准备下载...")
        self.progress_var.set(0)
        self.progress_text.set("准备下载...")
        
        # 禁用下载按钮
        ttk.Button(
            self.format_combobox.master, 
            text="开始下载", 
            command=self.start_download,
            style='Accent.TButton',
            state="disabled"
        ).pack(side=tk.RIGHT)
        
        # 在单独线程中下载视频
        threading.Thread(
            target=self._download_video_thread, 
            args=(download_url, full_path, selected_format), 
            daemon=True
        ).start()
    
    def _download_video_thread(self, url, save_path, format_info):
        """在单独线程中下载视频"""
        try:
            self.logger.info(f"开始下载视频: {save_path}")
            self.root.after(0, lambda: self.progress_text.set("连接到服务器..."))
            
            # 发送请求获取视频
            response = requests.get(url, stream=True, timeout=self.api_timeout)
            response.raise_for_status()
            
            # 获取文件大小
            total_size = int(response.headers.get('content-length', 0))
            block_size = 1024
            downloaded_size = 0
            
            # 创建临时文件
            temp_file = save_path + ".part"
            
            self.root.after(0, lambda: self.progress_text.set("开始下载..."))
            
            with open(temp_file, 'wb') as f:
                for data in response.iter_content(block_size):
                    if not data:
                        break
                    
                    f.write(data)
                    downloaded_size += len(data)
                    
                    # 计算进度百分比
                    progress = (downloaded_size / total_size) * 100 if total_size > 0 else 0
                    
                    # 更新进度条
                    self.root.after(0, lambda p=progress: self.progress_var.set(p))
                    
                    # 更新进度文本
                    downloaded_mb = downloaded_size / (1024 * 1024)
                    total_mb = total_size / (1024 * 1024)
                    progress_text = f"下载中: {downloaded_mb:.2f}MB / {total_mb:.2f}MB ({progress:.1f}%)"
                    self.root.after(0, lambda t=progress_text: self.progress_text.set(t))
            
            # 下载完成，重命名临时文件
            os.rename(temp_file, save_path)
            
            self.logger.info(f"视频下载完成: {save_path}")
            self.root.after(0, lambda: self.progress_text.set("下载完成"))
            self.root.after(0, lambda: self.status_var.set("就绪"))
            self.root.after(0, lambda: messagebox.showinfo("成功", f"视频下载完成:\n{save_path}"))
            
            # 恢复下载按钮
            self.root.after(0, lambda: ttk.Button(
                self.format_combobox.master, 
                text="开始下载", 
                command=self.start_download,
                style='Accent.TButton',
                state="normal"
            ).pack(side=tk.RIGHT))
        except Exception as e:
            self.logger.error(f"下载视频失败: {str(e)}")
            self.root.after(0, lambda: self.progress_text.set("下载失败"))
            self.root.after(0, lambda: self.status_var.set("就绪"))
            self.root.after(0, lambda: self._show_error_dialog(f"下载视频失败: {str(e)}"))
            
            # 清理临时文件
            if os.path.exists(save_path + ".part"):
                os.remove(save_path + ".part")

def main():
    root = tk.Tk()
    app = YouTubeDownloaderApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()    
