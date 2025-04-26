import os
import imaplib
import email
from email.header import decode_header
from datetime import datetime
import mysql.connector
from dotenv import load_dotenv
import logging
import email.utils
import re
import quopri
import base64

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()

class MailClient:
    def __init__(self):
        self.email_user = os.getenv('EMAIL_USER')
        self.email_password = os.getenv('EMAIL_PASSWORD')
        self.email_host = os.getenv('EMAIL_HOST')
        self.email_port = int(os.getenv('EMAIL_PORT'))
        
        # 数据库连接配置
        self.db_config = {
            'host': '127.0.0.1',
            'port': 3306,
            'user': 'root',
            'password': 'root',
            'database': 'mymail'
        }
        
    def connect_to_mailbox(self):
        """连接到邮箱服务器"""
        try:
            mail = imaplib.IMAP4_SSL(self.email_host, self.email_port)
            mail.login(self.email_user, self.email_password)
            return mail
        except Exception as e:
            logger.error(f"连接邮箱服务器失败: {str(e)}")
            raise

    def connect_to_database(self):
        """连接到MySQL数据库"""
        try:
            conn = mysql.connector.connect(**self.db_config)
            return conn
        except Exception as e:
            logger.error(f"连接数据库失败: {str(e)}")
            raise

    def decode_email_header(self, header):
        """解码邮件头信息"""
        if not header:
            return ""
        decoded_header = decode_header(header)
        header_parts = []
        for content, charset in decoded_header:
            if isinstance(content, bytes):
                if charset:
                    try:
                        header_parts.append(content.decode(charset))
                    except:
                        header_parts.append(content.decode('utf-8', errors='ignore'))
                else:
                    header_parts.append(content.decode('utf-8', errors='ignore'))
            else:
                header_parts.append(content)
        return ' '.join(header_parts)

    def decode_content(self, part):
        """解码邮件内容"""
        content = ""
        content_type = part.get_content_type()
        content_charset = part.get_content_charset()
        
        try:
            if part.get_content_maintype() == 'text':
                if part.get('Content-Transfer-Encoding') == 'quoted-printable':
                    content = quopri.decodestring(part.get_payload()).decode(content_charset or 'utf-8', errors='ignore')
                elif part.get('Content-Transfer-Encoding') == 'base64':
                    content = base64.b64decode(part.get_payload()).decode(content_charset or 'utf-8', errors='ignore')
                else:
                    content = part.get_payload(decode=True).decode(content_charset or 'utf-8', errors='ignore')
            else:
                # 对于非文本内容，记录类型
                content = f"[非文本内容: {content_type}]"
        except Exception as e:
            logger.warning(f"解码内容失败: {str(e)}")
            content = "[内容解码失败]"
            
        return content

    def get_email_content(self, message):
        """获取邮件内容"""
        content = []
        
        if message.is_multipart():
            for part in message.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                
                # 跳过附件
                if "attachment" in content_disposition:
                    continue
                    
                # 处理文本内容
                if content_type == "text/plain":
                    part_content = self.decode_content(part)
                    if part_content:
                        content.append(part_content)
                elif content_type == "text/html":
                    # 对于HTML内容，可以添加标记
                    part_content = self.decode_content(part)
                    if part_content:
                        content.append(f"[HTML内容]\n{part_content}")
        else:
            # 非多部分邮件
            content_type = message.get_content_type()
            if content_type == "text/plain":
                content.append(self.decode_content(message))
            elif content_type == "text/html":
                content.append(f"[HTML内容]\n{self.decode_content(message)}")
            else:
                content.append(f"[非文本内容: {content_type}]")
        
        # 合并所有内容
        return "\n\n".join(content) if content else "[无内容]"

    def parse_date(self, date_str):
        """解析邮件日期"""
        try:
            # 尝试使用email.utils解析日期
            parsed_date = email.utils.parsedate_to_datetime(date_str)
            return parsed_date
        except Exception as e:
            logger.warning(f"使用email.utils解析日期失败: {str(e)}")
            try:
                # 尝试使用datetime直接解析
                # 移除时区信息
                date_str = re.sub(r'[+-]\d{4}', '', date_str).strip()
                return datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S')
            except Exception as e:
                logger.warning(f"使用datetime解析日期失败: {str(e)}")
                return datetime.now()

    def save_email_to_db(self, conn, email_data):
        """保存邮件到数据库"""
        cursor = conn.cursor()
        try:
            sql = """
            INSERT INTO emails (message_id, subject, sender, recipients, cc, bcc, content, received_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
            subject = VALUES(subject),
            sender = VALUES(sender),
            recipients = VALUES(recipients),
            cc = VALUES(cc),
            bcc = VALUES(bcc),
            content = VALUES(content),
            received_date = VALUES(received_date)
            """
            cursor.execute(sql, (
                email_data['message_id'],
                email_data['subject'],
                email_data['sender'],
                email_data['recipients'],
                email_data['cc'],
                email_data['bcc'],
                email_data['content'],
                email_data['received_date']
            ))
            conn.commit()
            logger.info(f"邮件已保存到数据库: {email_data['subject']}")
        except Exception as e:
            logger.error(f"保存邮件到数据库失败: {str(e)}")
            conn.rollback()
        finally:
            cursor.close()

    def process_emails(self):
        """处理邮件"""
        mail = self.connect_to_mailbox()
        conn = self.connect_to_database()
        
        try:
            # 选择收件箱
            mail.select('INBOX')
            
            # 获取所有邮件
            _, messages = mail.search(None, 'ALL')
            message_count = len(messages[0].split())
            logger.info(f"找到 {message_count} 封邮件")
            
            for num in messages[0].split():
                try:
                    _, msg_data = mail.fetch(num, '(RFC822)')
                    email_body = msg_data[0][1]
                    message = email.message_from_bytes(email_body)
                    
                    # 获取邮件ID
                    message_id = message.get('Message-ID', '')
                    if not message_id:
                        message_id = f"NO_ID_{num.decode()}"
                    
                    # 解析日期
                    date_str = message.get('Date', '')
                    received_date = self.parse_date(date_str)
                    
                    # 获取邮件内容
                    content = self.get_email_content(message)
                    logger.info(f"邮件内容长度: {len(content)}")
                    
                    email_data = {
                        'message_id': message_id,
                        'subject': self.decode_email_header(message.get('Subject', '')),
                        'sender': self.decode_email_header(message.get('From', '')),
                        'recipients': self.decode_email_header(message.get('To', '')),
                        'cc': self.decode_email_header(message.get('Cc', '')),
                        'bcc': self.decode_email_header(message.get('Bcc', '')),
                        'content': content,
                        'received_date': received_date
                    }
                    
                    logger.info(f"正在处理邮件: {email_data['subject']} (ID: {message_id})")
                    self.save_email_to_db(conn, email_data)
                    
                except Exception as e:
                    logger.error(f"处理邮件 {num} 时发生错误: {str(e)}")
                    continue
                
        except Exception as e:
            logger.error(f"处理邮件时发生错误: {str(e)}")
        finally:
            mail.close()
            mail.logout()
            conn.close()

if __name__ == "__main__":
    client = MailClient()
    client.process_emails() 