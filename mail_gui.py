import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QTableWidget, QTableWidgetItem, QTextEdit, 
                            QLabel, QPushButton, QHeaderView, QSplitter, QMenu, QComboBox, QDateEdit)
from PyQt6.QtCore import Qt, QDateTime
from PyQt6.QtGui import QFont, QIcon, QPalette, QColor, QAction
import mysql.connector
from datetime import datetime
import logging
import re
from mail_client import MailClient

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
        
        # ===== 新增：收取邮件功能区 =====
        fetch_widget = QWidget()
        fetch_layout = QHBoxLayout(fetch_widget)
        fetch_layout.setContentsMargins(0, 0, 0, 0)
        fetch_layout.setSpacing(10)

        self.protocol_combo = QComboBox()
        self.protocol_combo.addItems(["IMAP", "POP3"])
        self.protocol_combo.setCurrentIndex(1)
        fetch_layout.addWidget(QLabel("协议："))
        fetch_layout.addWidget(self.protocol_combo)

        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.start_date_edit.setDateTime(QDateTime.currentDateTime().addMonths(-1))
        fetch_layout.addWidget(QLabel("起始日期："))
        fetch_layout.addWidget(self.start_date_edit)

        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.end_date_edit.setDateTime(QDateTime.currentDateTime())
        fetch_layout.addWidget(QLabel("结束日期："))
        fetch_layout.addWidget(self.end_date_edit)

        self.fetch_button = QPushButton("收取邮件")
        self.fetch_button.clicked.connect(self.on_fetch_mail)
        fetch_layout.addWidget(self.fetch_button)

        # 新增：刷新邮件列表按钮
        self.refresh_button = QPushButton("刷新邮件列表")
        self.refresh_button.clicked.connect(self.load_mail_list)
        fetch_layout.addWidget(self.refresh_button)

        # 新增：收取状态提示label
        self.status_label = QLabel("")
        fetch_layout.addWidget(self.status_label)

        main_layout.addWidget(fetch_widget)
        # ===== 新增功能区结束 =====
        
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
        header_layout.setSpacing(4)
        header_layout.setContentsMargins(8, 8, 8, 8)

        # 主题单独一行，字体加粗加大
        self.subject_label = SelectableLabel("主题：")
        subject_font = QFont()
        subject_font.setBold(True)
        subject_font.setPointSize(13)
        self.subject_label.setFont(subject_font)
        header_layout.addWidget(self.subject_label)

        # 发件人和时间一行
        sender_time_widget = QWidget()
        sender_time_layout = QHBoxLayout(sender_time_widget)
        sender_time_layout.setSpacing(10)
        sender_time_layout.setContentsMargins(0, 0, 0, 0)
        self.sender_label = SelectableLabel("发件人：")
        self.date_label = SelectableLabel("时间：")
        sender_time_layout.addWidget(self.sender_label)
        sender_time_layout.addWidget(self.date_label)
        sender_time_layout.addStretch()
        header_layout.addWidget(sender_time_widget)

        # 收件人单独一行，可换行
        self.recipients_label = SelectableLabel("收件人：")
        self.recipients_label.setWordWrap(True)
        header_layout.addWidget(self.recipients_label)

        # 抄送单独一行，可换行
        self.cc_label = SelectableLabel("抄送：")
        self.cc_label.setWordWrap(True)
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
        # 每次都新建连接，确保数据最新
        conn = mysql.connector.connect(
            host='127.0.0.1',
            port=3306,
            user='root',
            password='root',
            database='mymail'
        )
        cursor = conn.cursor()
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
            conn.close()
            
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
                self.subject_label.setText(f"主题：{subject}")
                self.sender_label.setText(f"发件人：{sender}")
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

    def on_fetch_mail(self):
        """点击收取邮件按钮，调用MailClient收取邮件"""
        self.status_label.setText("正在收取邮件，请稍候...")
        QApplication.processEvents()  # 立即刷新界面
        protocol = self.protocol_combo.currentText().lower()
        start_date = self.start_date_edit.date().toPyDate()
        end_date = self.end_date_edit.date().toPyDate()
        # 转为datetime对象
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())
        logger.info(f"开始收取邮件，协议: {protocol}, 起始: {start_dt}, 结束: {end_dt}")
        client = MailClient()
        if protocol == "pop3":
            client.process_emails_pop3(start_dt, end_dt)
        else:
            client.process_emails(start_dt, end_dt)
        self.load_mail_list()
        self.status_label.setText("")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MailClientGUI()
    window.show()
    sys.exit(app.exec()) 