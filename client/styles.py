"""
马维斯风格全局样式 · 支持深色/浅色切换
"""

# ---- 浅色主题（马维斯白底蓝调） ----
LIGHT_STYLE = """
/* 全局 */
QWidget {
    background-color: #f8f9fa;
    color: #2c3e50;
    font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
}

/* 左侧导航栏 */
QWidget#leftPanel {
    background-color: #ffffff;
    border-right: 1px solid #e9ecef;
}

QPushButton#navBtn {
    background-color: transparent;
    color: #5a6a7a;
    border: none;
    border-radius: 10px;
    text-align: left;
    font-size: 14px;
    font-weight: 500;
    padding: 10px 16px;
}
QPushButton#navBtn:hover {
    background-color: #f0f4f8;
    color: #4a90d9;
}
QPushButton#navBtn:checked {
    background-color: #e8f4fd;
    color: #4a90d9;
    font-weight: 700;
}

/* 右侧胶囊按钮 - 圆润 pill 风格 */
QPushButton#rightTab {
    background-color: #f0f4f8;
    color: #7a8a9a;
    border: none;
    border-radius: 16px;
    font-size: 13px;
    font-weight: 600;
    padding: 6px 16px;
}
QPushButton#rightTab:hover {
    background-color: #dce8f4;
    color: #4a90d9;
}
QPushButton#rightTab:checked {
    background-color: #4a90d9;
    color: #ffffff;
}

QLabel#sectionTitle {
    color: #4a90d9;
    font-size: 15px;
    font-weight: 700;
    background: transparent;
}

QLabel#userNameLabel {
    color: #5a6a7a;
    font-size: 13px;
    font-weight: 600;
    background: transparent;
}

QLabel#onlineStatus {
    color: #27ae60;
    font-size: 11px;
    background: transparent;
}

/* 聊天区 */
QWidget#chatContainer {
    background-color: #f8f9fa;
    border: 1px solid #e9ecef;
    border-radius: 14px;
}

QScrollArea#chatDisplay {
    background-color: #ffffff;
    border: none;
    border-radius: 12px;
}

QWidget#chatBubblesWidget {
    background-color: #ffffff;
}

QTextEdit#chatInput {
    background-color: #ffffff;
    border: 1px solid #e9ecef;
    border-radius: 10px;
    padding: 12px;
    font-size: 14px;
}

/* 主按钮 */
QPushButton#primaryBtn {
    background-color: #4a90d9;
    color: #ffffff;
    border: none;
    border-radius: 10px;
    font-size: 14px;
    font-weight: 600;
    padding: 10px 20px;
}
QPushButton#primaryBtn:hover {
    background-color: #3d7ec5;
}

/* 普通按钮 */
QPushButton {
    background-color: transparent;
    border: 1px solid #e0e4e8;
    border-radius: 8px;
    padding: 8px 16px;
    color: #5a6a7a;
}

/* 表格 */
QTableWidget {
    background-color: #ffffff;
    border: 1px solid #e9ecef;
    border-radius: 10px;
    gridline-color: #f0f4f8;
    font-size: 12px;
}
QTableWidget::item {
    padding: 6px;
}
QHeaderView::section {
    background-color: #f8f9fa;
    color: #5a6a7a;
    font-weight: 600;
    border: none;
    border-bottom: 1px solid #e9ecef;
    padding: 6px;
}

/* 设置区 */
QWidget#settingsPage {
    background-color: #ffffff;
}

QComboBox {
    background-color: #ffffff;
    border: 1px solid #e0e4e8;
    border-radius: 6px;
    padding: 6px 12px;
}

QScrollBar:vertical {
    background: #f8f9fa;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #ccd5de;
    border-radius: 4px;
    min-height: 30px;
}
"""

# ---- 深色主题 ----
DARK_STYLE = """
QWidget {
    background-color: #1a1d23;
    color: #d4d8e0;
    font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
}

QWidget#leftPanel {
    background-color: #1e2128;
    border-right: 1px solid #2a2e38;
}

QPushButton#navBtn {
    background-color: transparent;
    color: #8b8fa0;
    border: none;
    border-radius: 10px;
    text-align: left;
    font-size: 14px;
    font-weight: 500;
    padding: 10px 16px;
}
QPushButton#navBtn:hover {
    background-color: #242830;
    color: #5b8ce9;
}
QPushButton#navBtn:checked {
    background-color: #1e2840;
    color: #5b8ce9;
    font-weight: 700;
}

QPushButton#rightTab {
    background-color: #242830;
    color: #8b8fa0;
    border: none;
    border-radius: 16px;
    font-size: 13px;
    font-weight: 600;
    padding: 6px 16px;
}
QPushButton#rightTab:hover {
    background-color: #2a2e38;
    color: #5b8ce9;
}
QPushButton#rightTab:checked {
    background-color: #5b8ce9;
    color: #ffffff;
}

QLabel#sectionTitle {
    color: #5b8ce9;
    font-size: 15px;
    font-weight: 700;
    background: transparent;
}

QLabel#userNameLabel {
    color: #b8bcc8;
    font-size: 13px;
    font-weight: 600;
    background: transparent;
}

QLabel#onlineStatus {
    color: #27ae60;
    font-size: 11px;
    background: transparent;
}

QWidget#chatContainer {
    background-color: #1a1d23;
    border: 1px solid #2a2e38;
    border-radius: 14px;
}

QScrollArea#chatDisplay {
    background-color: #1e2128;
    border: none;
    border-radius: 12px;
}

QWidget#chatBubblesWidget {
    background-color: #1e2128;
}

QTextEdit#chatInput {
    background-color: #1e2128;
    border: 1px solid #2a2e38;
    border-radius: 10px;
    padding: 12px;
    font-size: 14px;
    color: #d4d8e0;
}

QPushButton#primaryBtn {
    background-color: #5b8ce9;
    color: #ffffff;
    border: none;
    border-radius: 10px;
    font-size: 14px;
    font-weight: 600;
    padding: 10px 20px;
}
QPushButton#primaryBtn:hover {
    background-color: #4a7cd9;
}

QPushButton {
    background-color: transparent;
    border: 1px solid #3a3e48;
    border-radius: 8px;
    padding: 8px 16px;
    color: #8b8fa0;
}

QTableWidget {
    background-color: #1e2128;
    border: 1px solid #2a2e38;
    border-radius: 10px;
    gridline-color: #242830;
    font-size: 12px;
    color: #d4d8e0;
}
QTableWidget::item {
    padding: 6px;
}
QHeaderView::section {
    background-color: #242830;
    color: #8b8fa0;
    font-weight: 600;
    border: none;
    border-bottom: 1px solid #2a2e38;
    padding: 6px;
}

QWidget#settingsPage {
    background-color: #1e2128;
}

QComboBox {
    background-color: #1e2128;
    color: #d4d8e0;
    border: 1px solid #3a3e48;
    border-radius: 6px;
    padding: 6px 12px;
}

QScrollBar:vertical {
    background: #1a1d23;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #3a3e48;
    border-radius: 4px;
    min-height: 30px;
}
"""

THEMES = {
    "浅色主题": LIGHT_STYLE,
    "深色主题": DARK_STYLE,
}

THEME_NAMES = list(THEMES.keys())


def get_style(theme_name="浅色主题"):
    """根据主题名称返回样式表"""
    return THEMES.get(theme_name, LIGHT_STYLE)
