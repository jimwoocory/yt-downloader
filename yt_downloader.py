import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
import subprocess
import os

yt_dlp_path = os.path.join(os.path.dirname(os.__file__), 'Scripts', 'yt-dlp.exe')
result = subprocess.run([yt_dlp_path, url, "-f", quality_choice, "-o", output_template], 
                        capture_output=True, text=True)
def download():
    url = url_entry.get()
    format_choice = format_var.get()
    # Use 'bestvideo+bestaudio/best' for highest quality available
    best_quality_format = 'bestvideo+bestaudio/best'
    
    if url:
        output_template = "./downloads/%(title)s.%(ext)s"
        try:
            messagebox.showinfo("Download started", f"Downloading {url} as {format_choice}")
            # Command options based on format selection
            if format_choice == 'Video':
                ydl_opts = ["yt-dlp", url, "-f", best_quality_format, "-o", output_template]
            else:  # format_choice == 'Audio'
                ydl_opts = ["yt-dlp", url, "-x", "--audio-format", "mp3", "-o", output_template]

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
format_var = tk.StringVar(value='Video')
format_choices = ['Video', 'Audio']
format_dropdown = ttk.Combobox(root, textvariable=format_var, values=format_choices)
format_dropdown.pack()

download_button = tk.Button(root, text="Download", command=download)
download_button.pack()

root.mainloop()
