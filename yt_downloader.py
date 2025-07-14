import yt_dlp
import sys
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox

def query_formats(url, proxy=None):
    """查询视频的所有可用格式"""
    ydl_opts = {
        'socket_timeout': 10,
        'proxy': proxy,
    }
    formats_info = ""
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=False)
        formats = info_dict.get('formats', [info_dict])
        formats_info += f"\nAvailable formats for: {info_dict.get('title')}\n"
        for f in formats:
            formats_info += f"Format ID: {f['format_id']}, Ext: {f['ext']}, Resolution: {f.get('resolution', 'N/A')}, ACodec: {f.get('acodec')}, VCodec: {f.get('vcodec')}, Filesize: {f.get('filesize')}\n"
    return formats_info

def download_video(url, format_id=None, proxy=None):
    """下载视频"""
    ydl_opts = {
        'socket_timeout': 10,
        'proxy': proxy,
        'format': format_id if format_id else 'best',
        'outtmpl': '%(title)s.%(ext)s'
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

def download_audio(url, proxy=None):
    """下载音频 (mp3)"""
    ydl_opts = {
        'socket_timeout': 10,
        'proxy': proxy,
        'format': 'bestaudio/best',
        'outtmpl': '%(title)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

def run_gui():
    root = tk.Tk()
    root.title("YouTube Downloader")
    root.geometry("500x300")

    def on_query():
        proxy = entry_proxy.get().strip() or None
        url = entry_url.get()
        if not url:
            messagebox.showwarning("Warning", "请输入视频链接")
            return
        result = query_formats(url, proxy)
        messagebox.showinfo("可用格式", result)

    def on_download_video():
        proxy = entry_proxy.get().strip() or None
        url = entry_url.get()
        fmt = simpledialog.askstring("格式ID", "请输入Format ID（可留空自动选择最佳）")
        try:
            download_video(url, fmt, proxy)
            messagebox.showinfo("成功", "视频下载完成")
        except Exception as e:
            if 'yt_dlp.utils.DownloadError' in str(type(e)) or 'Network' in str(e) or '403' in str(e):
                messagebox.showerror("网络错误", "连接 YouTube 失败，可能是网络限制或无代理所致。")
                return
            messagebox.showerror("错误", str(e))

    def on_download_audio():
        proxy = entry_proxy.get().strip() or None
        url = entry_url.get()
        try:
            download_audio(url, proxy)
            messagebox.showinfo("成功", "音频下载完成")
        except Exception as e:
            if 'yt_dlp.utils.DownloadError' in str(type(e)) or 'Network' in str(e) or '403' in str(e):
                messagebox.showerror("网络错误", "连接 YouTube 失败，可能是网络限制或无代理所致。")
                return
            messagebox.showerror("错误", str(e))

    tk.Label(root, text="输入代理地址 (可选):").pack(pady=5)
    entry_proxy = tk.Entry(root, width=60)
    entry_proxy.insert(0, 'http://127.0.0.1:7890')
    entry_proxy.pack(pady=5)

    tk.Label(root, text="输入YouTube链接:").pack(pady=10)
    entry_url = tk.Entry(root, width=60)
    entry_url.pack(pady=5)

    tk.Button(root, text="查询格式", command=on_query).pack(pady=5)
    tk.Button(root, text="下载视频", command=on_download_video).pack(pady=5)
    tk.Button(root, text="下载音频(MP3)", command=on_download_audio).pack(pady=5)

    root.mainloop()

def main():
    if len(sys.argv) == 1:
        run_gui()
    elif len(sys.argv) >= 3:
        command = sys.argv[1]
        url = sys.argv[2]
        proxy = sys.argv[3] if len(sys.argv) > 3 else None

        if command == "query":
            print(query_formats(url, proxy))
        elif command == "video":
            format_id = sys.argv[4] if len(sys.argv) > 4 else None
            download_video(url, format_id, proxy)
        elif command == "audio":
            download_audio(url, proxy)
        else:
            print("Invalid command. Use 'query', 'video', or 'audio'.")
    else:
        print("Usage:")
        print("  python yt_downloader.py query <url> [proxy]")
        print("  python yt_downloader.py video <url> [proxy] [format_id]")
        print("  python yt_downloader.py audio <url> [proxy]")

if __name__ == '__main__':
    main()
