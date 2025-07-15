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

class YouTubeDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("YouTube 下载器")
        self.root.geometry("1000x800")  # 增加窗口高度以容纳新组件
        self.root.minsize(900, 750)

        # 设置中文字体支持
        self.style = ttk.Style()
        self.style.configure("TLabel", font=("Microsoft YaHei UI", 12))
        self.style.configure("TButton", font=("Microsoft YaHei UI", 12))
        self.style.configure("TEntry", font=("Microsoft YaHei UI", 12))
        self.style.configure("TCombobox", font=("Microsoft YaHei UI", 12))
        self.style.configure("TScrolledtext", font=("Microsoft YaHei UI", 10))
        self.style.configure("TLabelframe.Label", font=("Microsoft YaHei UI", 14, "bold"))

        # 日志队列和结果队列
        self.log_queue = queue.Queue()
        self.result_queue = queue.Queue()

        # 下载任务列表和控制变量
        self.download_tasks = []
        self.current_task_index = 0
        self.total_tasks = 0
        self.abort_all_tasks = False
        
        # 视频信息缓存
        self.video_info = {}
        self.available_video_formats = []
        self.available_audio_formats = []

        # 配置日志
        self.setup_logging()

        # 创建界面
        self.create_widgets()

        # 加载下载历史
        self.load_download_history()
        
        # 启动队列处理线程
        self.processing_thread = threading.Thread(target=self.process_queue, daemon=True)
        self.processing_thread.start()
        
        # 启动日志处理线程
        self.root.after(100, self.process_log_messages)

        # 用于终止下载的变量
        self.ydl_instance = None
        self.is_downloading = False
        self.download_threads = {}  # 跟踪所有下载线程

    def setup_logging(self):
        """配置日志系统，将日志输出到GUI"""
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

        # 创建文件处理器
        log_dir = os.path.join(os.path.expanduser("~"), ".youtube_downloader_logs")
        os.makedirs(log_dir, exist_ok=True)
        log_filename = datetime.now().strftime("youtube_downloader_%Y%m%d_%H%M%S.log")
        file_handler = logging.FileHandler(os.path.join(log_dir, log_filename), encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        # 创建GUI处理器
        gui_handler = QueueHandler(self.log_queue)
        gui_handler.setLevel(logging.INFO) # GUI只显示INFO及以上级别的日志
        gui_handler.setFormatter(formatter)
        self.logger.addHandler(gui_handler)

        self.logger.info("日志系统初始化完成")

    def process_log_messages(self):
        """处理日志消息，更新日志UI"""
        while not self.log_queue.empty():
            try:
                level, msg = self.log_queue.get_nowait()
                self.log_text.config(state=tk.NORMAL)
                self.log_text.insert(tk.END, f"{msg}\n", level)
                self.log_text.config(state=tk.DISABLED)
                self.log_text.see(tk.END)
            except queue.Empty:
                pass
            except Exception as e:
                self.logger.error(f"处理日志消息失败: {str(e)}")
        self.root.after(100, self.process_log_messages)

    def create_widgets(self):
        """创建GUI界面组件"""
        main_frame = ttk.Frame(self.root, padding="10 10 10 10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # URL输入和代理设置
        url_frame = ttk.LabelFrame(main_frame, text="视频URL和代理设置", padding="10 10 10 10")
        url_frame.pack(fill=tk.X, pady=5)

        ttk.Label(url_frame, text="视频URL:").grid(row=0, column=0, sticky=tk.W, pady=5, padx=5)
        self.url_entry = ttk.Entry(url_frame, width=70)
        self.url_entry.grid(row=0, column=1, sticky=tk.W, pady=5, padx=5)
        self.url_entry.insert(0, "https://www.youtube.com/watch?v=")

        ttk.Button(url_frame, text="获取信息", command=self.fetch_video_info).grid(row=0, column=2, padx=5)
        
        # 批量下载支持
        ttk.Label(url_frame, text="或批量输入URLs (每行一个):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.urls_text = scrolledtext.ScrolledText(url_frame, wrap=tk.WORD, height=3)
        self.urls_text.grid(row=1, column=1, columnspan=2, sticky="ew", padx=5, pady=5)

        ttk.Label(url_frame, text="代理 (例如: http://127.0.0.1:7897):").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.proxy_entry = ttk.Entry(url_frame, width=50)
        self.proxy_entry.grid(row=2, column=1, sticky=tk.W, pady=5, padx=5)
        self.proxy_entry.insert(0, "http://127.0.0.1:7897")

        # 视频信息预览
        info_frame = ttk.LabelFrame(main_frame, text="视频信息预览", padding="10 10 10 10")
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
        options_frame = ttk.LabelFrame(main_frame, text="下载选项", padding="10 10 10 10")
        options_frame.pack(fill=tk.X, pady=5)

        ttk.Label(options_frame, text="保存路径:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.save_path_var = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Downloads"))
        ttk.Entry(options_frame, textvariable=self.save_path_var, width=50).grid(row=0, column=1, sticky=tk.W, padx=(0, 5))
        ttk.Button(options_frame, text="浏览...", command=self.browse_save_path).grid(row=0, column=2, sticky=tk.W)

        # 下载格式选择
        ttk.Label(options_frame, text="视频格式:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.video_format_var = tk.StringVar()
        self.video_format_combobox = ttk.Combobox(options_frame, textvariable=self.video_format_var, width=40, state="disabled")
        self.video_format_combobox.grid(row=1, column=1, sticky=tk.W, padx=5)

        ttk.Label(options_frame, text="音频格式:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.audio_format_var = tk.StringVar()
        self.audio_format_combobox = ttk.Combobox(options_frame, textvariable=self.audio_format_var, width=40, state="disabled")
        self.audio_format_combobox.grid(row=2, column=1, sticky=tk.W, padx=5)

        # 字幕选项
        self.subtitle_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="下载字幕", variable=self.subtitle_var).grid(row=3, column=0, sticky=tk.W, pady=5)
        
        # 按钮
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="开始下载", command=self.start_download, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="终止下载", command=self.stop_download, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="清空日志", command=self.clear_logs, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="查看历史", command=self.show_history, width=15).pack(side=tk.LEFT, padx=5)

        # 下载进度条
        progress_frame = ttk.LabelFrame(main_frame, text="下载进度", padding="10 10 10 10")
        progress_frame.pack(fill=tk.X, pady=5)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, expand=True, pady=5)

        self.progress_text = tk.StringVar(value="等待下载...")
        ttk.Label(progress_frame, textvariable=self.progress_text).pack(fill=tk.X, pady=2)

        # 日志输出区域
        log_frame = ttk.LabelFrame(main_frame, text="日志输出", padding="10 10 10 10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=15)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.config(state=tk.DISABLED)

        # 配置日志标签颜色
        self.log_text.tag_config("INFO", foreground="blue")
        self.log_text.tag_config("WARNING", foreground="orange")
        self.log_text.tag_config("ERROR", foreground="red")
        self.log_text.tag_config("CRITICAL", foreground="darkred", font=("Microsoft YaHei UI", 10, "bold"))

    def browse_save_path(self):
        """浏览并选择下载保存路径"""
        path = filedialog.askdirectory()
        if path:
            self.save_path_var.set(path)
            self.logger.info(f"下载路径设置为: {path}")

    def validate_url(self, url):
        """验证URL是否为有效的YouTube链接"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc, result.path]) and ("youtube.com" in result.netloc or "youtu.be" in result.netloc)
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
        
        # 清空之前的格式选项
        self.video_format_combobox.set("")
        self.audio_format_combobox.set("")
        self.video_format_combobox["values"] = []
        self.audio_format_combobox["values"] = []
        self.video_format_combobox.config(state="disabled")
        self.audio_format_combobox.config(state="disabled")
        self.available_video_formats = []
        self.available_audio_formats = []

        def _fetch():
            try:
                ydl_opts = {
                    'socket_timeout': 10,
                    'proxy': proxy,
                    'quiet': True,
                    'format': 'bestvideo*+bestaudio/best'
                }
                
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
                    
                    # 过滤并组织视频和音频格式
                    formats = info_dict.get('formats', [])
                    video_formats = []
                    audio_formats = []

                    for f in formats:
                        format_id = f.get('format_id')
                        ext = f.get('ext')
                        resolution = f.get('resolution')
                        acodec = f.get('acodec')
                        vcodec = f.get('vcodec')
                        filesize = f.get('filesize')
                        filesize_str = f.get('filesize_approx_str') or (f'{filesize / (1024*1024):.2f}MB' if filesize else '未知大小')

                        if vcodec != 'none' and resolution != 'audio only': # 视频格式
                            # 过滤掉不常见的视频格式，并限制分辨率范围
                            if ext in ['mp4', 'webm'] and resolution and 'p' in resolution:
                                height = int(resolution.replace('p', ''))
                                if 1080 <= height <= 4320 or height == 720: # 8K到1080P，包括720P
                                    video_formats.append({
                                        'display': f'{resolution} ({ext}, {filesize_str})',
                                        'format_id': format_id,
                                        'ext': ext
                                    })
                        elif acodec != 'none' and vcodec == 'none': # 音频格式
                            audio_formats.append({
                                'display': f'{acodec} ({ext}, {filesize_str})',
                                'format_id': format_id,
                                'ext': ext
                            })
                    
                    # 按照分辨率从高到低排序视频格式
                    video_formats.sort(key=lambda x: int(x['display'].split('p')[0]) if 'p' in x['display'] else 0, reverse=True)

                    self.available_video_formats = video_formats
                    self.available_audio_formats = audio_formats

                    self.root.after(0, self._update_format_comboboxes)
                    
                    # 保存视频信息
                    self.video_info[url] = info_dict
                    
                    self.result_queue.put(("success", f"成功获取视频信息: {title}"))
            except Exception as e:
                self.result_queue.put(("error", f"获取视频信息失败: {str(e)}"))
        
        # 在单独线程中获取信息
        threading.Thread(target=_fetch, daemon=True).start()

    def _update_format_comboboxes(self):
        """更新视频和音频格式下拉框"""
        # 更新视频格式下拉框
        video_display_options = [f['display'] for f in self.available_video_formats]
        self.video_format_combobox["values"] = video_display_options
        if video_display_options:
            self.video_format_combobox.current(0)
            self.video_format_combobox.config(state="readonly")
        else:
            self.video_format_combobox.config(state="disabled")

        # 更新音频格式下拉框
        audio_display_options = [f['display'] for f in self.available_audio_formats]
        self.audio_format_combobox["values"] = audio_display_options
        if audio_display_options:
            self.audio_format_combobox.current(0)
            self.audio_format_combobox.config(state="readonly")
        else:
            self.audio_format_combobox.config(state="disabled")

    def start_download(self):
        """开始下载"""
        urls_input = self.urls_text.get("1.0", tk.END).strip()
        if urls_input:
            urls = [url.strip() for url in urls_input.split("\n") if url.strip()]
        else:
            urls = [self.url_entry.get().strip()]

        urls = [url for url in urls if self.validate_url(url)]

        if not urls:
            messagebox.showerror("错误", "请输入有效的 YouTube 链接")
            return

        proxy = self.proxy_entry.get().strip() or None
        save_path = self.save_path_var.get()
        download_subtitles = self.subtitle_var.get()

        selected_video_format_display = self.video_format_var.get()
        selected_audio_format_display = self.audio_format_var.get()

        format_id = None
        ext = None

        if selected_video_format_display:
            for fmt in self.available_video_formats:
                if fmt['display'] == selected_video_format_display:
                    format_id = fmt['format_id']
                    ext = fmt['ext']
                    break
        elif selected_audio_format_display:
            for fmt in self.available_audio_formats:
                if fmt['display'] == selected_audio_format_display:
                    format_id = fmt['format_id']
                    ext = fmt['ext']
                    break
        
        if not format_id:
            messagebox.showerror("错误", "请选择一个下载格式")
            return

        # 准备下载任务
        self.download_tasks = urls.copy()
        self.current_task_index = 0
        self.total_tasks = len(urls)
        self.abort_all_tasks = False
        self.update_progress(0, "准备下载...")

        for url in urls:
            self.logger.info(f"添加下载任务: {url}")
            self.download_queue.put(("download", url, proxy, save_path, format_id, ext, download_subtitles))

    def stop_download(self):
        """终止正在进行的下载"""
        if not self.is_downloading:
            messagebox.showinfo("提示", "当前没有正在进行的下载")
            return

        self.abort_all_tasks = True
        self.logger.info("正在终止所有下载任务...")
        
        # 终止当前下载
        if self.ydl_instance:
            self.logger.info("正在终止下载...")
            self.ydl_instance._download_retcode = -1  # 设置退出码强制终止
            self.ydl_instance = None
            self.is_downloading = False
            self.update_progress(0, "下载已终止")
            self.logger.info("下载已终止")
        
        # 等待所有线程结束
        for task_id, thread in list(self.download_threads.items()):
            if thread.is_alive():
                self.logger.info(f"等待任务 {task_id} 终止...")
                thread.join(timeout=1.0)
        
        self.is_downloading = False
        self.ydl_instance = None
        self.download_threads = {}
        self.update_progress(0, "所有下载已终止")
        self.logger.info("所有下载任务已终止")

    def update_progress(self, percent, message):
        """更新进度条和进度信息"""
        self.progress_var.set(percent)
        self.progress_text.set(message)
        self.root.update_idletasks()

    def process_queue(self):
        """处理下载队列"""
        while True:
            try:
                if self.abort_all_tasks:
                    # 清空队列
                    while not self.download_queue.empty():
                        self.download_queue.get()
                        self.download_queue.task_done()
                    continue
                
                task = self.download_queue.get(timeout=1)
                if task[0] == "download":
                    self.current_task_index += 1
                    self.update_progress(
                        (self.current_task_index-1) / self.total_tasks * 100, 
                        f"准备下载 {self.current_task_index}/{self.total_tasks}"
                    )
                    # 为每个下载任务创建唯一ID
                    task_id = f"task_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    
                    # 在单独的线程中执行下载，以便可以独立控制每个任务
                    thread = threading.Thread(
                        target=self._download, 
                        args=(task_id, task[1], task[2], task[3], task[4], task[5], task[6]),
                        daemon=True
                    )
                    self.download_threads[task_id] = thread
                    thread.start()
                self.download_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"处理队列出错: {str(e)}")
                self.result_queue.put(("error", f"处理队列出错: {str(e)}"))

    def _download(self, task_id, url, proxy, save_path, format_id, ext, download_subtitles):
        """下载视频或音频的实际处理函数"""
        self.is_downloading = True

        try:
            ydl_opts = {
                'socket_timeout': 10,
                'proxy': proxy,
                'outtmpl': os.path.join(save_path, '%(title)s.%(ext)s'),
                'progress_hooks': [self.download_hook],
                'logger': self.logger,
                'writesubtitles': download_subtitles,
                'writeautomaticsub': download_subtitles,
                'subtitleslangs': ['en', 'zh-Hans', 'zh-Hant'],  # 下载多种语言字幕
                'format': format_id
            }

            self.ydl_instance = yt_dlp.YoutubeDL(ydl_opts)
            info_dict = self.ydl_instance.extract_info(url, download=True)

            if self.abort_all_tasks:  # 确保下载没有被用户终止
                self.result_queue.put(("info", f"下载已取消: {info_dict.get('title')}"))
                return
            
            self.result_queue.put(("success", f"下载完成: {info_dict.get('title')}"))
            self.update_progress(
                self.current_task_index / self.total_tasks * 100, 
                f"完成 {self.current_task_index}/{self.total_tasks}"
            )
            
            # 保存下载历史
            self.save_download_history(url, info_dict.get('title'), format_id, save_path)

        except Exception as e:
            if 'yt_dlp.utils.DownloadError' in str(type(e)) or 'Network' in str(e) or '403' in str(e):
                self.result_queue.put(("error", f"下载失败，可能是网络问题或视频不可用: {str(e)}"))
            else:
                self.result_queue.put(("error", f"下载失败: {str(e)}"))
        finally:
            self.is_downloading = False
            self.ydl_instance = None
            if task_id in self.download_threads:
                del self.download_threads[task_id]

    def download_hook(self, d):
        """下载进度回调函数"""
        if self.abort_all_tasks:
            return
            
        if d['status'] == 'downloading':
            percent = d.get('_percent_str', '?')
            speed = d.get('_speed_str', '?')
            total_bytes = d.get('_total_bytes_str', '?')
            downloaded_bytes = d.get('_downloaded_bytes_str', '?')
            eta = d.get('_eta_str', '?')
            
            message = f"下载中: {percent} (速度: {speed}, 已下载: {downloaded_bytes}/{total_bytes}, 预计剩余时间: {eta})"
            self.root.after(0, lambda: self.update_progress(float(d.get('downloaded_bytes', 0)) / d.get('total_bytes', 1) * 100, message))
        elif d['status'] == 'finished':
            self.root.after(0, lambda: self.update_progress(100, "下载完成"))
            self.logger.info(f"下载完成: {d['filename']}")
        elif d['status'] == 'error':
            self.root.after(0, lambda: self.update_progress(0, "下载失败"))
            self.logger.error(f"下载出错: {d.get('error', '未知错误')}")

    def clear_logs(self):
        """清空日志输出区域"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
    
    def load_download_history(self):
        """加载下载历史"""
        try:
            if os.path.exists("download_history.json"):
                with open("download_history.json", "r", encoding="utf-8") as f:
                    self.download_history = json.load(f)
            else:
                self.download_history = []
        except Exception as e:
            self.download_history = []
            self.logger.error(f"加载下载历史失败: {str(e)}")
    
    def save_download_history(self, url, title, format_id, save_path):
        """保存下载历史"""
        try:
            history_entry = {
                "url": url,
                "title": title,
                "format_id": format_id,
                "save_path": save_path,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            self.download_history.append(history_entry)
            
            # 只保留最近100条记录
            if len(self.download_history) > 100:
                self.download_history = self.download_history[-100:]
            
            with open("download_history.json", "w", encoding="utf-8") as f:
                json.dump(self.download_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"保存下载历史失败: {str(e)}")
    
    def show_history(self):
        """显示下载历史"""
        if not self.download_history:
            messagebox.showinfo("下载历史", "暂无下载历史记录")
            return
        
        history_window = tk.Toplevel(self.root)
        history_window.title("下载历史")
        history_window.geometry("800x500")
        history_window.minsize(700, 400)
        
        # 创建表格
        columns = ("序号", "标题", "URL", "格式", "保存路径", "时间")
        tree = ttk.Treeview(history_window, columns=columns, show="headings")
        
        # 设置列宽和标题
        for col in columns:
            tree.heading(col, text=col)
            if col == "标题":
                tree.column(col, width=200)
            elif col == "URL":
                tree.column(col, width=300)
            elif col == "保存路径":
                tree.column(col, width=150)
            else:
                tree.column(col, width=80)
        
        # 添加数据
        for i, entry in enumerate(reversed(self.download_history), 1):
            tree.insert("", "end", values=(
                i,
                entry["title"],
                entry["url"],
                entry["format_id"],
                entry["save_path"],
                entry["timestamp"]
            ))
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(history_window, orient="vertical", command=tree.yview)
        tree.configure(yscroll=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(fill=tk.BOTH, expand=True)
        
        # 添加双击打开文件位置功能
        def open_file_location(event):
            item = tree.selection()[0]
            values = tree.item(item, "values")
            path = values[4]
            
            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", path])
            else:  # Linux
                subprocess.run(["xdg-open", path])
        
        tree.bind("<Double-1>", open_file_location)

class QueueHandler(logging.Handler):
    """日志处理器，将日志消息放入队列"""
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue
    
    def emit(self, record):
        self.log_queue.put((record.levelname, self.format(record)))

def main():
    root = tk.Tk()
    app = YouTubeDownloaderApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()

