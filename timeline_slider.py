# -*- coding: utf-8 -*-
"""
Виджет шкалы времени (timeline slider) для выбора даты
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QScrollArea, QFrame
from PyQt6.QtCore import Qt, pyqtSignal, QRect
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont


class DateSliderWidget(QWidget):
    """Виджет шкалы дат с возможностью выбора"""
    
    date_selected = pyqtSignal(str)  # Сигнал: выбрана дата (YYYY-MM-DD)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.dates = []
        self.selected_index = -1
        self.setup_ui()
    
    def setup_ui(self):
        layout = QHBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Scroll area для прокрутки дат
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        self.scroll_content = QWidget()
        self.scroll_layout = QHBoxLayout()
        self.scroll_layout.setSpacing(2)
        self.scroll_layout.setContentsMargins(5, 5, 5, 5)
        self.scroll_content.setLayout(self.scroll_layout)
        
        self.scroll.setWidget(self.scroll_content)
        layout.addWidget(self.scroll)
        
        self.setLayout(layout)
    
    def set_dates(self, dates, selected_date=None):
        """
        Установить даты для отображения (только при первом создании или изменении периода)

        Параметры:
        - dates: list дат в формате YYYY-MM-DD
        - selected_date: выбранная дата (по умолчанию последняя)
        """
        # Сохранить текущую выбранную дату если есть
        if self.selected_index >= 0 and self.selected_index < len(self.dates):
            current_selected = self.dates[self.selected_index]
        else:
            current_selected = selected_date
        
        self.dates = dates
        self.selected_index = -1  # Сбросить индекс

        # Очистить старое
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Создать кнопки для каждой даты
        for idx, date in enumerate(dates):
            # Выбрать дату если она была выбрана ранее или это последняя дата
            is_selected = (date == current_selected) or (idx == len(dates) - 1 and current_selected is None)
            date_btn = DateButton(date, is_selected)
            date_btn.date_clicked.connect(self.on_date_clicked)
            self.scroll_layout.addWidget(date_btn)

            if is_selected:
                self.selected_index = idx

        self.scroll_layout.addStretch()
    
    def update_selection(self, selected_date):
        """Обновить только выделение даты (без пересоздания кнопок)"""
        if selected_date not in self.dates:
            return
        
        self.selected_index = self.dates.index(selected_date)
        
        # Обновить выделение всех кнопок
        for i in range(self.scroll_layout.count()):
            item = self.scroll_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), DateButton):
                btn = item.widget()
                btn.set_selected(btn.date == selected_date)
    
    def on_date_clicked(self, date):
        """Обработка клика по дате"""
        # Обновить выделение всех кнопок
        for i in range(self.scroll_layout.count()):
            item = self.scroll_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), DateButton):
                btn = item.widget()
                # Выделить только нажатую кнопку
                btn.set_selected(btn.date == date)
        
        # Обновить индекс
        if date in self.dates:
            self.selected_index = self.dates.index(date)
        
        # Отправить сигнал
        self.date_selected.emit(date)

    def get_selected_date(self):
        """Получить выбранную дату"""
        if self.selected_index >= 0 and self.selected_index < len(self.dates):
            return self.dates[self.selected_index]
        return None


class DateButton(QFrame):
    """Кнопка даты для шкалы"""
    
    date_clicked = pyqtSignal(str)
    
    def __init__(self, date, is_selected=False, parent=None):
        super().__init__(parent)
        self.date = date
        self.is_selected = is_selected
        self.setMinimumSize(70, 50)
        self.setMaximumSize(70, 50)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_style()
    
    def _update_style(self):
        """Обновить стиль"""
        if self.is_selected:
            self.setStyleSheet("""
                QFrame {
                    background-color: #89b4fa;
                    border-radius: 6px;
                    border: 2px solid #b4befe;
                }
                QLabel {
                    color: #1e1e2e;
                    font-weight: bold;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame {
                    background-color: #45475a;
                    border-radius: 6px;
                    border: 1px solid #585b70;
                }
                QFrame:hover {
                    background-color: #585b70;
                    border-color: #89b4fa;
                }
                QLabel {
                    color: #cdd6f4;
                }
            """)
    
    def set_selected(self, selected):
        """Установить состояние выбора"""
        self.is_selected = selected
        self._update_style()
        self.update()  # Принудительно обновить виджет

    def mousePressEvent(self, event):
        """Обработка клика"""
        if event.button() == Qt.MouseButton.LeftButton:
            # Сначала обновить выделение
            self.is_selected = True
            self._update_style()
            self.update()
            self.date_clicked.emit(self.date)
    
    def paintEvent(self, event):
        """Отрисовка"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Фон уже рисуется через stylesheet
        
        # Форматировать дату (ДД.ММ)
        try:
            from datetime import datetime
            date_obj = datetime.strptime(self.date, "%Y-%m-%d")
            date_str = date_obj.strftime("%d.%m")
            day_name = date_obj.strftime("%a")
        except:
            date_str = self.date
            day_name = ""
        
        # День недели
        painter.setPen(QColor('#89b4fa') if self.is_selected else QColor('#6c7086'))
        font = QFont('Segoe UI', 8)
        painter.setFont(font)
        painter.drawText(0, 12, 70, 14, Qt.AlignmentFlag.AlignCenter, day_name)
        
        # Дата
        painter.setPen(QColor('#1e1e2e') if self.is_selected else QColor('#cdd6f4'))
        font = QFont('Segoe UI', 10, QFont.Weight.Bold if self.is_selected else QFont.Weight.Normal)
        painter.setFont(font)
        painter.drawText(0, 28, 70, 20, Qt.AlignmentFlag.AlignCenter, date_str)
