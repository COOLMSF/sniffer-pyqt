#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
from PyQt5.QtWidgets import (QApplication, QDialog, QVBoxLayout, QHBoxLayout, 
                            QLabel, QPushButton, QGroupBox, QMessageBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QIcon

class AppSelectorDialog(QDialog):
    """
    Dialog to select which application to launch after successful login
    """
    
    def __init__(self, parent=None, username=None, user_role=None):
        super().__init__(parent)
        self.username = username
        self.user_role = user_role
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the selector dialog UI"""
        self.setWindowTitle("应用选择器")
        self.setMinimumSize(500, 300)
        self.setStyleSheet("""
            QDialog {
                background-color: #f5f5f5;
            }
            QPushButton {
                background-color: #2c3e50;
                color: white;
                border: none;
                padding: 15px;
                border-radius: 5px;
                font-size: 14px;
                min-height: 60px;
            }
            QPushButton:hover {
                background-color: #34495e;
            }
            QGroupBox {
                border: 1px solid #cccccc;
                border-radius: 5px;
                margin-top: 10px;
                font-weight: bold;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        
        # Main layout
        main_layout = QVBoxLayout(self)
        
        # Welcome header
        welcome_label = QLabel(f"欢迎, {self.username}!")
        welcome_label.setFont(QFont("Arial", 16, QFont.Bold))
        welcome_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(welcome_label)
        
        # Role info
        role_text = "管理员" if self.user_role == "admin" else "普通用户"
        role_label = QLabel(f"角色: {role_text}")
        role_label.setAlignment(Qt.AlignCenter)
        role_label.setStyleSheet("color: #3498db; margin-bottom: 20px;")
        main_layout.addWidget(role_label)
        
        # Instructions
        instruction_label = QLabel("请选择要启动的应用:")
        instruction_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(instruction_label)
        
        # IDS Application button
        ids_group = QGroupBox("网络安全分析工具")
        ids_layout = QVBoxLayout(ids_group)
        
        ids_description = QLabel("启动入侵检测系统主程序，用于捕获和分析网络流量")
        ids_description.setWordWrap(True)
        ids_description.setAlignment(Qt.AlignCenter)
        ids_layout.addWidget(ids_description)
        
        ids_button = QPushButton("启动入侵检测系统")
        ids_button.setIcon(QIcon.fromTheme("network-workgroup"))
        ids_button.clicked.connect(self.launch_ids)
        ids_layout.addWidget(ids_button)
        
        main_layout.addWidget(ids_group)
        
        # Rules Manager button
        rules_group = QGroupBox("规则管理器")
        rules_layout = QVBoxLayout(rules_group)
        
        rules_description = QLabel("启动规则管理器，用于查看和修改入侵检测规则")
        if self.user_role != "admin":
            rules_description.setText("启动规则管理器，用于查看入侵检测规则（只读模式）")
        rules_description.setWordWrap(True)
        rules_description.setAlignment(Qt.AlignCenter)
        rules_layout.addWidget(rules_description)
        
        rules_button = QPushButton("启动规则管理器")
        rules_button.setIcon(QIcon.fromTheme("document-properties"))
        rules_button.clicked.connect(self.launch_rules_manager)
        rules_layout.addWidget(rules_button)
        
        main_layout.addWidget(rules_group)
        
        # Exit button
        exit_button = QPushButton("退出")
        exit_button.clicked.connect(self.close)
        exit_button.setStyleSheet("background-color: #e74c3c;")
        main_layout.addWidget(exit_button)
    
    def launch_ids(self):
        """Launch the IDS main application"""
        try:
            # Get the path to ids_main.py
            script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ids_main.py")
            
            # Start the IDS main application
            if sys.platform.startswith('win'):
                # Windows
                subprocess.Popen(["python", script_path], creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                # Linux/Mac
                subprocess.Popen(["python3", script_path])
            
            # Close the selector dialog
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "启动失败", f"启动入侵检测系统失败: {str(e)}")
    
    def launch_rules_manager(self):
        """Launch the rules manager application"""
        try:
            # Get the path to rules_manager.py
            script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules_manager.py")
            
            # Start the rules manager application with user role argument
            args = ["--role", self.user_role]
            
            if sys.platform.startswith('win'):
                # Windows
                subprocess.Popen(["python", script_path] + args, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                # Linux/Mac
                subprocess.Popen(["python3", script_path] + args)
            
            # Close the selector dialog
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "启动失败", f"启动规则管理器失败: {str(e)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # For testing, default to admin role
    dialog = AppSelectorDialog(username="TestUser", user_role="admin")
    dialog.exec_()
