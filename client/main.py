"""
推票助手 v2.0 - 客户端入口
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from login import LoginWindow
from dashboard import Dashboard

def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    from PySide6.QtGui import QFont
    font = QFont("Microsoft YaHei", 10)
    app.setFont(font)
    
    login = LoginWindow()
    dashboard = None
    
    def on_login(username, server_url):
        nonlocal dashboard
        login.hide()
        dashboard = Dashboard(username, server_url)
        dashboard.login_signal.connect(on_logout)
        dashboard.show()
    
    def on_logout():
        nonlocal dashboard
        if dashboard:
            dashboard.close()
            dashboard.deleteLater()
            dashboard = None
        login.user_input.clear()
        login.pwd_input.clear()
        login.show()
    
    login.login_success.connect(on_login)
    login.show()
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
