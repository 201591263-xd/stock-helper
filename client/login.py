"""
登录/注册窗口 - 渐变背景 · 现代审美
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QFrame, QCheckBox
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QPalette, QLinearGradient, QBrush, QColor
from styles import get_style
from api import ApiClient
import json, os, base64

CONFIG_DIR = os.path.join(os.path.dirname(__file__), '..', '.config')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'client_config.json')

class LoginWindow(QWidget):
    login_success = Signal(str, str)

    def __init__(self):
        super().__init__()
        self.api = ApiClient()
        self.last_server = 'http://127.0.0.1:5128'
        self.last_user = ''
        self.setWindowTitle("晟创科技 · 推票助手")
        self.setFixedSize(440, 560)
        self._load_config()
        self._init_ui()

    def _load_config(self):
        self.saved_server = 'http://127.0.0.1:5128'
        self.saved_user = ''
        self.saved_pwd = ''
        self.auto_login = False
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    cfg = json.load(f)
                    self.saved_server = cfg.get('server', 'http://127.0.0.1:5128')
                    self.saved_user = cfg.get('username', '')
                    enc = cfg.get('password', '')
                    self.saved_pwd = base64.b64decode(enc).decode() if enc else ''
                    self.auto_login = cfg.get('auto_login', False)
        except:
            pass

    def _save_credentials(self, server, username, password, remember):
        cfg = {'server': server, 'username': username, 'auto_login': remember}
        if remember and password:
            cfg['password'] = base64.b64encode(password.encode()).decode()
        else:
            cfg['password'] = ''
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(cfg, f)

    def _init_ui(self):
        self.setObjectName("loginWindow")
        self.setStyleSheet("""
            QWidget#loginWindow {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #5b7fff, stop:0.5 #6c5ce7, stop:1 #a855f7);
            }
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setAlignment(Qt.AlignCenter)

        # 白色卡片 - 略微加大
        card = QWidget()
        card.setObjectName("loginCard")
        card.setFixedSize(380, 490)
        card.setStyleSheet("""
            QWidget#loginCard {
                background-color: #ffffff;
                border-radius: 20px;
            }
        """)

        layout = QVBoxLayout(card)
        layout.setSpacing(0)
        layout.setContentsMargins(40, 36, 40, 36)

        # ===== Logo 区（紧凑） =====
        logo_label = QLabel("晟创科技")
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setStyleSheet(
            "font-size: 24px; font-weight: 800; color: #4a90d9; background: transparent;"
        )
        layout.addWidget(logo_label)

        sub = QLabel("推票助手 v3.0")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet("color: #a0aab4; font-size: 12px; background: transparent; margin-top: 2px;")
        layout.addWidget(sub)

        # 细分隔线
        layout.addSpacing(16)
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: #eef0f2; max-height: 1px; margin: 0 20px;")
        layout.addWidget(sep)
        layout.addSpacing(24)

        # ===== 表单区 =====
        # 用户名（带图标容器）
        user_row = QHBoxLayout()
        user_row.setSpacing(0)
        user_icon = QLabel("👤")
        user_icon.setFixedWidth(40)
        user_icon.setAlignment(Qt.AlignCenter)
        user_icon.setStyleSheet("font-size: 16px; background: transparent; color: #8899aa;")

        self.user_input = QLineEdit(self.saved_user)
        self.user_input.setPlaceholderText("用户名")
        self.user_input.setFixedHeight(42)
        self.user_input.setStyleSheet(
            "QLineEdit { border: none; border-bottom: 2px solid #e0e4e8;"
            "  border-radius: 0; padding: 8px 4px; font-size: 14px; background: transparent;"
            "  color: #2c3e50; }"
            "QLineEdit:focus { border-bottom: 2px solid #4a90d9; }"
        )

        user_row.addWidget(user_icon)
        user_row.addWidget(self.user_input)
        layout.addLayout(user_row)
        layout.addSpacing(10)

        # 密码
        pwd_row = QHBoxLayout()
        pwd_row.setSpacing(0)
        pwd_icon = QLabel("🔒")
        pwd_icon.setFixedWidth(40)
        pwd_icon.setAlignment(Qt.AlignCenter)
        pwd_icon.setStyleSheet("font-size: 16px; background: transparent; color: #8899aa;")

        self.pwd_input = QLineEdit(self.saved_pwd)
        self.pwd_input.setPlaceholderText("密码")
        self.pwd_input.setEchoMode(QLineEdit.Password)
        self.pwd_input.setFixedHeight(42)
        self.pwd_input.setStyleSheet(
            "QLineEdit { border: none; border-bottom: 2px solid #e0e4e8;"
            "  border-radius: 0; padding: 8px 4px; font-size: 14px; background: transparent;"
            "  color: #2c3e50; }"
            "QLineEdit:focus { border-bottom: 2px solid #4a90d9; }"
        )
        self.pwd_input.returnPressed.connect(self._do_login)

        pwd_row.addWidget(pwd_icon)
        pwd_row.addWidget(self.pwd_input)
        layout.addLayout(pwd_row)

        layout.addSpacing(16)

        # 记住密码
        self.remember_check = QCheckBox("记住密码，自动登录")
        self.remember_check.setChecked(self.auto_login)
        self.remember_check.setStyleSheet(
            "QCheckBox { font-size: 12px; color: #8899aa; background: transparent; }"
        )
        layout.addWidget(self.remember_check)
        layout.addSpacing(6)

        # ===== 按钮 =====
        login_btn = QPushButton("登录")
        login_btn.setFixedHeight(44)
        login_btn.setCursor(Qt.PointingHandCursor)
        login_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #4a90d9; color: #ffffff; border: none; border-radius: 10px;"
            "  font-weight: 700; font-size: 15px;"
            "}"
            "QPushButton:hover { background-color: #3d7ec5; }"
            "QPushButton:pressed { background-color: #3568a8; }"
        )
        login_btn.clicked.connect(self._do_login)
        layout.addWidget(login_btn)

        layout.addSpacing(10)

        register_btn = QPushButton("注册新账号")
        register_btn.setFixedHeight(38)
        register_btn.setCursor(Qt.PointingHandCursor)
        register_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: transparent; color: #8899aa;"
            "  border: 1px solid #e0e4e8; border-radius: 10px; font-size: 13px;"
            "}"
            "QPushButton:hover { background-color: #f5f7fa; color: #4a90d9; border-color: #4a90d9; }"
        )
        register_btn.clicked.connect(self._do_register)
        layout.addWidget(register_btn)

        layout.addSpacing(14)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #c0c8d0; font-size: 11px; background: transparent;")
        layout.addWidget(self.status_label)

        layout.addStretch()
        outer.addWidget(card)

        # 自动登录
        if self.auto_login and self.saved_user and self.saved_pwd:
            self.status_label.setText("自动登录中...")
            QTimer.singleShot(300, self._do_login)

    def _do_login(self):
        username = self.user_input.text().strip()
        password = self.pwd_input.text()
        server = self.saved_server
        remember = self.remember_check.isChecked()

        if not username or not password:
            QMessageBox.warning(self, "提示", "请输入用户名和密码")
            return

        self.api = ApiClient(server)
        self.status_label.setText("正在连接...")

        try:
            result = self.api.login(username, password)
            if result.get('ok'):
                self._save_credentials(server, username, password, remember)
                self.login_success.emit(username, server)
            else:
                QMessageBox.warning(self, "登录失败", "用户名或密码错误")
        except Exception as e:
            QMessageBox.critical(self, "连接失败", f"无法连接到服务器: {str(e)}")

        self.status_label.setText("")

    def _do_register(self):
        username = self.user_input.text().strip()
        password = self.pwd_input.text()
        server = self.saved_server

        if not username or not password:
            QMessageBox.warning(self, "提示", "请输入用户名和密码")
            return

        if len(password) < 3:
            QMessageBox.warning(self, "提示", "密码至少3位")
            return

        self.api = ApiClient(server)
        result = self.api.register(username, password)

        if result.get('ok'):
            QMessageBox.information(self, "注册成功", f"用户 {username} 注册成功，请登录")
        else:
            QMessageBox.warning(self, "注册失败", result.get('error', '未知错误'))
