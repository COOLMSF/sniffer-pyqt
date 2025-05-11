#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import sqlite3
import hashlib
import subprocess
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QLabel, QLineEdit, QPushButton, QMessageBox, QTabWidget,
                            QGridLayout, QGroupBox, QDialog, QSpacerItem, QSizePolicy, QComboBox)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QIcon, QPixmap, QFont
from PyQt5 import QtCore

class DatabaseManager:
    """Manages the SQLite database for user authentication"""
    
    def __init__(self, db_path="users.db"):
        """Initialize the database connection and create tables if they don't exist"""
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self.create_tables()
    
    def create_tables(self):
        """Create the users table if it doesn't exist"""
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            salt TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )''')
        self.conn.commit()
    
    def generate_salt(self):
        """Generate a random salt for password hashing"""
        return os.urandom(32).hex()
    
    def hash_password(self, password, salt):
        """Hash a password with the given salt using SHA-256"""
        password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        return password_hash
    
    def add_user(self, username, password, role='user'):
        """Add a new user to the database with specified role (default: user)"""
        # Check if username already exists
        self.cursor.execute("SELECT username FROM users WHERE username = ?", (username,))
        if self.cursor.fetchone():
            return False, "用户名已存在"
        
        # Generate salt and hash password
        salt = self.generate_salt()
        hashed_password = self.hash_password(password, salt)
        
        # Insert new user with role
        try:
            self.cursor.execute(
                "INSERT INTO users (username, password, salt, role) VALUES (?, ?, ?, ?)",
                (username, hashed_password, salt, role)
            )
            self.conn.commit()
            return True, "用户创建成功"
        except Exception as e:
            return False, f"注册失败: {str(e)}"
    
    def verify_user(self, username, password):
        """Verify a user's credentials and return user information including role"""
        # Get the user from the database
        self.cursor.execute(
            "SELECT password, salt, role FROM users WHERE username = ?", 
            (username,)
        )
        result = self.cursor.fetchone()
        
        # If no user is found
        if not result:
            return False, "用户名不存在", None
        
        stored_password, salt, role = result
        hashed_input = self.hash_password(password, salt)
        
        # Check if passwords match
        if stored_password == hashed_input:
            # Update last login time
            self.cursor.execute(
                "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE username = ?",
                (username,)
            )
            self.conn.commit()
            return True, "登录成功", role
        else:
            return False, "密码错误", None
    
    def change_password(self, username, old_password, new_password):
        """Change a user's password"""
        # First verify the old password
        verified, message = self.verify_user(username, old_password)
        if not verified:
            return False, "原密码错误"
        
        # Generate new salt and hash the new password
        salt = self.generate_salt()
        hashed_password = self.hash_password(new_password, salt)
        
        # Update the password
        try:
            self.cursor.execute(
                "UPDATE users SET password = ?, salt = ? WHERE username = ?",
                (hashed_password, salt, username)
            )
            self.conn.commit()
            return True, "密码修改成功"
        except Exception as e:
            return False, f"密码修改失败: {str(e)}"
    
    def close(self):
        """Close the database connection"""
        self.conn.close()


class LoginWindow(QMainWindow):
    """Main login window with tabs for login, registration, and password change"""
    
    # Define signal that will pass username and role to main application
    accepted = QtCore.pyqtSignal(str, str)
    
    def __init__(self):
        super().__init__()
        self.db_manager = DatabaseManager()
        self.username = None
        self.user_role = None
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the main window and its widgets"""
        self.setWindowTitle("网络安全分析工具 - 用户登录")
        self.setMinimumSize(500, 400)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QTabWidget::pane {
                border: 1px solid #cccccc;
                background-color: white;
                border-radius: 5px;
            }
            QTabBar::tab {
                background-color: #e0e0e0;
                padding: 8px 20px;
                border: 1px solid #cccccc;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-bottom-color: white;
            }
            QLineEdit {
                padding: 8px;
                border: 1px solid #cccccc;
                border-radius: 4px;
                background-color: white;
            }
            QPushButton {
                background-color: #2c3e50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #34495e;
            }
            QPushButton:pressed {
                background-color: #1a252f;
            }
            QLabel {
                color: #333333;
            }
        """)
        
        # Central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Logo and title
        header_layout = QHBoxLayout()
        # Uncomment if you have a logo image
        # logo_label = QLabel()
        # logo_pixmap = QPixmap("path/to/logo.png").scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        # logo_label.setPixmap(logo_pixmap)
        # header_layout.addWidget(logo_label)
        
        title_label = QLabel("网络安全分析工具")
        title_label.setFont(QFont("Arial", 18, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(title_label)
        main_layout.addLayout(header_layout)
        
        # Tab widget for login, register, and change password
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        # Create tabs
        self.create_login_tab()
        self.create_register_tab()
        self.create_change_password_tab()
        
        # Add some spacing at the bottom
        main_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        
        # Footer with version info
        footer_label = QLabel("版本 1.0.0")
        footer_label.setAlignment(Qt.AlignRight)
        main_layout.addWidget(footer_label)
    
    def create_login_tab(self):
        """Create the login tab"""
        login_tab = QWidget()
        login_layout = QVBoxLayout(login_tab)
        
        # Login form group
        login_group = QGroupBox("用户登录")
        login_form = QGridLayout(login_group)
        
        # Username field
        username_label = QLabel("用户名:")
        self.login_username = QLineEdit()
        self.login_username.setPlaceholderText("输入用户名")
        login_form.addWidget(username_label, 0, 0)
        login_form.addWidget(self.login_username, 0, 1)
        
        # Password field
        password_label = QLabel("密码:")
        self.login_password = QLineEdit()
        self.login_password.setPlaceholderText("输入密码")
        self.login_password.setEchoMode(QLineEdit.Password)
        login_form.addWidget(password_label, 1, 0)
        login_form.addWidget(self.login_password, 1, 1)
        
        login_layout.addWidget(login_group)
        
        # Login button
        login_button = QPushButton("登录")
        login_button.clicked.connect(self.handle_login)
        login_layout.addWidget(login_button)
        
        # Add to tabs
        self.tabs.addTab(login_tab, "登录")
    
    def create_register_tab(self):
        """Create the registration tab"""
        register_tab = QWidget()
        register_layout = QVBoxLayout(register_tab)
        
        # Register form group
        register_group = QGroupBox("新用户注册")
        register_form = QGridLayout(register_group)
        
        # Username field
        username_label = QLabel("用户名:")
        self.register_username = QLineEdit()
        self.register_username.setPlaceholderText("创建用户名")
        register_form.addWidget(username_label, 0, 0)
        register_form.addWidget(self.register_username, 0, 1)
        
        # Password field
        password_label = QLabel("密码:")
        self.register_password = QLineEdit()
        self.register_password.setPlaceholderText("创建密码")
        self.register_password.setEchoMode(QLineEdit.Password)
        register_form.addWidget(password_label, 1, 0)
        register_form.addWidget(self.register_password, 1, 1)
        
        # Confirm password field
        confirm_label = QLabel("确认密码:")
        self.register_confirm = QLineEdit()
        self.register_confirm.setPlaceholderText("确认密码")
        self.register_confirm.setEchoMode(QLineEdit.Password)
        register_form.addWidget(confirm_label, 2, 0)
        register_form.addWidget(self.register_confirm, 2, 1)
        
        # Role selection
        role_label = QLabel("用户角色:")
        self.register_role_combo = QComboBox()
        self.register_role_combo.addItem("普通用户", "user")
        self.register_role_combo.addItem("管理员", "admin")
        register_form.addWidget(role_label, 3, 0)
        register_form.addWidget(self.register_role_combo, 3, 1)
        
        register_layout.addWidget(register_group)
        
        # Register button
        register_button = QPushButton("注册")
        register_button.clicked.connect(self.handle_register)
        register_layout.addWidget(register_button)
        
        # Add to tabs
        self.tabs.addTab(register_tab, "注册")
    
    def create_change_password_tab(self):
        """Create the change password tab"""
        change_tab = QWidget()
        change_layout = QVBoxLayout(change_tab)
        
        # Change password form group
        change_group = QGroupBox("修改密码")
        change_form = QGridLayout(change_group)
        
        # Username field
        username_label = QLabel("用户名:")
        self.change_username = QLineEdit()
        self.change_username.setPlaceholderText("输入用户名")
        change_form.addWidget(username_label, 0, 0)
        change_form.addWidget(self.change_username, 0, 1)
        
        # Old password field
        old_pass_label = QLabel("当前密码:")
        self.change_old_password = QLineEdit()
        self.change_old_password.setPlaceholderText("输入当前密码")
        self.change_old_password.setEchoMode(QLineEdit.Password)
        change_form.addWidget(old_pass_label, 1, 0)
        change_form.addWidget(self.change_old_password, 1, 1)
        
        # New password field
        new_pass_label = QLabel("新密码:")
        self.change_new_password = QLineEdit()
        self.change_new_password.setPlaceholderText("输入新密码")
        self.change_new_password.setEchoMode(QLineEdit.Password)
        change_form.addWidget(new_pass_label, 2, 0)
        change_form.addWidget(self.change_new_password, 2, 1)
        
        # Confirm new password field
        confirm_label = QLabel("确认新密码:")
        self.change_confirm = QLineEdit()
        self.change_confirm.setPlaceholderText("确认新密码")
        self.change_confirm.setEchoMode(QLineEdit.Password)
        change_form.addWidget(confirm_label, 3, 0)
        change_form.addWidget(self.change_confirm, 3, 1)
        
        change_layout.addWidget(change_group)
        
        # Change password button
        change_button = QPushButton("修改密码")
        change_button.clicked.connect(self.handle_change_password)
        change_layout.addWidget(change_button)
        
        # Add to tabs
        self.tabs.addTab(change_tab, "修改密码")
    
    def handle_login(self):
        """Handle login button click"""
        username = self.login_username.text().strip()
        password = self.login_password.text().strip()
        
        # Basic validation
        if not username or not password:
            reply = QMessageBox.warning(self, "登录失败", "用户名和密码不能为空！", 
                                      QMessageBox.Retry | QMessageBox.Cancel, QMessageBox.Retry)
            if reply == QMessageBox.Retry:
                # Clear password field and keep focus on it
                self.login_password.clear()
                self.login_password.setFocus()
            return
        
        # Check credentials
        success, message, role = self.db_manager.verify_user(username, password)
        if success:
            QMessageBox.information(self, "登录成功", f"欢迎 {username}! 正在启动主程序...")
            # Store username and role for later use
            self.username = username
            self.user_role = role
            # Launch the main application directly
            self.launch_main_application()
        else:
            reply = QMessageBox.warning(self, "登录失败", f"{message}\n是否要重试？", 
                                      QMessageBox.Retry | QMessageBox.Cancel, QMessageBox.Retry)
            if reply == QMessageBox.Retry:
                # Clear password field and keep focus on it
                self.login_password.clear()
                self.login_password.setFocus()
    
    def handle_register(self):
        """Handle registration button click"""
        username = self.register_username.text().strip()
        password = self.register_password.text()
        confirm = self.register_confirm.text()
        role = self.register_role_combo.currentData() # Get role from combo box
        
        # Validate inputs
        if not username or not password or not confirm:
            QMessageBox.warning(self, "注册失败", "所有字段都必须填写")
            return
        
        if password != confirm:
            QMessageBox.warning(self, "注册失败", "两次输入的密码不一致")
            return
        
        if len(password) < 6:
            QMessageBox.warning(self, "注册失败", "密码长度必须至少为6个字符")
            return
        
        # Try to add the user with the selected role
        success, message = self.db_manager.add_user(username, password, role)
        
        if success:
            QMessageBox.information(self, "注册成功", "用户 " + username + " 创建成功，请登录")
            self.tabs.setCurrentIndex(0)  # Switch to login tab
            self.register_username.clear()
            self.register_password.clear()
            self.register_confirm.clear()
        else:
            QMessageBox.warning(self, "注册失败", message)
    
    def handle_change_password(self):
        """Handle change password button click"""
        username = self.change_username.text().strip()
        old_password = self.change_old_password.text()
        new_password = self.change_new_password.text()
        confirm = self.change_confirm.text()
        
        # Validate inputs
        if not username or not old_password or not new_password or not confirm:
            QMessageBox.warning(self, "修改失败", "所有字段都必须填写")
            return
        
        if new_password != confirm:
            QMessageBox.warning(self, "修改失败", "两次输入的新密码不一致")
            return
        
        if len(new_password) < 6:
            QMessageBox.warning(self, "修改失败", "新密码长度必须至少为6个字符")
            return
        
        # Try to change the password
        success, message = self.db_manager.change_password(username, old_password, new_password)
        
        if success:
            QMessageBox.information(self, "修改成功", "密码修改成功，请使用新密码登录")
            self.tabs.setCurrentIndex(0)  # Switch to login tab
            self.change_username.clear()
            self.change_old_password.clear()
            self.change_new_password.clear()
            self.change_confirm.clear()
        else:
            QMessageBox.warning(self, "修改失败", message)
    
    def launch_main_application(self):
        """Launch the main application with user role"""
        try:
            # Get the path to main.py
            main_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
            
            # Start the main application
            if sys.platform.startswith('win'):
                # Windows
                subprocess.Popen(["python", main_script], creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                # Linux/Mac
                subprocess.Popen(["python3", main_script])
            
            # Close the login window
            self.close()
            
        except Exception as e:
            QMessageBox.critical(self, "启动失败", f"启动主程序失败: {str(e)}")
    
    def closeEvent(self, event):
        """Handle window close event"""
        self.db_manager.close()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Create the database if it doesn't exist
    db_path = "users.db"
    db_exists = os.path.exists(db_path)
    db_manager = DatabaseManager(db_path)
    
    # Create an admin user if this is a first-time setup
    if not db_exists:
        admin_username = "admin"
        admin_password = "admin123"
        db_manager.add_user(admin_username, admin_password, "admin")
        print(f"初始化: 创建管理员账号 (用户名: {admin_username}, 密码: {admin_password})")
    
    # Open the login window
    window = LoginWindow()
    window.show()
    
    sys.exit(app.exec_())
