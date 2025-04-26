import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QTableWidget, QTableWidgetItem, QTextEdit, 
                            QLabel, QPushButton, QHeaderView, QSplitter, QMenu)
from PyQt6.QtCore import Qt, QDateTime
from PyQt6.QtGui import QFont, QIcon, QPalette, QColor, QAction
import mysql.connector
from datetime import datetime
import logging
import re

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SelectableLabel(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.IBeamCursor)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | 
                                   Qt.TextInteractionFlag.TextSelectableByKeyboard)
        
    def contextMenuEvent(self, event):
        menu = QMenu(self)
        copy_action = QAction("复制", self)
        copy_action.triggered.connect(self.copy_text)
        menu.addAction(copy_action)
        menu.exec(event.globalPos())
        
    def copy_text(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.text())

class MailClientGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("申诉邮件处理器")
        self.setGeometry(100, 100, 1200, 800)
        
        # 设置应用图标
        self.setWindowIcon(QIcon("mail_icon.png"))
        
        # 设置现代风格的颜色
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f8ff;
            }
            QTableWidget {
                background-color: white;
                alternate-background-color: #f5f5f5;
                gridline-color: #e0e0e0;
                border: 1px solid #e0e0e0;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QTableWidget::item:selected {
                background-color: #e3f2fd;
                color: black;
            }
            QHeaderView::section {
                background-color: #e3f2fd;
                padding: 5px;
                border: 1px solid #e0e0e0;
                font-weight: bold;
            }
            QTextEdit {
                background-color: white;
                border: 1px solid #e0e0e0;
                padding: 5px;
            }
            QLabel {
                color: #2c3e50;
            }
        """)
        
        # 创建主窗口部件
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        # 创建主布局
        main_layout = QVBoxLayout(main_widget)
        
        # 创建分割器
        splitter = QSplitter(Qt.Orientation.Vertical)
        main_layout.addWidget(splitter)
        
        # 创建邮件列表
        self.mail_list = QTableWidget()
        self.mail_list.setColumnCount(4)
        self.mail_list.setHorizontalHeaderLabels(["发件人", "主题", "时间", "ID"])
        self.mail_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.mail_list.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.mail_list.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.mail_list.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.mail_list.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.mail_list.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.mail_list.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.mail_list.itemSelectionChanged.connect(self.on_mail_selected)
        self.mail_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.mail_list.customContextMenuRequested.connect(self.show_context_menu)
        
        # 创建邮件内容显示区域
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        
        # 邮件头部信息
        header_widget = QWidget()
        header_layout = QVBoxLayout(header_widget)
        
        self.sender_label = SelectableLabel("发件人：")
        self.subject_label = SelectableLabel("主题：")
        self.date_label = SelectableLabel("时间：")
        self.recipients_label = SelectableLabel("收件人：")
        self.cc_label = SelectableLabel("抄送：")
        
        # 设置标签字体
        font = QFont()
        font.setBold(True)
        for label in [self.sender_label, self.subject_label, self.date_label, 
                     self.recipients_label, self.cc_label]:
            label.setFont(font)
        
        header_layout.addWidget(self.sender_label)
        header_layout.addWidget(self.subject_label)
        header_layout.addWidget(self.date_label)
        header_layout.addWidget(self.recipients_label)
        header_layout.addWidget(self.cc_label)
        
        # 邮件内容
        self.content_text = QTextEdit()
        self.content_text.setReadOnly(True)
        self.content_text.setFont(QFont("Microsoft YaHei", 10))
        self.content_text.setAcceptRichText(True)
        
        content_layout.addWidget(header_widget)
        content_layout.addWidget(self.content_text)
        
        # 添加到分割器
        splitter.addWidget(self.mail_list)
        splitter.addWidget(content_widget)
        splitter.setSizes([300, 500])
        
        # 连接数据库
        self.connect_to_database()
        
        # 加载邮件列表
        self.load_mail_list()
        
    def show_context_menu(self, position):
        menu = QMenu()
        copy_action = QAction("复制", self)
        copy_action.triggered.connect(self.copy_selected_text)
        menu.addAction(copy_action)
        menu.exec(self.mail_list.viewport().mapToGlobal(position))
        
    def copy_selected_text(self):
        selected_items = self.mail_list.selectedItems()
        if selected_items:
            text = selected_items[0].text()
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
        
    def connect_to_database(self):
        """连接到MySQL数据库"""
        try:
            self.conn = mysql.connector.connect(
                host='127.0.0.1',
                port=3306,
                user='root',
                password='root',
                database='mymail'
            )
            logger.info("数据库连接成功")
        except Exception as e:
            logger.error(f"连接数据库失败: {str(e)}")
            sys.exit(1)
            
    def load_mail_list(self):
        """加载邮件列表"""
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT message_id, subject, sender, received_date 
                FROM emails 
                ORDER BY received_date DESC
            """)
            
            self.mail_list.setRowCount(0)
            for row in cursor.fetchall():
                message_id, subject, sender, received_date = row
                row_position = self.mail_list.rowCount()
                self.mail_list.insertRow(row_position)
                
                # 设置单元格内容
                self.mail_list.setItem(row_position, 0, QTableWidgetItem(sender))
                self.mail_list.setItem(row_position, 1, QTableWidgetItem(subject))
                self.mail_list.setItem(row_position, 2, QTableWidgetItem(
                    received_date.strftime("%Y-%m-%d %H:%M")))
                self.mail_list.setItem(row_position, 3, QTableWidgetItem(message_id))
            
            logger.info(f"成功加载 {self.mail_list.rowCount()} 封邮件")
                
        except Exception as e:
            logger.error(f"加载邮件列表失败: {str(e)}")
        finally:
            cursor.close()
            
    def is_html_content(self, content):
        """判断内容是否为HTML格式"""
        # 简单的HTML检测
        html_patterns = [
            r'<html[^>]*>',
            r'<body[^>]*>',
            r'<div[^>]*>',
            r'<p[^>]*>',
            r'<br[^>]*>',
            r'<span[^>]*>',
            r'<table[^>]*>',
            r'<tr[^>]*>',
            r'<td[^>]*>',
            r'<a[^>]*>',
            r'<img[^>]*>',
            r'<style[^>]*>',
            r'<script[^>]*>'
        ]
        
        for pattern in html_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        return False
            
    def on_mail_selected(self):
        """当选择邮件时显示邮件内容"""
        selected_rows = self.mail_list.selectedItems()
        if not selected_rows:
            return
            
        row = selected_rows[0].row()
        message_id = self.mail_list.item(row, 3).text()
        logger.info(f"选择邮件: {message_id}")
        
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT subject, sender, recipients, cc, content, received_date 
                FROM emails 
                WHERE message_id = %s
            """, (message_id,))
            
            row = cursor.fetchone()
            if row:
                subject, sender, recipients, cc, content, received_date = row
                
                # 更新邮件信息
                self.sender_label.setText(f"发件人：{sender}")
                self.subject_label.setText(f"主题：{subject}")
                self.date_label.setText(f"时间：{received_date.strftime('%Y-%m-%d %H:%M:%S')}")
                self.recipients_label.setText(f"收件人：{recipients}")
                self.cc_label.setText(f"抄送：{cc}")
                
                # 更新邮件内容
                if content:
                    logger.info(f"邮件内容长度: {len(content)}")
                    if self.is_html_content(content):
                        # 如果是HTML内容，使用HTML模式显示
                        self.content_text.setHtml(content)
                    else:
                        # 如果是纯文本内容，使用纯文本模式显示
                        self.content_text.setPlainText(content)
                else:
                    logger.warning("邮件内容为空")
                    self.content_text.setPlainText("(无内容)")
                
        except Exception as e:
            logger.error(f"加载邮件内容失败: {str(e)}")
            self.content_text.setPlainText(f"加载邮件内容失败: {str(e)}")
        finally:
            cursor.close()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MailClientGUI()
    window.show()
    sys.exit(app.exec()) 