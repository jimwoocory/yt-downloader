import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
from tkinter import filedialog
import subprocess
import os

def select_output_folder():
    folder_selected = filedialog.askdirectory()
    output_folder_var.set(folder_selected)
    # Update label displaying selected path
    output_folder_label.config(text=f"Selected Folder: {folder_selected}")

def download():
    url = url_entry.get()
    format_choice = format_var.get()
    output_folder = output_folder_var.get()
    best_quality_format = 'bestvideo+bestaudio/best'
    
    if not url:
        messagebox.showwarning("Input Error", "Please enter a valid URL")
        return
    
    if not output_folder:
        messagebox.showwarning("Path Error", "Please select a valid download folder")
        return
    
    # Create output template with user-selected folder
    output_template = os.path.join(output_folder, "%(title)s.%(ext)s")
    
    try:
        messagebox.showinfo("Download started", f"Downloading {url} as {format_choice} to {output_folder}")
        
        if format_choice == 'Video':
            ydl_opts = ["yt-dlp", url, "-f", best_quality_format, "-o", output_template]
        else:  # format_choice == 'Audio'
            ydl_opts = ["yt-dlp", url, "-x", "--audio-format", "mp3", "-o", output_template]

        result = subprocess.run(ydl_opts, capture_output=True, text=True)
        
        if result.returncode == 0:
            messagebox.showinfo("Download complete", "Download successful!")
        else:
            messagebox.showerror("Error", f"Error downloading: {result.stderr}")
    except Exception as e:
        messagebox.showerror("Error", f"Error downloading: {e}")

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

# Output folder selection
tk.Label(root, text="Select Output Folder:").pack()
output_folder_var = tk.StringVar()
output_folder_button = tk.Button(root, text="Select Folder", command=select_output_folder)
output_folder_button.pack()

output_folder_label = tk.Label(root, text="Selected Folder: None")
output_folder_label.pack()

download_button = tk.Button(root, text="Download", command=download)
download_button.pack()

root.mainloop()
