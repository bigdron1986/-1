# email_client.py
"""Клиент для получения отчетов по почте через IMAP"""

import imaplib
import email
from email.header import decode_header
import base64
from datetime import datetime, timedelta
import os
import tempfile
import shutil


class EmailReportClient:
    """Клиент для загрузки отчетов с почты Яндекс"""
    
    def __init__(self, login, password, imap_server='imap.yandex.ru', imap_port=993, debug=False):
        self.login = login
        self.password = password
        self.imap_server = imap_server
        self.imap_port = imap_port
        self.connection = None
        self.debug = debug
    
    def connect(self):
        """Подключение к почтовому ящику"""
        try:
            self.connection = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            self.connection.login(self.login, self.password)
            self.connection.select('INBOX')
            return True, "Подключение успешно"
        except imaplib.IMAP4.error as e:
            return False, f"Ошибка подключения: {str(e)}"
        except Exception as e:
            return False, f"Ошибка: {str(e)}"
    
    def disconnect(self):
        """Отключение от почтового ящика"""
        if self.connection:
            try:
                self.connection.close()
                self.connection.logout()
            except:
                pass
            self.connection = None
    
    def decode_subject(self, subject):
        """Декодирование темы письма"""
        if not subject:
            return ""
        
        decoded = decode_header(subject)
        result = ""
        for content, encoding in decoded:
            if isinstance(content, bytes):
                try:
                    result += content.decode(encoding or 'utf-8')
                except:
                    result += content.decode('latin-1')
            else:
                result += content
        return result
    
    def decode_sender(self, sender):
        """Декодирование отправителя"""
        if not sender:
            return ""
        
        decoded = decode_header(sender)
        result = ""
        for content, encoding in decoded:
            if isinstance(content, bytes):
                try:
                    result += content.decode(encoding or 'utf-8')
                except:
                    result += content.decode('latin-1')
            else:
                result += content
        return result
    
    def fetch_reports(self, sender_email='ams10@aminosib.ru', days_back=365, existing_dates=None):
        """
        Получение отчетов с почты.
        Если дата файла уже есть в existing_dates — файл пропускается (не скачивается).
        
        Args:
            sender_email: Email отправителя (по умолчанию ams10@aminosib.ru)
            days_back: За какой период искать письма (дней). 0 = все письма.
            existing_dates: set строк YYYY-MM-DD — даты, уже загруженные в БД
        
        Returns:
            dict: {
                'success': bool,
                'message': str,
                'emails_found': int,
                'attachments': list[dict]
            }
        """
        import re
        result = {
            'success': False,
            'message': '',
            'emails_found': 0,
            'attachments': []
        }
        
        if not self.connection:
            success, msg = self.connect()
            if not success:
                result['message'] = msg
                return result
        
        try:
            # Поиск писем от отправителя с фильтром по дате
            if days_back > 0:
                date_from = datetime.now() - timedelta(days=days_back)
                date_from_str = date_from.strftime('%d-%b-%Y').upper()
                search_criteria = f'(FROM "{sender_email}" SINCE {date_from_str})'
            else:
                search_criteria = f'(FROM "{sender_email}")'
            
            status, messages = self.connection.search(None, search_criteria)
            
            if status != 'OK':
                result['message'] = "Ошибка поиска писем"
                return result
            
            email_ids = messages[0].split()
            result['emails_found'] = len(email_ids)
            
            if not email_ids:
                result['message'] = f"Писем от {sender_email} не найдено"
                result['success'] = True
                return result
            
            for email_id in email_ids:
                try:
                    status, msg_data = self.connection.fetch(email_id, '(RFC822)')
                    if status != 'OK':
                        continue
                    
                    raw_email = msg_data[0][1]
                    email_message = email.message_from_bytes(raw_email)
                    
                    subject = self.decode_subject(email_message.get('Subject'))
                    sender = self.decode_sender(email_message.get('From'))
                    date_str = email_message.get('Date', '')
                    
                    attachments = self._extract_attachments(email_message)
                    
                    for attachment in attachments:
                        fname = attachment['filename']
                        if not (fname.startswith('termo_') and fname.endswith('.xlsx')):
                            continue

                        # Проверка по дате в имени файла
                        if existing_dates:
                            date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', fname)
                            if date_match:
                                from datetime import datetime as dt
                                try:
                                    file_date = dt.strptime(date_match.group(1), '%d.%m.%Y').strftime('%Y-%m-%d')
                                    if file_date in existing_dates:
                                        continue
                                except ValueError:
                                    pass

                        attachment['email_subject'] = subject
                        attachment['email_sender'] = sender
                        attachment['email_date'] = date_str
                        result['attachments'].append(attachment)
                    
                except Exception as e:
                    continue
            
            result['success'] = True
            result['message'] = f"Найдено {len(result['attachments'])} новых вложений termo_*.xlsx"
            
        except Exception as e:
            result['message'] = f"Ошибка: {str(e)}"
        
        return result
    
    def _extract_attachments(self, email_message):
        """Извлечение вложений из письма"""
        attachments = []
        
        if email_message.is_multipart():
            for part in email_message.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get_content_disposition())
                
                if 'attachment' in content_disposition:
                    try:
                        filename = part.get_filename()
                        if filename:
                            filename = self.decode_subject(filename)
                            payload = part.get_payload(decode=True)
                            if payload:
                                attachments.append({
                                    'filename': filename,
                                    'data': payload,
                                    'content_type': content_type,
                                    'size': len(payload)
                                })
                    except:
                        pass
        
        return attachments
    
    def save_attachment_to_temp(self, attachment):
        """Сохранение вложения во временный файл"""
        try:
            temp_dir = tempfile.mkdtemp(prefix='email_reports_')
            file_path = os.path.join(temp_dir, attachment['filename'])
            
            with open(file_path, 'wb') as f:
                f.write(attachment['data'])
            
            return file_path, temp_dir
        except:
            return None, None
    
    def cleanup_temp(self, temp_dir):
        """Очистка временных файлов"""
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except:
                pass


def test_email_connection(login, password):
    """Тест подключения к почте"""
    client = EmailReportClient(login, password)
    success, message = client.connect()
    client.disconnect()
    return success, message
