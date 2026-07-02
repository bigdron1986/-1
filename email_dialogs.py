# email_dialogs.py
"""Диалоги для работы с почтой"""

from datetime import datetime
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
                             QLineEdit, QCheckBox, QGroupBox, QFormLayout, 
                             QDialogButtonBox, QMessageBox, QSpinBox, QComboBox, 
                             QTextEdit, QProgressBar)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from email_client import EmailReportClient, test_email_connection
from env_loader import get_env


class EmailSettingsDialog(QDialog):
    """Диалог настроек почты"""
    
    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self.settings = settings or {}
        self._apply_env_defaults()
        
        self.setWindowTitle("📧 Настройки почты")
        self.setMinimumWidth(450)
        self.setModal(True)
        
        self.initUI()
    
    def _apply_env_defaults(self):
        if not self.settings.get('login'):
            self.settings['login'] = get_env('EMAIL_LOGIN')
        if not self.settings.get('password'):
            self.settings['password'] = get_env('EMAIL_PASSWORD')
        if not self.settings.get('imap_server') or self.settings['imap_server'] == 'imap.yandex.ru':
            self.settings['imap_server'] = get_env('EMAIL_IMAP_SERVER', 'imap.yandex.ru')
        if not self.settings.get('imap_port') or self.settings['imap_port'] == 993:
            self.settings['imap_port'] = int(get_env('EMAIL_IMAP_PORT', '993'))
        if not self.settings.get('sender_email') or self.settings['sender_email'] == 'ams10@aminosib.ru':
            self.settings['sender_email'] = get_env('EMAIL_SENDER', 'ams10@aminosib.ru')
        if not self.settings.get('days_back') or self.settings['days_back'] == 30:
            self.settings['days_back'] = int(get_env('EMAIL_DAYS_BACK', '30'))

    def initUI(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Заголовок
        title = QLabel("📧 Настройки подключения к почте Яндекс")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #89b4fa;")
        layout.addWidget(title)
        
        # Описание
        desc = QLabel(
            "Для подключения к почте Яндекс необходимо:\n"
            "1. Включить IMAP в настройках почтового ящика\n"
            "2. Создать пароль приложения (настройки → безопасность)\n"
            "3. Ввести логин и пароль приложения ниже"
        )
        desc.setStyleSheet("font-size: 11px; color: #a6adc8; line-height: 1.5;")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        # Настройки подключения
        conn_group = QGroupBox("🔌 Параметры подключения")
        conn_layout = QFormLayout()
        conn_layout.setSpacing(10)
        
        # Логин
        self.login_edit = QLineEdit()
        self.login_edit.setPlaceholderText("example@yandex.ru")
        self.login_edit.setText(self.settings.get('login', ''))
        self.login_edit.setMinimumWidth(250)
        conn_layout.addRow("Логин Яндекс:", self.login_edit)
        
        # Пароль
        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("Пароль приложения")
        self.password_edit.setText(self.settings.get('password', ''))
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        conn_layout.addRow("Пароль приложения:", self.password_edit)
        
        # Показать пароль
        self.show_password_check = QCheckBox("Показать пароль")
        self.show_password_check.stateChanged.connect(self.toggle_password_visibility)
        conn_layout.addRow("", self.show_password_check)
        
        # IMAP сервер
        self.imap_server_edit = QLineEdit()
        self.imap_server_edit.setText(self.settings.get('imap_server', 'imap.yandex.ru'))
        self.imap_server_edit.setMaximumWidth(200)
        conn_layout.addRow("IMAP сервер:", self.imap_server_edit)
        
        # Порт
        self.imap_port_spin = QSpinBox()
        self.imap_port_spin.setRange(1, 65535)
        self.imap_port_spin.setValue(self.settings.get('imap_port', 993))
        self.imap_port_spin.setMaximumWidth(200)
        conn_layout.addRow("Порт:", self.imap_port_spin)
        
        conn_group.setLayout(conn_layout)
        layout.addWidget(conn_group)
        
        # Настройки загрузки
        download_group = QGroupBox("📥 Параметры загрузки")
        download_layout = QFormLayout()
        download_layout.setSpacing(10)
        
        # Email отправителя
        self.sender_email_edit = QLineEdit()
        self.sender_email_edit.setText(self.settings.get('sender_email', 'ams10@aminosib.ru'))
        self.sender_email_edit.setMaximumWidth(250)
        download_layout.addRow("Email отправителя:", self.sender_email_edit)
        
        # Период
        self.days_back_spin = QSpinBox()
        self.days_back_spin.setRange(1, 3650)
        self.days_back_spin.setValue(self.settings.get('days_back', 30))
        self.days_back_spin.setSuffix(" дн.")
        self.days_back_spin.setMaximumWidth(200)
        download_layout.addRow("Период проверки:", self.days_back_spin)
        
        download_group.setLayout(download_layout)
        layout.addWidget(download_group)
        
        # Кнопки
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        # Тест подключения
        self.test_btn = QPushButton("🔍 Тест подключения")
        self.test_btn.setStyleSheet("background-color: #89b4fa; color: #1e1e2e; font-weight: bold; padding: 8px 16px;")
        self.test_btn.clicked.connect(self.test_connection)
        button_layout.addWidget(self.test_btn)
        
        # Сохранить/Отмена
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        
        for btn in button_box.buttons():
            if button_box.buttonRole(btn) == QDialogButtonBox.ButtonRole.AcceptRole:
                btn.setStyleSheet("background-color: #a6e3a1; color: #1e1e2e; font-weight: bold; padding: 8px 20px;")
            else:
                btn.setStyleSheet("background-color: #45475a; padding: 8px 20px;")
        
        button_layout.addWidget(button_box)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def toggle_password_visibility(self, state):
        """Показать/скрыть пароль"""
        if state == Qt.CheckState.Checked:
            self.password_edit.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
    
    def test_connection(self):
        """Тест подключения к почте"""
        login = self.login_edit.text().strip()
        password = self.password_edit.text()
        
        if not login or not password:
            QMessageBox.warning(self, "Ошибка", "Введите логин и пароль")
            return
        
        self.test_btn.setEnabled(False)
        self.test_btn.setText("⏳ Проверка...")
        
        # Тест подключения
        success, message = test_email_connection(login, password)
        
        if success:
            QMessageBox.information(self, "Успех", f"✅ {message}")
        else:
            QMessageBox.critical(self, "Ошибка", f"❌ {message}")
        
        self.test_btn.setEnabled(True)
        self.test_btn.setText("🔍 Тест подключения")
    
    def get_settings(self):
        """Получить настройки"""
        return {
            'login': self.login_edit.text().strip(),
            'password': self.password_edit.text(),
            'imap_server': self.imap_server_edit.text().strip(),
            'imap_port': self.imap_port_spin.value(),
            'sender_email': self.sender_email_edit.text().strip(),
            'days_back': self.days_back_spin.value()
        }


class EmailReportWorker(QThread):
    """Рабочий поток для загрузки отчетов"""
    progress = pyqtSignal(str)  # Сообщение о прогрессе
    log = pyqtSignal(str)  # Лог сообщение
    finished = pyqtSignal(dict)  # Результат
    error = pyqtSignal(str)  # Ошибка
    
    def __init__(self, email_settings, existing_dates=None):
        super().__init__()
        self.email_settings = email_settings
        self.existing_dates = existing_dates or set()
    
    def run(self):
        try:
            self.progress.emit("Подключение к почте...")
            
            client = EmailReportClient(
                login=self.email_settings['login'],
                password=self.email_settings['password'],
                imap_server=self.email_settings.get('imap_server', 'imap.yandex.ru'),
                imap_port=self.email_settings.get('imap_port', 993),
                debug=True
            )
            
            # Поиск отчётов (только новых)
            self.progress.emit("🔍 Поиск новых писем...")
            result = client.fetch_reports(
                sender_email=self.email_settings.get('sender_email', 'ams10@aminosib.ru'),
                days_back=self.email_settings.get('days_back', 365),
                existing_dates=self.existing_dates
            )
            
            if not result['success']:
                self.error.emit(result['message'])
                return
            
            self.progress.emit(f"✅ Найдено {result['emails_found']} писем, {len(result['attachments'])} вложений")
            
            # Сохранение файлов
            if result['attachments']:
                self.progress.emit("💾 Сохранение файлов...")
                saved_files = []
                
                for idx, attachment in enumerate(result['attachments'], 1):
                    self.progress.emit(f"Сохранение {idx}/{len(result['attachments'])}: {attachment['filename']}")
                    file_path, temp_dir = client.save_attachment_to_temp(attachment)
                    if file_path:
                        saved_files.append({
                            'file_path': file_path,
                            'temp_dir': temp_dir,
                            'filename': attachment['filename'],
                            'email_subject': attachment.get('email_subject', ''),
                            'email_date': attachment.get('email_date', '')
                        })
                
                result['saved_files'] = saved_files
                self.progress.emit(f"✅ Сохранено файлов: {len(saved_files)}")
            
            client.disconnect()
            self.finished.emit(result)
            
        except Exception as e:
            import traceback
            self.error.emit(f"{str(e)}\n\n{traceback.format_exc()}")


class EmailDownloadDialog(QDialog):
    """Диалог загрузки отчетов с почты"""

    # Сигнал для обновления дат в главном окне
    dates_loaded = pyqtSignal(list)  # Список дат в формате YYYY-MM-DD

    def __init__(self, parent=None, email_settings=None, auto_process=True):
        super().__init__(parent)
        self.email_settings = email_settings or {}
        self.downloaded_files = []
        self.auto_process = auto_process  # Автоматическая обработка после загрузки
        self.parent_window = parent

        self.setWindowTitle("📥 Загрузка отчетов с почты")
        self.setMinimumWidth(550)
        self.setMinimumHeight(500)
        self.setModal(True)

        self.initUI()
        self.worker = None

    def initUI(self):
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # Заголовок
        title = QLabel("📥 Загрузка отчетов с почты Яндекс")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #89b4fa;")
        layout.addWidget(title)

        # Статус
        self.status_label = QLabel("Готов к загрузке")
        self.status_label.setStyleSheet("font-size: 12px; color: #a6adc8; padding: 8px; background-color: #313244; border-radius: 4px;")
        layout.addWidget(self.status_label)

        # Прогресс бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Бесконечный режим
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Лог
        log_group = QGroupBox("📝 Журнал операций")
        log_layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFontFamily("Consolas")
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e2e;
                color: #cdd6f4;
                font-size: 11px;
                border: 1px solid #45475a;
                border-radius: 4px;
                padding: 4px;
            }
        """)
        self.log_text.setMinimumHeight(150)
        log_layout.addWidget(self.log_text)
        
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)

        # Список файлов
        files_group = QGroupBox("📋 Найденные файлы")
        files_layout = QVBoxLayout()

        self.files_list = QComboBox()
        self.files_list.setEditable(False)
        self.files_list.setMinimumHeight(100)
        files_layout.addWidget(self.files_list)

        files_group.setLayout(files_layout)
        layout.addWidget(files_group)

        # Кнопки
        button_layout = QHBoxLayout()

        # Загрузить
        self.download_btn = QPushButton("📥 Загрузить отчеты")
        self.download_btn.setStyleSheet("background-color: #a6e3a1; color: #1e1e2e; font-weight: bold; padding: 10px 20px;")
        self.download_btn.clicked.connect(self.start_download)
        button_layout.addWidget(self.download_btn)

        button_layout.addStretch()

        # Закрыть
        close_btn = QPushButton("Закрыть")
        close_btn.setStyleSheet("background-color: #45475a; padding: 8px 20px;")
        close_btn.clicked.connect(self.reject)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

        self.setLayout(layout)
        
        # Автозапуск после показа диалога
        if self.auto_process:
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(500, self.start_download)  # Запуск через 500мс после показа

    def log(self, message):
        """Добавить сообщение в журнал"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")

    def start_download(self):
        """Запуск загрузки в рабочем потоке"""
        if not self.email_settings.get('login') or not self.email_settings.get('password'):
            QMessageBox.warning(self, "Ошибка", "Настройте подключение к почте")
            return

        self.download_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.log_text.clear()
        self.files_list.clear()
        
        self.log("Инициализация загрузки...")

        # Собираем даты, уже существующие в БД — чтобы не качать их снова
        existing_dates = set()
        if self.parent_window and hasattr(self.parent_window, 'db_conn') and self.parent_window.db_conn:
            try:
                from database import get_all_dates
                existing_dates = set(get_all_dates(self.parent_window.db_conn))
                self.log(f"В БД уже есть {len(existing_dates)} дат")
            except Exception as e:
                self.log(f"Не удалось получить список дат из БД: {e}")

        # Создание и запуск рабочего потока
        self.worker = EmailReportWorker(self.email_settings, existing_dates=existing_dates)
        self.worker.progress.connect(self.on_progress)
        self.worker.log.connect(self.log)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def on_progress(self, message):
        """Обновление прогресса"""
        self.status_label.setText(message)

    def on_finished(self, result):
        """Загрузка завершена"""
        self.progress_bar.setVisible(False)
        self.download_btn.setEnabled(True)
        
        self.downloaded_files = result.get('saved_files', [])
        
        # Обновление списка файлов
        for file_info in self.downloaded_files:
            self.files_list.addItem(f"📄 {file_info['filename']} (из: {file_info['email_subject']})")
        
        # Автоматическая обработка
        if self.auto_process and self.downloaded_files:
            self.process_downloaded_files()

    def on_error(self, error_msg):
        """Ошибка загрузки"""
        self.progress_bar.setVisible(False)
        self.download_btn.setEnabled(True)
        self.status_label.setText(f"❌ Ошибка")
        
        QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки:\n\n{error_msg}")

    def process_downloaded_files(self):
        """Обработка загруженных файлов (парсинг XLSX и сохранение в БД)"""
        from data_parser import parse_thermometry_file
        from database import insert_readings, check_date_exists, delete_readings_for_date, get_all_dates
        import logging

        # Получить уже существующие даты в БД
        existing_dates = set(get_all_dates(self.parent_window.db_conn))
        logging.debug(f"existing_dates в БД: {existing_dates}")

        loaded_dates = []
        skipped_dates = []
        new_dates = []

        for file_info in self.downloaded_files:
            try:
                file_path = file_info['file_path']
                filename = file_info['filename']

                # Извлечь дату из имени файла (termo_ДД.ММ.ГГГГ.xlsx)
                import re
                date_match = re.search(r'termo_(\d{2}\.\d{2}\.\d{4})', filename)
                if date_match:
                    date_str = date_match.group(1)
                    from datetime import datetime
                    try:
                        date_obj = datetime.strptime(date_str, "%d.%m.%Y")
                        db_date = date_obj.strftime("%Y-%m-%d")
                        loaded_dates.append(db_date)

                        # Проверка на наличие в БД
                        logging.debug(f"Проверка даты {db_date} из {filename}: в БД={db_date in existing_dates}")
                        if db_date in existing_dates:
                            self.log(f"⏭️ Пропущен {filename} (дата {db_date} уже в БД)")
                            skipped_dates.append(date_str)
                            
                            # Очистка временных файлов
                            if file_info.get('temp_dir'):
                                import shutil
                                shutil.rmtree(file_info['temp_dir'], ignore_errors=True)
                            continue
                        else:
                            self.log(f"📥 Загрузка {filename} (дата {db_date})")
                            new_dates.append(db_date)
                    except Exception as e:
                        self.log(f"⚠️ Ошибка парсинга даты из {filename}: {e}")
                        pass

                # Парсинг XLSX файла
                report_date, readings = parse_thermometry_file(file_path)

                if readings:
                    # Дублирующая проверка существует ли такая дата
                    if check_date_exists(self.parent_window.db_conn, report_date):
                        self.log(f"⚠️ Дата {report_date} уже существует, замена...")
                        delete_readings_for_date(self.parent_window.db_conn, report_date)

                    # Сохранение в БД
                    insert_readings(self.parent_window.db_conn, readings)
                    self.log(f"✅ Сохранено в БД: {report_date}")

                # Очистка временных файлов
                if file_info.get('temp_dir'):
                    import shutil
                    shutil.rmtree(file_info['temp_dir'], ignore_errors=True)

            except Exception as e:
                self.log(f"❌ Ошибка обработки {file_info.get('filename', 'файл')}: {e}")
                import logging
                logging.exception(e)
        
        # Обновление дат в главном окне
        if new_dates and self.parent_window:
            self.dates_loaded.emit(new_dates)
            
            # Обновить диапазон дат в главном окне
            if hasattr(self.parent_window, 'update_date_range'):
                self.parent_window.update_date_range()
            
            # Сообщение с деталями
            msg = f"✅ Загружено и обработано файлов: {len(self.downloaded_files)}\n\n"
            if new_dates:
                msg += f"🆕 Добавлены даты ({len(new_dates)}):\n{', '.join(sorted(new_dates))}\n\n"
            if skipped_dates:
                msg += f"⏭️ Пропущено (уже в БД) ({len(skipped_dates)}):\n{', '.join(sorted(skipped_dates))}"
            
            QMessageBox.information(self, "Загрузка завершена", msg)
        else:
            # Все даты уже в БД
            msg = "⚠️ Новые отчеты не найдены\n\n"
            if skipped_dates:
                msg += f"Все загруженные файлы уже присутствуют в БД ({len(skipped_dates)} дат):\n"
                msg += ', '.join(sorted(skipped_dates)[:10])
                if len(skipped_dates) > 10:
                    msg += f" ... и ещё {len(skipped_dates) - 10}"
            
            QMessageBox.information(self, "Загрузка завершена", msg)
