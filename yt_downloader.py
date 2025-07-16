import yt_dlp
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import threading
import queue
import logging
import os
from datetime import datetime
import json

class YouTubeDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("YouTube 下载器")
        self.root.geometry("800x600")
        
        # 设置中文字体
        self.style = ttk.Style()
        self.style.configure('TLabel', font=('SimHei', 10))
        self.style.configure('TButton', font=('SimHei', 10))
        self.style.configure('TEntry', font=('SimHei', 10))
        self.style.configure('TCombobox', font=('SimHei', 10))
        
        # 初始化变量
        self.available_video_formats = []
        self.available_audio_formats = []
        self.download_tasks = []
        self.current_task_index = 0
        self.total_tasks = 0
        self.abort_all_tasks = False
        
        # 创建GUI组件
        self.create_widgets()
        
        # 设置日志
        self.setup_logging()
        
        # 启动队列处理线程
        self.processing_thread = threading.Thread(target=self.process_queue, daemon=True)
        self.processing_thread.start()
        
        # 启动结果处理
        self.root.after(100, self.process_results)
    
    def setup_logging(self):
        """设置日志系统"""
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        # 创建日志队列处理器
        class QueueHandler(logging.Handler):
            def __init__(self, log_queue):
                super().__init__()
                self.log_queue = log_queue
            
            def emit(self, record):
                self.log_queue.put((record.levelname, self.format(record)))
        
        # 创建日志队列
        self.result_queue = queue.Queue()
        self.log_handler = QueueHandler(self.result_queue)
        self.logger.addHandler(self.log_handler)
    
    def create_widgets(self):
        """创建GUI界面"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # URL输入框
        url_frame = ttk.LabelFrame(main_frame, text="视频URL", padding=10)
        url_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(url_frame, text="URL:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.url_entry = ttk.Entry(url_frame, width=60)
        self.url_entry.grid(row=0, column=1, sticky=tk.W, pady=5, padx=5)
        
        ttk.Button(url_frame, text="查询格式", command=self.query_formats).grid(row=0, column=2, padx=5)
        
        # 代理设置
        proxy_frame = ttk.LabelFrame(main_frame, text="代理设置", padding=10)
        proxy_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(proxy_frame, text="代理地址 (可选):").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.proxy_entry = ttk.Entry(proxy_frame, width=60)
        self.proxy_entry.grid(row=0, column=1, sticky=tk.W, pady=5, padx=5)
        self.proxy_entry.insert(0, "http://127.0.0.1:7890")
        
        # 保存路径
        path_frame = ttk.LabelFrame(main_frame, text="保存路径", padding=10)
        path_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(path_frame, text="路径:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.save_path_var = tk.StringVar(value=os.getcwd())
        ttk.Entry(path_frame, textvariable=self.save_path_var, width=50).grid(row=0, column=1, sticky=tk.W, pady=5, padx=5)
        ttk.Button(path_frame, text="浏览", command=self.browse_save_path).grid(row=0, column=2, padx=5)
        
        # 视频格式选择
        format_frame = ttk.LabelFrame(main_frame, text="下载格式", padding=10)
        format_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(format_frame, text="视频格式:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.video_format_var = tk.StringVar()
        self.video_format_combobox = ttk.Combobox(format_frame, textvariable=self.video_format_var, width=30)
        self.video_format_combobox.grid(row=0, column=1, sticky=tk.W, pady=5, padx=5)
        self.video_format_combobox.set("请先查询格式")
        self.video_format_combobox.config(state="disabled")
        
        # 音频格式选择
        ttk.Label(format_frame, text="音频格式:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.audio_format_var = tk.StringVar()
        self.audio_format_combobox = ttk.Combobox(format_frame, textvariable=self.audio_format_var, width=30)
        self.audio_format_combobox.grid(row=1, column=1, sticky=tk.W, pady=5, padx=5)
        self.audio_format_combobox.set("请先查询格式")
        self.audio_format_combobox.config(state="disabled")
        
        # 自定义格式下载
        custom_format_frame = ttk.Frame(format_frame)
        custom_format_frame.grid(row=1, column=2, sticky=tk.W, pady=5, padx=5)
        
        ttk.Label(custom_format_frame, text="自定义格式:").pack(side=tk.LEFT, padx=(0, 5))
        self.custom_format_var = tk.StringVar()
        ttk.Entry(custom_format_frame, textvariable=self.custom_format_var, width=10).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(custom_format_frame, text="下载", command=self.download_custom_format).pack(side=tk.LEFT)
        
        # 下载选项
        options_frame = ttk.LabelFrame(main_frame, text="下载选项", padding=10)
        options_frame.pack(fill=tk.X, pady=5)
        
        self.subtitle_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="下载字幕", variable=self.subtitle_var).grid(row=0, column=0, sticky=tk.W, pady=5)
        
        self.threads_var = tk.StringVar(value="4")
        ttk.Label(options_frame, text="线程数:").grid(row=0, column=1, sticky=tk.W, pady=5)
        ttk.Combobox(options_frame, textvariable=self.threads_var, values=["1", "2", "4", "8", "16"], width=5).grid(row=0, column=2, sticky=tk.W, pady=5, padx=5)
        
        # 下载按钮
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="开始下载", command=self.start_download, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="终止下载", command=self.stop_download, width=15).pack(side=tk.LEFT, padx=5)
        
        # 进度条
        progress_frame = ttk.LabelFrame(main_frame, text="下载进度", padding=10)
        progress_frame.pack(fill=tk.X, pady=5)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, length=100, mode='determinate')
        self.progress_bar.pack(fill=tk.X, expand=True)
        
        self.progress_label = ttk.Label(progress_frame, text="准备就绪")
        self.progress_label.pack(anchor=tk.W, pady=2)
        
        # 日志区域
        log_frame = ttk.LabelFrame(main_frame, text="日志", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=10)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.config(state=tk.DISABLED)
    
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
    
    def query_formats(self):
        """查询视频格式"""
        url = self.url_entry.get().strip()
        proxy = self.proxy_entry.get().strip() or None
        
        if not self.validate_url(url):
            messagebox.showerror("错误", "请输入有效的 YouTube 链接")
            return
            
        self.logger.info(f"查询视频格式: {url}")
        
        # 清空下拉菜单
        self.video_format_combobox.set("请先查询格式")
        self.video_format_combobox.config(state="disabled")
        self.audio_format_combobox.set("请先查询格式")
        self.audio_format_combobox.config(state="disabled")
        
        self.available_video_formats = []
        self.available_audio_formats = []
        
        def _query():
            try:
                ydl_opts = {
                    'socket_timeout': 10,
                    'proxy': proxy,
                    'quiet': True
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    self.logger.info("正在获取视频格式信息...")
                    info_dict = ydl.extract_info(url, download=False)
                    formats = info_dict.get('formats', [info_dict])
                    
                    # 筛选视频格式（720p到4320p）
                    for f in formats:
                        format_id = f['format_id']
                        ext = f['ext']
                        resolution = f.get('resolution', 'N/A')
                        acodec = f.get('acodec', 'N/A')
                        vcodec = f.get('vcodec', 'N/A')
                        filesize = f.get('filesize', 'N/A')
                        fps = f.get('fps', '?')
                        
                        # 提取分辨率中的数字部分
                        resolution_num = 0
                        if 'p' in resolution:
                            try:
                                resolution_num = int(resolution.replace('p', ''))
                            except ValueError:
                                pass
                        
                        # 筛选视频格式（720p到4320p，常见视频格式）
                        if (ext in ['mp4', 'webm', 'mkv'] and 
                            resolution != 'audio only' and
                            720 <= resolution_num <= 4320):
                            self.available_video_formats.append({
                                'id': format_id,
                                'ext': ext,
                                'resolution': resolution,
                                'acodec': acodec,
                                'vcodec': vcodec,
                                'filesize': filesize,
                                'fps': fps
                            })
                        
                        # 筛选音频格式
                        if acodec != 'none' and vcodec == 'none':
                            self.available_audio_formats.append({
                                'id': format_id,
                                'ext': ext,
                                'acodec': acodec,
                                'filesize': filesize
                            })
                    
                    # 按分辨率排序视频格式（从高到低）
                    self.available_video_formats.sort(
                        key=lambda x: int(x['resolution'].replace('p', '')) if 'p' in x['resolution'] else 0,
                        reverse=True
                    )
                    
                    # 使用root.after确保在主线程中更新UI
                    self.root.after(0, self._update_format_comboboxes)
                    
                    formats_info = f"\n可用视频格式 for: {info_dict.get('title')}\n"
                    for f in self.available_video_formats:
                        formats_info += f"ID: {f['id']}, 格式: {f['ext']}, 分辨率: {f['resolution']}, 帧率: {f['fps']}fps, 音频: {f['acodec']}, 视频: {f['vcodec']}, 大小: {f['filesize']}\n"
                    
                    formats_info += "\n可用音频格式:\n"
                    for f in self.available_audio_formats:
                        formats_info += f"ID: {f['id']}, 格式: {f['ext']}, 音频: {f['acodec']}, 大小: {f['filesize']}\n"
                    
                    self.result_queue.put(("info", formats_info))
            except Exception as e:
                self.result_queue.put(("error", f"查询格式失败: {str(e)}"))
        
        # 在单独线程中查询格式
        threading.Thread(target=_query, daemon=True).start()
    
    def _update_format_comboboxes(self):
        """更新格式下拉菜单"""
        # 更新视频格式下拉菜单
        if self.available_video_formats:
            video_format_values = []
            for f in self.available_video_formats:
                filesize_str = f['filesize'] if f['filesize'] != 'N/A' else '未知大小'
                video_format_values.append(f"{f['resolution']} ({f['ext']}, {filesize_str})")
            
            self.video_format_combobox["values"] = video_format_values
            self.video_format_combobox.config(state="readonly")
            self.video_format_combobox.current(0)  # 默认选择最高质量
        else:
            self.video_format_combobox["values"] = ["无可用视频格式"]
            self.video_format_combobox.config(state="disabled")
        
        # 更新音频格式下拉菜单
        if self.available_audio_formats:
            audio_format_values = []
            for f in self.available_audio_formats:
                filesize_str = f['filesize'] if f['filesize'] != 'N/A' else '未知大小'
                audio_format_values.append(f"{f['acodec']} ({f['ext']}, {filesize_str})")
            
            self.audio_format_combobox["values"] = audio_format_values
            self.audio_format_combobox.config(state="readonly")
            self.audio_format_combobox.current(0)  # 默认选择第一个
        else:
            self.audio_format_combobox["values"] = ["无可用音频格式"]
            self.audio_format_combobox.config(state="disabled")
    
    def download_custom_format(self):
        """下载自定义格式的视频或音频"""
        url = self.url_entry.get().strip()
        proxy = self.proxy_entry.get().strip() or None
        save_path = self.save_path_var.get()
        custom_format_id = self.custom_format_var.get().strip()
        download_subtitles = self.subtitle_var.get()
        thread_count = int(self.threads_var.get())
        
        if not self.validate_url(url):
            messagebox.showerror("错误", "请输入有效的 YouTube 链接")
            return
        
        if not custom_format_id:
            messagebox.showerror("错误", "请输入格式ID")
            return
            
        self.logger.info(f"开始下载自定义格式: {custom_format_id}")
        
        # 准备下载任务
        self.download_tasks = [url]
        self.current_task_index = 0
        self.total_tasks = 1
        self.abort_all_tasks = False
        self.update_progress(0, "准备下载...")
        
        # 创建下载队列
        self.download_queue = queue.Queue()
        self.download_queue.put(("download", url, proxy, save_path, custom_format_id, download_subtitles, thread_count))
    
    def start_download(self):
        """开始下载视频或音频"""
        url = self.url_entry.get().strip()
        proxy = self.proxy_entry.get().strip() or None
        save_path = self.save_path_var.get()
        download_subtitles = self.subtitle_var.get()
        thread_count = int(self.threads_var.get())
        
        if not self.validate_url(url):
            messagebox.showerror("错误", "请输入有效的 YouTube 链接")
            return
            
        # 获取用户选择的格式
        video_format_index = self.video_format_combobox.current()
        audio_format_index = self.audio_format_combobox.current()
        
        # 准备下载格式
        selected_formats = []
        
        # 添加视频格式
        if video_format_index >= 0 and self.available_video_formats:
            video_format = self.available_video_formats[video_format_index]
            selected_formats.append(video_format['id'])
            self.logger.info(f"选择视频格式: {video_format['resolution']} ({video_format['id']})")
        
        # 添加音频格式
        if audio_format_index >= 0 and self.available_audio_formats:
            audio_format = self.available_audio_formats[audio_format_index]
            selected_formats.append(audio_format['id'])
            self.logger.info(f"选择音频格式: {audio_format['acodec']} ({audio_format['id']})")
        
        # 如果没有选择任何格式，使用默认选项
        if not selected_formats:
            messagebox.showerror("错误", "请至少选择一种视频或音频格式")
            return
        
        # 构建最终的格式选择
        format_id = '+'.join(selected_formats) if len(selected_formats) > 1 else selected_formats[0]
        
        self.logger.info(f"开始下载: {url}")
        
        # 准备下载任务
        self.download_tasks = [url]
        self.current_task_index = 0
        self.total_tasks = 1
        self.abort_all_tasks = False
        self.update_progress(0, "准备下载...")
        
        # 创建下载队列
        self.download_queue = queue.Queue()
        self.download_queue.put(("download", url, proxy, save_path, format_id, download_subtitles, thread_count))
    
    def stop_download(self):
        """停止下载"""
        self.abort_all_tasks = True
        self.logger.info("停止下载")
    
    def update_progress(self, percent, message):
        """更新进度条和进度信息"""
        self.progress_var.set(percent)
        self.progress_label.config(text=message)
    
    def process_queue(self):
        """处理下载队列"""
        while True:
            try:
                task = self.download_queue.get(timeout=1)
                if task[0] == "download":
                    self._download(task[1], task[2], task[3], task[4], task[5], task[6])
                self.download_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"处理队列时出错: {str(e)}")
    
    def _download(self, url, proxy, save_path, format_id, download_subtitles, thread_count):
        """实际执行下载的方法"""
        try:
            # 检查是否需要提取音频
            is_audio = format_id.lower().startswith('audio') or format_id == 'bestaudio'
            
            # 设置yt-dlp选项
            ydl_opts = {
                'format': format_id,
                'outtmpl': f"{save_path}/%(title)s.%(ext)s",
                'writesubtitles': download_subtitles,
                'writeautomaticsub': download_subtitles,
                'subtitleslangs': ['en', 'zh'],
                'noplaylist': True,
                'continuedl': True,
                'quiet': True,
                'no_warnings': True,
                'socket_timeout': 10,
                'proxy': proxy,
                'concurrent_fragments': thread_count,
                'progress_hooks': [self._download_hook],
            }
            
            # 如果是音频下载，添加音频处理选项
            if is_audio:
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]
            
            # 开始下载
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=True)
            
            self.logger.info(f"下载完成: {info_dict.get('title')}")
            self.update_progress(100, "下载完成")
            
        except Exception as e:
            self.logger.error(f"下载失败: {str(e)}")
            self.update_progress(0, "下载失败")
    
    def _download_hook(self, d):
        """下载进度回调函数"""
        if d['status'] == 'downloading':
            percent = d.get('_percent_str', '?')
            speed = d.get('_speed_str', '?')
            eta = d.get('_eta_str', '?')
            self.logger.info(f"下载中: {percent} 速度: {speed} 剩余时间: {eta}")
            
            # 更新进度条
            if '%' in percent:
                try:
                    progress = float(percent.strip('%'))
                    self.update_progress(progress, f"下载中: {percent}")
                except:
                    pass
        elif d['status'] == 'finished':
            self.logger.info("下载完成，正在处理...")
    
    def process_results(self):
        """处理结果队列"""
        while not self.result_queue.empty():
            level, message = self.result_queue.get()
            self._append_log(message, level)
        self.root.after(100, self.process_results)
    
    def _append_log(self, message, level="INFO"):
        """向日志区域添加消息"""
        self.log_text.config(state=tk.NORMAL)
        if level == "ERROR":
            self.log_text.insert(tk.END, f"[错误] {message}\n", "error")
        elif level == "INFO":
            self.log_text.insert(tk.END, f"[信息] {message}\n", "info")
        elif level == "WARNING":
            self.log_text.insert(tk.END, f"[警告] {message}\n", "warning")
        self.log_text.config(state=tk.DISABLED)
        self.log_text.see(tk.END)

def main():
    root = tk.Tk()
    app = YouTubeDownloaderApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
