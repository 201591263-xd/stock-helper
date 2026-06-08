"""
聊天组件 - 马维斯圆润风格
支持: 板块分类展示, "买入 5万 易点天下301171" 格式
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit,
    QPushButton, QLabel, QFrame
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QTextCursor, QColor, QTextCharFormat
import re
from dataclasses import dataclass


@dataclass
class ParsedCommand:
    type: str = ""          # recommend / buy / sell / positions / history
    query: str = ""
    stock_code: str = ""
    stock_name: str = ""
    amount: float = 0.0     # 万元
    buy_price: float = 0.0  # 买入单价
    sell_price: float = 0.0 # 卖出单价
    board: str = ""


class ChatParser:
    """解析聊天输入中的指令"""

    def parse(self, text: str) -> ParsedCommand:
        text = text.strip()

        # "推荐 5万 主板" / "推荐 5万 创业板" / "推荐 3万 科创板"
        rec_with_board = re.match(r'推荐\s+(\d+\.?\d*)\s*万?\s*(主板|创业板|科创板|中小板)', text)
        if rec_with_board:
            amount = float(rec_with_board.group(1))
            board = rec_with_board.group(2)
            return ParsedCommand(type="recommend", query=text, amount=amount, board=board)

        # "推荐" / "推荐股票"
        if re.match(r'^推荐', text):
            return ParsedCommand(type="recommend", query=text)

        # "买入 5万 21.9 易点天下301171" / "买入 5万 21.9 易点天下 301171"（带价格）
        buy_match = re.match(r'买入\s+(\d+\.?\d*)\s*万?\s+(\d+\.?\d*)\s+(.+?)\s*(\d{6})', text)
        if buy_match:
            amount_raw = buy_match.group(1)
            price_raw = buy_match.group(2)
            stock_name = buy_match.group(3).strip()
            stock_code = buy_match.group(4)
            amount = float(amount_raw)
            buy_price = float(price_raw)
            return ParsedCommand(type="buy", stock_code=stock_code, stock_name=stock_name, amount=amount, buy_price=buy_price)

        # "买入 5万 易点天下 301171" / "买入 50000 易点天下301171"（无价格，兼容旧格式）
        buy_match = re.match(r'买入\s+(\d+\.?\d*)\s*万?\s*(.+?)\s*(\d{6})', text)
        if buy_match:
            amount_raw = buy_match.group(1)
            stock_name = buy_match.group(2).strip()
            stock_code = buy_match.group(3)
            amount = float(amount_raw) * 10000 if '万' in text else float(amount_raw)
            return ParsedCommand(type="buy", stock_code=stock_code, stock_name=stock_name, amount=amount / 10000)

        # "卖出 301171 42.5" 或 "卖出 301171"
        sell_match = re.match(r'卖出\s*(\d{6})\s*(\d+\.?\d*)?\s*$', text)
        if sell_match:
            code = sell_match.group(1)
            price_str = sell_match.group(2)
            sell_price = float(price_str) if price_str else 0.0
            return ParsedCommand(type="sell", stock_code=code, sell_price=sell_price)

        # "卖出 易点天下"（模糊匹配名称）
        sell_name_match = re.match(r'卖出\s*(.+)', text)
        if sell_name_match and not re.match(r'^\d{6}', sell_name_match.group(1)):
            target = sell_name_match.group(1).strip()
            return ParsedCommand(type="sell", stock_name=target)

        # "持仓"
        if re.match(r'^持仓', text):
            return ParsedCommand(type="positions")

        # "历史" / "买入历史"
        if re.match(r'^(买入)?历史', text):
            return ParsedCommand(type="history")

        return ParsedCommand(type="unknown", query=text)


class ChatWidget(QWidget):
    buy_signal = Signal(str, str, float, float, str, str)  # code, name, price, amount, sector, board

    def __init__(self, api, username):
        super().__init__()
        self.api = api
        self.username = username
        self.last_recommend = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标题栏
        header = QWidget()
        header.setFixedHeight(48)
        header.setStyleSheet("background-color: #ffffff; border-bottom: 1px solid #e9ecef; border-radius: 0px;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 0, 18, 0)

        title = QLabel(f"  对话 · {self.username}")
        title.setStyleSheet("color: #2c3e50; font-weight: 700; font-size: 14px; background: transparent;")

        self.time_label = QLabel("")
        self.time_label.setStyleSheet("color: #8899aa; font-size: 12px; background: transparent;")

        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(self.time_label)
        layout.addWidget(header)

        # 聊天显示区 - 圆润大卡片
        chat_container = QWidget()
        chat_container.setStyleSheet("background-color: #f8f9fa;")
        chat_layout = QVBoxLayout(chat_container)
        chat_layout.setContentsMargins(10, 10, 10, 10)

        self.chat_display = QTextEdit()
        self.chat_display.setObjectName("chatDisplay")
        self.chat_display.setReadOnly(True)
        chat_layout.addWidget(self.chat_display)
        layout.addWidget(chat_container)

        # 输入区 - 也是圆角
        input_frame = QWidget()
        input_frame.setFixedHeight(80)
        input_frame.setStyleSheet("background-color: #ffffff; border-top: 1px solid #e9ecef;")
        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(12, 10, 12, 10)

        row = QHBoxLayout()
        row.setSpacing(8)

        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText('输入"推荐"获取推票，或"买入 5万 易点天下301171"记录...')
        self.input_box.returnPressed.connect(self._send_message)
        self.input_box.setMinimumHeight(38)

        send_btn = QPushButton("发送")
        send_btn.setObjectName("primaryBtn")
        send_btn.setFixedSize(72, 38)
        send_btn.clicked.connect(self._send_message)

        row.addWidget(self.input_box)
        row.addWidget(send_btn)
        input_layout.addLayout(row)
        layout.addWidget(input_frame)

        self.setLayout(layout)

        self.timer = QTimer()
        self.timer.timeout.connect(self._update_time)
        self.timer.start(30000)
        self._update_time()

    def _update_time(self):
        from datetime import datetime
        self.time_label.setText(datetime.now().strftime('%H:%M:%S'))

    def _send_message(self):
        text = self.input_box.text().strip()
        if not text:
            return

        self.input_box.clear()

        # 解析买入指令: "买入 5万 易点天下301171" 或 "买入 50000 易点天下301171"
        buy_match = re.match(r'买入\s+(\d+\.?\d*)\s*万?\s*(.+?)(\d{6})', text)
        if buy_match:
            amount_raw = buy_match.group(1)
            stock_name = buy_match.group(2).strip()
            stock_code = buy_match.group(3)
            amount = float(amount_raw) * 10000 if '万' in text else float(amount_raw)

            if self.last_recommend and self.last_recommend['code'] == stock_code:
                s = self.last_recommend
                self.buy_signal.emit(stock_code, stock_name, s['price'], amount, s.get('sector', ''), s.get('board', ''))
                amount_str = f"{amount/10000:.0f}万" if amount >= 10000 else f"{amount:.0f}"
                self._append_system(f"✅ 已记录: {s['name']}({stock_code}) {amount_str} @ {s['price']:.2f}")
            else:
                self._append_system("⚠ 未找到该推荐记录，请先获取推票再买入")
            return

        # 旧格式兼容: "买入 301171"
        buy_match2 = re.match(r'买入\s*(\d{6})', text)
        if buy_match2:
            code = buy_match2.group(1)
            if self.last_recommend and self.last_recommend['code'] == code:
                s = self.last_recommend
                # 默认1万
                self.buy_signal.emit(code, s['name'], s['price'], 10000, s.get('sector', ''), s.get('board', ''))
                self._append_system(f"✅ 已记录: {s['name']}({code}) 1万 @ {s['price']:.2f}")
            else:
                self._append_system("⚠ 未找到该推荐记录")
            return

        self._append_user(text)

        result = self.api.chat(self.username, text)
        if result.get('ok'):
            reply = result.get('reply', '')
            self._append_ai(reply)
            stock = result.get('stock')
            if stock:
                self.last_recommend = stock
        else:
            self._append_system(f"错误: {result.get('error', '未知错误')}")

    def _append_user(self, text):
        c = self.chat_display.textCursor()
        c.movePosition(QTextCursor.End)

        fmt = QTextCharFormat()
        fmt.setForeground(QColor('#4a90d9'))
        fmt.setFontWeight(700)
        self.chat_display.setTextCursor(c)
        self.chat_display.insertPlainText(f'\n\n{self.username}  {self._now()}\n')

        fmt2 = QTextCharFormat()
        fmt2.setForeground(QColor('#2c3e50'))
        self.chat_display.setTextCursor(c)
        self.chat_display.insertPlainText(f'{text}\n')

        self._scroll_bottom()

    def _append_ai(self, text):
        c = self.chat_display.textCursor()
        c.movePosition(QTextCursor.End)

        fmt = QTextCharFormat()
        fmt.setForeground(QColor('#8899aa'))
        fmt.setFontWeight(700)
        self.chat_display.setTextCursor(c)
        self.chat_display.insertPlainText(f'\n\n晟创 · Marvis  {self._now()}\n')

        lines = text.split('\n')
        for line in lines:
            c.movePosition(QTextCursor.End)
            self.chat_display.setTextCursor(c)
            if line.startswith('【') or line.startswith('📈'):
                fmt2 = QTextCharFormat()
                fmt2.setForeground(QColor('#e37400'))
                fmt2.setFontWeight(700)
                self.chat_display.insertPlainText(f'{line}\n')
            elif line.startswith('💰') or line.startswith('📝'):
                fmt3 = QTextCharFormat()
                fmt3.setForeground(QColor('#5f6b7a'))
                self.chat_display.insertPlainText(f'{line}\n')
            else:
                fmt4 = QTextCharFormat()
                fmt4.setForeground(QColor('#5f6b7a'))
                self.chat_display.insertPlainText(f'{line}\n')

        self._scroll_bottom()

    def _append_system(self, text):
        c = self.chat_display.textCursor()
        c.movePosition(QTextCursor.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor('#8899aa'))
        self.chat_display.setTextCursor(c)
        self.chat_display.insertPlainText(f'\n\n{text}\n')
        self._scroll_bottom()

    def _scroll_bottom(self):
        sb = self.chat_display.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _now(self):
        from datetime import datetime
        return datetime.now().strftime('%H:%M')

    def show_welcome(self):
        self.chat_display.clear()
        self._append_system("欢迎使用晟创科技 · 推票助手 v3")
        self._append_system("学弟实时推票，员工一键跟买。")
        self._append_system("主板 / 创业板 / 科创板 分类推送，买入时请注明金额。")

        result = self.api.get_available_sectors()
        if result.get('ok'):
            sectors = result.get('sectors', [])
            if sectors:
                self._append_system(f"今日可用板块: {', '.join(sectors)}")
        self._append_system("格式示例: 推荐 → 买入 5万 易点天下301171")
