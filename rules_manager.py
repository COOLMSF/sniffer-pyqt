#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                            QLabel, QLineEdit, QPushButton, QMessageBox, QTabWidget,
                            QGridLayout, QGroupBox, QDialog, QTextEdit, QListWidget,
                            QSplitter, QFileDialog, QMenu, QAction, QListWidgetItem,
                            QComboBox)
from PyQt5.QtCore import Qt, QSize, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap, QFont

class RulesManager(QDialog):
    """
    Dialog for managing intrusion detection rules
    Provides different functionality based on user role
    """
    rules_updated = pyqtSignal()  # Signal to notify when rules are updated
    
    def __init__(self, parent=None, user_role="user"):
        super().__init__(parent)
        self.user_role = user_role
        self.rules_dir = "rules"
        self.current_rule_file = None
        self.setup_ui()
        self.load_rule_files()
    
    def setup_ui(self):
        """Set up the dialog UI"""
        self.setWindowTitle("规则管理器")
        self.setMinimumSize(800, 600)
        
        # Main layout
        main_layout = QVBoxLayout(self)
        
        # Header with role info
        role_label = QLabel(f"当前角色: {'管理员' if self.user_role == 'admin' else '普通用户'}")
        role_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        main_layout.addWidget(role_label)
        
        # Splitter for rule files list and rule content
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # Left panel - Rule files list
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # List of rule files
        self.rule_files_list = QListWidget()
        self.rule_files_list.itemClicked.connect(self.load_rule_content)
        left_layout.addWidget(QLabel("规则文件:"))
        left_layout.addWidget(self.rule_files_list)
        
        # Add new rule file button (admin only)
        if self.user_role == "admin":
            add_rule_file_button = QPushButton("添加新规则文件")
            add_rule_file_button.clicked.connect(self.add_new_rule_file)
            left_layout.addWidget(add_rule_file_button)
        
        splitter.addWidget(left_panel)
        
        # Right panel - Rule content
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Rule content
        self.rule_content_edit = QTextEdit()
        self.rule_content_edit.setReadOnly(self.user_role != "admin")  # Read-only for regular users
        right_layout.addWidget(QLabel("规则内容:"))
        right_layout.addWidget(self.rule_content_edit)
        
        # Save button (admin only)
        if self.user_role == "admin":
            save_button = QPushButton("保存规则")
            save_button.clicked.connect(self.save_rule_content)
            right_layout.addWidget(save_button)
        
        # Info area
        self.info_label = QLabel()
        self.info_label.setStyleSheet("color: #3498db;")
        right_layout.addWidget(self.info_label)
        
        splitter.addWidget(right_panel)
        
        # Set splitter proportions
        splitter.setSizes([200, 600])
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        
        # Test rules button (both roles)
        test_button = QPushButton("测试规则")
        test_button.clicked.connect(self.test_rules)
        button_layout.addWidget(test_button)
        
        # Close button
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.close)
        button_layout.addWidget(close_button)
        
        main_layout.addLayout(button_layout)
    
    def load_rule_files(self):
        """Load all rule files from the rules directory"""
        self.rule_files_list.clear()
        
        if not os.path.exists(self.rules_dir):
            QMessageBox.critical(self, 
                "错误", 
                f"规则目录 '{self.rules_dir}' 不存在!",
                QMessageBox.Ok)
            return
            
        for rule_file in os.listdir(self.rules_dir):
            if rule_file.endswith('.txt'):
                self.rule_files_list.addItem(rule_file)
    
    def load_rule_content(self, item):
        """Load content of the selected rule file"""
        self.current_rule_file = item.text()
        file_path = os.path.join(self.rules_dir, self.current_rule_file)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                self.rule_content_edit.setText(content)
                self.info_label.setText(f"已加载: {self.current_rule_file}")
        except Exception as e:
            self.rule_content_edit.setText("")
            self.info_label.setText(f"加载 {self.current_rule_file} 时出错: {str(e)}")
    
    def save_rule_content(self):
        """Save changes to rule file (admin only)"""
        if self.user_role != "admin":
            QMessageBox.warning(self, "权限拒绝", "只有管理员可以修改规则")
            return
            
        if not self.current_rule_file:
            QMessageBox.warning(self, "保存失败", "请先选择一个规则文件")
            return
            
        file_path = os.path.join(self.rules_dir, self.current_rule_file)
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(self.rule_content_edit.toPlainText())
            self.info_label.setText(f"规则 {self.current_rule_file} 已保存")
            
            # Emit signal that rules have been updated
            self.rules_updated.emit()
            
            QMessageBox.information(self, "保存成功", f"规则文件 {self.current_rule_file} 已成功保存")
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存规则时出错: {str(e)}")
    
    def add_new_rule_file(self):
        """Add a new rule file (admin only)"""
        if self.user_role != "admin":
            QMessageBox.warning(self, "权限拒绝", "只有管理员可以添加新规则")
            return
            
        dialog = AddRuleFileDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            filename = dialog.get_filename()
            content = dialog.get_content()
            
            # Ensure file has .txt extension
            if not filename.endswith('.txt'):
                filename += '.txt'
                
            file_path = os.path.join(self.rules_dir, filename)
            
            # Check if file already exists
            if os.path.exists(file_path):
                reply = QMessageBox.question(self, "文件已存在", 
                    f"规则文件 {filename} 已存在。要覆盖它吗?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.No:
                    return
            
            # Save the file
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.load_rule_files()  # Refresh list
                
                # Select the new file
                items = self.rule_files_list.findItems(filename, Qt.MatchExactly)
                if items:
                    self.rule_files_list.setCurrentItem(items[0])
                    self.load_rule_content(items[0])
                
                # Emit signal that rules have been updated
                self.rules_updated.emit()
                
                QMessageBox.information(self, "成功", f"新规则文件 {filename} 已创建")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"创建规则文件时出错: {str(e)}")
    
    def test_rules(self):
        """Test if the rules are properly formatted and loadable"""
        if not os.path.exists(self.rules_dir):
            QMessageBox.critical(self, "错误", "规则目录不存在!")
            return
            
        # Simple test - try to load all rules
        rules_loaded = 0
        errors = []
        
        for rule_file in os.listdir(self.rules_dir):
            file_path = os.path.join(self.rules_dir, rule_file)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    # Check if there's any content
                    if not any(line.strip() for line in lines):
                        errors.append(f"{rule_file} - 文件为空")
                        continue
                        
                    # Count non-empty lines
                    valid_lines = sum(1 for line in lines if line.strip())
                    rules_loaded += valid_lines
            except Exception as e:
                errors.append(f"{rule_file} - {str(e)}")
        
        if errors:
            error_text = "\n".join(errors)
            QMessageBox.warning(self, "测试结果", 
                f"加载了 {rules_loaded} 条规则，但有 {len(errors)} 个错误:\n\n{error_text}")
        else:
            QMessageBox.information(self, "测试成功", 
                f"成功加载了 {rules_loaded} 条规则，未发现错误")


class AddRuleFileDialog(QDialog):
    """Dialog for adding a new rule file"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the dialog UI"""
        self.setWindowTitle("添加新规则文件")
        self.setMinimumSize(500, 400)
        
        layout = QVBoxLayout(self)
        
        # File name input
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("文件名:"))
        self.filename_edit = QLineEdit()
        self.filename_edit.setPlaceholderText("例如: custom_rules.txt")
        name_layout.addWidget(self.filename_edit)
        layout.addLayout(name_layout)
        
        # Rule type selection
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("规则类型:"))
        self.rule_type_combo = QComboBox()
        self.rule_type_combo.addItems(["HTTP 关键词", "Nikto 攻击关键词", "Shell Shock 关键词", "用户名关键词", "密码关键词", "自定义"])
        self.rule_type_combo.currentIndexChanged.connect(self.update_template)
        type_layout.addWidget(self.rule_type_combo)
        layout.addLayout(type_layout)
        
        # Content editor
        layout.addWidget(QLabel("规则内容:"))
        self.content_edit = QTextEdit()
        self.content_edit.setPlaceholderText("每行输入一个规则")
        layout.addWidget(self.content_edit)
        
        # Buttons
        button_layout = QHBoxLayout()
        ok_button = QPushButton("确认")
        ok_button.clicked.connect(self.accept)
        cancel_button = QPushButton("取消")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        
        # Initialize with default template
        self.update_template()
    
    def update_template(self):
        """Update the content editor with a template based on the selected rule type"""
        rule_type = self.rule_type_combo.currentText()
        
        if "HTTP" in rule_type:
            self.content_edit.setText("Authorization: Basic\nWWW-Authenticate")
            self.filename_edit.setText("http.txt")
        elif "Nikto" in rule_type:
            self.content_edit.setText("Nikto\nnikto\nNIKTO")
            self.filename_edit.setText("nikto.txt")
        elif "Shell Shock" in rule_type:
            self.content_edit.setText("() { :; };\n(){:;};\n() { :;};\n() { : ; } ;\n() {:; };")
            self.filename_edit.setText("shock.txt")
        elif "用户名" in rule_type:
            self.content_edit.setText("mac\nlog\nlogin\nwpname\nahd_username\nunickname\nnickname\nuser\nuser_name")
            self.filename_edit.setText("user.txt")
        elif "密码" in rule_type:
            self.content_edit.setText("pass\nahd_password\npassword\n_password\npasswd\nsession_password\nsessionpassword")
            self.filename_edit.setText("pass.txt")
        else:  # Custom
            self.content_edit.setText("")
            self.filename_edit.setText("custom.txt")
    
    def get_filename(self):
        """Get the entered filename"""
        return self.filename_edit.text()
    
    def get_content(self):
        """Get the entered content"""
        return self.content_edit.toPlainText()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # For testing - default to admin role
    dialog = RulesManager(user_role="admin")
    dialog.show()
    sys.exit(app.exec_())
