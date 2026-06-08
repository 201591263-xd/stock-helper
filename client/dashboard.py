"""
推票助手 v4.0 - 主面板（整合更新系统）
布局: 左160px(导航+退出) | 中弹性(聊天/持仓/历史/卖出/设置) | 右280px(实时数据)
"""
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QStackedWidget, QTextEdit, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame, QComboBox, QScrollArea, QButtonGroup, QInputDialog,
    QMessageBox
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor, QFont
from styles import get_style, THEME_NAMES
from api import ApiClient
from chat import ChatParser

# 手续费常量
COMMISSION_RATE = 0.00025
TRANSFER_RATE  = 0.00001
STAMP_RATE     = 0.001

def calc_pnl(buy_price, sell_price, amount_wan):
    """含手续费的实际净利润，amount_wan: 金额(万元)"""
    N = amount_wan * 10000 / buy_price
    buy_total = N * buy_price
    buy_fee = max(buy_total * COMMISSION_RATE, 5) + buy_total * TRANSFER_RATE
    sell_total = N * sell_price
    sell_fee = max(sell_total * COMMISSION_RATE, 5) + sell_total * TRANSFER_RATE + sell_total * STAMP_RATE
    return round(sell_total - buy_total - (buy_fee + sell_fee), 2)


class Dashboard(QWidget):
    login_signal = Signal()  # 退出登录时触发

    def __init__(self, username, server_url):
        super().__init__()
        self.username = username
        self.api = ApiClient(server_url, username=username)
        self.current_theme = "浅色主题"
        self._history_offset = 0
        self._history_limit = 20
        self._history_has_more = False
        self._sell_history_offset = 0
        self._pinned_codes = set()

        self.setWindowTitle("晟创科技 · 推票助手")
        self.resize(1600, 800)
        self.setMinimumSize(1100, 680)

        self._init_ui()
        self._apply_theme()
        self._load_theme_pref()

        # 定时刷新 30 秒
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(30000)

        # 首次加载右侧栏
        QTimer.singleShot(1500, self._load_right_panel)

    # ============================================================
    #  UI 构建
    # ============================================================
    def _init_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---------- 左栏 180px ----------
        self.left_panel = QWidget()
        self.left_panel.setObjectName("leftPanel")
        self.left_panel.setFixedWidth(180)

        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(14, 24, 14, 12)
        left_layout.setSpacing(6)

        brand = QLabel("晟创科技")
        brand.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        brand.setStyleSheet(
            "font-size: 18px; font-weight: 800; color: #4a90d9; "
            "background: transparent; padding: 6px 2px 12px 2px;"
        )
        left_layout.addWidget(brand)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: #e9ecef; max-height: 1px;")
        left_layout.addWidget(sep)
        left_layout.addSpacing(4)

        # 导航页签
        self.nav_btns = []
        nav_labels = ["💬  对话", "📊  我的持仓", "📋  买入历史", "📤  卖出历史"]
        self._page_index_map = [0, 1, 2, 3]  # 0=chat, 1=positions, 2=history, 3=sell_history
        for i, text in enumerate(nav_labels):
            btn = QPushButton(text)
            btn.setObjectName("navBtn")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, idx=i: self._on_nav(idx))
            self.nav_btns.append(btn)
            left_layout.addWidget(btn)

        left_layout.addStretch()

        # 退出登录
        self.logout_btn = QPushButton("🚪 退出登录")
        self.logout_btn.setObjectName("navBtn")
        self.logout_btn.setCursor(Qt.PointingHandCursor)
        self.logout_btn.clicked.connect(self._on_logout)
        left_layout.addWidget(self.logout_btn)

        # 设置
        settings_btn = QPushButton("⚙ 设置")
        settings_btn.setObjectName("navBtn")
        settings_btn.setCursor(Qt.PointingHandCursor)
        settings_btn.clicked.connect(lambda: self._on_nav(4))
        left_layout.addWidget(settings_btn)

        user_line = QHBoxLayout()
        user_name = QLabel(self.username)
        user_name.setObjectName("userNameLabel")
        status = QLabel("● 在线")
        status.setObjectName("onlineStatus")
        user_line.addWidget(user_name)
        user_line.addStretch()
        user_line.addWidget(status)
        left_layout.addLayout(user_line)

        root.addWidget(self.left_panel)

        # ---------- 中间主区域 ----------
        self.mid_stack = QStackedWidget()

        self.chat_page = self._build_chat_page()               # 0
        self.mid_stack.addWidget(self.chat_page)

        self.position_page = self._build_position_page()       # 1
        self.mid_stack.addWidget(self.position_page)

        self.history_page = self._build_history_page()         # 2
        self.mid_stack.addWidget(self.history_page)

        self.sell_history_page = self._build_sell_history_page()  # 3
        self.mid_stack.addWidget(self.sell_history_page)

        self.settings_page = self._build_settings_page()       # 4
        self.mid_stack.addWidget(self.settings_page)

        root.addWidget(self.mid_stack)

        # ---------- 右栏 280px ----------
        self.right_panel = QWidget()
        self.right_panel.setFixedWidth(400)

        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(4, 32, 4, 16)
        right_layout.setSpacing(8)

        cap_layout = QHBoxLayout()
        cap_layout.setSpacing(6)

        self.btn_bought = QPushButton("已买入")
        self.btn_bought.setObjectName("rightTab")
        self.btn_bought.setCheckable(True)
        self.btn_bought.clicked.connect(lambda: self._on_right_tab(0))

        self.btn_not_bought = QPushButton("未买入")
        self.btn_not_bought.setObjectName("rightTab")
        self.btn_not_bought.setCheckable(True)
        self.btn_not_bought.clicked.connect(lambda: self._on_right_tab(1))

        self.btn_today = QPushButton("今日统计")
        self.btn_today.setObjectName("rightTab")
        self.btn_today.setCheckable(True)
        self.btn_today.clicked.connect(lambda: self._on_right_tab(2))

        self.right_tab_group = QButtonGroup()
        self.right_tab_group.addButton(self.btn_bought, 0)
        self.right_tab_group.addButton(self.btn_not_bought, 1)
        self.right_tab_group.addButton(self.btn_today, 2)

        cap_layout.addWidget(self.btn_bought)
        cap_layout.addWidget(self.btn_not_bought)
        cap_layout.addWidget(self.btn_today)
        right_layout.addLayout(cap_layout)

        self.right_stack = QStackedWidget()

        self.right_bought = self._build_bought_card()
        self.right_stack.addWidget(self.right_bought)

        self.right_not_bought = self._build_not_bought_card()
        self.right_stack.addWidget(self.right_not_bought)

        self.right_today = self._build_stats_card()
        self.right_stack.addWidget(self.right_today)

        right_layout.addWidget(self.right_stack, 1)
        root.addWidget(self.right_panel)

        self.nav_btns[0].setChecked(True)
        self._on_nav(0)
        self._on_right_tab(0)

    # ============================================================
    #  聊天页（保持不变）
    # ============================================================
    def _build_chat_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        self.chat_container = QWidget()
        self.chat_container.setObjectName("chatContainer")
        chat_layout = QVBoxLayout(self.chat_container)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        chat_layout.setSpacing(0)

        self.chat_scroll = QScrollArea()
        self.chat_scroll.setObjectName("chatDisplay")
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setMinimumHeight(400)

        self.chat_bubbles = QWidget()
        self.chat_bubbles.setObjectName("chatBubblesWidget")
        self.bubbles_layout = QVBoxLayout(self.chat_bubbles)
        self.bubbles_layout.setContentsMargins(12, 12, 12, 12)
        self.bubbles_layout.setSpacing(0)
        self.bubbles_layout.addStretch()
        self.chat_scroll.setWidget(self.chat_bubbles)

        input_row = QHBoxLayout()
        input_row.setContentsMargins(10, 8, 10, 10)
        input_row.setSpacing(8)

        self.chat_input = QTextEdit()
        self.chat_input.setObjectName("chatInput")
        self.chat_input.setPlaceholderText(
            "输入指令，如：推荐 5万 主板\n"
            "买入 5万 21.9 易点天下301171\n"
            "卖出 301171 / 持仓 / 历史"
        )
        self.chat_input.setFixedHeight(56)
        self.chat_input.keyPressEvent = self._on_chat_key

        send_btn = QPushButton("发送")
        send_btn.setObjectName("primaryBtn")
        send_btn.setFixedSize(64, 36)
        send_btn.clicked.connect(self._on_send)

        input_row.addWidget(self.chat_input)
        input_row.addWidget(send_btn)
        chat_layout.addLayout(input_row)
        chat_layout.insertWidget(0, self.chat_scroll, 1)

        layout.addWidget(self.chat_container)
        return page

    def _on_chat_key(self, event):
        if event.key() == Qt.Key_Return and not event.modifiers():
            self._on_send()
        else:
            QTextEdit.keyPressEvent(self.chat_input, event)

    def _on_send(self):
        text = self.chat_input.toPlainText().strip()
        if not text:
            return
        self.chat_input.clear()
        self._append_chat(f"🧑 {self.username}", text)

        try:
            result = self._process_command(text)
            if result is not None:
                self._append_chat("🤖 推票助手", result)
        except Exception as e:
            self._append_chat("🤖 推票助手", f"⚠ 错误: {str(e)}")

    def _append_chat(self, sender, msg):
        from datetime import datetime
        now = datetime.now().strftime('%H:%M')
        is_dark = self.current_theme != "浅色主题"

        bubble = QFrame()
        row = QHBoxLayout(bubble)
        row.setContentsMargins(0, 8, 0, 8)

        # 时间标签，最左侧
        time_lbl = QLabel(f"<span style='color:#8899aa; font-size:10px;'>{now}</span>")
        time_lbl.setFixedWidth(40)
        time_lbl.setAlignment(Qt.AlignTop)
        time_lbl.setStyleSheet("background: transparent;")

        if sender.startswith("🧑"):
            alias = sender.replace("🧑", "").strip()
            row.addWidget(time_lbl)
            row.addStretch()
            inner = QFrame()
            inner.setObjectName("userBubble")
            inner.setStyleSheet(
                "QFrame#userBubble {"
                "background-color:#4a90d9; border-radius:20px;"
                "padding:12px 16px; border:none;"
                "}"
            )
            inner.setMaximumWidth(400)
            il = QVBoxLayout(inner)
            il.setContentsMargins(0, 0, 0, 0)
            il.setSpacing(4)
            hdr = QLabel(f"<span style='color:#a8c8f0; font-size:11px;'>{alias}</span>")
            hdr.setStyleSheet("background: transparent;")
            txt = QLabel(msg)
            txt.setWordWrap(True)
            txt.setStyleSheet("color:#ffffff; font-size:14px; background:transparent;")
            il.addWidget(hdr)
            il.addWidget(txt)
            row.addWidget(inner)

        elif sender.startswith("🤖"):
            alias = sender.replace("🤖", "").strip()
            bg = "#f0f4f8" if not is_dark else "#2a2e38"
            color = "#2c3e50" if not is_dark else "#d4d8e0"
            hdr_color = "#8899aa" if not is_dark else "#6a7a8a"
            row.addWidget(time_lbl)
            inner = QFrame()
            inner.setObjectName("aiBubble")
            inner.setStyleSheet(
                f"QFrame#aiBubble {{"
                f"background-color:{bg}; border-radius:20px;"
                f"padding:12px 16px; border:none;"
                f"}}"
            )
            inner.setMaximumWidth(400)
            il = QVBoxLayout(inner)
            il.setContentsMargins(0, 0, 0, 0)
            il.setSpacing(4)
            hdr = QLabel(f"<span style='color:{hdr_color}; font-size:11px;'>{alias}</span>")
            hdr.setStyleSheet("background: transparent;")
            txt = QLabel(msg)
            txt.setWordWrap(True)
            txt.setStyleSheet(f"color:{color}; font-size:14px; background:transparent;")
            il.addWidget(hdr)
            il.addWidget(txt)
            row.addWidget(inner)
            row.addStretch()

        else:
            row.addStretch()
            inner = QFrame()
            inner.setStyleSheet(
                "background-color:#e9ecef; border-radius:12px; padding:8px 16px; border:none;"
            )
            il = QVBoxLayout(inner)
            il.setContentsMargins(0, 0, 0, 0)
            txt = QLabel(msg)
            txt.setStyleSheet("color:#6c7a89; font-size:12px; background:transparent;")
            il.addWidget(txt)
            row.addWidget(inner)
            row.addStretch()

        self.bubbles_layout.insertWidget(self.bubbles_layout.count() - 1, bubble)
        QTimer.singleShot(30, lambda:
            self.chat_scroll.verticalScrollBar().setValue(
                self.chat_scroll.verticalScrollBar().maximum()))

    def _show_welcome(self):
        if self.bubbles_layout.count() > 1:
            return
        is_dark = self.current_theme != "浅色主题"
        text_c = "#d4d8e0" if is_dark else "#2c3e50"
        sub_c = "#8899aa"
        card_bg = "#242830" if is_dark else "#ffffff"
        line_c = "#3a4048" if is_dark else "#e9ecef"

        w = QWidget()
        wl = QVBoxLayout(w)
        wl.setContentsMargins(8, 8, 8, 8)

        hdr = QLabel(
            "<div style='text-align:center; padding:24px 0 12px;'>"
            "<div style='font-size:36px;'>🚀</div>"
            f"<div style='font-size:20px; font-weight:700; color:{text_c}; margin-top:8px;'>欢迎使用推票助手</div>"
            f"<div style='font-size:13px; color:{sub_c}; margin-top:4px;'>晟创科技 · 学弟实时推票 · 员工一键跟买</div>"
            "</div>"
        )
        hdr.setWordWrap(True)
        wl.addWidget(hdr)

        card = QFrame()
        card.setObjectName("welcomeCard")
        card.setStyleSheet(
            f"QFrame#welcomeCard {{"
            f"background-color:{card_bg}; border-radius:14px;"
            f"border:1px solid {line_c};}}"
        )
        cl = QVBoxLayout(card)
        cl.setContentsMargins(18, 18, 20, 18)
        cl.setSpacing(8)
        cl.addWidget(QLabel(
            f"<span style='font-size:14px; font-weight:600; color:{text_c};'>📖 使用指南</span>"
        ))
        guide_items = [
            "<b style='color:#4a90d9;'>推荐 5万 主板</b> 请求学弟推票",
            "<b style='color:#4a90d9;'>买入 5万 21.9 易点天下301171</b> 带价格买入",
            "<b style='color:#4a90d9;'>卖出 301171</b> 持仓页点击卖出按钮",
            "<b style='color:#4a90d9;'>持仓</b> 查看持仓+盈亏",
            "<b style='color:#4a90d9;'>历史</b> 买入/卖出历史",
        ]
        for item in guide_items:
            lb = QLabel(f"<span style='font-size:13px; color:{sub_c}; line-height:2;'>{item}</span>")
            lb.setWordWrap(True)
            cl.addWidget(lb)
        wl.addWidget(card)

        footer = QLabel(
            f"<div style='text-align:center; font-size:12px; color:{sub_c}; padding:8px 0;'>"
            f"左侧导航切换 · 右侧今日数据"
            f"</div>"
        )
        wl.addWidget(footer)

        self.bubbles_layout.insertWidget(self.bubbles_layout.count() - 1, w)

    def _process_command(self, text):
        parser = ChatParser()
        cmd = parser.parse(text)

        if cmd.type == "recommend":
            board = getattr(cmd, 'board', '') or ''
            amount = getattr(cmd, 'amount', 0) or 0
            r = self.api.recommend(cmd.query, board=board, amount=amount)
            if r.get('ok'):
                stocks = r.get('stocks', [])
                if not stocks:
                    return "暂无推荐"
                header = f"📊 {board} 推荐（{amount}万仓位）:" if board else "📊 推荐股票:"
                lines = [header]
                for s in stocks:
                    lines.append(f"• {s['code']} {s['name']} （{s.get('board','')}） {s.get('reason','')}")
                return "\n".join(lines)
            return "获取推荐失败"

        elif cmd.type == "buy":
            buy_price = getattr(cmd, 'buy_price', 0) or 0
            r = self.api.add_position(cmd.stock_code, cmd.stock_name, cmd.amount, cmd.board, buy_price)
            if r.get('ok'):
                self._load_positions()
                self._load_history(reset=True)
                self._load_right_panel()
                price_str = f"@{buy_price}" if buy_price else f"市价@{r.get('price','')}"
                return f"✅ 已买入 {cmd.stock_name}({cmd.stock_code}) {cmd.amount}万 {price_str}"
            return f"买入失败: {r.get('error','')}"

        elif cmd.type == "sell":
            sell_price = getattr(cmd, 'sell_price', 0) or 0
            if cmd.stock_code:
                if sell_price > 0:
                    self._do_sell_direct(cmd.stock_code, cmd.stock_name or cmd.stock_code, sell_price)
                else:
                    self._do_sell_with_dialog(cmd.stock_code, cmd.stock_name)
            else:
                return "请提供股票代码，如：卖出 301171 42.5"
            return None

        elif cmd.type == "positions":
            self._on_nav(1)
            return None

        elif cmd.type == "history":
            self._on_nav(2)
            return None

        return (
            "未知指令。支持：\n"
            "• 推荐 5万 主板\n"
            "• 买入 5万 21.9 易点天下301171\n"
            "• 卖出 301171\n"
            "• 持仓 / 历史"
        )

    def _do_sell_with_dialog(self, code, name):
        """弹出卖出价输入框"""
        sell_price, ok = QInputDialog.getDouble(
            self, "卖出确认",
            f"请输入 {name}({code}) 卖出价格：",
            value=0.00, min=0.01, max=9999.99, decimals=2
        )
        if not ok or sell_price <= 0:
            return
        self._do_sell_direct(code, name, sell_price)

    def _do_sell_direct(self, code, name, sell_price):
        r = self.api.sell(code, sell_price)
        if r.get('ok'):
            self._append_chat("🤖 系统", f"✅ 已卖出 {name}({code}) @{sell_price}")
            self._load_positions()
            self._load_sell_history(reset=True)
            self._load_right_panel()
        else:
            self._append_chat("🤖 系统", f"卖出失败: {r.get('error','')}")

    # ============================================================
    #  持仓页 - 含持仓天数 + 盈亏
    # ============================================================
    def _build_position_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("我的持仓")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        self.pos_table = QTableWidget()
        self.pos_table.setColumnCount(9)
        self.pos_table.setHorizontalHeaderLabels([
            "代码", "名称", "板块", "买入价", "现价", "金额(万)", "持仓天数", "盈亏", "操作"
        ])
        self.pos_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.pos_table.verticalHeader().setVisible(False)
        self.pos_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.pos_table.setSelectionBehavior(QTableWidget.SelectRows)

        layout.addWidget(self.pos_table)
        return page

    def _load_positions(self):
        r = self.api.get_positions()
        stocks = r.get('stocks', []) if r.get('ok') else []
        self.pos_table.setRowCount(len(stocks))

        from datetime import datetime, date
        today = date.today()

        for i, s in enumerate(stocks):
            code = s.get('code', '')
            name = s.get('name', '')
            board = s.get('board', '')
            buy_price = s.get('buy_price', 0)
            amount = s.get('amount', '')
            cur_price = s.get('current_price', 0)
            buy_time = s.get('buy_time', '')

            # 持仓天数
            hold_days = "—"
            try:
                buy_date = datetime.strptime(buy_time[:10], '%Y-%m-%d').date()
                hold_days = str((today - buy_date).days + 1) + "天"
            except:
                pass

            # 盈亏（含手续费）
            if cur_price and buy_price:
                pnl = calc_pnl(buy_price, cur_price, float(amount))
                pnl_str = f"{'🟢' if pnl >= 0 else '🔴'}{pnl:+.0f}"
            else:
                pnl_str = "—"

            self.pos_table.setItem(i, 0, QTableWidgetItem(code))
            self.pos_table.setItem(i, 1, QTableWidgetItem(name))
            self.pos_table.setItem(i, 2, QTableWidgetItem(board))
            self.pos_table.setItem(i, 3, QTableWidgetItem(str(buy_price)))
            self.pos_table.setItem(i, 4, QTableWidgetItem(str(cur_price) if cur_price else "—"))
            self.pos_table.setItem(i, 5, QTableWidgetItem(str(amount)))
            self.pos_table.setItem(i, 6, QTableWidgetItem(hold_days))
            self.pos_table.setItem(i, 7, QTableWidgetItem(pnl_str))

            sell_btn = QPushButton("操作（卖出）")
            sell_btn.setObjectName("smallDangerBtn")
            sell_btn.setCursor(Qt.PointingHandCursor)
            sell_btn.clicked.connect(
                lambda checked, c=code, n=name: self._do_sell_with_dialog(c, n)
            )
            self.pos_table.setCellWidget(i, 8, sell_btn)

    # ============================================================
    #  买入历史页
    # ============================================================
    def _build_history_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("买入历史")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        self.hist_table = QTableWidget()
        self.hist_table.setColumnCount(6)
        self.hist_table.setHorizontalHeaderLabels(["代码", "名称", "板块", "买入价", "金额(万)", "时间"])
        self.hist_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.hist_table.verticalHeader().setVisible(False)
        self.hist_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.hist_table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.hist_table)

        self.load_more_btn = QPushButton("加载更多")
        self.load_more_btn.setObjectName("primaryBtn")
        self.load_more_btn.clicked.connect(self._load_more_history)
        self.load_more_btn.setVisible(False)
        layout.addWidget(self.load_more_btn, alignment=Qt.AlignCenter)

        return page

    def _load_history(self, reset=False):
        if reset:
            self._history_offset = 0
            self.hist_table.setRowCount(0)

        r = self.api.get_history(offset=self._history_offset, limit=self._history_limit)
        if r.get('ok'):
            rows = r.get('rows', [])
            total = r.get('total', 0)
            current = self.hist_table.rowCount()
            self.hist_table.setRowCount(current + len(rows))
            for i, h in enumerate(rows):
                idx = current + i
                self.hist_table.setItem(idx, 0, QTableWidgetItem(h.get('code', '')))
                self.hist_table.setItem(idx, 1, QTableWidgetItem(h.get('name', '')))
                self.hist_table.setItem(idx, 2, QTableWidgetItem(h.get('board', '')))
                self.hist_table.setItem(idx, 3, QTableWidgetItem(str(h.get('buy_price', ''))))
                self.hist_table.setItem(idx, 4, QTableWidgetItem(str(h.get('amount', ''))))
                self.hist_table.setItem(idx, 5, QTableWidgetItem(h.get('time', '')))

            self._history_offset += len(rows)
            self._history_has_more = self._history_offset < total
            self.load_more_btn.setVisible(self._history_has_more)

    def _load_more_history(self):
        self._load_history(reset=False)

    # ============================================================
    #  卖出历史页
    # ============================================================
    def _build_sell_history_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("卖出历史")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        self.sell_hist_table = QTableWidget()
        self.sell_hist_table.setColumnCount(7)
        self.sell_hist_table.setHorizontalHeaderLabels([
            "代码", "名称", "买入价", "卖出价", "金额(万)", "盈亏", "时间"
        ])
        self.sell_hist_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.sell_hist_table.verticalHeader().setVisible(False)
        self.sell_hist_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.sell_hist_table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.sell_hist_table)

        return page

    def _load_sell_history(self, reset=False):
        if reset:
            self._sell_history_offset = 0
            self.sell_hist_table.setRowCount(0)

        r = self.api.get_sell_history()
        if r.get('ok'):
            rows = r.get('rows', [])
            self.sell_hist_table.setRowCount(len(rows))
            for i, h in enumerate(rows):
                self.sell_hist_table.setItem(i, 0, QTableWidgetItem(h.get('code', '')))
                self.sell_hist_table.setItem(i, 1, QTableWidgetItem(h.get('name', '')))
                self.sell_hist_table.setItem(i, 2, QTableWidgetItem(str(h.get('buy_price', ''))))
                self.sell_hist_table.setItem(i, 3, QTableWidgetItem(str(h.get('sell_price', ''))))
                self.sell_hist_table.setItem(i, 4, QTableWidgetItem(str(h.get('amount', ''))))
                pnl = h.get('profit', 0)
                pnl_str = f"{'🟢' if pnl >= 0 else '🔴'}{pnl:+.0f}"
                self.sell_hist_table.setItem(i, 5, QTableWidgetItem(pnl_str))
                self.sell_hist_table.setItem(i, 6, QTableWidgetItem(h.get('time', '')))

    # ============================================================
    #  设置页
    # ============================================================
    def _build_settings_page(self):
        page = QWidget()
        page.setObjectName("settingsPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel("设置")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)
        layout.addSpacing(12)

        theme_label = QLabel("主题颜色")
        theme_label.setStyleSheet("font-size: 14px; font-weight: 600;")
        layout.addWidget(theme_label)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(THEME_NAMES)
        self.theme_combo.setCurrentText(self.current_theme)
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
        layout.addWidget(self.theme_combo)

        layout.addSpacing(16)
        save_btn = QPushButton("保存设置")
        save_btn.setObjectName("primaryBtn")
        save_btn.setFixedWidth(120)
        save_btn.clicked.connect(self._save_theme)
        layout.addWidget(save_btn)
        layout.addStretch()
        return page

    def _on_theme_changed(self, name):
        self.current_theme = name
        self._apply_theme()

    def _apply_theme(self):
        self.setStyleSheet(get_style(self.current_theme))
        self._on_right_tab(self.right_stack.currentIndex())

    def _save_theme(self):
        try:
            self.api.save_theme(self.current_theme)
        except:
            pass

    def _load_theme_pref(self):
        try:
            r = self.api.get_theme()
            if r.get('ok') and r.get('theme') in THEME_NAMES:
                self.current_theme = r.get('theme')
                self.theme_combo.setCurrentText(self.current_theme)
                self._apply_theme()
        except:
            pass

    # ============================================================
    #  右栏：真实数据
    # ============================================================
    def _build_bought_card(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        self.bought_table = QTableWidget()
        self.bought_table.setColumnCount(5)
        self.bought_table.setHorizontalHeaderLabels(["代码", "名称", "金额(万)", "买入价", "现价"])
        self.bought_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.bought_table.verticalHeader().setVisible(False)
        self.bought_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.bought_table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.bought_table)
        return w

    def _build_not_bought_card(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        self.not_bought_table = QTableWidget()
        self.not_bought_table.setColumnCount(6)
        self.not_bought_table.setHorizontalHeaderLabels(["代码", "名称", "板块", "推荐价", "现价", "涨跌幅"])
        self.not_bought_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.not_bought_table.verticalHeader().setVisible(False)
        self.not_bought_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.not_bought_table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.not_bought_table)
        return w

    def _build_stats_card(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 8, 8, 8)
        self.stats_label = QLabel()
        self.stats_label.setAlignment(Qt.AlignCenter)
        self.stats_label.setWordWrap(True)
        layout.addWidget(self.stats_label)
        layout.addStretch()
        return w

    def _load_right_panel(self):
        """从 /api/daily/summary 拉取实时数据填充右栏"""
        r = self.api.get_daily_summary()
        if not r.get('ok'):
            return

        bought = r.get('bought', [])
        not_bought = r.get('not_bought', [])
        total_pnl = r.get('total_pnl', 0)

        self._load_bought_table(bought)
        self._load_not_bought_table(not_bought)
        self._render_stats(total_pnl, len(bought), len(not_bought))

    def _load_bought_table(self, items):
        self.bought_table.setRowCount(len(items))
        for i, item in enumerate(items):
            self.bought_table.setItem(i, 0, QTableWidgetItem(item.get('code', '')))
            self.bought_table.setItem(i, 1, QTableWidgetItem(item.get('name', '')))
            self.bought_table.setItem(i, 2, QTableWidgetItem(str(item.get('amount', ''))))

            buy_price = item.get('buy_price', 0)
            self.bought_table.setItem(i, 3, QTableWidgetItem(str(buy_price) if buy_price else "—"))

            cur_price = item.get('current_price', 0)
            self.bought_table.setItem(i, 4, QTableWidgetItem(str(cur_price) if cur_price else "—"))

    def _load_not_bought_table(self, items):
        self.not_bought_table.setRowCount(len(items))
        for i, item in enumerate(items):
            self.not_bought_table.setItem(i, 0, QTableWidgetItem(item.get('code', '')))
            self.not_bought_table.setItem(i, 1, QTableWidgetItem(item.get('name', '')))
            self.not_bought_table.setItem(i, 2, QTableWidgetItem(item.get('board', '')))

            rec_price = item.get('rec_price', 0)
            self.not_bought_table.setItem(i, 3, QTableWidgetItem(str(rec_price) if rec_price else "—"))

            cur_price = item.get('current_price', 0)
            self.not_bought_table.setItem(i, 4, QTableWidgetItem(str(cur_price) if cur_price else "—"))

            change_pct = item.get('change_pct', 0)
            pct_color = '#27ae60' if change_pct >= 0 else '#e74c3c'
            pct_item = QTableWidgetItem(f"{change_pct:+.2f}%" if change_pct else "—")
            pct_item.setForeground(QColor(pct_color))
            self.not_bought_table.setItem(i, 5, pct_item)

    def _render_stats(self, total_pnl, bought_count, not_bought_count):
        self.stats_label.setText(
            f"<div style='text-align:center; padding:12px;'>"
            f"<div style='font-size:28px; font-weight:800; "
            f"color:{'#27ae60' if total_pnl >= 0 else '#e74c3c'};'>"
            f"{total_pnl:+.0f}</div>"
            f"<div style='font-size:11px; color:#8899aa;'>今日盈亏(元)</div>"
            f"<div style='margin-top:10px; font-size:12px; color:#6c7a89;'>"
            f"已买入 {bought_count} 只 · 未买入 {not_bought_count} 只</div>"
            f"</div>"
        )

    def _on_right_tab(self, idx):
        btns = [self.btn_bought, self.btn_not_bought, self.btn_today]
        for i, b in enumerate(btns):
            b.setChecked(i == idx)
        self.right_stack.setCurrentIndex(idx)

    # ============================================================
    #  导航切换
    # ============================================================
    def _on_nav(self, idx):
        for b in self.nav_btns:
            b.setChecked(False)
        if idx < 4:
            self.nav_btns[idx].setChecked(True)

        self.mid_stack.setCurrentIndex(idx)

        if idx == 0:
            self._show_welcome()
        elif idx == 1:
            self._load_positions()
        elif idx == 2:
            self._load_history(reset=True)
        elif idx == 3:
            self._load_sell_history(reset=True)

    def _on_logout(self):
        reply = QMessageBox.question(
            self, "退出登录", "确定要退出登录吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.login_signal.emit()

    # ============================================================
    #  定时刷新
    # ============================================================
    def _refresh(self):
        cur = self.mid_stack.currentIndex()
        if cur == 1:
            self._load_positions()
        elif cur == 2:
            self._load_history(reset=True)
        elif cur == 3:
            self._load_sell_history(reset=True)
        self._load_right_panel()
