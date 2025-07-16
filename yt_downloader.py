# 原代码...

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

# 后续代码保持不变...    
