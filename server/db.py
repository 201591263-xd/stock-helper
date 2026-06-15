"""
中心数据库 - SQLite 单文件
表: users, buy_history, recommendations, sectors
新增: board 字段（主板/创业板/科创板）, amount 字段（买入金额）
"""
import sqlite3, os, datetime, hashlib

DB_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(DB_DIR, "stock_data.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

from contextlib import contextmanager

@contextmanager
def db_conn():
    """上下文管理器，确保连接正确关闭"""
    conn = get_conn()
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            client_ip TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            last_login TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS buy_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            stock_code TEXT NOT NULL,
            stock_name TEXT NOT NULL,
            buy_price REAL NOT NULL,
            amount REAL DEFAULT 0,
            board TEXT DEFAULT '',
            buy_time TEXT DEFAULT (datetime('now','localtime')),
            sector TEXT DEFAULT '',
            note TEXT DEFAULT ''
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT NOT NULL,
            stock_name TEXT NOT NULL,
            sector TEXT NOT NULL,
            board TEXT DEFAULT '',
            recommend_price REAL,
            recommend_date TEXT DEFAULT (date('now','localtime')),
            recommended_by TEXT DEFAULT ''
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS sector_daily (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sector TEXT NOT NULL,
            used_date TEXT DEFAULT (date('now','localtime')),
            stock_code TEXT,
            username TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT NOT NULL,
            buy_price REAL NOT NULL,
            current_price REAL,
            buy_date TEXT,
            feedback_date TEXT DEFAULT (datetime('now','localtime')),
            is_win INTEGER DEFAULT 0,
            note TEXT DEFAULT ''
        )
    ''')

    # 兼容旧表：无 amount/board 列时自动添加
    try:
        c.execute('ALTER TABLE buy_history ADD COLUMN amount REAL DEFAULT 0')
    except: pass
    try:
        c.execute('ALTER TABLE buy_history ADD COLUMN board TEXT DEFAULT ""')
    except: pass
    try:
        c.execute('ALTER TABLE recommendations ADD COLUMN board TEXT DEFAULT ""')
    except: pass

    # 兼容旧表：无 client_ip 列
    try:
        c.execute('ALTER TABLE users ADD COLUMN client_ip TEXT DEFAULT ""')
    except: pass
    c.execute('CREATE INDEX IF NOT EXISTS idx_buy_user ON buy_history(username)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_buy_time ON buy_history(buy_time)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_rec_date ON recommendations(recommend_date)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_rec_code ON recommendations(stock_code)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_sector_date ON sector_daily(used_date, sector)')

    conn.commit()
    conn.close()

# ========== 用户 ==========

def user_login(username: str, password: str) -> bool:
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT password_hash FROM users WHERE username=?', (username,))
    row = c.fetchone()
    if row:
        pw = hashlib.sha256(password.encode()).hexdigest()
        if pw == row['password_hash']:
            c.execute('UPDATE users SET last_login=datetime("now","localtime") WHERE username=?', (username,))
            conn.commit()
            conn.close()
            return True
    conn.close()
    return False

def user_register(username: str, password: str, client_ip: str = '') -> str:
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT username FROM users WHERE username=?', (username,))
    if c.fetchone():
        conn.close()
        return '用户名已存在'
    # IP 绑定限制：同一 IP 最多注册 1 个账号
    if client_ip:
        c.execute('SELECT COUNT(*) as cnt FROM users WHERE client_ip=?', (client_ip,))
        if c.fetchone()['cnt'] >= 1:
            conn.close()
            return '该设备已注册过账号'
    pw = hashlib.sha256(password.encode()).hexdigest()
    c.execute('INSERT INTO users (username, password_hash, client_ip) VALUES (?,?,?)', (username, pw, client_ip))
    conn.commit()
    conn.close()
    return ''

# ========== 买入记录 ==========

def add_buy_record(username: str, stock_code: str, stock_name: str, buy_price: float, amount: float = 0, sector: str = '', board: str = ''):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        'INSERT INTO buy_history (username, stock_code, stock_name, buy_price, amount, sector, board) VALUES (?,?,?,?,?,?,?)',
        (username, stock_code, stock_name, buy_price, amount, sector, board)
    )
    conn.commit()
    conn.close()

def get_buy_history(username: str = '', limit: int = 200):
    conn = get_conn()
    c = conn.cursor()
    if username:
        c.execute('SELECT * FROM buy_history WHERE username=? ORDER BY buy_time DESC LIMIT ?', (username, limit))
    else:
        c.execute('SELECT * FROM buy_history ORDER BY buy_time DESC LIMIT ?', (limit,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def get_recently_bought_codes(username: str, days: int = 3):
    """返回最近N天内买入过的股票代码列表，用于排除推荐"""
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        SELECT DISTINCT stock_code FROM buy_history
        WHERE username = ?
        AND buy_time >= datetime('now', 'localtime', ?)
    ''', (username, f'-{days} days'))
    codes = [r['stock_code'] for r in c.fetchall()]
    conn.close()
    return codes


def get_buy_history_paginated(username: str = '', offset: int = 0, limit: int = 20):
    """分页买入历史，返回 (rows, total_count)"""
    conn = get_conn()
    c = conn.cursor()

    if username:
        c.execute('SELECT COUNT(*) as cnt FROM buy_history WHERE username=?', (username,))
        total = c.fetchone()['cnt']
        c.execute(
            'SELECT * FROM buy_history WHERE username=? ORDER BY buy_time DESC LIMIT ? OFFSET ?',
            (username, limit, offset)
        )
    else:
        c.execute('SELECT COUNT(*) as cnt FROM buy_history')
        total = c.fetchone()['cnt']
        c.execute('SELECT * FROM buy_history ORDER BY buy_time DESC LIMIT ? OFFSET ?', (limit, offset))

    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows, total


# ========== 用户偏好 ==========


def save_user_pref(username: str, key: str, value: str):
    conn = get_conn()
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS user_prefs (username TEXT, key TEXT, value TEXT, PRIMARY KEY(username, key))')
    c.execute('INSERT OR REPLACE INTO user_prefs (username, key, value) VALUES (?,?,?)', (username, key, value))
    conn.commit()
    conn.close()


def get_user_pref(username: str, key: str) -> str:
    conn = get_conn()
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS user_prefs (username TEXT, key TEXT, value TEXT, PRIMARY KEY(username, key))')
    c.execute('SELECT value FROM user_prefs WHERE username=? AND key=?', (username, key))
    row = c.fetchone()
    conn.close()
    return row['value'] if row else ''

def get_all_positions():
    """所有持仓聚合"""
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        SELECT stock_code, stock_name, MAX(buy_price) as buy_price,
               SUM(amount) as total_amount, MAX(buy_time) as buy_time,
               MAX(board) as board,
               GROUP_CONCAT(DISTINCT username) as holders
        FROM buy_history
        GROUP BY stock_code
        ORDER BY buy_time DESC
    ''')
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def get_user_positions(username: str):
    """个人持仓聚合"""
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        SELECT stock_code, stock_name, MAX(buy_price) as buy_price,
               SUM(amount) as total_amount, MAX(buy_time) as buy_time,
               MAX(board) as board
        FROM buy_history WHERE username=?
        GROUP BY stock_code ORDER BY buy_time DESC
    ''', (username,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

# ========== 板块轮动 ==========

def get_available_sectors():
    """返回今日仍有候选余量的板块（每板块每天最多15次推荐）"""
    MAX_PER_SECTOR = 15
    today = datetime.date.today().isoformat()
    ALL_SECTORS = ['消费', '科技', '新能源', '医药', '金融', '周期', '军工', 'AI']
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT sector, COUNT(*) as cnt FROM sector_daily WHERE used_date=? GROUP BY sector HAVING cnt >= ?', (today, MAX_PER_SECTOR))
    used_up = {r['sector'] for r in c.fetchall()}
    conn.close()
    return [s for s in ALL_SECTORS if s not in used_up]

def mark_sector_used(sector: str, stock_code: str, username: str):
    today = datetime.date.today().isoformat()
    conn = get_conn()
    c = conn.cursor()
    c.execute('INSERT INTO sector_daily (sector, used_date, stock_code, username) VALUES (?,?,?,?)', (sector, today, stock_code, username))
    conn.commit()
    conn.close()

def reset_daily():
    today = datetime.date.today().isoformat()
    conn = get_conn()
    c = conn.cursor()
    c.execute('DELETE FROM sector_daily WHERE used_date < ?', (today,))
    conn.commit()
    conn.close()

# ========== 推荐记录 ==========

def add_recommendation(stock_code: str, stock_name: str, sector: str, price: float, username: str, board: str = ''):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        'INSERT INTO recommendations (stock_code, stock_name, sector, recommend_price, recommended_by, board) VALUES (?,?,?,?,?,?)',
        (stock_code, stock_name, sector, price, username, board)
    )
    conn.commit()
    conn.close()

def get_today_recommendations(username: str = ''):
    today = datetime.date.today().isoformat()
    conn = get_conn()
    c = conn.cursor()
    if username:
        c.execute('SELECT * FROM recommendations WHERE recommend_date=? AND recommended_by=? ORDER BY id DESC', (today, username))
    else:
        c.execute('SELECT * FROM recommendations WHERE recommend_date=? ORDER BY id DESC', (today,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

# ========== 反馈与胜率 ==========

def record_feedback(stock_code: str, buy_price: float, current_price: float = 0, is_win: int = 0, note: str = ''):
    """记录买入后的实际涨跌反馈"""
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        'INSERT INTO feedback (stock_code, buy_price, current_price, buy_date, is_win, note) VALUES (?,?,?,date("now","localtime"),?,?)',
        (stock_code, buy_price, current_price, is_win, note)
    )
    conn.commit()
    conn.close()


def feedback_stats():
    """统计胜率：胜/负/总"""
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT COUNT(*) as total, SUM(is_win) as wins FROM feedback WHERE is_win IS NOT NULL')
    row = c.fetchone()
    total = row['total'] or 0
    wins = row['wins'] or 0
    losses = total - wins
    win_rate = round(wins / total * 100, 1) if total > 0 else 0
    conn.close()
    return {'total': total, 'wins': wins, 'losses': losses, 'win_rate': win_rate}


def get_stock_feedback(codes: list):
    """按股票代码批量查询历史胜率（用于 Hermes 记忆注入）"""
    if not codes:
        return []
    placeholders = ','.join('?' * len(codes))
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        f'SELECT f.stock_code, MAX(b.stock_name) as stock_name, COUNT(*) as total, SUM(f.is_win) as wins '
        f'FROM feedback f LEFT JOIN buy_history b ON f.stock_code=b.stock_code '
        f'WHERE f.stock_code IN ({placeholders}) AND f.is_win IS NOT NULL '
        f'GROUP BY f.stock_code',
        codes
    )
    rows = []
    for r in c.fetchall():
        total = r['total'] or 0
        wins = r['wins'] or 0
        rows.append({
            'stock_code': r['stock_code'],
            'stock_name': r['stock_name'] or r['stock_code'],
            'total': total,
            'wins': wins,
            'win_rate': round(wins / total * 100, 1)
        })
    conn.close()
    return rows

# ========== 卖出记录 ==========

def record_sell(username: str, stock_code: str, stock_name: str, sell_price: float, buy_price: float, amount: float, board: str = ''):
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS sell_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            stock_code TEXT NOT NULL,
            stock_name TEXT NOT NULL,
            buy_price REAL NOT NULL,
            sell_price REAL NOT NULL,
            amount REAL DEFAULT 0,
            board TEXT DEFAULT '',
            sell_time TEXT DEFAULT (datetime('now','localtime'))
        )
    ''')
    c.execute('INSERT INTO sell_records (username, stock_code, stock_name, buy_price, sell_price, amount, board) VALUES (?,?,?,?,?,?,?)',
              (username, stock_code, stock_name, buy_price, sell_price, amount, board))
    conn.commit()
    conn.close()


def get_sell_history(username: str = '', limit: int = 100):
    conn = get_conn()
    c = conn.cursor()
    if username:
        c.execute('SELECT * FROM sell_records WHERE username=? ORDER BY sell_time DESC LIMIT ?', (username, limit))
    else:
        c.execute('SELECT * FROM sell_records ORDER BY sell_time DESC LIMIT ?', (limit,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_daily_summary(username: str):
    """今日统计：已买入/未买入"""
    today = datetime.date.today().isoformat()
    conn = get_conn()
    c = conn.cursor()

    c.execute(
        'SELECT stock_code, stock_name, SUM(amount) as total_amount, MAX(buy_price) as buy_price, MAX(board) as board, MAX(buy_time) as buy_time '
        'FROM buy_history WHERE username=? AND date(buy_time)=? GROUP BY stock_code ORDER BY buy_time DESC',
        (username, today)
    )
    bought = [dict(r) for r in c.fetchall()]

    c.execute(
        'SELECT DISTINCT stock_code, stock_name, recommend_price, board FROM recommendations WHERE recommend_date=?',
        (today,)
    )
    recs = {r['stock_code']: dict(r) for r in c.fetchall()}

    bought_codes = {b['stock_code'] for b in bought}
    not_bought = [recs[code] for code in recs if code not in bought_codes]

    conn.close()
    return {'bought': bought, 'not_bought': not_bought, 'today': today}


init_db()
