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
        self.root.title("YouTube 下载器 V1")
        self.root.geometry("1000x800")  # 增加窗口高度以容纳新组件
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
        
        # 格式信息
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
        
        # 启动结果处理
        self.root.after(100, self.process_results)
        
        # 用于终止下载的变量
        self.ydl_instance = None
        self.is_downloading = False
        self.download_threads = {}  # 跟踪所有下载线程
    
    def setup_logging(self):
        """配置日志系统，将日志输出到GUI"""
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        # 创建日志处理器，将日志输出到GUI
        self.log_handler = QueueHandler(self.result_queue)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        self.log_handler.setFormatter(formatter)
        self.logger.addHandler(self.log_handler)
    
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
        
        # 视频格式选择
        ttk.Label(options_frame, text="视频格式:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.video_format_var = tk.StringVar()
        self.video_format_combobox = ttk.Combobox(options_frame, textvariable=self.video_format_var, width=30)
        self.video_format_combobox.grid(row=1, column=1, sticky=tk.W, pady=5, padx=5)
        self.video_format_combobox.set("请先查询格式")
        self.video_format_combobox.config(state="disabled")
        
        # 自定义格式下载
        custom_format_frame = ttk.Frame(options_frame)
        custom_format_frame.grid(row=1, column=2, sticky=tk.W, pady=5, padx=5)
        
        ttk.Label(custom_format_frame, text="自定义格式:").pack(side=tk.LEFT, padx=(0, 5))
        self.custom_format_var = tk.StringVar()
        ttk.Entry(custom_format_frame, textvariable=self.custom_format_var, width=10).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(custom_format_frame, text="下载", command=self.download_custom_format).pack(side=tk.LEFT)
        
        # 音频格式选择
        ttk.Label(options_frame, text="音频格式:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.audio_format_var = tk.StringVar()
        self.audio_format_combobox = ttk.Combobox(options_frame, textvariable=self.audio_format_var, width=30)
        self.audio_format_combobox.grid(row=2, column=1, sticky=tk.W, pady=5, padx=5)
        self.audio_format_combobox.set("请先查询格式")
        self.audio_format_combobox.config(state="disabled")
        
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
    
    def start_download(self):
        """开始下载视频或音频"""
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
        
        # 准备下载任务
        self.download_tasks = urls.copy()
        self.current_task_index = 0
        self.total_tasks = len(urls)
        self.abort_all_tasks = False
        self.update_progress(0, "准备下载...")
        
        for url in urls:
            self.logger.info(f"添加下载任务: {url}")
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
            self.ydl_instance._download_retcode = -1  # 设置退出码强制终止
        
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
        self.progress_label.config(text=message)
    
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
                if task[0] == "query":
                    self._query_formats(task[1], task[2])
                elif task[0] == "download":
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
                        args=(task_id, task[1], task[2], task[3], task[4], task[5], task[6], task[7], task[8]),
                        daemon=True
                    )
                    self.download_threads[task_id] = thread
                    thread.start()
                self.download_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"处理任务时出错: {str(e)}")
    
    def _query_formats(self, url, proxy):
        """查询视频格式的实际处理函数"""
        # 此函数与query_formats中的_query函数功能相同，保留用于兼容
        # 实际使用中，所有格式查询都通过query_formats方法完成
        pass
    
    def _download(self, task_id, url, proxy, save_path, format_id, download_subtitles, thread_count, transcode, transcode_format):
        """下载视频或音频的实际处理函数"""
        self.is_downloading = True
        
        try:
            # 检查是否需要提取音频
            is_audio = format_id.lower().startswith('audio') or format_id == 'bestaudio'
            
            # 检查ffmpeg是否可用（如果需要合并格式或提取音频）
            needs_ffmpeg = (
                '+' in format_id or  # 格式包含+表示需要合并
                (format_id.lower().startswith('audio') or format_id == 'bestaudio')  # 音频提取需要ffmpeg
            )
            
            if needs_ffmpeg and not self.check_ffmpeg():
                raise RuntimeError("需要ffmpeg来合并格式或提取音频，但未找到ffmpeg。请安装ffmpeg并确保其在系统PATH中。")
            
            ydl_opts = {
                'socket_timeout': 10,
                'proxy': proxy,
                'format': format_id,
                'outtmpl': f"{save_path}/%(title)s.%(ext)s",
                'progress_hooks': [self.download_hook],
                'quiet': True,
                'no_warnings': True,
                'logger': self.logger,
                'writesubtitles': download_subtitles,
                'writeautomaticsub': download_subtitles,
                'subtitleslangs': ['en', 'zh-Hans', 'zh-Hant'],  # 下载多种语言字幕
                'concurrent_fragments': thread_count  # 多线程下载
            }
            
            if is_audio:
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3' if format_id == 'bestaudio' else 'best',
                    'preferredquality': '192',
                }]
            
            self.logger.info(f"开始下载到: {save_path}")
            
            # 更新进度条
            self.update_progress(
                (self.current_task_index-1) / self.total_tasks * 100, 
                f"下载中 {self.current_task_index}/{self.total_tasks}"
            )
            
            # 保存ydl实例用于终止下载
            self.ydl_instance = yt_dlp.YoutubeDL(ydl_opts)
            
            # 开始下载
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
            
            # 如果启用了转码，执行转码
            if transcode:
                original_file = f"{save_path}/{info_dict.get('title', 'video')}.{info_dict.get('ext', 'mp4')}"
                transcoded_file = f"{save_path}/{info_dict.get('title', 'video')}.{transcode_format}"
                
                self.result_queue.put(("info", f"开始转码: {original_file} -> {transcoded_file}"))
                self.transcode_file(original_file, transcoded_file)
        
        except Exception as e:
            error_msg = str(e)
            if "ffmpeg" in error_msg.lower() or "FFmpeg" in error_msg:
                self.result_queue.put(("error", f"下载失败: 需要ffmpeg但未安装。请安装ffmpeg并确保其在系统PATH中。"))
            elif 'yt_dlp.utils.DownloadError' in str(type(e)) or 'Network' in error_msg or '403' in error_msg:
                self.result_queue.put(("error", "连接 YouTube 失败，可能是网络限制或无代理所致。"))
            else:
                self.result_queue.put(("error", f"下载失败: {error_msg}"))
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
            eta = d.get('_eta_str', '?')
            self.result_queue.put(("progress", f"下载中: {percent} 速度: {speed} 剩余时间: {eta}"))
            
            # 更新进度条
            if '%' in percent:
                try:
                    progress = float(percent.strip('%'))
                    overall_progress = (self.current_task_index-1 + progress/100) / self.total_tasks * 100
                    self.update_progress(overall_progress, f"下载中 {self.current_task_index}/{self.total_tasks}: {percent}")
                except:
                    pass
        elif d['status'] == 'finished':
            self.result_queue.put(("info", "正在处理文件..."))
    
    def process_results(self):
        """处理结果队列"""
        try:
            while not self.result_queue.empty():
                result = self.result_queue.get()
                if result[0] == "info":
                    self._append_log(result[1], "info")
                elif result[0] == "error":
                    self._append_log(f"错误: {result[1]}", "error")
                elif result[0] == "success":
                    self._append_log(f"成功: {result[1]}", "success")
                elif result[0] == "progress":
                    self._update_progress(result[1])
        except Exception as e:
            self._append_log(f"处理结果时出错: {str(e)}", "error")
        
        # 每隔100毫秒检查一次结果队列
        self.root.after(100, self.process_results)
    
    def _append_log(self, message, tag="info"):
        """向日志区域添加消息"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n", tag)
        self.log_text.config(state=tk.DISABLED)
        self.log_text.see(tk.END)
    
    def _update_progress(self, message):
        """更新进度信息"""
        self.log_text.config(state=tk.NORMAL)
        # 清除最后一行（进度信息）
        self.log_text.delete("end-2l", "end-1c")
        self.log_text.insert(tk.END, message + "\n", "progress")
        self.log_text.config(state=tk.DISABLED)
        self.log_text.see(tk.END)
    
    def clear_logs(self):
        """清空日志区域"""
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
    
    def check_ffmpeg(self):
        """检查系统中是否安装了ffmpeg"""
        try:
            subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

class QueueHandler(logging.Handler):
    """日志处理器，将日志消息放入队列"""
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue
    
    def emit(self, record):
        self.log_queue.put(("info", self.format(record)))

def main():
    """程序入口点"""
    root = tk.Tk()
    app = YouTubeDownloaderApp(root)
    root.mainloop()

if __name__ == '__main__':
    main()    
