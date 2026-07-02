# dialogs.py
"""Диалоговые окна для приложения Термометрия"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
                             QComboBox, QCheckBox, QDateEdit, QScrollArea, QFrame,
                             QDialogButtonBox, QGroupBox, QGridLayout)
from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QFont, QShowEvent
from database import get_silo_list, get_hot_spots_for_silo


class SiloHotspotsDialog(QDialog):
    """Диалог выбора силоса и горячих точек для графика"""

    def __init__(self, db_conn, parent=None, temp_threshold=15.0, last_silo=None, last_points=None):
        super().__init__(parent)
        self.db_conn = db_conn
        self.temp_threshold = temp_threshold
        self.last_silo = last_silo
        self.last_points = last_points or []
        self.selected_silo = None
        self.selected_points = []

        self.setWindowTitle("Выбор силоса и горячих точек")
        self.setMinimumSize(600, 500)
        self.setModal(True)

        self.initUI()
        
    def initUI(self):
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Заголовок
        title = QLabel("📈 Выбор данных для графика")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #89b4fa;")
        layout.addWidget(title)
        
        # Выбор силоса
        silo_group = QGroupBox("1️⃣ Выберите силос")
        silo_layout = QHBoxLayout()

        self.silo_combo = QComboBox()
        self.silo_combo.setMinimumWidth(250)
        self.silo_combo.addItem("-- Выберите силос --")
        silos = get_silo_list(self.db_conn, exclude_operational=True)
        self.silo_combo.addItems(silos)
        self.silo_combo.currentTextChanged.connect(self.on_silo_changed)

        # Установить последний выбранный силос и загрузить точки
        if self.last_silo and self.last_silo in silos:
            self.silo_combo.setCurrentText(self.last_silo)
            # Явно загрузить точки для последнего силоса
            self.on_silo_changed(self.last_silo)

        silo_layout.addWidget(QLabel("Силос:"))
        silo_layout.addWidget(self.silo_combo)
        
        # Кнопка обновления точек
        self.refresh_btn = QPushButton("🔄 Обновить")
        self.refresh_btn.setMaximumWidth(120)
        self.refresh_btn.setStyleSheet("background-color: #89b4fa; color: #1e1e2e; font-weight: bold; padding: 6px 12px; border-radius: 4px;")
        self.refresh_btn.clicked.connect(self.refresh_hotspots)
        silo_layout.addWidget(self.refresh_btn)
        
        silo_layout.addStretch()
        silo_group.setLayout(silo_layout)
        layout.addWidget(silo_group)
        
        # Выбор диапазона дат
        date_group = QGroupBox("2️⃣ Диапазон дат")
        date_layout = QHBoxLayout()
        
        self.start_date = QDateEdit(calendarPopup=True)
        self.start_date.setDate(QDate.currentDate().addMonths(-1))
        self.start_date.setCalendarPopup(True)
        self.start_date.setMinimumWidth(130)
        
        self.end_date = QDateEdit(calendarPopup=True)
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setCalendarPopup(True)
        self.end_date.setMinimumWidth(130)
        
        date_layout.addWidget(QLabel("С:"))
        date_layout.addWidget(self.start_date)
        date_layout.addWidget(QLabel("По:"))
        date_layout.addWidget(self.end_date)
        date_layout.addStretch()
        date_group.setLayout(date_layout)
        layout.addWidget(date_group)
        
        # Выбор горячих точек
        points_group = QGroupBox("3️⃣ Выберите горячие точки (макс. температура за период)")
        points_layout = QVBoxLayout()
        points_layout.setSpacing(5)
        
        self.hotpoints_info = QLabel("Выберите силос для загрузки горячих точек")
        self.hotpoints_info.setStyleSheet("color: #6c7086; font-size: 11px;")
        points_layout.addWidget(self.hotpoints_info)
        
        # Scroll area для чекбоксов
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setMaximumHeight(250)
        
        self.scroll_content = QFrame()
        self.scroll_layout = QVBoxLayout()
        self.scroll_layout.setSpacing(3)
        self.scroll_layout.setContentsMargins(5, 5, 5, 5)
        self.scroll_content.setLayout(self.scroll_layout)
        self.scroll.setWidget(self.scroll_content)
        
        points_layout.addWidget(self.scroll)
        points_group.setLayout(points_layout)
        layout.addWidget(points_group)
        
        # Кнопки
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        
        # Стилизация кнопок
        for btn in button_box.buttons():
            if button_box.buttonRole(btn) == QDialogButtonBox.ButtonRole.AcceptRole:
                btn.setStyleSheet("background-color: #a6e3a1; color: #1e1e2e; font-weight: bold; padding: 8px 20px;")
            else:
                btn.setStyleSheet("background-color: #45475a; padding: 8px 20px;")
        
        layout.addWidget(button_box)
        
        self.setLayout(layout)
    
    def on_silo_changed(self, silo):
        """Изменение выбранного силоса"""
        # Игнорировать вызовы во время инициализации
        if not hasattr(self, 'scroll_layout') or not hasattr(self, 'hotpoints_info'):
            return

        try:
            self.selected_silo = silo if silo != "-- Выберите силос --" else None

            # Очистить список чекбоксов
            while self.scroll_layout.count():
                item = self.scroll_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            if not self.selected_silo:
                self.hotpoints_info.setText("Выберите силос для загрузки горячих точек")
                return

            # Загрузить горячие точки
            start_date = self.start_date.date().toString("yyyy-MM-dd")
            end_date = self.end_date.date().toString("yyyy-MM-dd")

            print(f"Загрузка горячих точек для {self.selected_silo}, {start_date} - {end_date}")
            hot_spots = get_hot_spots_for_silo(
                self.db_conn, self.selected_silo, start_date, end_date, self.temp_threshold
            )
            print(f"Найдено горячих точек: {len(hot_spots) if hot_spots else 0}")

            if not hot_spots:
                self.hotpoints_info.setText(f"Горячих точек не найдено (порог: {self.temp_threshold}°C)")
                return

            # Сгруппировать по датчикам и найти максимум
            sensor_max = {}
            for hs in hot_spots:
                print(f"HS: {hs}")
                key = (hs[1], hs[2])  # suspension, sensor
                if key not in sensor_max or hs[3] > sensor_max[key]['temp']:
                    sensor_max[key] = {'temp': hs[3], 'date': hs[4]}

            # Сортировка по температуре
            sorted_sensors = sorted(
                sensor_max.items(),
                key=lambda x: x[1]['temp'],
                reverse=True
            )

            self.hotpoints_info.setText(f"Найдено {len(sorted_sensors)} горячих точек:")

            # Создать чекбокс "Выбрать все"
            select_all_cb = QCheckBox("✅ Выбрать все")
            select_all_cb.setStyleSheet("font-size: 13px; font-weight: bold; padding: 5px; color: #89b4fa;")
            select_all_cb.stateChanged.connect(self.toggle_all_checkboxes)
            self.scroll_layout.addWidget(select_all_cb)

            # Разделительная линия
            line = QFrame()
            line.setFrameShape(QFrame.Shape.HLine)
            line.setStyleSheet("background-color: #45475a; min-height: 2px;")
            self.scroll_layout.addWidget(line)

            # Создать чекбоксы для точек
            for (susp, sensor), info in sorted_sensors[:30]:  # Максимум 30 точек
                cb = QCheckBox(f"Подв. {susp}, Датчик {sensor} — макс: {info['temp']:.1f}°C")
                cb.setProperty('suspension', susp)
                cb.setProperty('sensor', sensor)
                cb.setStyleSheet("font-size: 12px; padding: 3px;")

                # Отметить последние выбранные точки
                if self.last_points and (susp, sensor) in self.last_points:
                    cb.setChecked(True)

                self.scroll_layout.addWidget(cb)

            self.scroll_layout.addStretch()
        except Exception as e:
            print(f"Ошибка в on_silo_changed: {e}")
            import traceback
            traceback.print_exc()
            if hasattr(self, 'hotpoints_info'):
                self.hotpoints_info.setText(f"⚠️ Ошибка: {e}")
                self.hotpoints_info.setStyleSheet("color: #f38ba8; font-size: 12px; font-weight: bold;")

    def toggle_all_checkboxes(self, state):
        """Отметить/снять все чекбоксы"""
        from PyQt6.QtWidgets import QCheckBox
        # state может быть int (0 или 2) или Qt.CheckState
        is_checked = state == 2 or state == True
        for i in range(self.scroll_layout.count()):
            item = self.scroll_layout.itemAt(i)
            if item.widget() and isinstance(item.widget(), QCheckBox):
                # Пропустить чекбокс "Выбрать все"
                if item.widget().text() == "✅ Выбрать все":
                    continue
                item.widget().setChecked(is_checked)

    def refresh_hotspots(self):
        """Принудительно обновить горячие точки для текущего силоса"""
        current_silo = self.silo_combo.currentText()
        if current_silo and current_silo != "-- Выберите силос --":
            self.on_silo_changed(current_silo)

    def showEvent(self, event: QShowEvent):
        """Загрузка точек при каждом показе диалога"""
        super().showEvent(event)
        # Загрузить точки для текущего силоса при показе диалога
        current_silo = self.silo_combo.currentText()
        if current_silo and current_silo != "-- Выберите силос --":
            # Небольшая задержка чтобы UI успел отрисоваться
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(100, lambda: self.on_silo_changed(current_silo))

    def get_data(self):
        """Получить выбранные данные"""
        return {
            'silo': self.selected_silo,
            'start_date': self.start_date.date().toString("yyyy-MM-dd"),
            'end_date': self.end_date.date().toString("yyyy-MM-dd"),
            'points': self.selected_points
        }
    
    def reject(self):
        """Обработка нажатия Cancel"""
        print("Диалог: вызван reject()")
        super().reject()

    def accept(self):
        """Обработка нажатия OK"""
        try:
            print(f"Диалог: вызван accept(). selected_silo={self.selected_silo}")
            
            if not self.selected_silo:
                self.hotpoints_info.setText("⚠️ Выберите силос!")
                self.hotpoints_info.setStyleSheet("color: #f38ba8; font-size: 12px; font-weight: bold;")
                return

            # Собрать выбранные точки
            self.selected_points = []
            for i in range(self.scroll_layout.count()):
                item = self.scroll_layout.itemAt(i)
                if item.widget() and isinstance(item.widget(), QCheckBox) and item.widget().isChecked():
                    susp = item.widget().property('suspension')
                    sensor = item.widget().property('sensor')
                    print(f"  Выбран чекбокс: подв.{susp}, датчик {sensor}")
                    if susp is not None and sensor is not None:
                        self.selected_points.append((susp, sensor))

            print(f"  Собрано точек: {len(self.selected_points)}")
            
            if not self.selected_points:
                self.hotpoints_info.setText("⚠️ Выберите хотя бы одну горячую точку!")
                self.hotpoints_info.setStyleSheet("color: #f38ba8; font-size: 12px; font-weight: bold;")
                return

            print("Диалог: вызов super().accept()")
            super().accept()
        except Exception as e:
            print(f"Ошибка в accept: {e}")
            import traceback
            traceback.print_exc()
            self.hotpoints_info.setText(f"⚠️ Ошибка: {e}")
            self.hotpoints_info.setStyleSheet("color: #f38ba8; font-size: 12px; font-weight: bold;")


class ExportMenuDialog(QDialog):
    """Всплывающее меню экспорта"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setMinimumWidth(250)
        self.initUI()
        
    def initUI(self):
        layout = QVBoxLayout()
        layout.setSpacing(5)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Заголовок
        title = QLabel("📤 Экспорт данных")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #89b4fa; padding: 5px;")
        layout.addWidget(title)
        
        # Кнопки экспорта
        self.btn_save_graph = QPushButton("💾 Сохранить график (PNG/JPG)")
        self.btn_save_graph.setStyleSheet("text-align: left; padding: 8px;")
        self.btn_save_graph.clicked.connect(lambda: self.on_export('graph'))
        layout.addWidget(self.btn_save_graph)
        
        self.btn_hotspots = QPushButton("🔥 Экспорт перегрева (XLSX)")
        self.btn_hotspots.setStyleSheet("text-align: left; padding: 8px;")
        self.btn_hotspots.clicked.connect(lambda: self.on_export('hotspots'))
        layout.addWidget(self.btn_hotspots)
        
        self.btn_breaks = QPushButton("⚠️ Экспорт обрывов (XLSX)")
        self.btn_breaks.setStyleSheet("text-align: left; padding: 8px;")
        self.btn_breaks.clicked.connect(lambda: self.on_export('breaks'))
        layout.addWidget(self.btn_breaks)
        
        self.btn_changes = QPushButton("📊 Экспорт изменений (XLSX)")
        self.btn_changes.setStyleSheet("text-align: left; padding: 8px;")
        self.btn_changes.clicked.connect(lambda: self.on_export('changes'))
        layout.addWidget(self.btn_changes)
        
        self.setLayout(layout)
    
    def on_export(self, export_type):
        self.setResult(export_type)
        self.close()


class ExportDropdownButton(QPushButton):
    """Кнопка с выпадающим меню экспорта"""
    
    def __init__(self, parent=None, on_export_callback=None):
        super().__init__("📤 Экспорт ▼", parent)
        self.on_export_callback = on_export_callback
        self.clicked.connect(self.show_menu)
        self.setStyleSheet("""
            QPushButton {
                background-color: #89b4fa;
                color: #1e1e2e;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #b4befe;
            }
        """)
    
    def show_menu(self):
        menu = ExportMenuDialog(self)
        menu.exec()
        result = menu.result()
        if result and self.on_export_callback:
            self.on_export_callback(result)
