"""
客户端 API 通信模块 - v4.0
"""
import requests


class ApiClient:
    def __init__(self, server_url='http://127.0.0.1:5128', username=''):
        self.server_url = server_url.rstrip('/')
        self.username = username

    def _post(self, path, data=None, timeout=45):
        try:
            resp = requests.post(f'{self.server_url}{path}', json=data or {}, timeout=timeout)
            return resp.json()
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    def _get(self, path, timeout=5):
        try:
            resp = requests.get(f'{self.server_url}{path}', timeout=timeout)
            return resp.json()
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    # ---- 账户 ----
    def login(self, username, password):
        return self._post('/api/login', {'username': username, 'password': password})

    def register(self, username, password):
        return self._post('/api/register', {'username': username, 'password': password})

    # ---- 推荐 ----
    def recommend(self, query="", board="", amount=0):
        return self._post('/api/recommend', {
            'username': self.username,
            'query': query,
            'board': board,
            'amount': amount
        })

    # ---- 持仓 ----
    def get_positions(self):
        return self._post('/api/positions', {'username': self.username})

    def add_position(self, stock_code, stock_name, amount, board="", buy_price=0):
        return self._post('/api/position/add', {
            'username': self.username,
            'stock_code': stock_code,
            'stock_name': stock_name,
            'amount': amount,
            'board': board,
            'buy_price': buy_price
        })

    def remove_position(self, stock_code):
        return self._post('/api/position/remove', {
            'username': self.username,
            'stock_code': stock_code
        })

    # ---- 卖出 ----
    def sell(self, stock_code, sell_price):
        return self._post('/api/sell', {
            'username': self.username,
            'stock_code': stock_code,
            'sell_price': sell_price
        })

    def get_sell_history(self):
        return self._post('/api/sell/history', {'username': self.username})

    # ---- 买入历史（分页） ----
    def get_history(self, offset=0, limit=20):
        return self._post('/api/history', {
            'username': self.username,
            'offset': offset,
            'limit': limit
        })

    # ---- 每日统计 ----
    def get_daily_summary(self):
        return self._post('/api/daily/summary', {'username': self.username})

    # ---- 主题 ----
    def save_theme(self, theme_name):
        return self._post('/api/theme/save', {
            'username': self.username,
            'theme': theme_name
        })

    def get_theme(self):
        return self._post('/api/theme/get', {'username': self.username})
