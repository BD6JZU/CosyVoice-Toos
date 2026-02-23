import sys
import os
import time
import json
import threading
import dashscope
from dashscope.audio.tts_v2 import VoiceEnrollmentService, SpeechSynthesizer, AudioFormat
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QFormLayout, QLineEdit, QPushButton, QLabel, QFileDialog, 
                            QMessageBox, QGroupBox, QTableWidget, QTableWidgetItem, 
                            QHeaderView, QProgressBar, QComboBox, QTextEdit, QAbstractItemView,
                            QSpinBox, QDoubleSpinBox, QSlider)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor

# ===========================
# 样式表
# ===========================
STYLESHEET = """
QMainWindow { background-color: #f5f7fa; }
QGroupBox { border: 1px solid #e1e4e8; border-radius: 6px; margin-top: 10px; background-color: #ffffff; font-weight: bold; padding-top: 15px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #24292e; }
QLineEdit, QComboBox { border: 1px solid #d1d5da; border-radius: 4px; padding: 6px; }
QLineEdit:focus { border: 1px solid #0366d6; }
QPushButton { background-color: #0366d6; color: white; border: none; border-radius: 4px; padding: 6px 12px; font-weight: bold; }
QPushButton:hover { background-color: #0256b9; }
QPushButton:pressed { background-color: #024494; }
QPushButton#DeleteBtn { background-color: #d73a49; }
QPushButton#DeleteBtn:hover { background-color: #b92534; }
QPushButton#RefreshBtn { background-color: #2ea44f; }
QTableWidget { border: 1px solid #e1e4e8; selection-background-color: #f1f8ff; selection-color: #24292e; }
QTextEdit { background-color: #24292e; color: #e1e4e8; border-radius: 6px; font-family: Consolas; font-size: 12px; }
QProgressBar { border: 1px solid #e1e4e8; background-color: #ffffff; text-align: center; border-radius: 3px; color: black; }
QProgressBar::chunk { background-color: #2ea44f; border-radius: 3px; }
"""

# ===========================
# 1. 列表查询线程
# ===========================
class VoiceQueryThread(QThread):
    finished = pyqtSignal(list)
    log_signal = pyqtSignal(str)
    
    def __init__(self, api_key):
        super().__init__()
        self.api_key = api_key

    def run(self):
        try:
            dashscope.api_key = self.api_key
            service = VoiceEnrollmentService(api_key=self.api_key)
            
            all_voices = []
            page_index = 0  # 改回0（你的SDK分页从0开始）
            page_size = 50 
            
            self.log_signal.emit(f"正在拉取列表 (Page {page_index})...")
            
            while True:
                try:
                    resp = service.list_voices(page_index=page_index, page_size=page_size)
                except Exception as e:
                    self.log_signal.emit(f"API 调用异常: {str(e)}")
                    break

                current_page_voices = []
                # ========== 核心修复：优先处理列表格式 ==========
                # 情况1：resp直接是列表（你的SDK返回格式）
                if isinstance(resp, list):
                    current_page_voices = resp
                # 情况2：resp是DashScopeResponse对象（官方标准格式）
                elif hasattr(resp, 'output'):
                    output = resp.output
                    if isinstance(output, dict):
                        current_page_voices = output.get('voice_list', [])
                    elif hasattr(output, 'voice_list'):
                        current_page_voices = output.voice_list
                # 情况3：resp是字典（兼容其他格式）
                elif isinstance(resp, dict):
                    current_page_voices = resp.get('voice_list', [])

                self.log_signal.emit(f"Page {page_index} 获取到 {len(current_page_voices)} 条音色数据")
                
                if not current_page_voices:
                    if page_index == 0:  # 匹配你的分页起始值
                        self.log_signal.emit("提示: 第 0 页返回为空，账号下可能没有音色。")
                    break
                
                all_voices.extend(current_page_voices)
                
                if len(current_page_voices) < page_size:
                    break
                
                page_index += 1
                time.sleep(0.1)

            self.finished.emit(all_voices)
            
        except Exception as e:
            self.log_signal.emit(f"查询线程未知错误: {str(e)}")
            self.finished.emit([])

# ===========================
# 2. 语音合成线程
# ===========================
class SpeechSynthesisThread(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str)
    
    def __init__(self, api_key, text, output_path, voice_id, model, volume, speech_rate):
        super().__init__()
        self.api_key = api_key
        self.text = text
        self.output_path = output_path
        self.voice_id = voice_id
        self.model = model
        self.volume = volume
        self.speech_rate = speech_rate

    # [重要] 缩进修复：run 方法必须在 class 内部
    def run(self):
        try:
            # 1. 设置 API Key
            dashscope.api_key = self.api_key 
            self.progress.emit(10, f"初始化模型: {self.model}")
            
            # 2. 实例化 Synthesizer
            synthesizer = SpeechSynthesizer(
                model=self.model,
                voice=self.voice_id,
                format=AudioFormat.MP3_22050HZ_MONO_256KBPS,
                volume=self.volume,          
                speech_rate=self.speech_rate
            )
            
            self.progress.emit(40, "正在向阿里云发送请求...")
            
            # 3. 调用 API
            # 文档说明：call 方法直接返回二进制音频数据 (bytes)
            audio_data = synthesizer.call(self.text)
            
            self.progress.emit(80, "接收数据完成，正在保存...")

            # 4. 直接处理 bytes 数据
            if isinstance(audio_data, bytes) and len(audio_data) > 0:
                # 确保保存目录存在
                output_dir = os.path.dirname(self.output_path)
                if output_dir and not os.path.exists(output_dir):
                    os.makedirs(output_dir)
                
                # 写入文件
                with open(self.output_path, 'wb') as f:
                    f.write(audio_data)
                    
                self.progress.emit(100, "✅ 合成成功")
                self.finished.emit(True, self.output_path)
            
            # 处理可能的异常返回 (虽然通常会直接抛出异常)
            elif hasattr(audio_data, 'output'): 
                # 如果返回的是错误对象
                msg = getattr(audio_data.output, 'message', '未知错误')
                self.finished.emit(False, f"API 返回错误: {msg}")
            else:
                # 其他情况
                self.finished.emit(False, f"合成失败: 返回了非音频数据 ({type(audio_data)})")

        except Exception as e:
            # 捕获 SDK 抛出的所有错误（如 API Key 错误、欠费、网络超时等）
            error_msg = str(e)
            self.progress.emit(0, "❌ 发生错误")
            self.finished.emit(False, f"执行异常: {error_msg}")

# ===========================
# 3. 音色复刻线程
# ===========================
class VoiceEnrollmentThread(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str)
    
    def __init__(self, api_key, audio_url, voice_name, model):
        super().__init__()
        self.api_key = api_key
        self.audio_url = audio_url
        self.voice_name = voice_name
        self.model = model

    def run(self):
        try:
            # 确保 API Key 生效
            dashscope.api_key = self.api_key
            service = VoiceEnrollmentService(api_key=self.api_key)
            
            self.progress.emit(10, f"提交复刻任务 ({self.model})...")
            
            kwargs = {
                'target_model': self.model, 
                'prefix': self.voice_name,
                'url': self.audio_url
            }
            if 'v3' in self.model:
                kwargs['language_hints'] = ['zh']
                
            # 提交任务
            try:
                voice_id = service.create_voice(**kwargs)
            except Exception as e:
                self.finished.emit(False, f"提交任务失败: {str(e)}")
                return

            self.progress.emit(30, f"任务已提交，ID: {voice_id}")
            
            # 轮询状态
            max_retry = 120 
            retry_count = 0
            
            # [修改点] 完善状态映射表
            status_map = {
                "OK": "训练完成",
                "SUCCEEDED": "训练完成",
                "RUNNING": "训练中",
                "DEPLOYING": "模型部署中",  # 加上这个
                "FAILED": "训练失败",
                "UNDEPLOYED": "音频质量不达标",
                "UNKNOWN": "状态未知"
            }
            
            while retry_count < max_retry: 
                time.sleep(5)
                retry_count += 1
                try:
                    res = service.query_voice(voice_id=voice_id)
                    
                    # === 解析状态 ===
                    status = "UNKNOWN"
                    output = getattr(res, 'output', None)
                    if output:
                        if isinstance(output, dict):
                            status = output.get('status', 'UNKNOWN')
                        else:
                            status = getattr(output, 'status', 'UNKNOWN')
                    
                    if status == "UNKNOWN":
                        if isinstance(res, dict):
                            status = res.get('status', 'UNKNOWN')
                        else:
                            status = getattr(res, 'status', 'UNKNOWN')

                    # === [核心修改] 日志显示优化 ===
                    # 无论真实状态是 DEPLOYING 还是 RUNNING，都显示为 "RUNNING" 风格
                    display_status = "RUNNING" if status == "DEPLOYING" else status
                    status_desc = status_map.get(status, status)
                    
                    self.progress.emit(30 + int(retry_count/max_retry*40), 
                                      f"训练中 [{display_status}] - {status_desc}...")
                    
                    # 判断是否成功
                    if status == "OK" or status == "SUCCEEDED":
                        self.finished.emit(True, voice_id)
                        return
                    elif status in ["FAILED", "UNDEPLOYED"]:
                        self.finished.emit(False, f"复刻失败: {status}")
                        return
                    
                except Exception as e:
                    self.progress.emit(30 + retry_count, f"查询报错: {str(e)}，重试中...")
                    continue
                
            self.finished.emit(False, f"训练超时（{max_retry*5}秒），请稍后刷新列表查看")
        except Exception as e:
            self.finished.emit(False, f"系统错误: {str(e)}")

# ===========================
# 4. 主窗口
# ===========================
class VoiceEnrollmentApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("阿里云 CosyVoice 声音复刻工具  by Gao_xiaohai")
        self.resize(1100, 850)
        self.setStyleSheet(STYLESHEET)
        
        self.current_voice_id = None
        self.current_model = None
        self.thread_lock = threading.Lock()  # 新增：线程互斥锁
        
        self.init_ui()
        self.log("程序已就绪。")

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # --- 左侧面板 ---
        left = QVBoxLayout()
        
        # 1. API 配置（新增：显示/隐藏API Key按钮）
        group1 = QGroupBox("1. API 配置")
        f1 = QFormLayout()
        self.api_input = QLineEdit()
        self.api_input.setPlaceholderText("填写你的API Key")
        self.api_input.setEchoMode(QLineEdit.Password)
        
        # 新增：显示/隐藏按钮
        self.show_api_btn = QPushButton("显示")
        self.show_api_btn.setCheckable(True)
        self.show_api_btn.clicked.connect(self.toggle_api_visibility)
        
        # 新增：水平布局放输入框和按钮
        api_layout = QHBoxLayout()
        api_layout.addWidget(self.api_input)
        api_layout.addWidget(self.show_api_btn)
        
        self.model_combo = QComboBox()
        self.model_combo.addItems(["cosyvoice-v3-plus", "cosyvoice-v3-flash", "cosyvoice-v2", "cosyvoice-v1"])
        self.model_combo.setCurrentText("cosyvoice-v3-plus")
        f1.addRow("API Key:", api_layout)  # 替换原有行
        f1.addRow("使用模型:", self.model_combo)
        group1.setLayout(f1)
        
        # 2. 复刻操作
        group2 = QGroupBox("2. 新建音色")
        f2 = QFormLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("http://... (wav/mp3)")
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("英文/数字前缀 (如 myvoice)")
        self.btn_enroll = QPushButton("开始复刻音色")
        self.btn_enroll.setCursor(Qt.PointingHandCursor)
        self.btn_enroll.clicked.connect(self.action_enroll)
        f2.addRow("音频 URL:", self.url_input)
        f2.addRow("音色名称:", self.name_input)
        f2.addRow(self.btn_enroll)
        group2.setLayout(f2)
        
        # 3. 音色列表
        group3 = QGroupBox("3. 音色列表")
        v3 = QVBoxLayout()
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["音色ID", "状态", "模型 (猜测)"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)  # 禁止双击编辑
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.itemClicked.connect(self.action_table_click)
        
        btns = QHBoxLayout()
        self.btn_refresh = QPushButton("刷新列表")
        self.btn_refresh.setObjectName("RefreshBtn")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.clicked.connect(self.action_refresh)
        
        self.btn_use = QPushButton("使用选中")
        self.btn_use.clicked.connect(self.action_use)
        
        self.btn_del = QPushButton("删除选中")
        self.btn_del.setObjectName("DeleteBtn")
        self.btn_del.clicked.connect(self.action_delete)
        
        btns.addWidget(self.btn_refresh)
        btns.addStretch()
        btns.addWidget(self.btn_use)
        btns.addWidget(self.btn_del)
        v3.addWidget(self.table)
        v3.addLayout(btns)
        group3.setLayout(v3)
        
        # 4. 语音合成
        group4 = QGroupBox("4. 语音合成")
        v4 = QVBoxLayout()
        
        self.lbl_info = QLabel("当前状态: 未选择音色")
        self.lbl_info.setStyleSheet("color: #666; font-weight: bold;")
        v4.addWidget(self.lbl_info)
        
        # --- A. 音量调节 (0-100) ---
        h_vol = QHBoxLayout()
        h_vol.addWidget(QLabel("音量:"))
        
        # 1. 音量滑块
        self.slider_vol = QSlider(Qt.Horizontal)
        self.slider_vol.setRange(0, 100)
        self.slider_vol.setValue(50)
        
        # 2. 音量数字框
        self.spin_vol = QSpinBox()
        self.spin_vol.setRange(0, 100)
        self.spin_vol.setValue(50)
        self.spin_vol.setFixedWidth(60)
        
        # 3. 双向绑定信号
        # 滑块动 -> 数字变
        self.slider_vol.valueChanged.connect(self.spin_vol.setValue)
        # 数字变 -> 滑块动
        self.spin_vol.valueChanged.connect(self.slider_vol.setValue)
        
        h_vol.addWidget(self.slider_vol)
        h_vol.addWidget(self.spin_vol)
        v4.addLayout(h_vol)
        
        # --- B. 语速调节 (0.5 - 2.0) ---
        # 技巧: QSlider只支持整数，我们将范围设为 5-20 (代表 0.5-2.0)
        h_speed = QHBoxLayout()
        h_speed.addWidget(QLabel("语速:"))
        
        # 1. 语速滑块 (5 - 20)
        self.slider_speed = QSlider(Qt.Horizontal)
        self.slider_speed.setRange(5, 20) 
        self.slider_speed.setValue(10) # 默认 1.0
        
        # 2. 语速数字框 (0.5 - 2.0)
        self.spin_speed = QDoubleSpinBox()
        self.spin_speed.setRange(0.5, 2.0)
        self.spin_speed.setSingleStep(0.1)
        self.spin_speed.setValue(1.0)
        self.spin_speed.setFixedWidth(60)
        
        # 3. 双向绑定信号 (需要数值转换)
        # 滑块(int) -> 除以10 -> 数字框(float)
        self.slider_speed.valueChanged.connect(lambda v: self.spin_speed.setValue(v / 10.0))
        # 数字框(float) -> 乘以10 -> 滑块(int)
        self.spin_speed.valueChanged.connect(lambda v: self.slider_speed.setValue(int(v * 10)))
        
        h_speed.addWidget(self.slider_speed)
        h_speed.addWidget(self.spin_speed)
        v4.addLayout(h_speed)
        
        # --- C. 文本与路径输入 (保持不变) ---
        self.txt_input = QLineEdit()
        self.txt_input.setPlaceholderText("请输入要合成的文本...")
        v4.addWidget(self.txt_input)
        
        h_path = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("保存路径...")
        btn_path = QPushButton("选择路径")
        btn_path.clicked.connect(self.action_path)
        h_path.addWidget(self.path_input)
        h_path.addWidget(btn_path)
        v4.addLayout(h_path)
        
        self.btn_gen = QPushButton("开始合成音频")
        self.btn_gen.setCursor(Qt.PointingHandCursor)
        self.btn_gen.setStyleSheet("QPushButton { font-weight: bold; padding: 5px; }")
        self.btn_gen.clicked.connect(self.action_gen)
        v4.addWidget(self.btn_gen)
        
        group4.setLayout(v4)
        
        left.addWidget(group1)
        left.addWidget(group2)
        left.addWidget(group3)
        left.addWidget(group4)
        
        # --- 右侧日志 ---
        right = QVBoxLayout()
        self.logs = QTextEdit()
        self.logs.setReadOnly(True)
        self.pbar = QProgressBar()
        self.pbar.setValue(0)
        
        right.addWidget(QLabel("运行日志:"))
        right.addWidget(self.logs)
        right.addWidget(self.pbar)
        
        layout.addLayout(left, 6)
        layout.addLayout(right, 4)

    # 新增：API Key显示/隐藏切换
    def toggle_api_visibility(self):
        if self.show_api_btn.isChecked():
            self.api_input.setEchoMode(QLineEdit.Normal)
            self.show_api_btn.setText("隐藏")
        else:
            self.api_input.setEchoMode(QLineEdit.Password)
            self.show_api_btn.setText("显示")

    # --- 辅助方法 ---
    def log(self, m):
        t = time.strftime('%H:%M:%S')
        self.logs.append(f"[{t}] {m}")
        sb = self.logs.verticalScrollBar()
        sb.setValue(sb.maximum())

    # --- 槽函数 ---
    def action_refresh(self):
        key = self.api_input.text().strip()
        if not key:
            QMessageBox.warning(self, "提示", "请先填写 API Key")
            return
            
        with self.thread_lock:
            self.btn_refresh.setEnabled(False)
            self.btn_refresh.setText("刷新中...")
            self.table.setRowCount(0)
            
            self.worker = VoiceQueryThread(key)
            self.worker.log_signal.connect(self.log)
            self.worker.finished.connect(self.on_refresh_done)
            self.worker.start()

    def on_refresh_done(self, voices):
        self.btn_refresh.setEnabled(True)
        self.btn_refresh.setText("刷新列表")
        self.table.setRowCount(len(voices))
        
        self.log(f"刷新完成，共获取 {len(voices)} 条记录。")
        
        for i, v in enumerate(voices):
            v_dict = v if isinstance(v, dict) else v.__dict__
            
            v_id = v_dict.get('voice_id', 'Unknown')
            status = v_dict.get('status', 'Unknown')
            
            self.table.setItem(i, 0, QTableWidgetItem(str(v_id)))
            
            item_status = QTableWidgetItem(str(status))
            if status == "OK":
                item_status.setForeground(QColor("#2ea44f"))
            else:
                item_status.setForeground(QColor("#d73a49"))
            self.table.setItem(i, 1, item_status)
            
            guess = "Unknown"
            if "v3-plus" in str(v_id): guess = "cosyvoice-v3-plus"
            elif "v3-flash" in str(v_id): guess = "cosyvoice-v3-flash"
            elif "v2" in str(v_id): guess = "cosyvoice-v2"
            elif "v1" in str(v_id): guess = "cosyvoice-v1"
            self.table.setItem(i, 2, QTableWidgetItem(guess))

    def action_enroll(self):
        key = self.api_input.text().strip()
        url = self.url_input.text().strip()
        name = self.name_input.text().strip()
        
        if not key:
            QMessageBox.warning(self, "参数缺失", "请填写 API Key")
            return
        if not url:
            QMessageBox.warning(self, "参数缺失", "请填写音频 URL")
            return
        if not name:
            QMessageBox.warning(self, "参数缺失", "请填写音色名称 (prefix)")
            return

        with self.thread_lock:
            self.btn_enroll.setEnabled(False)
            self.worker_enroll = VoiceEnrollmentThread(key, url, name, self.model_combo.currentText())
            self.worker_enroll.progress.connect(lambda v, m: [self.pbar.setValue(v), self.log(m)])
            self.worker_enroll.finished.connect(self.on_enroll_finished)
            self.worker_enroll.start()

    def on_enroll_finished(self, success, msg):
        self.btn_enroll.setEnabled(True)
        self.pbar.setValue(100 if success else 0)
        if success:
            self.log(f"复刻成功! ID: {msg}")
            QMessageBox.information(self, "成功", f"音色创建成功\nID: {msg}")
            self.action_refresh()
        else:
            self.log(f"复刻失败: {msg}")
            QMessageBox.critical(self, "失败", msg)

    def action_table_click(self):
        pass

    def action_use(self):
        # [修改] 获取所有选中的行
        selected_rows = self.table.selectionModel().selectedRows()
        
        if len(selected_rows) == 0:
            QMessageBox.warning(self, "提示", "请先在列表中选中一行")
            return
        
        # [新增] 检查是否多选
        if len(selected_rows) > 1:
            QMessageBox.warning(self, "不可用", "当前选择了多个音色。\n合成时只能选择一个音色，请取消多选。")
            return
            
        # [修改] 获取第一行（也是唯一一行）的索引
        row = selected_rows[0].row()
        
        v_id = self.table.item(row, 0).text()
        status = self.table.item(row, 1).text()
        
        if status != "OK":
            QMessageBox.warning(self, "不可用", "该音色状态不是 OK，无法使用。")
            return
            
        model_guess = self.table.item(row, 2).text()
        if model_guess == "Unknown":
            model_guess = self.model_combo.currentText()
            
        self.current_voice_id = v_id
        self.current_model = model_guess
        
        self.lbl_info.setText(f"已选中: {v_id}\n模型: {model_guess}")
        self.lbl_info.setStyleSheet("color: #0366d6; font-weight: bold;")
        self.log(f"已激活音色: {v_id}")

    def action_path(self):
        path, _ = QFileDialog.getSaveFileName(self, "保存文件", "output.mp3", "MP3 Files (*.mp3)")
        if path:
            self.path_input.setText(path)

    def action_gen(self):
        key = self.api_input.text().strip()
        txt = self.txt_input.text().strip()
        out = self.path_input.text().strip()
        
        # --- 获取界面上的音量和语速参数 ---
        vol = self.spin_vol.value()
        speed = self.spin_speed.value()
        # -----------------------
        
        if not key:
            QMessageBox.warning(self, "提示", "缺少 API Key")
            return
        if not self.current_voice_id:
            QMessageBox.warning(self, "提示", "请先选择一个音色并点击'使用选中'")
            return
        if not txt:
            QMessageBox.warning(self, "提示", "请输入要合成的文本")
            return
        if not out:
            QMessageBox.warning(self, "提示", "请选择保存路径")
            return

        with self.thread_lock:
            self.btn_gen.setEnabled(False)
            self.pbar.setValue(0)  # 重置进度条
            # 这里传入 vol 和 speed
            self.worker_gen = SpeechSynthesisThread(key, txt, out, self.current_voice_id, self.current_model, vol, speed)
            self.worker_gen.progress.connect(lambda v, m: [self.pbar.setValue(v), self.log(m)])
            self.worker_gen.finished.connect(self.on_gen_finished)
            self.worker_gen.start()

    def on_gen_finished(self, success, msg):
        with self.thread_lock:
            self.btn_gen.setEnabled(True)
            self.pbar.setValue(100 if success else 0)
            if success:
                QMessageBox.information(self, "成功", f"文件已保存至:\n{msg}")
            else:
                QMessageBox.warning(self, "失败", msg)

    def action_delete(self):
        # [修改] 获取所有选中的行
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows: 
            return
        
        # 收集所有选中的 ID 和行号（倒序处理避免索引错乱）
        selected_data = []
        for index in selected_rows:
            row = index.row()
            v_id = self.table.item(row, 0).text()
            selected_data.append((row, v_id))
        
        count = len(selected_data)
        if QMessageBox.question(self, "确认", f"确定要删除选中的 {count} 个音色吗？\n此操作不可恢复！") != QMessageBox.Yes:
            return
            
        try:
            key = self.api_input.text().strip()
            dashscope.api_key = key
            service = VoiceEnrollmentService()
            
            self.log(f"--- 开始批量删除 {count} 个音色 ---")
            success_count = 0
            
            # [新增] 倒序删除行（避免索引错乱）
            for row, v_id in sorted(selected_data, key=lambda x: x[0], reverse=True):
                try:
                    resp = service.delete_voice(voice_id=v_id)
                    if hasattr(resp, 'status') and resp.status != 'OK':
                        raise ValueError(f"删除失败，官方返回状态: {resp.status}")
                    self.table.removeRow(row)
                    self.log(f"已删除: {v_id}")
                    success_count += 1
                except Exception as e:
                    self.log(f"删除 {v_id} 失败: {str(e)}")
                    
            self.log(f"--- 批量删除结束，成功 {success_count}/{count} ---")
            self.action_refresh() # 刷新列表
            
        except Exception as e:
            QMessageBox.critical(self, "错误", str(e))

if __name__ == "__main__":
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app = QApplication(sys.argv)
    font = QFont("Microsoft YaHei", 9)
    app.setFont(font)
    win = VoiceEnrollmentApp()
    win.show()
    sys.exit(app.exec_())