#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube下载器打包脚本
自动安装依赖并打包为可执行文件
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def run_command(cmd, description=""):
    """运行命令并显示进度"""
    print(f"\n{'='*60}")
    print(f"🔄 {description}")
    print(f"{'='*60}")
    print(f"执行命令: {cmd}")
    
    try:
        result = subprocess.run(cmd, shell=True, check=True, 
                              capture_output=True, text=True, encoding='utf-8')
        if result.stdout:
            print("✅ 输出:")
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 错误: {e}")
        if e.stdout:
            print("标准输出:", e.stdout)
        if e.stderr:
            print("错误输出:", e.stderr)
        return False

def check_python():
    """检查Python版本"""
    version = sys.version_info
    print(f"🐍 Python版本: {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ 需要Python 3.8或更高版本")
        return False
    
    print("✅ Python版本符合要求")
    return True

def install_dependencies():
    """安装依赖"""
    print("\n📦 安装依赖包...")
    
    # 升级pip
    if not run_command(f"{sys.executable} -m pip install --upgrade pip", "升级pip"):
        print("⚠️ pip升级失败，继续安装依赖...")
    
    # 安装基础依赖
    dependencies = [
        "yt-dlp>=2025.12.8",
        "requests>=2.31.0",
        "pyinstaller>=6.0.0"
    ]
    
    for dep in dependencies:
        if not run_command(f"{sys.executable} -m pip install {dep}", f"安装 {dep}"):
            print(f"❌ 安装 {dep} 失败")
            return False
    
    print("✅ 所有依赖安装完成")
    return True

def create_spec_file():
    """创建PyInstaller规格文件"""
    spec_content = '''# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['youtube_downloader.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'yt_dlp',
        'yt_dlp.extractor',
        'yt_dlp.downloader',
        'requests',
        'urllib3',
        'certifi',
        'charset_normalizer',
        'idna',
        'websockets',
        'brotli',
        'mutagen',
        'pycryptodomex',
        'tkinter',
        'tkinter.ttk',
        'tkinter.scrolledtext',
        'tkinter.filedialog',
        'tkinter.messagebox'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='YouTube_Downloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
    version_file=None
)
'''
    
    with open('youtube_downloader.spec', 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
    print("✅ PyInstaller规格文件创建完成")

def build_executable():
    """构建可执行文件"""
    print("\n🔨 开始构建可执行文件...")
    
    # 创建规格文件
    create_spec_file()
    
    # 定义输出目录
    releases_dir = Path("releases")
    dist_dir = releases_dir / "dist"
    
    # 创建目录
    releases_dir.mkdir(exist_ok=True)
    dist_dir.mkdir(exist_ok=True)
    
    # 清理之前的构建
    build_folder = Path("build")
    if build_folder.exists():
        print(f"🗑️ 清理旧的 {build_folder} 文件夹")
        shutil.rmtree(build_folder)
    
    if dist_dir.exists():
        print(f"🗑️ 清理旧的 {dist_dir} 文件夹")
        shutil.rmtree(dist_dir)
    
    # 构建
    cmd = f"{sys.executable} -m PyInstaller youtube_downloader.spec --clean --noconfirm --distpath {dist_dir}"
    
    if not run_command(cmd, "构建可执行文件"):
        print("❌ 构建失败")
        return False
    
    # 检查输出文件
    exe_path = dist_dir / "YouTube_Downloader.exe"
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"✅ 构建成功!")
        print(f"📁 输出文件: {exe_path.absolute()}")
        print(f"📏 文件大小: {size_mb:.1f} MB")
        return True
    else:
        print("❌ 未找到输出文件")
        return False

def create_portable_package():
    """创建便携版包"""
    print("\n📦 创建便携版包...")
    
    package_dir = Path("YouTube_Downloader_Portable")
    
    # 创建包目录
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir()
    
    # 复制可执行文件
    exe_source = Path("releases/dist/YouTube_Downloader.exe")
    if exe_source.exists():
        shutil.copy2(exe_source, package_dir / "YouTube_Downloader.exe")
    
    # 创建说明文件
    readme_content = """# YouTube 下载器 V1

## 🎬 功能特性

✅ **完整YouTube支持**
- 支持普通YouTube视频链接
- 支持YouTube Music链接
- 支持播放列表

✅ **完整下载功能**
- 格式查询和选择
- 批量下载支持
- 字幕下载
- 多线程下载
- 转码功能

✅ **用户体验**
- 现代化界面设计
- 下载历史记录
- 详细进度显示
- 智能错误诊断

## 🚀 使用方法

1. **启动程序**: 双击 `YouTube_Downloader.exe`

2. **输入链接**: 
   - 单个链接: 在顶部输入框粘贴YouTube链接
   - 批量链接: 在批量输入框中每行一个链接

3. **网络设置**:
   - 输入代理地址 (如: http://127.0.0.1:7897) 或留空使用直连

4. **获取信息**: 点击"获取信息"查看视频详情

5. **选择格式**: 点击"查询格式"选择下载质量

6. **开始下载**: 配置保存路径后点击"开始下载"

## 🔧 网络配置

### 代理设置
- 如果使用代理软件 (如Clash、V2Ray等)，请输入正确的代理地址
- 通常是 http://127.0.0.1:7897

### 直连模式
- 如果网络可以直接访问YouTube，留空代理地址即可

## 📋 格式说明

### 推荐格式
- `bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best`: 最佳视频+最佳音频 (推荐)
- `best`: 最高质量单文件
- `worst`: 最低质量 (节省空间)

### 自定义格式
- 点击"查询格式"查看所有可用格式
- 双击选择或使用推荐格式
- 支持组合格式 (如: `137+140`)

## 🛠️ 故障排除

### 网络连接问题
1. 检查代理软件是否运行
2. 尝试切换直连/代理模式
3. 检查防火墙设置

### 下载失败
1. 检查保存路径权限
2. 确保磁盘空间充足
3. 尝试不同的格式ID

### 链接无效
1. 确保链接完整且有效
2. 尝试在浏览器中打开链接验证

## 📞 技术支持

如遇问题，请查看程序内的运行日志获取详细错误信息。

---
YouTube 下载器 V1
支持YouTube视频和音乐下载
"""
    
    with open(package_dir / "README.md", 'w', encoding='utf-8') as f:
        f.write(readme_content)
    
    # 创建启动脚本
    batch_content = """@echo off
chcp 65001 >nul
title YouTube 下载器 V1
echo.
echo ========================================
echo    YouTube 下载器 V1
echo ========================================
echo.
echo 正在启动程序...
echo.
start "" "YouTube_Downloader.exe"
"""
    
    with open(package_dir / "启动程序.bat", 'w', encoding='gbk') as f:
        f.write(batch_content)
    
    print(f"✅ 便携版包创建完成: {package_dir.absolute()}")
    return True

def main():
    """主函数"""
    print("🚀 YouTube下载器打包工具")
    print("=" * 60)
    
    # 检查Python版本
    if not check_python():
        input("按回车键退出...")
        return
    
    # 检查源文件
    if not os.path.exists('youtube_downloader.py'):
        print("❌ 未找到源文件 youtube_downloader.py")
        input("按回车键退出...")
        return
    
    print("✅ 源文件检查通过")
    
    # 安装依赖
    if not install_dependencies():
        print("❌ 依赖安装失败")
        input("按回车键退出...")
        return
    
    # 构建可执行文件
    if not build_executable():
        print("❌ 构建失败")
        input("按回车键退出...")
        return
    
    # 创建便携版包
    if not create_portable_package():
        print("❌ 便携版包创建失败")
        input("按回车键退出...")
        return
    
    print("\n" + "=" * 60)
    print("🎉 打包完成!")
    print("=" * 60)
    print("📁 输出文件:")
    print("   • releases/dist/YouTube_Downloader.exe (单文件)")
    print("   • YouTube_Downloader_Portable/ (便携版)")
    print("\n💡 使用说明:")
    print("   • 单文件版本: 直接运行 YouTube_Downloader.exe")
    print("   • 便携版: 解压后运行 启动程序.bat")
    print("\n✨ 功能特性:")
    print("   • 支持YouTube视频和音乐下载")
    print("   • 格式查询和选择")
    print("   • 批量下载支持")
    print("   • 下载历史记录")
    print("   • 多线程下载")
    
    input("\n按回车键退出...")

if __name__ == "__main__":
    main()
