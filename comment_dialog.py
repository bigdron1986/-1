# -*- coding: utf-8 -*-
"""
Диалог для просмотра и добавления комментариев к силосу
Поддержка нескольких комментариев за одну дату
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, 
                             QPushButton, QListWidget, QListWidgetItem, QGroupBox, QMessageBox)
from PyQt6.QtCore import Qt, QDate
from datetime import datetime


class SiloCommentDialog(QDialog):
    """Диалог комментариев для силоса"""
    
    def __init__(self, parent, silo_name, current_date, db_conn):
        super().__init__(parent)
        self.silo_name = silo_name
        self.current_date = current_date
        self.db_conn = db_conn
        
        self.setWindowTitle(f"📝 Комментарии - Силос {silo_name}")
        self.setMinimumSize(500, 400)
        self.resize(500, 400)
        
        self.setup_ui()
        self.load_comments()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Заголовок
        title_label = QLabel(f"🏭 Силос {self.silo_name}")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #89b4fa;")
        layout.addWidget(title_label)
        
        # Список комментариев (история)
        history_group = QGroupBox("📋 История комментариев")
        history_layout = QVBoxLayout()
        
        self.comments_list = QListWidget()
        self.comments_list.setStyleSheet("""
            QListWidget {
                background-color: #313244;
                border: 1px solid #45475a;
                border-radius: 6px;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #45475a;
            }
            QListWidget::item:selected {
                background-color: #45475a;
            }
        """)
        self.comments_list.itemClicked.connect(self.on_comment_selected)
        self.comments_list.itemDoubleClicked.connect(self.on_comment_double_clicked)
        history_layout.addWidget(self.comments_list)
        
        history_group.setLayout(history_layout)
        layout.addWidget(history_group)
        
        # Новый комментарий
        current_group = QGroupBox(f"📅 Добавить комментарий на {self.format_date(self.current_date)}")
        current_layout = QVBoxLayout()
        
        self.comment_edit = QTextEdit()
        self.comment_edit.setPlaceholderText("Введите комментарий...")
        self.comment_edit.setMaximumHeight(100)
        self.comment_edit.setStyleSheet("""
            QTextEdit {
                background-color: #313244;
                border: 1px solid #45475a;
                border-radius: 6px;
                color: #cdd6f4;
                font-size: 13px;
                padding: 8px;
            }
            QTextEdit:focus {
                border-color: #89b4fa;
            }
        """)
        current_layout.addWidget(self.comment_edit)
        
        # Кнопки
        button_layout = QHBoxLayout()
        
        self.save_btn = QPushButton("💾 Добавить")
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #a6e3a1;
                color: #1e1e2e;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #94e2d5;
            }
        """)
        self.save_btn.clicked.connect(self.save_comment)
        button_layout.addWidget(self.save_btn)
        
        self.delete_selected_btn = QPushButton("🗑️ Удалить выбранный")
        self.delete_selected_btn.setStyleSheet("""
            QPushButton {
                background-color: #f38ba8;
                color: #1e1e2e;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #f5c2e7;
            }
        """)
        self.delete_selected_btn.clicked.connect(self.delete_selected_comment)
        button_layout.addWidget(self.delete_selected_btn)
        
        self.delete_all_btn = QPushButton("🗑️ Удалить все за дату")
        self.delete_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #930000;
                color: #ffffff;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #b30000;
            }
        """)
        self.delete_all_btn.clicked.connect(self.delete_all_for_date)
        button_layout.addWidget(self.delete_all_btn)
        
        button_layout.addStretch()
        
        self.close_btn = QPushButton("Закрыть")
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: #45475a;
                padding: 8px 16px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #585b70;
            }
        """)
        self.close_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.close_btn)
        
        current_layout.addLayout(button_layout)
        current_group.setLayout(current_layout)
        layout.addWidget(current_group)
        
        self.setLayout(layout)
    
    def format_date(self, date_str):
        """Форматировать дату в ДД.ММ.ГГГГ"""
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            return date_obj.strftime("%d.%m.%Y")
        except:
            return date_str
    
    def load_comments(self):
        """Загрузить комментарии из БД"""
        from database import get_comments_for_silo
        
        self.comments_list.clear()
        comments = get_comments_for_silo(self.db_conn, self.silo_name)
        
        if not comments:
            item = QListWidgetItem("Нет комментариев")
            item.setForeground(Qt.GlobalColor.gray)
            self.comments_list.addItem(item)
        else:
            for comment_id, date, comment, created_at in comments:
                display_text = f"📅 {self.format_date(date)}: {comment[:50]}..." if len(comment) > 50 else f"📅 {self.format_date(date)}: {comment}"
                item = QListWidgetItem(display_text)
                item.setData(Qt.ItemDataRole.UserRole, (comment_id, date, comment, created_at))
                # Выделить комментарии за текущую дату
                if date == self.current_date:
                    item.setForeground(Qt.GlobalColor.yellow)
                self.comments_list.addItem(item)
    
    def on_comment_selected(self, item):
        """Обработка выбора комментария из истории"""
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            comment_id, date, comment, created_at = data
            # Загрузить этот комментарий в поле ввода (для копирования/редактирования)
            self.comment_edit.setPlainText(comment)
    
    def on_comment_double_clicked(self, item):
        """Двойной клик — удалить этот комментарий"""
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            comment_id, date, comment, created_at = data
            reply = QMessageBox.question(self, "Удалить комментарий",
                                         f"Удалить этот комментарий?\n\n{comment[:100]}",
                                         QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                from database import delete_comment
                delete_comment(self.db_conn, comment_id)
                self.comment_edit.clear()
                self.load_comments()
    
    def save_comment(self):
        """Добавить новый комментарий"""
        from database import save_comment
        
        comment_text = self.comment_edit.toPlainText().strip()
        
        if comment_text:
            save_comment(self.db_conn, self.silo_name, self.current_date, comment_text)
            self.comment_edit.clear()
            self.load_comments()
    
    def delete_selected_comment(self):
        """Удалить выбранный комментарий"""
        current_item = self.comments_list.currentItem()
        if not current_item:
            return
        
        data = current_item.data(Qt.ItemDataRole.UserRole)
        if data:
            comment_id, date, comment, created_at = data
            reply = QMessageBox.question(self, "Удалить комментарий",
                                         f"Удалить этот комментарий?\n\n{comment[:100]}",
                                         QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                from database import delete_comment
                delete_comment(self.db_conn, comment_id)
                self.comment_edit.clear()
                self.load_comments()
    
    def delete_all_for_date(self):
        """Удалить все комментарии за текущую дату"""
        reply = QMessageBox.question(self, "Удалить все за дату",
                                     f"Удалить ВСЕ комментарии за {self.format_date(self.current_date)}?",
                                     QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            from database import delete_comments_for_silo_date
            delete_comments_for_silo_date(self.db_conn, self.silo_name, self.current_date)
            self.comment_edit.clear()
            self.load_comments()
