import yt_dlp
import sys
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
import logging
import queue
from urllib.parse import urlparse

class YouTubeDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("YouTube 下载器")
        self.root.geometry("900x600")
        self.root.minsize(800, 500)
        
        # 设置中文字体支持
        self.style = ttk.Style()
        self.style.configure('TLabel', font=('SimHei', 10))
        self.style.configure('TButton', font=('SimHei', 10))
        self.style.configure('TEntry', font=('SimHei', 10))
        self.style.configure('TCombobox', font=('SimHei', 10))
        
        # 创建下载任务队列和结果队列
        self.download_queue = queue.Queue()
        self.result_queue = queue.Queue()
        
        # 配置日志
        self.setup_logging()
        
        # 创建界面
        self.create_widgets()
        
        # 启动队列处理线程
        self.processing_thread = threading.Thread(target=self.process_queue, daemon=True)
        self.processing_thread.start()
        
        # 启动结果处理
        self.root.after(100, self.process_results)
    
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
        
        ttk.Label(url_frame, text="代理地址 (可选):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.proxy_entry = ttk.Entry(url_frame, width=60)
        self.proxy_entry.grid(row=1, column=1, sticky=tk.W, pady=5, padx=5)
        self.proxy_entry.insert(0, "http://127.0.0.1:7890")
        
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
        self.format_var = tk.StringVar(value="best")
        format_frame = ttk.Frame(options_frame)
        format_frame.grid(row=1, column=1, sticky=tk.W, pady=5)
        
        ttk.Radiobutton(format_frame, text="最佳质量", variable=self.format_var, value="best").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(format_frame, text="仅音频 (MP3)", variable=self.format_var, value="audio").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(format_frame, text="自定义格式", variable=self.format_var, value="custom").pack(side=tk.LEFT, padx=5)
        
        self.custom_format_entry = ttk.Entry(format_frame, width=10)
        self.custom_format_entry.pack(side=tk.LEFT, padx=(5, 0))
        self.custom_format_entry.insert(0, "format_id")
        self.custom_format_entry.config(state=tk.DISABLED)
        
        self.format_var.trace_add("write", self.on_format_change)
        
        # 按钮
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="查询格式", command=self.query_formats, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="开始下载", command=self.start_download, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="清空日志", command=self.clear_logs, width=15).pack(side=tk.LEFT, padx=5)
        
        # 下载进度和日志
        log_frame = ttk.LabelFrame(main_frame, text="下载日志", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 创建一个带有垂直滚动条的文本区域
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=10)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.config(state=tk.DISABLED)
        
        # 配置文本标签样式
        self.log_text.tag_configure("error", foreground="red")
        self.log_text.tag_configure("success", foreground="green")
        self.log_text.tag_configure("info", foreground="black")
        self.log_text.tag_configure("progress", foreground="blue")
    
    def on_format_change(self, *args):
        """格式选择变更时的处理函数"""
        if self.format_var.get() == "custom":
            self.custom_format_entry.config(state=tk.NORMAL)
        else:
            self.custom_format_entry.config(state=tk.DISABLED)
    
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
        url = self.url_entry.get().strip()
        proxy = self.proxy_entry.get().strip() or None
        save_path = self.save_path_var.get()
        format_choice = self.format_var.get()
        
        if not self.validate_url(url):
            messagebox.showerror("错误", "请输入有效的 YouTube 链接")
            return
        
        if format_choice == "custom":
            format_id = self.custom_format_entry.get().strip()
            if not format_id:
                messagebox.showerror("错误", "自定义格式不能为空")
                return
        else:
            format_id = "best" if format_choice == "best" else "bestaudio/best"
        
        self.logger.info(f"开始下载: {url}")
        self.download_queue.put(("download", url, proxy, save_path, format_id, format_choice))
    
    def process_queue(self):
        """处理下载队列"""
        while True:
            try:
                task = self.download_queue.get(timeout=1)
                if task[0] == "query":
                    self._query_formats(task[1], task[2])
                elif task[0] == "download":
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
            self.root.after(0, lambda: messagebox.showinfo("可用格式", formats_info))
        except Exception as e:
            self.result_queue.put(("error", f"查询格式失败: {str(e)}"))
    
    def _download(self, url, proxy, save_path, format_id, format_choice):
        """下载视频或音频的实际处理函数"""
        try:
            ydl_opts = {
                'socket_timeout': 10,
                'proxy': proxy,
                'format': format_id,
                'outtmpl': f"{save_path}/%(title)s.%(ext)s",
                'progress_hooks': [self.download_hook],
                'quiet': True,
                'no_warnings': True,
                'logger': self.logger  # 将yt-dlp的日志输出到我们的日志系统
            }
            
            if format_choice == "audio":
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                self.logger.info(f"开始下载到: {save_path}")
                info_dict = ydl.extract_info(url, download=True)
                self.result_queue.put(("success", f"下载完成: {info_dict.get('title')}"))
        
        except Exception as e:
            self.result_queue.put(("error", f"下载失败: {str(e)}"))
    
    def download_hook(self, d):
        """下载进度回调函数"""
        if d['status'] == 'downloading':
            percent = d.get('_percent_str', '?')
            speed = d.get('_speed_str', '?')
            eta = d.get('_eta_str', '?')
            self.result_queue.put(("progress", f"下载中: {percent} 速度: {speed} 剩余时间: {eta}"))
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
                    messagebox.showerror("错误", result[1])
                elif result[0] == "success":
                    self._append_log(f"成功: {result[1]}", "success")
                    messagebox.showinfo("成功", result[1])
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
    if len(sys.argv) == 1:
        root = tk.Tk()
        app = YouTubeDownloaderApp(root)
        root.mainloop()
    else:
        # 保留命令行模式
        print("命令行模式暂不支持，请直接运行程序")

if __name__ == '__main__':
    main()    
