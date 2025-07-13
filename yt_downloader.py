import yt_dlp
import sys
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox

def query_formats(url):
    """查询视频的所有可用格式"""
    ydl_opts = {}
    formats_info = ""
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=False)
        formats = info_dict.get('formats', [info_dict])
        formats_info += f"\nAvailable formats for: {info_dict.get('title')}\n"
        for f in formats:
            formats_info += f"Format ID: {f['format_id']}, Ext: {f['ext']}, Resolution: {f.get('resolution', 'N/A')}, ACodec: {f.get('acodec')}, VCodec: {f.get('vcodec')}, Filesize: {f.get('filesize')}\n"
    return formats_info

def download_video(url, format_id=None):
    """下载视频"""
    ydl_opts = {
        'format': format_id if format_id else 'best',
        'outtmpl': '%(title)s.%(ext)s'
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

def download_audio(url):
    """下载音频 (mp3)"""
    ydl_opts = {
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
        url = entry_url.get()
        if not url:
            messagebox.showwarning("Warning", "请输入视频链接")
            return
        result = query_formats(url)
        messagebox.showinfo("可用格式", result)

    def on_download_video():
        url = entry_url.get()
        fmt = simpledialog.askstring("格式ID", "请输入Format ID（可留空自动选择最佳）")
        try:
            download_video(url, fmt)
            messagebox.showinfo("成功", "视频下载完成")
        except Exception as e:
            messagebox.showerror("错误", str(e))

    def on_download_audio():
        url = entry_url.get()
        try:
            download_audio(url)
            messagebox.showinfo("成功", "音频下载完成")
        except Exception as e:
            messagebox.showerror("错误", str(e))

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

        if command == "query":
            print(query_formats(url))
        elif command == "video":
            format_id = sys.argv[3] if len(sys.argv) > 3 else None
            download_video(url, format_id)
        elif command == "audio":
            download_audio(url)
        else:
            print("Invalid command. Use 'query', 'video', or 'audio'.")
    else:
        print("Usage:")
        print("  python yt_downloader.py query <url>")
        print("  python yt_downloader.py video <url> [format_id]")
        print("  python yt_downloader.py audio <url>")

if __name__ == '__main__':
    main()
