import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import queue
import logging
import yt_dlp
import os
import time
from datetime import datetime

class YouTubeDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("YouTube 视频下载器")
        self.root.geometry("800x600")
        self.root.resizable(True, True)
        
        # 设置中文字体
        self.root.option_add("*Font", "SimHei 10")
        
        # 创建主框架
        self.main_frame = ttk.Frame(root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 初始化变量
        self.url_var = tk.StringVar()
        self.proxy_var = tk.StringVar()
        self.title_var = tk.StringVar(value="标题: ")
        self.duration_var = tk.StringVar(value="时长: ")
        self.views_var = tk.StringVar(value="观看次数: ")
        self.uploader_var = tk.StringVar(value="上传者: ")
        self.status_var = tk.StringVar(value="就绪")
        self.download_path = os.path.join(os.path.expanduser("~"), "Downloads", "YouTubeVideos")
        self.video_info = {}
        self.available_video_formats = []
        self.available_audio_formats = []
        self.all_formats = []
        self.downloading = False
        
        # 创建日志系统
        self.create_logger()
        
        # 创建UI组件
        self.create_widgets()
        
        # 结果队列，用于线程间通信
        self.result_queue = queue.Queue()
        
        # 启动队列处理
        self.process_queue()
    
    def create_logger(self):
        """创建日志系统"""
        self.logger = logging.getLogger("YouTubeDownloader")
        self.logger.setLevel(logging.DEBUG)
        
        # 创建文件处理器
        if not os.path.exists("logs"):
            os.makedirs("logs")
        log_file = os.path.join("logs", f"downloader_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # 创建格式化器
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # 添加处理器到logger
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        # 添加一个特殊级别用于格式信息
        logging.addLevelName(logging.INFO + 1, "FORMAT")
    
    def create_widgets(self):
        """创建UI组件"""
        # URL输入框
        url_frame = ttk.Frame(self.main_frame)
        url_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(url_frame, text="视频URL:").pack(side=tk.LEFT, padx=5)
        self.url_entry = ttk.Entry(url_frame, textvariable=self.url_var, width=60)
        self.url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # 代理设置
        proxy_frame = ttk.Frame(self.main_frame)
        proxy_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(proxy_frame, text="代理服务器:").pack(side=tk.LEFT, padx=5)
        self.proxy_entry = ttk.Entry(proxy_frame, textvariable=self.proxy_var, width=30)
        self.proxy_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Label(proxy_frame, text="(可选，格式: http://host:port)").pack(side=tk.LEFT, padx=5)
        
        # 按钮框架
        btn_frame = ttk.Frame(self.main_frame)
        btn_frame.pack(fill=tk.X, pady=10)
        
        self.fetch_btn = ttk.Button(btn_frame, text="获取视频信息", command=self.fetch_video_info)
        self.fetch_btn.pack(side=tk.LEFT, padx=5)
        
        self.download_btn = ttk.Button(btn_frame, text="开始下载", command=self.download_video, state=tk.DISABLED)
        self.download_btn.pack(side=tk.LEFT, padx=5)
        
        # 视频信息框架
        info_frame = ttk.LabelFrame(self.main_frame, text="视频信息")
        info_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(info_frame, textvariable=self.title_var).pack(anchor=tk.W, padx=5, pady=2)
        ttk.Label(info_frame, textvariable=self.duration_var).pack(anchor=tk.W, padx=5, pady=2)
        ttk.Label(info_frame, textvariable=self.views_var).pack(anchor=tk.W, padx=5, pady=2)
        ttk.Label(info_frame, textvariable=self.uploader_var).pack(anchor=tk.W, padx=5, pady=2)
        
        # 格式选择框架
        format_frame = ttk.LabelFrame(self.main_frame, text="下载选项")
        format_frame.pack(fill=tk.X, pady=10)
        
        # 视频格式选择
        video_format_frame = ttk.Frame(format_frame)
        video_format_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(video_format_frame, text="视频格式:").pack(side=tk.LEFT, padx=5)
        self.video_format_combobox = ttk.Combobox(video_format_frame, state="disabled", width=40)
        self.video_format_combobox.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # 音频格式选择
        audio_format_frame = ttk.Frame(format_frame)
        audio_format_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(audio_format_frame, text="音频格式:").pack(side=tk.LEFT, padx=5)
        self.audio_format_combobox = ttk.Combobox(audio_format_frame, state="disabled", width=40)
        self.audio_format_combobox.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # 下载路径选择
        path_frame = ttk.Frame(format_frame)
        path_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(path_frame, text="下载路径:").pack(side=tk.LEFT, padx=5)
        self.path_entry = ttk.Entry(path_frame, width=50)
        self.path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.path_entry.insert(0, self.download_path)
        
        browse_btn = ttk.Button(path_frame, text="浏览", command=self.browse_path)
        browse_btn.pack(side=tk.LEFT, padx=5)
        
        # 下载进度条
        progress_frame = ttk.Frame(self.main_frame)
        progress_frame.pack(fill=tk.X, pady=10)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, length=100, mode='determinate')
        self.progress_bar.pack(fill=tk.X, expand=True)
        
        # 状态标签
        status_frame = ttk.Frame(self.main_frame)
        status_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(status_frame, text="状态:").pack(side=tk.LEFT, padx=5)
        ttk.Label(status_frame, textvariable=self.status_var).pack(side=tk.LEFT, padx=5)
        
        # 日志区域
        log_frame = ttk.LabelFrame(self.main_frame, text="下载日志")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, width=80, height=10)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.log_text.config(state=tk.DISABLED)
    
    def validate_url(self, url):
        """验证URL是否为有效的YouTube链接"""
        return url.startswith("https://www.youtube.com/") or url.startswith("https://youtu.be/")
    
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
        self.all_formats = []  # 清空所有格式信息

        def _fetch():
            try:
                ydl_opts = {
                    'socket_timeout': 10,
                    'proxy': proxy,
                    'quiet': True,
                    'format': 'bestvideo*+bestaudio/best',
                    'noplaylist': True,  # 只获取单个视频，不处理播放列表
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

                    # 收集所有格式信息用于调试和日志输出
                    self.logger.info("所有可用格式信息:")
                    for f in formats:
                        format_id = f.get('format_id')
                        ext = f.get('ext')
                        resolution = f.get('resolution')
                        acodec = f.get('acodec')
                        vcodec = f.get('vcodec')
                        filesize = f.get('filesize')
                        filesize_str = f.get('filesize_approx_str') or (f'{filesize / (1024*1024):.2f}MB' if filesize else '未知大小')
                        fps = f.get('fps', '?')
                        format_note = f.get('format_note', '')
                        
                        # 保存所有格式信息
                        self.all_formats.append({
                            'format_id': format_id,
                            'ext': ext,
                            'resolution': resolution,
                            'acodec': acodec,
                            'vcodec': vcodec,
                            'filesize': filesize_str,
                            'fps': fps,
                            'format_note': format_note
                        })
                        
                        # 记录格式信息到日志
                        format_info = f"格式ID: {format_id}, 扩展名: {ext}, 分辨率: {resolution}, 音频编码: {acodec}, 视频编码: {vcodec}, 大小: {filesize_str}"
                        if fps != '?':
                            format_info += f", FPS: {fps}"
                        if format_note:
                            format_info += f", 备注: {format_note}"
                            
                        self.logger.log(logging.INFO + 1, format_info)  # 使用特殊级别以便在日志中突出显示

                        # 改进的格式筛选逻辑
                        if vcodec != 'none' and resolution != 'audio only': # 视频格式
                            # 只显示常见的视频格式，排除低质量和特殊格式
                            if (ext in ['mp4', 'webm', 'mkv'] and 
                                resolution not in ['144p', '240p'] and
                                'HLS' not in format_note):
                                video_formats.append({
                                    'display': f'{resolution} ({ext}, {filesize_str})',
                                    'format_id': format_id,
                                    'ext': ext
                                })
                        elif acodec != 'none' and vcodec == 'none': # 音频格式
                            # 只显示常见的音频格式
                            if ext in ['mp3', 'm4a', 'webm', 'wav']:
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
        """更新格式下拉菜单"""
        if self.available_video_formats:
            self.video_format_combobox["values"] = [f['display'] for f in self.available_video_formats]
            self.video_format_combobox.config(state="readonly")
            self.video_format_combobox.current(0)  # 默认选择第一个（最高质量）
        else:
            self.video_format_combobox["values"] = ["无可用视频格式"]
            self.video_format_combobox.config(state="disabled")
        
        if self.available_audio_formats:
            self.audio_format_combobox["values"] = [f['display'] for f in self.available_audio_formats]
            self.audio_format_combobox.config(state="readonly")
            self.audio_format_combobox.current(0)  # 默认选择第一个
        else:
            self.audio_format_combobox["values"] = ["无可用音频格式"]
            self.audio_format_combobox.config(state="disabled")
        
        # 启用下载按钮
        if self.available_video_formats or self.available_audio_formats:
            self.download_btn.config(state=tk.NORMAL)
        else:
            self.download_btn.config(state=tk.DISABLED)
    
    def browse_path(self):
        """浏览并选择下载路径"""
        from tkinter import filedialog
        
        path = filedialog.askdirectory(title="选择下载文件夹", initialdir=self.download_path)
        if path:
            self.download_path = path
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, path)
    
    def download_video(self):
        """下载视频或音频"""
        if self.downloading:
            messagebox.showinfo("提示", "正在下载中，请等待当前下载完成")
            return
            
        url = self.url_entry.get().strip()
        if not url or url not in self.video_info:
            messagebox.showerror("错误", "请先获取视频信息")
            return
            
        # 获取用户选择的格式
        video_format_index = self.video_format_combobox.current()
        audio_format_index = self.audio_format_combobox.current()
        
        # 检查是否选择了格式
        if video_format_index < 0 and audio_format_index < 0:
            messagebox.showerror("错误", "请至少选择一种视频或音频格式")
            return
            
        # 创建下载目录（如果不存在）
        download_path = self.path_entry.get().strip()
        if not download_path:
            download_path = self.download_path
        
        if not os.path.exists(download_path):
            try:
                os.makedirs(download_path)
                self.logger.info(f"创建下载目录: {download_path}")
            except Exception as e:
                messagebox.showerror("错误", f"无法创建下载目录: {str(e)}")
                return
        
        # 获取视频信息
        info_dict = self.video_info[url]
        title = info_dict.get('title', 'video')
        # 替换文件名中的非法字符
        safe_title = "".join([c for c in title if c not in r'\/:*?"<>|'])
        
        # 更新状态
        self.status_var.set("准备下载...")
        self.progress_var.set(0)
        self.downloading = True
        self.fetch_btn.config(state=tk.DISABLED)
        self.download_btn.config(state=tk.DISABLED)
        
        def _download():
            try:
                # 构建下载选项
                ydl_opts = {
                    'outtmpl': os.path.join(download_path, f"{safe_title}.%(ext)s"),
                    'progress_hooks': [self._download_progress_hook],
                    'socket_timeout': 10,
                    'proxy': self.proxy_entry.get().strip() or None,
                    'format': '',
                    'postprocessors': [],
                    'logger': self.logger,
                    'noprogress': False,
                    'quiet': False,
                }
                
                # 设置下载格式
                format_selection = []
                
                if video_format_index >= 0:
                    video_format = self.available_video_formats[video_format_index]
                    format_selection.append(video_format['format_id'])
                    self.logger.info(f"选择视频格式: {video_format['display']}")
                
                if audio_format_index >= 0:
                    audio_format = self.available_audio_formats[audio_format_index]
                    format_selection.append(audio_format['format_id'])
                    self.logger.info(f"选择音频格式: {audio_format['display']}")
                
                if len(format_selection) > 1:
                    ydl_opts['format'] = '+'.join(format_selection)
                elif len(format_selection) == 1:
                    ydl_opts['format'] = format_selection[0]
                else:
                    ydl_opts['format'] = 'bestvideo*+bestaudio/best'
                
                # 如果只下载音频，添加音频后处理器
                if video_format_index < 0 and audio_format_index >= 0:
                    audio_ext = self.available_audio_formats[audio_format_index]['ext']
                    ydl_opts['postprocessors'] = [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': audio_ext,
                        'preferredquality': '192',
                    }]
                
                self.logger.info(f"开始下载: {title}")
                self.logger.info(f"下载选项: {ydl_opts}")
                
                # 开始下载
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                
                self.result_queue.put(("success", f"下载完成: {title}"))
            except Exception as e:
                self.result_queue.put(("error", f"下载失败: {str(e)}"))
            finally:
                self.root.after(0, self._download_complete)
        
        # 在单独线程中下载
        threading.Thread(target=_download, daemon=True).start()
    
    def _download_progress_hook(self, d):
        """下载进度回调函数"""
        if d['status'] == 'downloading':
            if 'downloaded_bytes' in d and 'total_bytes' in d:
                percent = d['downloaded_bytes'] / d['total_bytes'] * 100
                self.progress_var.set(percent)
                self.status_var.set(f"下载中: {percent:.1f}%")
                self._log_message(f"下载进度: {percent:.1f}%")
            elif 'eta' in d:
                eta = d['eta']
                self.status_var.set(f"下载中，剩余时间: {eta}秒")
        elif d['status'] == 'finished':
            self.progress_var.set(100)
            self.status_var.set("正在处理文件...")
    
    def _download_complete(self):
        """下载完成后的处理"""
        self.downloading = False
        self.fetch_btn.config(state=tk.NORMAL)
        self.download_btn.config(state=tk.NORMAL)
    
    def _log_message(self, message):
        """将消息添加到日志区域"""
        self.root.after(0, self._update_log_text, message)
    
    def _update_log_text(self, message):
        """更新日志文本区域"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
    
    def process_queue(self):
        """处理结果队列中的消息"""
        try:
            while True:
                try:
                    result = self.result_queue.get_nowait()
                except queue.Empty:
                    break
                
                status, message = result
                self._log_message(message)
                
                if status == "success":
                    self.status_var.set(message)
                    messagebox.showinfo("成功", message)
                elif status == "error":
                    self.status_var.set(f"错误: {message}")
                    self._download_complete()
                    messagebox.showerror("错误", message)
        finally:
            self.root.after(100, self.process_queue)

def main():
    root = tk.Tk()
    app = YouTubeDownloaderApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()    
