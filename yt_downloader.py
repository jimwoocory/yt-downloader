import yt_dlp
import sys
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import threading
import queue
import logging
from urllib.parse import urlparse
import os
from datetime import datetime
import json
import subprocess
import platform

class YouTubeDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("YouTube 下载器 V1")
        self.root.geometry("1000x800")
        self.root.minsize(900, 750)

        # Center the main window
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - 1000) // 2
        y = (screen_height - 800) // 2
        self.root.geometry(f"1000x800+{x}+{y}")

        # 设置中文字体支持，使用类似Grok的sans-serif字体
        self.style = ttk.Style()
        self.style.configure('TLabel', font=('Arial', 10))
        self.style.configure('TButton', font=('Arial', 10))
        self.style.configure('TEntry', font=('Arial', 10))
        self.style.configure('TCombobox', font=('Arial', 10))

        # 初始化变量
        self.download_queue = queue.Queue()
        self.result_queue = queue.Queue()
        
        self.download_tasks = []
        self.current_task_index = 0
        self.total_tasks = 0
        self.abort_all_tasks = False

        self.video_info = {}

        self.setup_logging()

        self.create_widgets()
        
        self.load_download_history()
        
        self.processing_thread = threading.Thread(target=self.process_queue, daemon=True)
        self.processing_thread.start()

        self.root.after(100, self.process_results)
        
        self.ydl_instance = None
        self.is_downloading = False
        self.download_threads = {}

    def setup_logging(self):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

        class QueueHandler(logging.Handler):
            def __init__(self, log_queue):
                super().__init__()
                self.log_queue = log_queue
            
            def emit(self, record):
                self.log_queue.put((record.levelname, self.format(record)))
        
        self.result_queue = queue.Queue()
        self.log_handler = QueueHandler(self.result_queue)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        self.log_handler.setFormatter(formatter)
        self.logger.addHandler(self.log_handler)

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        url_frame = ttk.LabelFrame(main_frame, text="视频信息", padding=10)
        url_frame.pack(fill=tk.X, pady=5)

        ttk.Label(url_frame, text="YouTube 链接:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.url_entry = ttk.Entry(url_frame, width=60)
        self.url_entry.grid(row=0, column=1, sticky=tk.W, pady=5, padx=5)
        self.url_entry.insert(0, "https://www.youtube.com/watch?v=")

        ttk.Button(url_frame, text="获取信息", command=self.fetch_video_info).grid(row=0, column=2, padx=5, rowspan=2, sticky=tk.NS)

        ttk.Label(url_frame, text="或批量输入URLs (每行一个):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.urls_text = scrolledtext.ScrolledText(url_frame, wrap=tk.WORD, height=3)
        self.urls_text.grid(row=1, column=1, sticky=tk.W, pady=5, padx=5)

        ttk.Label(url_frame, text="代理地址 (可选):").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.proxy_entry = ttk.Entry(url_frame, width=60)
        self.proxy_entry.grid(row=2, column=1, sticky=tk.W, pady=5, padx=5)
        self.proxy_entry.insert(0, "http://127.0.0.1:7897")

        # 保存路径，默认“D:/360MoveData/”
        path_frame = ttk.LabelFrame(main_frame, text="保存路径", padding=10)
        path_frame.pack(fill=tk.X, pady=5)

        ttk.Label(path_frame, text="路径:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.save_path_var = tk.StringVar(value="D:/360MoveData/")
        ttk.Entry(path_frame, textvariable=self.save_path_var, width=50).grid(row=0, column=1, sticky=tk.W, pady=5, padx=5)
        ttk.Button(path_frame, text="浏览", command=self.browse_save_path).grid(row=0, column=2, padx=5)

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

        options_frame = ttk.LabelFrame(main_frame, text="下载选项", padding=10)
        options_frame.pack(fill=tk.X, pady=5)

        # 只保留第一行功能，删除第二行重复
        ttk.Label(options_frame, text="自定义格式ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.format_id_var = tk.StringVar(value="bv*+ba/b")
        ttk.Entry(options_frame, textvariable=self.format_id_var, width=15).grid(row=0, column=1, sticky=tk.W, pady=5, padx=5)
        ttk.Button(options_frame, text="查询格式", command=self.query_formats).grid(row=0, column=2, padx=5)

        self.subtitle_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="下载字幕", variable=self.subtitle_var).grid(row=0, column=3, sticky=tk.W, pady=5, padx=5)

        ttk.Label(options_frame, text="线程数:").grid(row=0, column=4, sticky=tk.W, pady=5)
        self.threads_var = tk.StringVar(value="4")
        ttk.Combobox(options_frame, textvariable=self.threads_var, values=["1", "2", "4", "8", "16"], width=5).grid(row=0, column=5, sticky=tk.W, pady=5, padx=5)

        self.transcode_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="下载后转码", variable=self.transcode_var).grid(row=0, column=6, sticky=tk.W, pady=5, padx=5)
        self.transcode_format = tk.StringVar(value="mp4")
        ttk.Combobox(options_frame, textvariable=self.transcode_format, values=["mp4", "mkv", "avi", "mov", "webm"], width=10).grid(row=0, column=7, sticky=tk.W, pady=5, padx=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="开始下载", command=self.start_download, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="终止下载", command=self.stop_download, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="清空日志", command=self.clear_logs, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="查看历史", command=self.show_history, width=15).pack(side=tk.LEFT, padx=5)

        progress_frame = ttk.LabelFrame(main_frame, text="下载进度", padding=10)
        progress_frame.pack(fill=tk.X, pady=5)

        self.progress_label = ttk.Label(progress_frame, text="准备就绪")
        self.progress_label.pack(anchor=tk.W, pady=2)

        self.progress_bar = ttk.Progressbar(progress_frame, orient='horizontal', mode='determinate', maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=5)

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
        path = filedialog.askdirectory()
        if path:
            self.save_path_var.set(path)

    def validate_url(self, url):
        try:
            parsed = urlparse(url)
            return all([parsed.scheme, parsed.netloc, parsed.path])
        except ValueError:
            return False

    def fetch_video_info(self):
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

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info_dict = ydl.extract_info(url, download=False)

                    title = info_dict.get('title', '未知标题')
                    duration = info_dict.get('duration', 0)
                    views = info_dict.get('view_count', 0)
                    uploader = info_dict.get('uploader', '未知上传者')

                    duration_str = "未知"
                    if duration:
                        hours, remainder = divmod(int(duration), 3600)
                        minutes, seconds = divmod(remainder, 60)
                        if hours > 0:
                            duration_str = f"{hours}小时{minutes}分{seconds}秒"
                        else:
                            duration_str = f"{minutes}分{seconds}秒"

                    views_str = f"{views:,}"

                    self.title_var.set(f"标题: {title}")
                    self.duration_var.set(f"时长: {duration_str}")
                    self.views_var.set(f"观看次数: {views_str}")
                    self.uploader_var.set(f"上传者: {uploader}")

                    self.video_info[url] = info_dict

                    self.result_queue.put(("info", f"[视频信息] 成功获取: {title}"))
            except Exception as e:
                self.result_queue.put(("error", f"[视频信息] 获取失败: {str(e)}"))

        threading.Thread(target=_fetch, daemon=True).start()

    def query_formats(self):
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

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info_dict = ydl.extract_info(url, download=False)
                    formats = info_dict.get('formats', [info_dict])

                    # 简化格式信息，只显示关键字段
                    formats_info = f"\n[格式查询] 可用格式 for: {info_dict.get('title')}\n"
                    for f in formats:
                        format_id = f['format_id']
                        ext = f['ext']
                        resolution = f['resolution'] if 'resolution' in f else f.get('height', '?') or 'audio only'
                        filesize = f.get('filesize', 'N/A')

                        formats_info += f"ID: {format_id}, 格式: {ext}, 分辨率: {resolution}, 大小: {filesize}\n"

                    self.result_queue.put(("info", formats_info))

                    best_video = None
                    best_audio = None

                    for f in formats:
                        if (f.get('vcodec', 'none') != 'none' and 
                            f.get('acodec', 'none') == 'none' and 
                            (best_video is None or int(f.get('height', 0)) > int(best_video.get('height', 0)))):
                            best_video = f

                        if (f.get('acodec', 'none') != 'none' and 
                            f.get('vcodec', 'none') == 'none' and 
                            (best_audio is None or int(f.get('abr', 0)) > int(best_audio.get('abr', 0)))):
                            best_audio = f

                    if best_video and best_audio:
                        recommended_format = f"{best_video['format_id']}+{best_audio['format_id']}"
                        self.root.after(0, lambda: self.format_id_var.set(recommended_format))
                        self.result_queue.put(("info", f"[推荐格式] ID: {recommended_format} (最佳视频+最佳音频)"))
            
            except Exception as e:
                self.result_queue.put(("error", f"[格式查询] 失败: {str(e)}"))

        threading.Thread(target=_query, daemon=True).start()

    def start_download(self):
        urls = []
        single_url = self.url_entry.get().strip()
        multi_urls = self.urls_text.get(1.0, tk.END).strip().split('\n')

        if single_url and self.validate_url(single_url):
            urls.append(single_url)

        for url in multi_urls:
            url = url.strip()
            if url and self.validate_url(url) and url not in urls:
                urls.append(url)

        if not urls:
            messagebox.showerror("错误", "请输入有效的 YouTube 链接")
            return

        proxy = self.proxy_entry.get().strip() or None
        save_path = self.save_path_var.get()
        download_subtitles = self.subtitle_var.get()
        thread_count = int(self.threads_var.get())
        transcode = self.transcode_var.get()
        transcode_format = self.transcode_format.get()

        format_id = self.format_id_var.get().strip()

        if not format_id:
            messagebox.showerror("错误", "请输入有效的格式ID")
            return

        self.download_tasks = urls.copy()
        self.current_task_index = 0
        self.total_tasks = len(urls)
        self.abort_all_tasks = False
        self.update_progress(0, "[进度] 准备下载...")

        self.download_queue = queue.Queue()
        for url in urls:
            self.logger.info(f"[任务] 添加下载: {url} (格式: {format_id})")
            self.download_queue.put(("download", url, proxy, save_path, format_id, download_subtitles, thread_count, transcode, transcode_format))

    def stop_download(self):
        if not self.is_downloading:
            messagebox.showinfo("提示", "当前没有正在进行的下载")
            return

        self.abort_all_tasks = True
        self.logger.info("[终止] 所有下载任务...")

        if self.ydl_instance:
            self.ydl_instance._download_retcode = -1

        for task_id, thread in list(self.download_threads.items()):
            if thread.is_alive():
                self.logger.info(f"[终止] 等待任务 {task_id}...")
                thread.join(timeout=1.0)

        self.is_downloading = False
        self.ydl_instance = None
        self.download_threads = {}
        self.update_progress(0, "[进度] 所有下载已终止")
        self.logger.info("[终止] 所有下载任务已终止")

    def update_progress(self, percent, message):
        self.progress_bar['value'] = percent
        self.progress_label.config(text=message)
        self.root.update_idletasks()

    def process_queue(self):
        while True:
            try:
                if self.abort_all_tasks:
                    while not self.download_queue.empty():
                        self.download_queue.get()
                        self.download_queue.task_done()
                    continue

                task = self.download_queue.get(timeout=1)
                if task[0] == "download":
                    self.current_task_index += 1
                    self.update_progress(
                        (self.current_task_index-1) / self.total_tasks * 100, 
                        f"[进度] 准备下载 {self.current_task_index}/{self.total_tasks}"
                    )

                    task_id = f"task_{datetime.now().strftime('%Y%m%d%H%M%S')}"

                    thread = threading.Thread(
                        target=self._download, 
                        args=(task_id, task[1], task[2], task[3], task[4], task[5], task[6], task[7], task[8]),
                        daemon=True
                    )
                    self.download_threads[task_id] = thread
                    thread.start()
                self.download_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"[错误] 处理任务: {str(e)}")

    def _download(self, task_id, url, proxy, save_path, format_id, download_subtitles, thread_count, transcode, transcode_format):
        self.is_downloading = True

        try:
            is_audio = format_id.lower().startswith('audio') or format_id == 'bestaudio'

            needs_ffmpeg = (
                '+' in format_id or 
                is_audio
            )

            if needs_ffmpeg and not self.check_ffmpeg():
                raise RuntimeError("[FFmpeg] 需要但未找到。请安装并添加PATH。")

            ydl_opts = {
                'format': format_id,
                'outtmpl': f"{save_path}/%(title)s.%(ext)s",
                'noplaylist': True,
                'continuedl': True,
                'quiet': True,
                'no_warnings': True,
                'socket_timeout': 10,
                'proxy': proxy,
                'concurrent_fragments': thread_count,
                'progress_hooks': [self._download_hook],
                'logger': self.logger,
                'writesubtitles': download_subtitles,
                'writeautomaticsub': download_subtitles,
                'subtitleslangs': ['en', 'zh-Hans', 'zh-Hant'],
            }

            if is_audio:
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3' if format_id == 'bestaudio' else 'best',
                    'preferredquality': '192',
                }]

            self.logger.info(f"[下载] 开始到: {save_path}")

            self.update_progress(
                (self.current_task_index-1) / self.total_tasks * 100, 
                f"[进度] 下载中 {self.current_task_index}/{self.total_tasks}"
            )

            self.ydl_instance = yt_dlp.YoutubeDL(ydl_opts)

            info_dict = self.ydl_instance.extract_info(url, download=True)

            if self.abort_all_tasks:
                self.result_queue.put(("info", f"[取消] 下载: {info_dict.get('title')}"))
                return

            self.logger.info(f"[完成] 下载: {info_dict.get('title')}")
            self.update_progress(100, "[进度] 下载完成")
            self.result_queue.put(("success", f"[成功] 下载完成: {info_dict.get('title')}"))
            self.update_progress(
                self.current_task_index / self.total_tasks * 100, 
                f"[进度] 完成 {self.current_task_index}/{self.total_tasks}"
            )

            self.save_download_history(url, info_dict.get('title'), format_id, save_path)

            # 下载完成弹窗提示打开文件夹
            if messagebox.askyesno("[提示] 下载完成", f"是否打开下载文件夹浏览 {info_dict.get('title')}？"):
                self.open_folder(save_path)

            if transcode:
                original_file = f"{save_path}/{info_dict.get('title', 'video')}.{info_dict.get('ext', 'mp4')}"
                transcoded_file = f"{save_path}/{info_dict.get('title', 'video')}.{transcode_format}"
                
                self.result_queue.put(("info", f"[转码] 开始: {original_file} -> {transcoded_file}"))
                self.transcode_file(original_file, transcoded_file)

        except Exception as e:
            self.logger.error(f"[失败] 下载: {str(e)}")
            self.update_progress(0, "[进度] 下载失败")
            error_msg = str(e)
            if "ffmpeg" in error_msg.lower() or "FFmpeg" in error_msg:
                self.result_queue.put(("error", f"[失败] 下载: 需要ffmpeg但未安装。请安装并添加PATH。"))
            elif 'yt_dlp.utils.DownloadError' in str(type(e)) or 'Network' in error_msg or '403' in error_msg:
                self.result_queue.put(("error", f"[失败] 下载: 连接失败，网络问题或代理。"))
            else:
                self.result_queue.put(("error", f"[失败] 下载: {error_msg}"))
        finally:
            self.is_downloading = False
            self.ydl_instance = None
            if task_id in self.download_threads:
                del self.download_threads[task_id]

    def open_folder(self, path):
        """打开下载文件夹"""
        try:
            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", path])
            else:  # Linux
                subprocess.run(["xdg-open", path])
        except Exception as e:
            self.result_queue.put(("error", f"[错误] 打开文件夹失败: {str(e)}"))

    def _download_hook(self, d):
        if self.abort_all_tasks:
            return

        if d['status'] == 'downloading':
            percent = d.get('_percent_str', '?')
            speed = d.get('_speed_str', '?')
            eta = d.get('_eta_str', '?')
            self.result_queue.put(("progress", f"[进度] 下载中: {percent} 速度: {speed} 剩余: {eta}"))

            if '%' in percent:
                try:
                    progress = float(percent.strip('%'))
                    overall_progress = (self.current_task_index-1 + progress/100) / self.total_tasks * 100
                    self.update_progress(overall_progress, f"[进度] 下载中 {self.current_task_index}/{self.total_tasks}: {percent}")
                except:
                    pass
        elif d['status'] == 'finished':
            self.result_queue.put(("info", "[处理] 正在处理文件..."))

    def process_results(self):
        try:
            while not self.result_queue.empty():
                result = self.result_queue.get()
                if result[0] == "info":
                    self._append_log(result[1], "info")
                elif result[0] == "error":
                    self._append_log(result[1], "error")
                elif result[0] == "success":
                    self._append_log(result[1], "success")
                elif result[0] == "progress":
                    self._update_progress(result[1])
        except Exception as e:
            self._append_log(f"[错误] 处理结果: {str(e)}", "error")

        self.root.after(100, self.process_results)

    def _append_log(self, message, tag="info"):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n", tag)
        self.log_text.config(state=tk.DISABLED)
        self.log_text.see(tk.END)

    def _update_progress(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete("end-2l", "end-1c")
        self.log_text.insert(tk.END, message + "\n", "progress")
        self.log_text.config(state=tk.DISABLED)
        self.log_text.see(tk.END)

    def clear_logs(self):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)

    def load_download_history(self):
        try:
            if os.path.exists("download_history.json"):
                with open("download_history.json", "r", encoding="utf-8") as f:
                    self.download_history = json.load(f)
            else:
                self.download_history = []
        except Exception as e:
            self.download_history = []
            self.logger.error(f"[加载] 下载历史失败: {str(e)}")

    def save_download_history(self, url, title, format_id, save_path):
        try:
            history_entry = {
                "url": url,
                "title": title,
                "format_id": format_id,
                "save_path": save_path,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            self.download_history.append(history_entry)

            if len(self.download_history) > 100:
                self.download_history = self.download_history[-100:]

            with open("download_history.json", "w", encoding="utf-8") as f:
                json.dump(self.download_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"[保存] 下载历史失败: {str(e)}")

    def show_history(self):
        if not self.download_history:
            messagebox.showinfo("[历史] 下载", "暂无记录")
            return

        history_window = tk.Toplevel(self.root)
        history_window.title("下载历史")
        history_window.geometry("800x500")
        history_window.minsize(700, 400)

        columns = ("序号", "标题", "URL", "格式", "保存路径", "时间")
        tree = ttk.Treeview(history_window, columns=columns, show="headings")

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

        for i, entry in enumerate(reversed(self.download_history), 1):
            tree.insert("", "end", values=(
                i,
                entry["title"],
                entry["url"],
                entry["format_id"],
                entry["save_path"],
                entry["timestamp"]
            ))

        scrollbar = ttk.Scrollbar(history_window, orient="vertical", command=tree.yview)
        tree.configure(yscroll=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(fill=tk.BOTH, expand=True)

        def open_file_location(event):
            item = tree.selection()[0]
            values = tree.item(item, "values")
            path = values[4]

            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Darwin":
                subprocess.run(["open", path])
            else:
                subprocess.run(["xdg-open", path])

        tree.bind("<Double-1>", open_file_location)

    def transcode_file(self, input_file, output_file):
        try:
            try:
                subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            except (subprocess.SubprocessError, FileNotFoundError):
                self.result_queue.put(("error", "[转码失败] 未找到ffmpeg。请安装并添加PATH。"))
                return

            cmd = [
                "ffmpeg",
                "-i", input_file,
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "23",
                "-c:a", "aac",
                "-strict", "experimental",
                "-y",
                output_file
            ]

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )

            while True:
                output = process.stderr.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    pass

            return_code = process.wait()

            if return_code == 0:
                self.result_queue.put(("success", f"[转码成功] {output_file}"))
            else:
                self.result_queue.put(("error", f"[转码失败] 返回代码: {return_code}"))

        except Exception as e:
            self.result_queue.put(("error", f"[转码出错] : {str(e)}"))

    def check_ffmpeg(self):
        try:
            subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

def show_splash_screen(root):
    splash = tk.Toplevel(root)
    splash.title("加载中...")
    splash.geometry("400x300")
    splash.overrideredirect(True)
    splash.attributes('-topmost', True)

    screen_width = splash.winfo_screenwidth()
    screen_height = splash.winfo_screenheight()
    x = (screen_width - 400) // 2
    y = (screen_height - 300) // 2
    splash.geometry(f"400x300+{x}+{y}")

    label = tk.Label(splash, text="YouTube 下载器", font=('Arial', 18, 'bold'), fg="red")
    label.pack(pady=20)

    progress = ttk.Progressbar(splash, orient='horizontal', mode='indeterminate', length=300)
    progress.pack(pady=20)
    progress.start(10)

    status_label = tk.Label(splash, text="加载中...", font=('Arial', 12))
    status_label.pack()

    def close_splash():
        progress.stop()
        splash.destroy()
        root.deiconify()

    root.after(3000, close_splash)

def main():
    root = tk.Tk()
    root.withdraw()
    show_splash_screen(root)
    app = YouTubeDownloaderApp(root)
    root.mainloop()

if __name__ == '__main__':
    main()
