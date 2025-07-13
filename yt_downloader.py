import tkinter as tk
def on_query():
    url = entry_url.get().strip()
    if not url:
        messagebox.showwarning("Warning", "请输入视频链接")
        return
    result = query_formats(url)
    messagebox.showinfo("可用格式", result)

def on_download_video():
    url = entry_url.get().strip()
    format_id = format_var.get().strip() if format_var.get() != "" else None
    try:
        size_limit = int(size_var.get()) if size_var.get().isdigit() else None
    except:
        size_limit = None

    if not url:
        messagebox.showwarning("Warning", "请输入视频链接")
        return
    try:
        download_video(url, format_id, size_limit)
        messagebox.showinfo("成功", "视频下载完成")
    except Exception as e:
        messagebox.showerror("错误", "下载视频时出错:\n" + str(e))

def on_download_audio():
    url = entry_url.get().strip()
    format_id = format_var.get().strip() if format_var.get() != "" else None
    try:
        size_limit = int(size_var.get()) if size_var.get().isdigit() else None
    except:
        size_limit = None

    if not url:
        messagebox.showwarning("Warning", "请输入视频链接")
        return
    try:
        download_audio(url, format_id, size_limit)
        messagebox.showinfo("成功", "音频下载完成")
    except Exception as e:
        messagebox.showerror("错误", "下载音频时出错:\n" + str(e))

# 创建界面控件
tk.Label(root, text="输入 YouTube 链接:").pack(pady=10)
entry_url = tk.Entry(root, width=60)
entry_url.pack(pady=5)

tk.Label(root, text="选择视频格式 (可选):").pack(pady=5)
format_var = tk.StringVar()
tk.OptionMenu(root, format_var, 'best', 'worst', 'bestvideo', 'worstvideo').pack(pady=5)

tk.Label(root, text="设置文件大小限制 (MB, 可选):").pack(pady=5)
size_var = tk.StringVar()
tk.OptionMenu(root, size_var, '50', '100', '200', '500').pack(pady=5)

tk.Button(root, text="查询格式", command=on_query).pack(pady=5)
tk.Button(root, text="下载视频", command=on_download_video).pack(pady=5)
tk.Button(root, text="下载音频(MP3)", command=on_download_audio).pack(pady=5)

root.mainloop()
