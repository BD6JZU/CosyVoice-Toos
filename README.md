# 🎙️ Voice Enrollment System (声纹采集系统)

基于 Python 和 PyQt5 开发的桌面端声纹采集与录入工具。

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![PyQt5](https://img.shields.io/badge/GUI-PyQt5-green)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Mac%20%7C%20Linux-lightgrey)

## 📖 项目简介

本项目是一个用于 **[声纹识别 / 语音采集]** 的客户端应用。它提供了一个用户友好的图形界面，允许用户进行录音、回放，并将音频数据（或声纹特征）上传至服务器/保存到本地。

主要用于辅助声纹识别系统的注册（Enrollment）阶段。

## ✨ 主要功能

*   **图形化界面**：使用 PyQt5 构建，界面简洁，操作直观。
*   **高清屏适配**：支持 Windows 高分屏缩放（High DPI Scaling），在 2K/4K 屏幕下显示清晰。
*   **音频录制**：支持实时语音录制与停止。
*   **状态反馈**：实时显示录音状态及处理进度。
*   **独立运行**：支持通过 PyInstaller 打包为独立 `.exe` 文件，无需安装 Python 环境即可运行。

## 🛠️ 技术栈

*   **编程语言**: Python 3.x
*   **GUI 框架**: PyQt5
*   **音频处理**: (此处填写你用的库，如 PyAudio / SoundDevice / Librosa)
*   **网络请求**: (如有，填写 requests / httpx)
*   **打包工具**: PyInstaller

## 🚀 快速开始

### 1. 环境要求

确保你的电脑上安装了 Python 3.8 或以上版本。

### 2. 克隆项目

```bash
git clone https://github.com/你的用户名/你的仓库名.git
cd 你的仓库名
```

### 3. 安装依赖

建议使用虚拟环境：

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境 (Windows)
venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

> **注意**: 如果还没有 `requirements.txt`，可以通过 `pip freeze > requirements.txt` 生成。

### 4. 运行程序

```bash
python main.py
```

*(注：请将 `main.py` 替换为你实际的主程序文件名)*

## 📦 打包指南 (Build)

本项目支持使用 `PyInstaller` 打包为独立的可执行文件（.exe）。

1.  安装 PyInstaller：
    ```bash
    pip install pyinstaller
    ```

2.  执行打包命令：
    ```bash
    # 单文件打包模式 (推荐)
    pyinstaller -F -w main.py

    ```

3.  **产物说明**：
    *   打包完成后，可执行文件位于 `dist/` 目录下。
    *   `build/` 目录为临时构建文件，可以安全删除。

## ⚠️ 常见问题

**Q: 在 4K 屏幕上界面字体太小或模糊？**
A: 本程序已内置高分屏适配代码。如果仍有问题，请尝试在系统设置中调整缩放比例，或检查 PyQt5 版本是否为最新。

```python
# 核心适配代码
if hasattr(Qt, 'AA_EnableHighDpiScaling'):
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
```

## 🤝 贡献与反馈

欢迎提交 Issue 或 Pull Request 来完善这个项目！

1.  Fork 本仓库
2.  新建 Feat_xxx 分支
3.  提交代码
4.  新建 Pull Request