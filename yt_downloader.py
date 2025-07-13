import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
import subprocess

def download():
    url = url_entry.get()
    format_choice = format_var.get()
    quality_choice = quality_var.get()

    if url:
        output_template = f"./downloads/%(title)s.%(ext)s"
        ydl_opts = ["yt-dlp", url, "-f", quality_choice, "-o", output_template]

        try:
            messagebox.showinfo("Download started", f"Downloading {url} as {format_choice}")
            result = subprocess.run(ydl_opts, capture_output=True, text=True)
            messagebox.showinfo("Download complete", result.stdout)
        except Exception as e:
            messagebox.showerror("Error", f"Error downloading: {e}")
    else:
        messagebox.showwarning("Input Error", "Please enter a valid URL")

root = tk.Tk()
root.title("YouTube Downloader")

tk.Label(root, text="YouTube URL:").pack()

url_entry = tk.Entry(root, width=50)
url_entry.pack()

tk.Label(root, text="Choose Format:").pack()
format_var = tk.StringVar(value='bestvideo+bestaudio')
formats = {
    'Video MP4': 'bestvideo+bestaudio', 
    'Audio MP3': 'bestaudio/best[ext=m4a]'
}
format_dropdown = ttk.Combobox(root, textvariable=format_var, values=list(formats.keys()))
format_dropdown.pack()

tk.Label(root, text="Choose Quality:").pack()
quality_var = tk.StringVar(value='best')
qualities = ['best[height<=1080]', 'best[height<=720]', 'worstaudio']
quality_dropdown = ttk.Combobox(root, textvariable=quality_var, values=qualities)
quality_dropdown.pack()

download_button = tk.Button(root, text="Download", command=download)
download_button.pack()

root.mainloop()
