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
        self.root.geometry("900x700")  # 增加窗口高度以容纳新组件
        self.root.minsize(800, 600)
        self.root.geometry("1000x800")  # 增加窗口高度以容纳新组件
        self.root.minsize(900, 750)

        # 设置中文字体支持
        self.style = ttk.Style()
@@ -28,15 +31,24 @@
        self.download_queue = queue.Queue()
        self.result_queue = queue.Queue()

        # 下载任务列表
        # 下载任务列表和控制变量
        self.download_tasks = []
        self.current_task_index = 0
        self.total_tasks = 0
        self.abort_all_tasks = False
        
        # 视频信息缓存
        self.video_info = {}

        # 配置日志
        self.setup_logging()

        # 创建界面
        self.create_widgets()

        # 加载下载历史
        self.load_download_history()
        
        # 启动队列处理线程
        self.processing_thread = threading.Thread(target=self.process_queue, daemon=True)
        self.processing_thread.start()
@@ -47,6 +59,7 @@
        # 用于终止下载的变量
        self.ydl_instance = None
        self.is_downloading = False
        self.download_threads = {}  # 跟踪所有下载线程

    def setup_logging(self):
        """配置日志系统，将日志输出到GUI"""
@@ -74,6 +87,8 @@
        self.url_entry.grid(row=0, column=1, sticky=tk.W, pady=5, padx=5)
        self.url_entry.insert(0, "https://www.youtube.com/watch?v=")

        ttk.Button(url_frame, text="获取信息", command=self.fetch_video_info).grid(row=0, column=2, padx=5)
        
        # 批量下载支持
        ttk.Label(url_frame, text="或批量输入URLs (每行一个):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.urls_text = scrolledtext.ScrolledText(url_frame, wrap=tk.WORD, height=3)
@@ -84,6 +99,20 @@
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
@@ -97,22 +126,48 @@
        ttk.Entry(save_path_frame, textvariable=self.save_path_var, width=50).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(save_path_frame, text="浏览...", command=self.browse_save_path).pack(side=tk.LEFT)

        # 下载格式
        # 下载格式预设
        ttk.Label(options_frame, text="下载格式:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.format_var = tk.StringVar(value="custom")
        format_frame = ttk.Frame(options_frame)
        format_frame.grid(row=1, column=1, sticky=tk.W, pady=5)

        ttk.Radiobutton(format_frame, text="视频或音频（MP3）", variable=self.format_var, value="custom").pack(side=tk.LEFT, padx=5)
        
        self.custom_format_entry = ttk.Entry(format_frame, width=10)
        self.custom_format_entry.pack(side=tk.LEFT, padx=(5, 0))
        self.format_preset = tk.StringVar(value="custom")
        
        # 预设选项
        format_presets = [
            ("最高质量视频", "bestvideo+bestaudio"),
            ("720p 视频", "best[height<=720]"),
            ("480p 视频", "best[height<=480]"),
            ("360p 视频", "best[height<=360]"),
            ("仅音频 (MP3)", "bestaudio"),
            ("仅音频 (原始格式)", "bestaudio"),
            ("自定义", "custom")
        ]
        
        for i, (text, value) in enumerate(format_presets):
            ttk.Radiobutton(format_frame, text=text, variable=self.format_preset, value=value).grid(row=i//4, column=i%4, sticky=tk.W, padx=5, pady=2)
        
        # 自定义格式ID
        ttk.Label(options_frame, text="自定义格式ID:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.custom_format_entry = ttk.Entry(options_frame, width=20)
        self.custom_format_entry.grid(row=2, column=1, sticky=tk.W, pady=5, padx=5)
        self.custom_format_entry.insert(0, "ID号")
        self.custom_format_entry.config(state=tk.NORMAL)

        # 字幕选项
        self.subtitle_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="下载字幕", variable=self.subtitle_var).grid(row=2, column=1, sticky=tk.W, pady=5)
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
@@ -122,6 +177,7 @@
        ttk.Button(button_frame, text="开始下载", command=self.start_download, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="终止下载", command=self.stop_download, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="清空日志", command=self.clear_logs, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="查看历史", command=self.show_history, width=15).pack(side=tk.LEFT, padx=5)

        # 下载进度条
        progress_frame = ttk.LabelFrame(main_frame, text="下载进度", padding=10)
@@ -161,6 +217,61 @@
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
@@ -193,36 +304,55 @@

        proxy = self.proxy_entry.get().strip() or None
        save_path = self.save_path_var.get()
        format_id = self.custom_format_entry.get().strip()
        format_preset = self.format_preset.get()
        custom_format = self.custom_format_entry.get().strip()
        download_subtitles = self.subtitle_var.get()
        thread_count = int(self.threads_var.get())
        transcode = self.transcode_var.get()
        transcode_format = self.transcode_format.get()

        if not format_id:
            messagebox.showerror("错误", "ID号不能为空")
        # 确定最终使用的格式ID
        format_id = custom_format if format_preset == "custom" else format_preset
        
        if format_preset == "custom" and not format_id:
            messagebox.showerror("错误", "自定义格式ID不能为空")
            return

        # 准备下载任务
        self.download_tasks = urls.copy()
        self.current_task_index = 0
        self.total_tasks = len(urls)
        self.abort_all_tasks = False
        self.update_progress(0, "准备下载...")

        for url in urls:
            self.logger.info(f"添加下载任务: {url}")
            self.download_queue.put(("download", url, proxy, save_path, format_id, download_subtitles))
            self.download_queue.put(("download", url, proxy, save_path, format_id, download_subtitles, thread_count, transcode, transcode_format))

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
@@ -233,6 +363,13 @@
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
                if task[0] == "query":
                    self._query_formats(task[1], task[2])
@@ -242,7 +379,18 @@
                        (self.current_task_index-1) / self.total_tasks * 100, 
                        f"准备下载 {self.current_task_index}/{self.total_tasks}"
                    )
                    self._download(task[1], task[2], task[3], task[4], task[5])
                    
                    # 为每个下载任务创建唯一ID
                    task_id = f"task_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    
                    # 在单独的线程中执行下载，以便可以独立控制每个任务
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
@@ -272,19 +420,22 @@
                    vcodec = f.get('vcodec', 'N/A')
                    filesize = f.get('filesize', 'N/A')

                    formats_info += f"ID: {format_id}, 格式: {ext}, 分辨率: {resolution}, 音频: {acodec}, 视频: {vcodec}, 大小: {filesize}\n"
                    # 只显示常见的格式
                    if (ext in ['mp4', 'webm', 'mkv', 'flv', 'avi'] and resolution != 'audio only') or \
                       (acodec != 'none' and resolution == 'audio only'):
                        formats_info += f"ID: {format_id}, 格式: {ext}, 分辨率: {resolution}, 音频: {acodec}, 视频: {vcodec}, 大小: {filesize}\n"

            self.result_queue.put(("info", formats_info))
        except Exception as e:
            self.result_queue.put(("error", f"查询格式失败: {str(e)}"))

    def _download(self, url, proxy, save_path, format_id, download_subtitles):
    def _download(self, task_id, url, proxy, save_path, format_id, download_subtitles, thread_count, transcode, transcode_format):
        """下载视频或音频的实际处理函数"""
        self.is_downloading = True

        try:
            # 检查是否需要提取音频
            is_audio = format_id.lower().startswith('audio')
            is_audio = format_id.lower().startswith('audio') or format_id == 'bestaudio'

            ydl_opts = {
                'socket_timeout': 10,
@@ -297,13 +448,14 @@
                'logger': self.logger,
                'writesubtitles': download_subtitles,
                'writeautomaticsub': download_subtitles,
                'subtitleslangs': ['en', 'zh-Hans', 'zh-Hant']  # 下载多种语言字幕
                'subtitleslangs': ['en', 'zh-Hans', 'zh-Hant'],  # 下载多种语言字幕
                'concurrent_fragments': thread_count  # 多线程下载
            }

            if is_audio:
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredcodec': 'mp3' if format_id == 'bestaudio' else 'best',
                    'preferredquality': '192',
                }]

@@ -321,14 +473,26 @@
            # 开始下载
            info_dict = self.ydl_instance.extract_info(url, download=True)

            if self.is_downloading:  # 确保下载没有被用户终止
                self.result_queue.put(("success", f"下载完成: {info_dict.get('title')}"))
                self.update_progress(
                    self.current_task_index / self.total_tasks * 100, 
                    f"完成 {self.current_task_index}/{self.total_tasks}"
                )
            else:
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
            
            # 如果启用了转码，执行转码
            if transcode:
                original_file = f"{save_path}/{info_dict.get('title', 'video')}.{info_dict.get('ext', 'mp4')}"
                transcoded_file = f"{save_path}/{info_dict.get('title', 'video')}.{transcode_format}"
                
                self.result_queue.put(("info", f"开始转码: {original_file} -> {transcoded_file}"))
                self.transcode_file(original_file, transcoded_file)

        except Exception as e:
            if 'yt_dlp.utils.DownloadError' in str(type(e)) or 'Network' in str(e) or '403' in str(e):
@@ -338,9 +502,14 @@
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
@@ -398,6 +567,152 @@
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
    
    def transcode_file(self, input_file, output_file):
        """转码文件"""
        try:
            # 检查ffmpeg是否存在
            try:
                subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            except (subprocess.SubprocessError, FileNotFoundError):
                self.result_queue.put(("error", "转码失败: 未找到ffmpeg。请确保ffmpeg已安装并添加到系统PATH中。"))
                return
            
            # 构建ffmpeg命令
            cmd = [
                "ffmpeg",
                "-i", input_file,
                "-c:v", "libx264",  # 使用x264编码
                "-preset", "medium",  # 编码速度预设
                "-crf", "23",        # 质量控制
                "-c:a", "aac",       # 音频编码
                "-strict", "experimental",
                "-y",                # 覆盖已存在文件
                output_file
            ]
            
            # 执行转码
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            # 监控转码进度
            while True:
                output = process.stderr.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    # 可以在这里解析输出以获取进度信息
                    pass
            
            return_code = process.wait()
            
            if return_code == 0:
                self.result_queue.put(("success", f"转码完成: {output_file}"))
                # 删除原始文件（可选）
                # os.remove(input_file)
            else:
                self.result_queue.put(("error", f"转码失败，返回代码: {return_code}"))
        
        except Exception as e:
            self.result_queue.put(("error", f"转码过程中出错: {str(e)}"))

class QueueHandler(logging.Handler):
    """日志处理器，将日志消息放入队列"""
