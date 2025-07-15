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

class YouTubeDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("YouTube 下载器")
        self.root.geometry("900x700")  # 增加窗口高度以容纳新组件
        self.root.minsize(800, 600)
        
        # 设置中文字体支持
        self.style = ttk.Style()
        self.style.configure('TLabel', font=('SimHei', 10))
        self.style.configure('TButton', font=('SimHei', 10))
        self.style.configure('TEntry', font=('SimHei', 10))
        self.style.configure('TCombobox', font=('SimHei', 10))
        
        # 创建下载任务队列和结果队列
        self.download_queue = queue.Queue()
        self.result_queue = queue.Queue()
        
        # 下载任务列表
        self.download_tasks = []
        
        # 配置日志
        self.setup_logging()
        
        # 创建界面
        self.create_widgets()
        
        # 启动队列处理线程
        self.processing_thread = threading.Thread(target=self.process_queue, daemon=True)
        self.processing_thread.start()
        
        # 启动结果处理
        self.root.after(100, self.process_results)
        
        # 用于终止下载的变量
        self.ydl_instance = None
        self.is_downloading = False
    
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
        
        # 批量下载支持
        ttk.Label(url_frame, text="或批量输入URLs (每行一个):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.urls_text = scrolledtext.ScrolledText(url_frame, wrap=tk.WORD, height=3)
        self.urls_text.grid(row=1, column=1, sticky=tk.W, pady=5, padx=5)
        
        ttk.Label(url_frame, text="代理地址 (可选):").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.proxy_entry = ttk.Entry(url_frame, width=60)
        self.proxy_entry.grid(row=2, column=1, sticky=tk.W, pady=5, padx=5)
        self.proxy_entry.insert(0, "http://127.0.0.1:7897")
        
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
        
        # 下载格式
        ttk.Label(options_frame, text="下载格式:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.format_var = tk.StringVar(value="custom")
        format_frame = ttk.Frame(options_frame)
        format_frame.grid(row=1, column=1, sticky=tk.W, pady=5)
        
        ttk.Radiobutton(format_frame, text="视频或音频（MP3）", variable=self.format_var, value="custom").pack(side=tk.LEFT, padx=5)
        
        self.custom_format_entry = ttk.Entry(format_frame, width=10)
        self.custom_format_entry.pack(side=tk.LEFT, padx=(5, 0))
        self.custom_format_entry.insert(0, "ID号")
        self.custom_format_entry.config(state=tk.NORMAL)
        
        # 字幕选项
        self.subtitle_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="下载字幕", variable=self.subtitle_var).grid(row=2, column=1, sticky=tk.W, pady=5)
        
        # 按钮
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="查询格式", command=self.query_formats, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="开始下载", command=self.start_download, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="终止下载", command=self.stop_download, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="清空日志", command=self.clear_logs, width=15).pack(side=tk.LEFT, padx=5)
        
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
    
    def query_formats(self):
        """查询视频格式"""
        url = self.url_entry.get().strip()
        proxy = self.proxy_entry.get().strip() or None
        
        if not self.validate_url(url):
            messagebox.showerror("错误", "请输入有效的 YouTube 链接")
            return
            
        self.logger.info(f"查询视频格式: {url}")
        self.download_queue.put(("query", url, proxy))
    
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
        format_id = self.custom_format_entry.get().strip()
        download_subtitles = self.subtitle_var.get()
        
        if not format_id:
            messagebox.showerror("错误", "ID号不能为空")
            return
        
        # 准备下载任务
        self.download_tasks = urls.copy()
        self.current_task_index = 0
        self.total_tasks = len(urls)
        self.update_progress(0, "准备下载...")
        
        for url in urls:
            self.logger.info(f"添加下载任务: {url}")
            self.download_queue.put(("download", url, proxy, save_path, format_id, download_subtitles))
    
    def stop_download(self):
        """终止正在进行的下载"""
        if not self.is_downloading:
            messagebox.showinfo("提示", "当前没有正在进行的下载")
            return
            
        if self.ydl_instance:
            self.logger.info("正在终止下载...")
            self.ydl_instance._download_retcode = -1  # 设置退出码强制终止
            self.ydl_instance = None
            self.is_downloading = False
            self.update_progress(0, "下载已终止")
            self.logger.info("下载已终止")
    
    def update_progress(self, percent, message):
        """更新进度条和进度信息"""
        self.progress_var.set(percent)
        self.progress_label.config(text=message)
    
    def process_queue(self):
        """处理下载队列"""
        while True:
            try:
                task = self.download_queue.get(timeout=1)
                if task[0] == "query":
                    self._query_formats(task[1], task[2])
                elif task[0] == "download":
                    self.current_task_index += 1
                    self.update_progress(
                        (self.current_task_index-1) / self.total_tasks * 100, 
                        f"准备下载 {self.current_task_index}/{self.total_tasks}"
                    )
                    self._download(task[1], task[2], task[3], task[4], task[5])
                self.download_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"处理任务时出错: {str(e)}")
    
    def _query_formats(self, url, proxy):
        """查询视频格式的实际处理函数"""
        try:
            ydl_opts = {
                'socket_timeout': 10,
                'proxy': proxy,
                'quiet': True
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                self.logger.info("正在获取视频信息...")
                info_dict = ydl.extract_info(url, download=False)
                formats = info_dict.get('formats', [info_dict])
                
                formats_info = f"\n可用格式 for: {info_dict.get('title')}\n"
                for f in formats:
                    format_id = f['format_id']
                    ext = f['ext']
                    resolution = f.get('resolution', 'N/A')
                    acodec = f.get('acodec', 'N/A')
                    vcodec = f.get('vcodec', 'N/A')
                    filesize = f.get('filesize', 'N/A')
                    
                    formats_info += f"ID: {format_id}, 格式: {ext}, 分辨率: {resolution}, 音频: {acodec}, 视频: {vcodec}, 大小: {filesize}\n"
            
            self.result_queue.put(("info", formats_info))
        except Exception as e:
            self.result_queue.put(("error", f"查询格式失败: {str(e)}"))
    
    def _download(self, url, proxy, save_path, format_id, download_subtitles):
        """下载视频或音频的实际处理函数"""
        self.is_downloading = True
        
        try:
            # 检查是否需要提取音频
            is_audio = format_id.lower().startswith('audio')
            
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
                'subtitleslangs': ['en', 'zh-Hans', 'zh-Hant']  # 下载多种语言字幕
            }
            
            if is_audio:
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
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
            
            if self.is_downloading:  # 确保下载没有被用户终止
                self.result_queue.put(("success", f"下载完成: {info_dict.get('title')}"))
                self.update_progress(
                    self.current_task_index / self.total_tasks * 100, 
                    f"完成 {self.current_task_index}/{self.total_tasks}"
                )
            else:
                self.result_queue.put(("info", f"下载已取消: {info_dict.get('title')}"))
        
        except Exception as e:
            if 'yt_dlp.utils.DownloadError' in str(type(e)) or 'Network' in str(e) or '403' in str(e):
                self.result_queue.put(("error", "连接 YouTube 失败，可能是网络限制或无代理所致。"))
            else:
                self.result_queue.put(("error", f"下载失败: {str(e)}"))
        finally:
            self.is_downloading = False
            self.ydl_instance = None
    
    def download_hook(self, d):
        """下载进度回调函数"""
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
