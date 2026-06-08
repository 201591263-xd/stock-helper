"""
推票助手 v4.0 启动器 - 单文件运行
内置完整 Flask 后端 + PySide6 客户端 + 自动更新
"""
import os, sys, threading, time, socket, urllib.request, zipfile, shutil, subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

LOCAL_VERSION = "4.3"
# 用 GitHub Releases 免费托管更新包：把 version.json 和 stock-helper-v4.zip 上传到 Release
# 格式：https://github.com/你的用户名/仓库名/releases/latest/download/version.json
UPDATE_SERVER = "https://github.com/201591263-xd/stock-helper/releases/latest/download"  # 留空则跳过自动更新，填 GitHub Releases 地址后生效
SERVER_BASE = "http://127.0.0.1"


def get_base_dir():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

BASE = get_base_dir()


def find_free_port(start=5128):
    for port in range(start, start + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', port)) != 0:
                return port
    return start

PORT = find_free_port(5128)
SERVER_URL = f"{SERVER_BASE}:{PORT}"


def start_server():
    """启动完整 server.py（Hermes推票 + 飞书通知）"""
    server_dir = os.path.join(BASE, 'server')
    sys.path.insert(0, server_dir)
    os.chdir(server_dir)

    from server import app
    app.config['PORT'] = PORT
    app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)


def wait_server_ready(timeout=30):
    for _ in range(timeout * 2):
        try:
            urllib.request.urlopen(f'{SERVER_URL}/api/ping', timeout=1)
            return True
        except:
            time.sleep(0.5)
    return False


def download_multithread(url, save_path, threads=8):
    """多线程分片下载，大幅提升 GitHub 下载速度"""
    import tempfile
    # 获取文件大小
    req = urllib.request.Request(url, method='HEAD')
    resp = urllib.request.urlopen(req, timeout=10)
    total_size = int(resp.headers.get('Content-Length', 0))
    resp.close()
    if total_size == 0:
        # fallback to single-thread
        urllib.request.urlretrieve(url, save_path)
        return

    chunk_size = total_size // threads
    part_files = []

    def download_chunk(start, end, idx):
        part_path = tempfile.mktemp(suffix=f'.part{idx}')
        req = urllib.request.Request(url, headers={'Range': f'bytes={start}-{end}'})
        resp = urllib.request.urlopen(req, timeout=30)
        with open(part_path, 'wb') as f:
            while True:
                data = resp.read(1024 * 1024)
                if not data:
                    break
                f.write(data)
        return part_path

    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = []
        for i in range(threads):
            start = i * chunk_size
            end = start + chunk_size - 1 if i < threads - 1 else total_size - 1
            futures.append(executor.submit(download_chunk, start, end, i))
        
        for f in as_completed(futures):
            part_files.append(f.result())

    # 合并分片
    part_files.sort(key=lambda x: int(x.rsplit('part', 1)[1]))
    with open(save_path, 'wb') as out:
        for pf in part_files:
            with open(pf, 'rb') as inf:
                shutil.copyfileobj(inf, out)
            os.remove(pf)


def check_update():
    """从远端服务器检查版本，有更新则自动下载升级并重启"""
    if not UPDATE_SERVER:
        return  # 未配置更新地址，跳过

    # 多源尝试获取 version.json（国内 CDN 优先）
    remote_ver = ''
    urls = [
        f'https://ghproxy.net/https://github.com/201591263-xd/stock-helper/releases/latest/download/version.json',
        f'https://gh-proxy.com/https://github.com/201591263-xd/stock-helper/releases/latest/download/version.json',
        f'https://ghp.ci/https://github.com/201591263-xd/stock-helper/releases/latest/download/version.json',
        f'{UPDATE_SERVER}/version.json',  # 最后走直连
    ]
    for url in urls:
        try:
            resp = urllib.request.urlopen(url, timeout=5)
            data = json.loads(resp.read().decode())
            remote_ver = data.get('version', '')
            break
        except:
            continue
    if not remote_ver or remote_ver == LOCAL_VERSION:
        return  # 检查失败或已是最新，跳过

    # 弹窗确认（用 PySide6 QMessageBox，比 tkinter 更可靠）
    from PySide6.QtWidgets import QMessageBox, QApplication as QA2
    import sys as _sys2
    _app = QA2(_sys2.argv)
    reply = QMessageBox.question(
        None, "推票助手更新",
        f"检测到新版本 v{remote_ver}，当前 v{LOCAL_VERSION}。\n\n是否立即更新并重启？",
        QMessageBox.Yes | QMessageBox.No
    )
    _app.quit()
    if reply != QMessageBox.Yes:
        return

    # 下载更新包
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        zip_path = os.path.join(base_dir, '_update.zip')

        direct_url = f'{UPDATE_SERVER}/stock-helper-v4.zip'
        # CDN 加速镜像，国内优先，逐个尝试
        cdn_mirrors = [
            f'https://ghproxy.net/{direct_url}',
            f'https://gh-proxy.com/{direct_url}',
            f'https://ghp.ci/{direct_url}',
            direct_url,  # 最后走直连
        ]
        downloaded = False
        for url in cdn_mirrors:
            try:
                download_multithread(url, zip_path)
                downloaded = True
                break
            except:
                continue
        if not downloaded:
            raise Exception("所有下载源均失败")

        # 解压到临时目录
        extract_to = os.path.join(base_dir, '_update_new')
        if os.path.exists(extract_to):
            shutil.rmtree(extract_to)
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(extract_to)

        # 当前 app 目录
        app_dir = getattr(sys, '_MEIPASS', os.path.dirname(__file__))

        # 写 bat 脚本来替换文件并重启
        bat = f'''@echo off
timeout /t 2 /nobreak >nul
xcopy /E /Y "{extract_to}\\*" "{app_dir}\\"
rmdir /S /Q "{extract_to}"
del "{zip_path}"
start "" "{os.path.join(app_dir, '推票助手_v4', '推票助手_v4.exe')}"
del "%~f0"
'''
        bat_path = os.path.join(base_dir, '_update_replace.bat')
        with open(bat_path, 'w', encoding='gbk') as f:
            f.write(bat)

        subprocess.Popen(['cmd', '/c', bat_path], creationflags=0x00000008)
        os._exit(0)
    except Exception as e:
        subprocess.run([
            'powershell', '-NoProfile', '-Command',
            f'[System.Windows.MessageBox]::Show("更新失败: {e}", "推票助手更新", "OK", "Error")'
        ], timeout=5)


def start_client():
    if not wait_server_ready():
        print("服务端启动超时")
        return

    check_update()

    # 看门狗：每5秒检测服务端，挂了自动重启
    def watchdog():
        while True:
            time.sleep(5)
            try:
                urllib.request.urlopen(f'{SERVER_URL}/api/ping', timeout=2)
            except:
                print("服务端失联，重启中...")
                t = threading.Thread(target=start_server, daemon=True)
                t.start()
                wait_server_ready(15)

    threading.Thread(target=watchdog, daemon=True).start()

    client_dir = os.path.join(BASE, 'client')
    sys.path.insert(0, client_dir)
    os.chdir(client_dir)

    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setFont(QFont("Microsoft YaHei", 10))

    from login import LoginWindow
    from dashboard import Dashboard

    server_url = f'http://127.0.0.1:{PORT}'
    login = LoginWindow()
    dashboard = None

    def on_login(username):
        nonlocal dashboard
        login.hide()
        dashboard = Dashboard(username, server_url)
        dashboard.login_signal.connect(on_logout)
        dashboard.show()

    def on_logout():
        nonlocal dashboard
        if dashboard:
            dashboard.hide()
            dashboard.deleteLater()
            dashboard = None
        login.show()

    login.login_success.connect(on_login)
    login.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    import json
    import multiprocessing
    multiprocessing.freeze_support()
    t = threading.Thread(target=start_server, daemon=True)
    t.start()
    start_client()
