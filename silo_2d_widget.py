# -*- coding: utf-8 -*-
"""
2D виджет силоса в стиле промышленного интерфейса
Силос в форме трапеции с треугольной крышей
Стрелка дельты справа от силоса
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QFrame
from PyQt6.QtCore import Qt, QPoint, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QLinearGradient, QPolygon


class Silo2DWidget(QWidget):
    """2D виджет силоса со стрелкой дельты справа"""
    
    # Сигнал клика по силосу
    silo_clicked = pyqtSignal(str, str)  # silo_name, date
    
    def __init__(self, silo_name, current_temp=None, delta=None, delta_threshold=1.0,
                 has_comment=False, date=None, sensor_info=None, is_leader_changed=False, parent=None):
        """
        Параметры:
        - silo_name: название силоса (например, "3а")
        - current_temp: текущая температура (float или None)
        - delta: изменение температуры за сутки (float или None)
        - delta_threshold: порог дельты для цветового выделения
        - sensor_info: строка с информацией о датчике (например, "Подвеска 5, Датчик 3")
        - is_leader_changed: True если этот датчик стал лидером вместо другого
        """
        super().__init__(parent)
        self.silo_name = silo_name
        self.current_temp = current_temp
        self.delta = delta
        self.delta_threshold = delta_threshold
        self.has_comment = has_comment
        self.date = date
        self.sensor_info = sensor_info
        self.is_leader_changed = is_leader_changed
        self.setMinimumSize(160, 180)
        self.setMaximumSize(180, 200)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_tooltip()

    def _update_tooltip(self):
        """Обновить подсказку"""
        tooltip = f"Силос {self.silo_name}\n"
        if self.current_temp is not None:
            delta_str = f"{self.delta:+.1f}°C" if self.delta is not None else "Нет данных"
            tooltip += f"Температура: {self.current_temp:.1f}°C\n"
            tooltip += f"Дельта за сутки: {delta_str}\n"
            if self.sensor_info:
                tooltip += f"📍 Датчик: {self.sensor_info}\n"
            
            # Информация о смене лидера
            if self.is_leader_changed:
                tooltip += "\n🔄 Лидер изменился!\n"
            elif self.sensor_info:
                tooltip += "\n✅ Датчик не менялся\n"
        else:
            tooltip += "Нет данных\n"

        if self.has_comment:
            tooltip += "📝 Есть комментарий"

        self.setToolTip(tooltip)

    def set_data(self, current_temp, delta, has_comment=None, sensor_info=None, is_leader_changed=False):
        """Установить данные"""
        self.current_temp = current_temp
        self.delta = delta
        if has_comment is not None:
            self.has_comment = has_comment
        if sensor_info is not None:
            self.sensor_info = sensor_info
        if is_leader_changed is not None:
            self.is_leader_changed = is_leader_changed
        self._update_tooltip()
        self.update()
    
    def mousePressEvent(self, event):
        """Обработка клика по силосу"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.silo_clicked.emit(self.silo_name, self.date)
    
    def _get_delta_color(self, delta):
        """Получить цвет для дельты с учётом порога"""
        if delta is None:
            return QColor('#808080')  # Серый
        if abs(delta) < self.delta_threshold:
            return QColor('#808080')  # Серый (в пределах порога)
        if delta > 0:
            # Нагрев - красный
            if delta >= 5:
                return QColor('#dc0000')  # Тёмно-красный
            else:
                return QColor('#ff4444')  # Красный
        else:
            # Охлаждение - зелёный
            if delta <= -5:
                return QColor('#006600')  # Тёмно-зелёный
            else:
                return QColor('#00aa00')  # Зелёный
    
    def _get_temp_color(self, temp):
        """Получить цвет для температуры (для индикатора)"""
        if temp is None:
            return QColor('#404040')
        if temp >= 35:
            return QColor('#dc0000')
        elif temp >= 25:
            return QColor('#ff4444')
        elif temp >= 15:
            return QColor('#ffaa00')
        elif temp >= 0:
            return QColor('#00aa00')
        else:
            return QColor('#0066cc')
    
    def paintEvent(self, event):
        """Отрисовка силоса и стрелки"""
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            width = self.width()
            height = self.height()

            # Параметры
            silo_width = 100
            margin_top = 15
            margin_bottom = 10
            silo_roof_height = 20
            silo_body_height = height - margin_top - margin_bottom - silo_roof_height
            
            # Позиция силоса (слева)
            silo_left = 5
            silo_right = silo_left + silo_width
            body_top = margin_top + silo_roof_height
            body_bottom = height - margin_bottom
            
            roof_center_x = silo_left + silo_width / 2
            roof_top = margin_top
            
            # Общая ширина виджета
            widget_width = self.width()

            # === Рисуем крышу (треугольник) ===
            roof_points = [
                QPoint(int(roof_center_x), int(roof_top)),
                QPoint(int(silo_left), int(body_top)),
                QPoint(int(silo_right), int(body_top))
            ]
            roof_polygon = QPolygon(roof_points)
            
            roof_gradient = QLinearGradient(roof_center_x, roof_top, roof_center_x, body_top)
            roof_gradient.setColorAt(0, QColor('#606060'))
            roof_gradient.setColorAt(1, QColor('#404040'))
            
            painter.setBrush(QBrush(roof_gradient))
            painter.setPen(QPen(QColor('#505050'), 2))
            painter.drawPolygon(roof_polygon)

            # === Рисуем корпус силоса (трапеция) ===
            body_points = [
                QPoint(int(silo_left), int(body_top)),
                QPoint(int(silo_right), int(body_top)),
                QPoint(int(silo_right - 4), int(body_bottom)),
                QPoint(int(silo_left + 4), int(body_bottom))
            ]
            body_polygon = QPolygon(body_points)
            
            body_gradient = QLinearGradient(silo_left, body_top, silo_right, body_top)
            body_gradient.setColorAt(0, QColor('#505050'))
            body_gradient.setColorAt(0.5, QColor('#707070'))
            body_gradient.setColorAt(1, QColor('#505050'))
            
            painter.setBrush(QBrush(body_gradient))
            painter.setPen(QPen(QColor('#404040'), 2))
            painter.drawPolygon(body_polygon)
            
            # === Рисуем название силоса ===
            painter.setPen(QColor('#ffffff'))
            font = QFont('Segoe UI', 9, QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(
                int(silo_left),
                int(body_top + 14),
                int(silo_width),
                16,
                Qt.AlignmentFlag.AlignCenter,
                f"С{self.silo_name}"
            )
            
            # === Рисуем иконку комментария (если есть) ===
            if self.has_comment:
                painter.setPen(QColor('#f9e2af'))
                font = QFont('Segoe UI', 14, QFont.Weight.Bold)
                painter.setFont(font)
                painter.drawText(
                    int(silo_right - 25),
                    int(body_top + 5),
                    20,
                    20,
                    Qt.AlignmentFlag.AlignCenter,
                    "📝"
                )
            
            # === Рисуем индикатор температуры ===
            center_x = silo_left + silo_width / 2
            center_y = body_top + silo_body_height / 2
            circle_radius = 20  # Увеличенный круг
            
            if self.current_temp is not None:
                # Фон круга
                painter.setBrush(QBrush(QColor('#202020')))
                painter.setPen(QPen(QColor('#404040'), 2))
                painter.drawEllipse(
                    int(center_x - circle_radius),
                    int(center_y - circle_radius),
                    int(circle_radius * 2),
                    int(circle_radius * 2)
                )
                
                # Цветной индикатор
                temp_color = self._get_temp_color(self.current_temp)
                painter.setBrush(QBrush(temp_color))
                painter.setPen(QPen(temp_color, 2))
                indicator_radius = circle_radius - 3
                painter.drawEllipse(
                    int(center_x - indicator_radius),
                    int(center_y - indicator_radius),
                    int(indicator_radius * 2),
                    int(indicator_radius * 2)
                )
                
                # Температура внутри круга (без округления)
                painter.setPen(QColor('#ffffff'))
                font = QFont('Segoe UI', 10, QFont.Weight.Bold)
                painter.setFont(font)
                painter.drawText(
                    int(center_x - circle_radius),
                    int(center_y - circle_radius),
                    int(circle_radius * 2),
                    int(circle_radius * 2),
                    Qt.AlignmentFlag.AlignCenter,
                    f"{self.current_temp:.1f}°"
                )
            else:
                # Нет данных
                painter.setBrush(QBrush(QColor('#404040')))
                painter.setPen(QPen(QColor('#505050'), 2))
                painter.drawEllipse(
                    int(center_x - circle_radius),
                    int(center_y - circle_radius),
                    int(circle_radius * 2),
                    int(circle_radius * 2)
                )
                
                painter.setPen(QColor('#808080'))
                font = QFont('Segoe UI', 8)
                painter.setFont(font)
                painter.drawText(
                    int(center_x - circle_radius),
                    int(center_y - circle_radius),
                    int(circle_radius * 2),
                    int(circle_radius * 2),
                    Qt.AlignmentFlag.AlignCenter,
                    "--"
                )
            
            # === Рисуем стрелку дельты справа ===
            arrow_x = silo_right + 15  # Увеличенное расстояние от силоса
            arrow_y = height / 2
            arrow_width = 18
            arrow_height = 20
            
            if self.delta is not None:
                arrow_color = self._get_delta_color(self.delta)
                
                # Рисуем стрелку
                if self.delta > 0:
                    # Стрелка вверх (нагрев)
                    arrow_points = [
                        QPoint(int(arrow_x + arrow_width/2), int(arrow_y - arrow_height/2)),  # Вершина
                        QPoint(int(arrow_x), int(arrow_y + arrow_height/2)),  # Левый нижний
                        QPoint(int(arrow_x + arrow_width), int(arrow_y + arrow_height/2))  # Правый нижний
                    ]
                elif self.delta < 0:
                    # Стрелка вниз (охлаждение)
                    arrow_points = [
                        QPoint(int(arrow_x), int(arrow_y - arrow_height/2)),  # Левый верхний
                        QPoint(int(arrow_x + arrow_width), int(arrow_y - arrow_height/2)),  # Правый верхний
                        QPoint(int(arrow_x + arrow_width/2), int(arrow_y + arrow_height/2))  # Вершина
                    ]
                else:
                    # Горизонтальная линия (нет изменений)
                    arrow_points = [
                        QPoint(int(arrow_x), int(arrow_y - 3)),
                        QPoint(int(arrow_x + arrow_width), int(arrow_y - 3)),
                        QPoint(int(arrow_x + arrow_width), int(arrow_y + 3)),
                        QPoint(int(arrow_x), int(arrow_y + 3))
                    ]
                
                arrow_polygon = QPolygon(arrow_points)
                painter.setBrush(QBrush(arrow_color))
                painter.setPen(QPen(arrow_color, 2))
                painter.drawPolygon(arrow_polygon)
                
                # Значение дельты СПРАВА от стрелки
                painter.setPen(arrow_color)
                font = QFont('Segoe UI', 9, QFont.Weight.Bold)
                painter.setFont(font)
                delta_text = f"{abs(self.delta):.1f}"
                painter.drawText(
                    int(arrow_x + arrow_width + 2),  # Справа от стрелки
                    int(arrow_y - 10),
                    35,  # Ширина области для текста
                    20,
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    delta_text
                )
            else:
                # Нет данных - серый прочерк
                painter.setPen(QColor('#808080'))
                font = QFont('Segoe UI', 10)
                painter.setFont(font)
                painter.drawText(
                    int(arrow_x + arrow_width + 2),
                    int(arrow_y - 10),
                    35,
                    20,
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    "--"
                )

        except Exception as e:
            print(f"Ошибка отрисовки Silo2DWidget: {e}")


class SiloLineWidget(QWidget):
    """Виджет линии силосов (ряд)"""
    
    # Сигнал клика по силосу
    silo_clicked = pyqtSignal(str, str)  # silo_name, date
    
    def __init__(self, line_name, silos_data, delta_threshold=1.0, date=None, parent=None):
        """
        Параметры:
        - line_name: название линии ("А" или "Б")
        - silos_data: dict {silo_name: {'current_temp': temp, 'delta': delta}}
        - delta_threshold: порог дельты для цветового выделения
        """
        super().__init__(parent)
        self.line_name = line_name
        self.silos_data = silos_data
        self.delta_threshold = delta_threshold
        self.date = date
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(2)
        layout.setContentsMargins(2, 2, 2, 2)
        
        # Заголовок линии
        title_label = QLabel(f"Линия {self.line_name}")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                font-weight: bold;
                color: #89b4fa;
                padding: 2px;
            }
        """)
        layout.addWidget(title_label)
        
        # Силосы в ряд
        silos_layout = QHBoxLayout()
        silos_layout.setSpacing(3)
        silos_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        # Сортировать силосы по номеру
        sorted_silos = sorted(
            self.silos_data.keys(),
            key=lambda x: int(''.join(filter(str.isdigit, x))) if any(c.isdigit() for c in x) else 0
        )
        
        for silo_name in sorted_silos:
            data = self.silos_data.get(silo_name, {})
            current_temp = data.get('current_temp')
            delta = data.get('delta')
            has_comment = data.get('has_comment', False)
            sensor_info = data.get('sensor_info', None)
            is_leader_changed = data.get('is_leader_changed', False)
            silo_widget = Silo2DWidget(silo_name, current_temp, delta, self.delta_threshold,
                                       has_comment, self.date, sensor_info, is_leader_changed)
            silo_widget.silo_clicked.connect(self.silo_clicked.emit)
            silos_layout.addWidget(silo_widget)
        
        layout.addLayout(silos_layout)
        self.setLayout(layout)


class SilosOverviewWidget(QWidget):
    """Общий виджет со всеми силосами (2 линии)"""
    
    # Сигнал клика по силосу
    silo_clicked = pyqtSignal(str, str)  # silo_name, date
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.delta_threshold = 1.0  # Порог дельты по умолчанию
    
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(5)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Контейнер для линий
        self.lines_container = QWidget()
        self.lines_layout = QVBoxLayout()
        self.lines_layout.setSpacing(10)
        self.lines_container.setLayout(self.lines_layout)
        
        layout.addWidget(self.lines_container)
        
        # Убрана легенда для экономии места
        
        self.setLayout(layout)
    
    def _create_legend(self):
        """Создать компактную легенду"""
        widget = QFrame()
        widget.setFrameStyle(QFrame.Shape.StyledPanel)
        widget.setStyleSheet("""
            QFrame {
                background-color: #313244;
                border-radius: 6px;
                padding: 4px;
            }
        """)
        
        layout = QHBoxLayout()
        layout.setSpacing(10)
        
        # Легенда дельты
        label = QLabel("Δ за сутки:")
        label.setStyleSheet("font-size: 10px; color: #cdd6f4;")
        layout.addWidget(label)
        
        legend_items = [
            ("#ff4444", "↑ >+1°C нагрев"),
            ("#00aa00", "↓ <-1°C охлаждение"),
            ("#808080", "· ±<1°C норма"),
        ]
        
        for color, text in legend_items:
            color_box = QLabel()
            color_box.setMaximumSize(14, 14)
            color_box.setMinimumSize(14, 14)
            color_box.setStyleSheet(f"background-color: {color}; border-radius: 3px;")
            layout.addWidget(color_box)
            label = QLabel(text)
            label.setStyleSheet("font-size: 10px; color: #cdd6f4;")
            layout.addWidget(label)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
    
    def update_silos(self, silos_data, date=None, comments=None, previous_leaders=None, current_leaders=None):
        """
        Обновить отображение силосов

        Параметры:
        - silos_data: dict {silo: {suspension: {sensor: delta_data}}}
        - date: текущая дата
        - comments: dict {silo: has_any_comment} — True если есть хоть один комментарий в истории
        - previous_leaders: dict {silo: {silo, suspension, sensor, temperature}} — лидеры за предыдущую дату
        - current_leaders: dict {silo: {silo, suspension, sensor, temperature}} — лидеры за текущую дату
        """
        print(f"update_silos вызван с silos_data: {len(silos_data) if silos_data else 0} силосов")
        print(f"date: {date}, comments: {comments}")
        print(f"previous_leaders: {previous_leaders}, current_leaders: {current_leaders}")

        # Очистить старое
        while self.lines_layout.count():
            item = self.lines_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Разделить силосы по линиям и подготовить данные
        # Исключаем оперативные силоса (1а, 1б, 2а, 2б)
        line_a = {}
        line_b = {}

        comments = comments or {}
        previous_leaders = previous_leaders or {}
        current_leaders = current_leaders or {}

        for silo, suspensions in silos_data.items():
            # Пропустить оперативные силоса
            if silo in ['1а', '1б', '2а', '2б', '1a', '1b', '2a', '2b']:
                print(f"Пропущен оперативный силос: {silo}")
                continue

            # Найти максимальную температуру среди всех датчиков
            max_temp = None
            max_sensor_info = None
            max_susp = None
            max_sensor = None

            for susp, sensors in suspensions.items():
                for sensor, data in sensors.items():
                    current = data.get('current')

                    if max_temp is None or (current is not None and current > max_temp):
                        max_temp = current
                        max_sensor_info = f"Подвеска {susp}, Датчик {sensor}"
                        max_susp = susp
                        max_sensor = sensor

            # Найти максимальную дельту
            max_delta = None
            for susp, sensors in suspensions.items():
                for sensor, data in sensors.items():
                    delta = data.get('delta', 0)
                    if max_delta is None or abs(delta) > abs(max_delta):
                        max_delta = delta

            # Проверить смену лидера для ЭТОГО СИЛОСА
            prev_leader = previous_leaders.get(silo)
            curr_leader = current_leaders.get(silo)
            is_leader_changed = False
            if prev_leader and curr_leader:
                is_leader_changed = (
                    prev_leader.get('suspension') != curr_leader.get('suspension') or
                    prev_leader.get('sensor') != curr_leader.get('sensor')
                )

            # Распределить по линиям
            has_comment = comments.get(silo, False)
            print(f"Силос {silo}: temp={max_temp}, delta={max_delta}, has_comment={has_comment}, sensor={max_sensor_info}, leader_changed={is_leader_changed}")
            if 'а' in silo.lower():
                line_a[silo] = {
                    'current_temp': max_temp,
                    'delta': max_delta,
                    'has_comment': has_comment,
                    'sensor_info': max_sensor_info,
                    'is_leader_changed': is_leader_changed
                }
            elif 'б' in silo.lower():
                line_b[silo] = {
                    'current_temp': max_temp,
                    'delta': max_delta,
                    'has_comment': has_comment,
                    'sensor_info': max_sensor_info,
                    'is_leader_changed': is_leader_changed
                }
            else:
                line_a[silo] = {
                    'current_temp': max_temp,
                    'delta': max_delta,
                    'has_comment': has_comment,
                    'sensor_info': max_sensor_info,
                    'is_leader_changed': is_leader_changed
                }

        print(f"Линия А: {len(line_a)} силосов, Линия Б: {len(line_b)} силосов")
        
        # Создать виджеты линий
        if line_a:
            line_a_widget = SiloLineWidget("А", line_a, self.delta_threshold, date)
            line_a_widget.silo_clicked.connect(self.silo_clicked.emit)
            self.lines_layout.addWidget(line_a_widget)

        if line_b:
            line_b_widget = SiloLineWidget("Б", line_b, self.delta_threshold, date)
            line_b_widget.silo_clicked.connect(self.silo_clicked.emit)
            self.lines_layout.addWidget(line_b_widget)

        if not line_a and not line_b:
            no_data_label = QLabel("⚠️ Нет данных")
            no_data_label.setStyleSheet("color: #6c7086; font-size: 14px; padding: 20px;")
            no_data_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.lines_layout.addWidget(no_data_label)
