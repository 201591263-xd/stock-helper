"""
推票引擎服务器 - Flask REST API v2026.06.08-hc
端口: 5128
新增: 主板/创业板分类, 买入金额
"""
from flask import Flask, request, jsonify
import datetime, os, sys, re, subprocess, requests

print("===== MODULE SERVER LOADED V20260608-HC =====", flush=True)

sys.path.insert(0, os.path.dirname(__file__))
import db
from ashare_quote import get_realtime_quote, get_batch_quotes

# 文件日志（exe 无控制台时的调试手段）
_LOG_PATH = os.path.join(os.path.expanduser('~'), '推票助手_debug.log')
def _log(msg):
    ts = datetime.datetime.now().strftime('%H:%M:%S')
    try:
        with open(_LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(f'[{ts}] {msg}\n')
    except:
        pass  # 静默失败，不阻碍主流程

# DEBUG: confirm module loaded in exe
try:
    with open(os.path.join(os.path.expanduser('~'), 'server_module_loaded.txt'), 'w') as _f:
        _f.write('v2026.06.08-hc LOADED\n')
except:
    pass

FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/35378857-c303-44c0-996e-bb9f3f0aa197"
HERMES_EXE = r"C:\Program Files\Tencent\Marvis\MarvisAgent\1.0.1100.188\runtime\python311\Scripts\hermes.exe"
HERMES_CWD = r"C:\Program Files\Tencent\Marvis\MarvisAgent\1.0.1100.188\runtime\python311"

_VERSION_MARKER = "V20260608-HC-FIX"
app = Flask(__name__)
app.config['VERSION_MARKER'] = _VERSION_MARKER

# 全局异常兜底，防止未捕获异常导致进程崩溃
@app.errorhandler(Exception)
def handle_exception(e):
    import traceback
    traceback.print_exc()
    return jsonify({'error': str(e)}), 500

@app.errorhandler(500)
def handle_500(e):
    return jsonify({'error': '服务器内部错误'}), 500

def classify_board(code: str) -> str:
    """根据代码前缀判断板块"""
    if code.startswith('60') or code.startswith('00'):
        return '主板'
    elif code.startswith('30'):
        return '创业板'
    elif code.startswith('68'):
        return '科创板'
    return ''

# 手续费常量
COMMISSION_RATE = 0.00025   # 万2.5 佣金
TRANSFER_RATE  = 0.00001    # 过户费
STAMP_RATE     = 0.001      # 印花税（仅卖出）

def calc_pnl(buy_price: float, sell_price: float, amount_wan: float) -> float:
    """
    含手续费的实际净利润
    amount_wan: 买入金额(万元)
    """
    N = amount_wan * 10000 / buy_price   # 持股数量(股)
    buy_total = N * buy_price
    buy_fee   = max(buy_total * COMMISSION_RATE, 5) + buy_total * TRANSFER_RATE
    sell_total = N * sell_price
    sell_fee   = max(sell_total * COMMISSION_RATE, 5) + sell_total * TRANSFER_RATE + sell_total * STAMP_RATE
    return round(sell_total - buy_total - (buy_fee + sell_fee), 2)

def is_trading_time():
    now = datetime.datetime.now()
    if now.weekday() >= 5:
        return False
    t = now.time()
    return (datetime.time(9, 30) <= t <= datetime.time(11, 30)) or \
           (datetime.time(13, 0) <= t <= datetime.time(15, 0))

# ========== 板块行情排序 ==========

# 旧版硬编码池（保留作为兜底 + 主板/科创板使用）
FALLBACK_POOL = {
    '科技': [('000063','中兴通讯','5G龙头大盘'), ('002415','海康威视','AI视觉龙头'), ('603501','韦尔股份','CIS芯片'), ('603019','中科曙光','算力中军'), ('000977','浪潮信息','AI服务器中盘'), ('000938','紫光股份','ICT中盘'), ('600584','长电科技','封测中盘')],
    'AI': [('002230','科大讯飞','AI大模型中盘'), ('300418','昆仑万维','AI+游戏出海'), ('300229','拓尔思','NLP中盘'), ('688256','寒武纪','AI芯片龙头'), ('300502','新易盛','光模块龙头'), ('300496','中科创达','智能OS中盘'), ('688088','虹软科技','视觉AI中小')],
    '消费': [('600519','贵州茅台','白酒龙头大盘'), ('600887','伊利股份','乳业龙头'), ('603345','安井食品','速冻中盘'), ('603517','绝味食品','卤制品中盘'), ('002568','百润股份','预调酒中盘'), ('600872','中炬高新','调味品中盘'), ('002507','涪陵榨菜','消费品中盘')],
    '新能源': [('300750','宁德时代','电池龙头大盘'), ('002594','比亚迪','新能源整车'), ('300274','阳光电源','逆变器龙头'), ('300073','当升科技','正极中盘'), ('603659','璞泰来','负极中盘'), ('002812','恩捷股份','隔膜龙头'), ('002709','天赐材料','电解液中盘')],
    '医药': [('600276','恒瑞医药','创新药龙头'), ('300760','迈瑞医疗','器械龙头大盘'), ('603259','药明康德','CXO龙头'), ('002821','凯莱英','CDMO中盘'), ('300759','康龙化成','CRO中盘'), ('603127','昭衍新药','安评中盘'), ('300363','博腾股份','CDMO小盘弹性')],
    '金融': [('601318','中国平安','保险龙头大盘'), ('600036','招商银行','股份行龙头'), ('300059','东方财富','互联网券商'), ('300803','指南针','券商IT中盘'), ('688318','财富趋势','通达信中盘'), ('603383','顶点软件','金融IT小盘'), ('300773','拉卡拉','支付中盘')],
    '军工': [('600760','中航沈飞','战斗机龙头'), ('600893','航发动力','发动机龙头'), ('688297','中无人机','无人机中盘'), ('688239','航宇科技','航空锻件中小'), ('300855','图南股份','高温合金中小'), ('688281','华秦科技','隐身材料中小'), ('688375','国博电子','TR组件中盘')],
    '周期': [('601899','紫金矿业','铜金龙头大盘'), ('603799','华友钴业','钴+前驱体中盘'), ('002738','中矿资源','锂矿中盘'), ('002240','盛新锂能','锂盐中盘'), ('002756','永兴材料','锂云母中盘'), ('002460','赣锋锂业','锂资源龙头'), ('600585','海螺水泥','水泥龙头')],
}

def get_pool(board_filter=''):
    """
    获取股票池：创业板用硬编码池，主板/科创板用兜底池
    """
    if board_filter == '创业板':
        return _get_cyb_pool()
    return {k: list(v) for k, v in FALLBACK_POOL.items()}


def _get_cyb_pool():
    """创业板股票池：硬编码 24 只标的，覆盖 8 个板块"""
    return {
        '科技': [('300750', '宁德时代', '电池龙头'), ('300274', '阳光电源', '逆变器龙头'), ('300124', '汇川技术', '工控龙头')],
        'AI': [('300033', '同花顺', 'AI+金融'), ('300624', '万兴科技', 'AI创意工具'), ('300502', '新易盛', '光模块龙头')],
        '消费': [('300908', '仲景食品', '调味品'), ('300755', '华致酒行', '酒类流通'), ('300783', '三只松鼠', '休闲零食')],
        '新能源': [('300014', '亿纬锂能', '锂电龙头'), ('300568', '星源材质', '隔膜龙头'), ('300450', '先导智能', '锂电设备')],
        '医药': [('300760', '迈瑞医疗', '医疗器械龙头'), ('300122', '智飞生物', '疫苗龙头'), ('300347', '泰格医药', 'CRO龙头')],
        '金融': [('300059', '东方财富', '互联网券商'), ('300033', '同花顺', 'AI+金融'), ('300773', '拉卡拉', '第三方支付')],
        '军工': [('300775', '三角防务', '航空锻件'), ('300699', '光威复材', '碳纤维'), ('300034', '钢研高纳', '高温合金')],
        '周期': [('300618', '寒锐钴业', '钴龙头'), ('300505', '川金诺', '磷化工'), ('300437', '清水源', '水处理')],
    }

def rank_sectors_by_performance(sectors, board_filter='', pool=None):
    """根据各板块候选股的当日平均涨跌幅排序，返回从好到差的板块列表"""
    if pool is None:
        pool = get_pool(board_filter)
    prefix_map = {'主板': ('60','00'), '创业板': ('30',), '科创板': ('68',)}
    prefixes = prefix_map.get(board_filter, ())

    def _sector_score(sector):
        candidates = pool.get(sector, [])
        if board_filter and prefixes:
            candidates = [(c, n, r) for c, n, r in candidates if c.startswith(prefixes)]
        if not candidates:
            return (sector, -999, 0)

        codes = [c for c, _, _ in candidates]
        quotes = get_batch_quotes(codes)
        chgs = []
        for code in codes:
            q = quotes.get(code, {})
            chg = q.get('change_pct', 0)
            if chg is not None:
                chgs.append(chg)
        
        avg_chg = round(sum(chgs) / len(chgs), 2) if chgs else 0
        up_count = sum(1 for c in chgs if c > 0)
        return (sector, avg_chg, up_count)

    results = []
    for sector in sectors:
        sector_name, avg_chg, up_count = _sector_score(sector)
        results.append((sector_name, avg_chg, up_count))

    results.sort(key=lambda x: (x[1], x[2]), reverse=True)
    ranked = [r[0] for r in results]

    log_lines = [f"{name}: +{avg}% ({up}up)" for name, avg, up in results if avg > -999]
    if log_lines:
        print(f"[行情排序] {' > '.join(log_lines)}")

    return ranked

def call_hermes(sector: str, exclude_codes: list, board_filter: str = '', pool=None) -> dict:
    """调用 Hermes CLI 做推票决策
    board_filter: 板块过滤（'主板'/'创业板'/'科创板'），为空则不过滤
    pool: 动态股票池，为None时使用get_pool()
    """
    import random

    if pool is None:
        pool = get_pool(board_filter)

    candidates = pool.get(sector, [('000001','平安银行','银行')])

    # 板块过滤：按代码前缀筛选
    if board_filter:
        prefix_map = {'主板': ('60','00'), '创业板': ('30',), '科创板': ('68',)}
        prefixes = prefix_map.get(board_filter, ())
        if prefixes:
            candidates = [(c, n, r) for c, n, r in candidates if c.startswith(prefixes)]
        if not candidates:
            return None  # 该板块下没有对应 board 的标的

    available = [(c, n, r) for c, n, r in candidates if c not in exclude_codes]
    if not available:
        return None

    # 先查行情，同时收集涨跌幅用于过滤
    stock_list_lines = []
    all_negative = True
    scored_candidates = []  # (code, name, reason, price, change_pct)
    for code, name, reason in available:
        q = get_realtime_quote(code)
        price = q.get('price', 0) if q else 0
        chg = q.get('change_pct', 0) if q else 0
        scored_candidates.append((code, name, reason, price, chg))
        stock_list_lines.append(f"  {code} {name} 现价{price:.2f} 涨跌幅{chg:+.2f}% 背景:{reason}")
        if chg > -1.0:
            all_negative = False

    # 过滤：有上涨票时排除跌幅超过-3%的；全跌时不排除任何票
    if not all_negative:
        scored_candidates = [(c, n, r, p, chg) for c, n, r, p, chg in scored_candidates if chg > -3.0]
        if not scored_candidates:
            return None  # 全部跌幅超-3%，该板块放弃

    # 重新生成股票行（用过滤后的list）
    stock_list_lines = [f"  {c} {n} 现价{p:.2f} 涨跌幅{chg:+.2f}% 背景:{r}" for c, n, r, p, chg in scored_candidates]

    # 注入历史记忆：每只候选股的实盘反馈
    history_section = ""
    try:
        stats = db.feedback_stats()
        stock_perf = db.get_stock_feedback(list(set(c for c, _, _ in available)))
        if stock_perf:
            perf_lines = []
            for item in stock_perf:
                perf_lines.append(f"  {item['stock_code']} {item['stock_name']}: 推{item['total']}次 胜{item['wins']}次 胜率{item['win_rate']}%")
            history_section = f"""\n\n历史实盘战绩（你之前推荐过的票）：
整体胜率 {stats['win_rate']}%（{stats['wins']}胜{stats['losses']}负 共{stats['total']}笔）
{chr(10).join(perf_lines)}"""
    except:
        pass

    # 注入历史推票记录：某人某时推了某票（buy_history + sell_records）
    rec_history = ""
    try:
        conn = db.get_conn()
        c = conn.cursor()
        c.execute('''SELECT username, stock_code, stock_name, buy_price, buy_time, amount, board 
                     FROM buy_history ORDER BY buy_time DESC LIMIT 20''')
        buys = c.fetchall()
        c.execute('''SELECT username, stock_code, stock_name, buy_price, sell_price, sell_time, board 
                     FROM sell_records ORDER BY sell_time DESC LIMIT 20''')
        sells = c.fetchall()
        conn.close()

        if buys or sells:
            rec_lines = []
            for b in buys:
                rec_lines.append(f"  {b['username']} {b['buy_time']} 推了 {b['stock_name']}({b['stock_code']}) 买入价{b['buy_price']:.2f} {b['amount']}万 {b['board'] or ''}")
            for s in sells:
                rec_lines.append(f"  {s['username']} {s['sell_time']} 卖出 {s['stock_name']}({s['stock_code']}) 买{s['buy_price']:.2f}→卖{s['sell_price']:.2f} {s['board'] or ''}")
            rec_history = f"""\n\n历史推票记录（其他人之前的推荐，参考时机和选票偏好）：
{chr(10).join(rec_lines)}"""
    except:
        pass

    # 构造 prompt 调用 Hermes
    prompt = f"""你是A股短线推票分析师。当前板块【{sector}】，候选标的如下：
{chr(10).join(stock_list_lines)}{history_section}{rec_history}

你是一个有判断力的推票分析师，不要机械地每次都推龙头，也不要永远不推龙头。根据以下框架动态决策：

【情绪周期判断】（从涨跌幅和板块热度推断）
- 冰点/退潮期（多数票跌幅>2%）：降低风险偏好，优先选中盘防御标的，避开高波动小票，龙头也可考虑
- 回暖期（多数票微涨0-2%）：均衡配置，龙头和中盘各半，选趋势刚启动的
- 高潮期（板块涨幅>3%，多票>5%）：激进选弹性小票，龙头已经涨多了不追

【选票优先级】
1. 看涨跌幅：涨幅适中（1-5%）> 涨幅过大（>7%）> 跌幅票
2. 看弹性：高潮期优先中小盘弹性票，退潮期优先龙头/中盘防御
3. 看分歧：优先当日有分歧（非缩量涨停）的票，避开一字板/秒板的一致股
4. 避免重复：历史近期已多次推荐的票，优先换新的

【核心原则】不要形成固定偏好。上周推过的龙头下周可能还是好票，上周推过的小票下周可能已经走坏。每次独立判断。

请从上述标的中推荐1只最值得买入的股票，给出代码、名称和简短理由（≤50字）。
回复格式：
推荐: 股票代码 名称
理由: xxx"""

    # 重试机制：最多3次，每次超时45s
    output = ""
    for attempt in range(3):
        try:
            result = subprocess.run(
                [HERMES_EXE, '--cli', '--yolo', '-z', prompt, 'chat'],
                capture_output=True, text=True, timeout=45,
                encoding='utf-8', errors='replace',
                cwd=HERMES_CWD
            )
            _log(f"HERMES attempt={attempt+1} rc={result.returncode} stdout_len={len(result.stdout)} stderr_len={len(result.stderr)}")
            if result.stderr.strip():
                _log(f"HERMES stderr: {result.stderr[:300]}")
            output = result.stdout.strip()
            if output:
                break
            _log(f"HERMES EMPTY OUTPUT attempt={attempt+1}")
        except subprocess.TimeoutExpired:
            _log(f"HERMES TIMEOUT attempt={attempt+1}")
        except Exception as e:
            _log(f"HERMES EXCEPTION attempt={attempt+1}: {e}")

    # 解析 Hermes 输出
    code = name = reason = ""
    m = re.search(r'推荐[：:]\s*(\d{6})\s*(\S+)', output)
    if m:
        code = m.group(1)
        name = m.group(2)
    m2 = re.search(r'理由[：:]\s*(.+?)(?:\n|$)', output)
    if m2:
        reason = m2.group(1).strip()
    _log(f"HERMES parse: code={code} name={name} reason_len={len(reason)}")

    # 验证 Hermes 返回的股票必须在过滤后的候选池内，防止越界推荐
    if code and code not in [c for c, _, _ in available]:
        code = name = reason = ""
    # 如果回退后结果仍不在池内，说明 Hermes 理解错了，改为强制随机
    if not code or not name:
        if available:
            pick = random.choice(available)
            code, name, reason = pick
        else:
            return None

    board = classify_board(code)
    q = get_realtime_quote(code)
    price = q.get('price', 0) if q else 0

    db.add_recommendation(code, name, sector, price, 'system', board)
    db.mark_sector_used(sector, code, 'system')

    return {
        'code': code,
        'name': name,
        'price': price,
        'sector': sector,
        'board': board,
        'reason': reason
    }


def send_feishu_buy_notification(username: str, stock_code: str, stock_name: str,
                                  buy_price: float, amount: float, sector: str, board: str, buy_time: str):
    """推送买入通知到飞书群"""
    try:
        card = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": "[买入通知] 推票助手"},
                    "template": "blue"
                },
                "elements": [
                    {"tag": "div", "fields": [
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**员工**\n{username}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**板块**\n{sector or '-'}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**股票**\n{stock_name}({stock_code})"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**金额**\n{amount}万"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**买入价**\n{buy_price:.2f}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**板块**\n{board or '-'}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**时间**\n{buy_time}"}},
                    ]}
                ]
            }
        }
        requests.post(FEISHU_WEBHOOK, json=card, timeout=5)
    except:
        pass

# ========== API ==========

@app.route('/api/ping', methods=['GET'])
def ping():
    return jsonify({'ok': True, 'server_time': datetime.datetime.now().isoformat()})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    ok = db.user_login(data.get('username', ''), data.get('password', ''))
    return jsonify({'ok': ok})

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    client_ip = request.remote_addr or ''
    err = db.user_register(data.get('username', ''), data.get('password', ''), client_ip)
    return jsonify({'ok': err == '', 'error': err})

@app.route('/api/debug/board_filter', methods=['POST'])
def debug_board_filter():
    data = request.json or {}
    board_filter = data.get('board_filter', '')
    sector = data.get('sector', '金融')

    pool = get_pool(board_filter)
    candidates = pool.get(sector, [])
    all_codes = [c[0] for c in candidates]

    if board_filter:
        prefix_map = {'主板': ('60','00'), '创业板': ('30',), '科创板': ('68',)}
        prefixes = prefix_map.get(board_filter, ())
        if prefixes:
            candidates = [(c, n, r) for c, n, r in candidates if c.startswith(prefixes)]
    filtered_codes = [c[0] for c in candidates]

    return jsonify({
        'sector': sector,
        'board_filter': board_filter,
        'prefixes': list(prefix_map.get(board_filter, ())) if board_filter else [],
        'all_codes': all_codes,
        'filtered_codes': filtered_codes,
        'guard_check': any(c.startswith(prefix_map.get(board_filter, ('30',))) for c in all_codes) if board_filter else None
    })


@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    username = data.get('username', '')
    message = data.get('message', '')

    if not is_trading_time() and 'debug' not in (data.get('message','') + data.get('query','')).lower():
        return jsonify({
            'ok': True,
            'reply': '当前非交易时段（交易时间：周一至周五 9:30-11:30, 13:00-15:00）',
            'type': 'text'
        })

    sectors = db.get_available_sectors()
    if not sectors:
        return jsonify({
            'ok': True,
            'reply': '今日所有板块已推荐完毕，明天再来。',
            'type': 'text'
        })

    today_recs = db.get_today_recommendations()
    exclude_codes = [r['stock_code'] for r in today_recs]

    # 解析用户输入的板块关键词（创业板/主板/科创板）
    board_filter = ''
    for kw in ['创业板', '主板', '科创板']:
        if kw in message:
            board_filter = kw
            break

    # 构建动态股票池
    pool = get_pool(board_filter)

    # 按当天行情排序板块，优先推表现好的板块
    ranked_sectors = rank_sectors_by_performance(sectors, board_filter, pool)
    # 有板块过滤时，严格限定只搜索有匹配候选的板块
    if board_filter:
        before = list(ranked_sectors)
        ranked_sectors = [s for s in ranked_sectors if any(
            c.startswith({'主板':('60','00'),'创业板':('30',),'科创板':('68',)}.get(board_filter,()))
            for c, _, _ in pool.get(s, [])
        )]
        print(f'[BOARD_GUARD] filter={board_filter} before={before} after={ranked_sectors}', flush=True)
    if not ranked_sectors:
        return jsonify({
            'ok': True,
            'reply': f'今日暂无{board_filter}的合适推荐标的。',
            'type': 'text'
        })
    result = None
    used_sector = ''
    for sector in ranked_sectors:
        result = call_hermes(sector, exclude_codes, board_filter, pool)
        if result:
            used_sector = sector
            break

    if result is None:
        hint = '今日暂无'
        if board_filter:
            hint += f'{board_filter}的'
        hint += '合适推荐标的。'
        return jsonify({
            'ok': True,
            'reply': hint,
            'type': 'text'
        })

    reply = (
        f"【{result['sector']}板块 · {result['board']}】\n"
        f"📈 {result['name']}({result['code']})\n"
        f"💰 现价: {result['price']:.2f}\n"
        f"📝 逻辑: {result['reason']}\n\n"
        f"要记录买入吗？回复「买入 5万 {result['name']}{result['code']}」"
    )

    return jsonify({
        'ok': True,
        'reply': reply,
        'type': 'recommend',
        'stock': result
    })

@app.route('/api/buy', methods=['POST'])
def buy():
    data = request.json
    username = data.get('username', '')
    stock_code = data.get('stock_code', '')
    stock_name = data.get('stock_name', '')
    buy_price = data.get('buy_price', 0)
    amount = data.get('amount', 0)
    sector = data.get('sector', '')
    board = data.get('board', '')

    if not all([username, stock_code]):
        return jsonify({'ok': False, 'error': '参数缺失'})

    if buy_price <= 0:
        q = get_realtime_quote(stock_code)
        buy_price = q.get('price', 0) if q else 0

    if not board:
        board = classify_board(stock_code)

    buy_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    db.add_buy_record(username, stock_code, stock_name, buy_price, amount, sector, board)
    send_feishu_buy_notification(username, stock_code, stock_name, buy_price, amount, sector, board, buy_time)
    return jsonify({'ok': True, 'price': buy_price, 'amount': amount})

@app.route('/api/positions', methods=['GET', 'POST'])
def positions():
    username = ''
    if request.method == 'GET':
        username = request.args.get('username', '')
    else:
        username = (request.json or {}).get('username', '')

    if username:
        pos = db.get_user_positions(username)
    else:
        pos = db.get_all_positions()

    if not pos:
        return jsonify({'ok': True, 'stocks': []})

    codes = list(set(p['stock_code'] for p in pos))
    quotes = get_batch_quotes(codes)

    stocks = []
    for p in pos:
        code = p['stock_code']
        q = quotes.get(code, {})
        stocks.append({
            'code': code,
            'name': p['stock_name'],
            'board': p.get('board', ''),
            'amount': p.get('total_amount', 0),
            'buy_price': p.get('buy_price', 0),
            'current_price': q.get('price', 0),
            'change_pct': q.get('change_pct', 0),
        })

    return jsonify({'ok': True, 'stocks': stocks})


@app.route('/api/position/add', methods=['POST'])
def position_add():
    data = request.json or {}
    username = data.get('username', '')
    code = data.get('stock_code', '')
    name = data.get('stock_name', '')
    amount = data.get('amount', 0)
    board = data.get('board', '') or classify_board(code)
    buy_price = data.get('buy_price', 0)

    if not username or not code:
        return jsonify({'ok': False, 'error': '参数缺失'})

    if buy_price <= 0:
        q = get_realtime_quote(code)
        buy_price = q.get('price', 0) if q else 0

    buy_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    db.add_buy_record(username, code, name, buy_price, amount, '', board)
    send_feishu_buy_notification(username, code, name, buy_price, amount, '', board, buy_time)
    return jsonify({'ok': True, 'price': buy_price})


@app.route('/api/position/remove', methods=['POST'])
def position_remove():
    data = request.json or {}
    username = data.get('username', '')
    stock_code = data.get('stock_code', '')

    # 先查买入记录用于写入卖出历史
    conn = db.get_conn()
    c = conn.cursor()
    c.execute('SELECT stock_name, buy_price, SUM(amount) as total_amount, MAX(board) as board FROM buy_history WHERE username=? AND stock_code=? GROUP BY stock_code',
              (username, stock_code))
    buy_info = c.fetchone()

    if buy_info:
        db.record_sell(username, stock_code, buy_info['stock_name'], 0, buy_info['buy_price'],
                       buy_info['total_amount'] or 0, buy_info['board'] or '')

    c.execute('DELETE FROM buy_history WHERE username=? AND stock_code=?', (username, stock_code))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@app.route('/api/sell', methods=['POST'])
def sell_stock():
    """卖出：记录卖出价并写入卖出历史"""
    data = request.json or {}
    username = data.get('username', '')
    stock_code = data.get('stock_code', '')
    sell_price = data.get('sell_price', 0)

    if not username or not stock_code or sell_price <= 0:
        return jsonify({'ok': False, 'error': '参数缺失或卖出价无效'})

    conn = db.get_conn()
    c = conn.cursor()
    c.execute('SELECT stock_name, buy_price, SUM(amount) as total_amount, MAX(board) as board FROM buy_history WHERE username=? AND stock_code=? GROUP BY stock_code',
              (username, stock_code))
    buy_info = c.fetchone()

    if not buy_info:
        conn.close()
        return jsonify({'ok': False, 'error': '未找到该持仓'})

    db.record_sell(username, stock_code, buy_info['stock_name'], sell_price, buy_info['buy_price'],
                   buy_info['total_amount'] or 0, buy_info['board'] or '')

    # 学弟学习：记录盈亏反馈
    is_win = 1 if sell_price > buy_info['buy_price'] else 0
    note = f"{username}卖出 {buy_info['stock_name']}({stock_code}) 买入{buy_info['buy_price']}→卖出{sell_price}"
    db.record_feedback(stock_code, buy_info['buy_price'], sell_price, is_win, note)

    c.execute('DELETE FROM buy_history WHERE username=? AND stock_code=?', (username, stock_code))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@app.route('/api/sell/history', methods=['POST'])
def sell_history():
    data = request.json or {}
    username = data.get('username', '')
    rows = db.get_sell_history(username)
    formatted = []
    for r in rows:
        formatted.append({
            'code': r['stock_code'],
            'name': r['stock_name'],
            'buy_price': r['buy_price'],
            'sell_price': r['sell_price'],
            'amount': r.get('amount', 0),
            'profit': calc_pnl(r['buy_price'], r['sell_price'], r.get('amount', 0)),
            'board': r.get('board', ''),
            'time': r.get('sell_time', ''),
        })
    return jsonify({'ok': True, 'rows': formatted})


@app.route('/api/daily/summary', methods=['POST'])
def daily_summary():
    data = request.json or {}
    username = data.get('username', '')
    result = db.get_daily_summary(username)

    # 取行情
    all_codes = [r['stock_code'] for r in result['bought']] + [r['stock_code'] for r in result['not_bought']]
    quotes = get_batch_quotes(all_codes) if all_codes else {}

    bought_list = []
    for r in result['bought']:
        code = r['stock_code']
        q = quotes.get(code, {})
        buy_price = r['buy_price']
        cur_price = q.get('price', buy_price)
        amount = r['total_amount']
        pnl = calc_pnl(buy_price, cur_price, amount) if cur_price and buy_price else 0
        pnl_pct = round((cur_price - buy_price) / buy_price * 100, 2) if buy_price else 0
        bought_list.append({
            'code': code, 'name': r['stock_name'], 'board': r.get('board', ''),
            'buy_price': buy_price, 'current_price': cur_price, 'amount': amount,
            'pnl': pnl, 'pnl_pct': pnl_pct
        })

    not_bought_list = []
    for r in result['not_bought']:
        code = r['stock_code']
        q = quotes.get(code, {})
        not_bought_list.append({
            'code': code, 'name': r['stock_name'], 'board': r.get('board', ''),
            'rec_price': r.get('recommend_price', 0),
            'current_price': q.get('price', 0),
            'change_pct': q.get('change_pct', 0)
        })

    total_pnl = sum(b['pnl'] for b in bought_list)
    return jsonify({
        'ok': True,
        'bought': bought_list,
        'not_bought': not_bought_list,
        'total_pnl': total_pnl
    })


@app.route('/api/recommend', methods=['POST'])
def recommend():
    print("===== RECOMMEND V20260608-HC-FIX =====", flush=True)
    data = request.json or {}
    username = data.get('username', '')
    query = data.get('query', '')

    if not is_trading_time() and 'debug' not in query.lower():
        return jsonify({
            'ok': True,
            'reply': '当前非交易时段（交易时间：周一至周五 9:30-11:30, 13:00-15:00）',
            'stocks': []
        })

    sectors = db.get_available_sectors()
    if not sectors:
        return jsonify({
            'ok': True,
            'reply': '今日所有板块已推荐完毕',
            'stocks': []
        })

    today_recs = db.get_today_recommendations()
    exclude_codes = [r['stock_code'] for r in today_recs]

    # 解析用户输入的板块关键词（创业板/主板/科创板）
    board_filter = ''
    for kw in ['创业板', '主板', '科创板']:
        if kw in query:
            board_filter = kw
            break

    # 构建动态股票池
    pool = get_pool(board_filter)

    # 按当天行情排序板块，优先推表现好的板块
    ranked_sectors = rank_sectors_by_performance(sectors, board_filter, pool)
    # 有板块过滤时，排除完全无匹配候选股的板块（score=-999）
    if board_filter:
        before = list(ranked_sectors)
        ranked_sectors = [s for s in ranked_sectors if any(
            c.startswith({'主板':('60','00'),'创业板':('30',),'科创板':('68',)}.get(board_filter,()))
            for c, _, _ in pool.get(s, [])
        )]
        _log(f'RECOMMEND board_filter={board_filter} pool_keys={list(pool.keys())} pool_total={sum(len(v) for v in pool.values())} before={before} after={ranked_sectors}')
    if not ranked_sectors:
        _log(f'RECOMMEND NO_SECTORS board_filter={board_filter} pool_keys={list(pool.keys())} sectors={sectors}')
        return jsonify({
            'ok': True,
            'reply': f'NO_STOCKS:{board_filter}:pool={len(pool) if pool else 0}:marker=V20260608-HC-FIX',
            'stocks': []
        })
    result = None
    for sector in ranked_sectors:
        result = call_hermes(sector, exclude_codes, board_filter, pool)
        if result:
            break
    if result is None:
        return jsonify({'ok': True, 'stocks': []})

    return jsonify({
        'ok': True,
        'stocks': [result]
    })


@app.route('/api/history', methods=['GET', 'POST'])
def history():
    username = ''
    offset = 0
    limit = 200

    if request.method == 'POST':
        data = request.json or {}
        username = data.get('username', '')
        offset = data.get('offset', 0)
        limit = data.get('limit', 200)
    else:
        username = request.args.get('username', '')
        offset = int(request.args.get('offset', 0))
        limit = int(request.args.get('limit', 200))

    rows, total = db.get_buy_history_paginated(username=username, offset=offset, limit=limit)
    formatted = []
    for r in rows:
        formatted.append({
            'code': r['stock_code'],
            'name': r['stock_name'],
            'board': r.get('board', ''),
            'buy_price': r.get('buy_price', 0),
            'amount': r.get('amount', 0),
            'time': r.get('buy_time', ''),
        })

    return jsonify({'ok': True, 'rows': formatted, 'total': total, 'offset': offset, 'limit': limit})


@app.route('/api/theme/save', methods=['POST'])
def theme_save():
    data = request.json or {}
    username = data.get('username', '')
    theme = data.get('theme', '浅色主题')
    db.save_user_pref(username, 'theme', theme)
    return jsonify({'ok': True})


@app.route('/api/theme/get', methods=['GET', 'POST'])
def theme_get():
    username = ''
    if request.method == 'POST':
        data = request.json or {}
        username = data.get('username', '')
    else:
        username = request.args.get('username', '')

    theme = db.get_user_pref(username, 'theme') or '浅色主题'
    return jsonify({'ok': True, 'theme': theme})

APP_VERSION = "4.5"
UPDATE_ZIP = os.path.join(os.path.dirname(__file__), "..", "推票助手_v4.zip")

@app.route('/api/version', methods=['GET'])
def api_version():
    return jsonify({'version': APP_VERSION})

@app.route('/api/update/download', methods=['GET'])
def api_update_download():
    if not os.path.exists(UPDATE_ZIP):
        return jsonify({'ok': False, 'error': '更新包不存在'}), 404
    from flask import send_file
    return send_file(UPDATE_ZIP, as_attachment=True, download_name='推票助手_v4.zip')

def main():
    print("=" * 50)
    print(" 晟创科技 · 推票引擎 v3")
    print(f" 地址: http://0.0.0.0:5128")
    print(f" 时间: {datetime.datetime.now().isoformat()}")
    print("=" * 50)
    _log('SERVER_START')
    db.reset_daily()
    ports = [5128, 5129, 5130]
    for port in ports:
        try:
            app.run(host='0.0.0.0', port=port, debug=False)
            break
        except OSError as e:
            print(f"端口 {port} 被占用，尝试下一个... ({e})", flush=True)
            _log(f'PORT_{port}_CONFLICT')
    else:
        print("所有端口均被占用，无法启动", flush=True)
        _log('SERVER_START_FAILED_ALL_PORTS')

if __name__ == '__main__':
    main()
