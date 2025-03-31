from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QCheckBox, QComboBox, QPushButton, QGroupBox,
                             QMessageBox, QApplication, QTabWidget, QListWidget,
                             QDialogButtonBox, QFrame, QWidget)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        
        self.setWindowTitle("Настройки JL Delete Lock")
        self.setMinimumWidth(450)
        self.setMinimumHeight(400)
        
        # Защита от непредвиденного закрытия
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        
        # Настраиваем интерфейс
        self.setup_ui()
        
        # Загружаем текущие настройки в элементы управления
        self.load_settings()
        
        # Применяем стиль Windows 11
        self.set_windows11_style()
    
    def setup_ui(self):
        main_layout = QVBoxLayout()
        
        # Создаем вкладки
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # Вкладка "Основные"
        general_tab = QWidget()
        general_layout = QVBoxLayout()
        general_tab.setLayout(general_layout)
        
        # Группа настроек автозапуска
        autostart_group = QGroupBox("Автозапуск")
        autostart_layout = QVBoxLayout()
        
        self.autostart_checkbox = QCheckBox("Запускать программу при старте Windows")
        autostart_layout.addWidget(self.autostart_checkbox)
        
        autostart_group.setLayout(autostart_layout)
        general_layout.addWidget(autostart_group)
        
        # Группа настроек горячих клавиш
        hotkey_group = QGroupBox("Горячие клавиши")
        hotkey_layout = QVBoxLayout()
        
        self.hotkey_checkbox = QCheckBox("Использовать горячие клавиши")
        hotkey_layout.addWidget(self.hotkey_checkbox)
        
        hotkey_combo_layout = QHBoxLayout()
        hotkey_combo_layout.addWidget(QLabel("Комбинация клавиш:"))
        
        self.modifier_combo = QComboBox()
        self.modifier_combo.addItems(["ALT", "CTRL", "SHIFT", "WIN"])
        hotkey_combo_layout.addWidget(self.modifier_combo)
        
        hotkey_combo_layout.addWidget(QLabel("+"))
        
        self.key_combo = QComboBox()
        self.key_combo.addItems(["DELETE", "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12", 
                                "L", "O", "P", "R", "U"])
        hotkey_combo_layout.addWidget(self.key_combo)
        
        hotkey_layout.addLayout(hotkey_combo_layout)
        
        # Пояснение о перезапуске для применения горячих клавиш
        hotkey_note = QLabel("Примечание: изменение горячих клавиш требует перезапуска программы")
        hotkey_note.setStyleSheet("color: #666; font-style: italic;")
        hotkey_layout.addWidget(hotkey_note)
        
        hotkey_group.setLayout(hotkey_layout)
        general_layout.addWidget(hotkey_group)
        
        # Группа поведения при закрытии
        close_group = QGroupBox("Поведение при закрытии")
        close_layout = QVBoxLayout()
        
        self.close_to_tray_checkbox = QCheckBox("Сворачивать программу в трей при закрытии")
        close_layout.addWidget(self.close_to_tray_checkbox)
        
        self.show_tray_notifications_checkbox = QCheckBox("Показывать уведомления в трее")
        close_layout.addWidget(self.show_tray_notifications_checkbox)
        
        close_group.setLayout(close_layout)
        general_layout.addWidget(close_group)
        
        # Группа подтверждений
        confirm_group = QGroupBox("Подтверждения")
        confirm_layout = QVBoxLayout()
        
        self.confirm_delete_checkbox = QCheckBox("Запрашивать подтверждение при удалении файла")
        confirm_layout.addWidget(self.confirm_delete_checkbox)
        
        confirm_group.setLayout(confirm_layout)
        general_layout.addWidget(confirm_group)
        
        # Добавляем вкладку "Основные"
        self.tab_widget.addTab(general_tab, "Основные")
        
        # Вкладка "Интеграция"
        integration_tab = QWidget()
        integration_layout = QVBoxLayout()
        integration_tab.setLayout(integration_layout)
        
        # Группа настроек контекстного меню
        context_group = QGroupBox("Контекстное меню Windows")
        context_layout = QVBoxLayout()
        
        # Используем контейнер с лейблом вместо wordwrap для чекбокса
        self.context_checkbox = QCheckBox()
        context_label = QLabel("Добавить пункт 'Проверить через JL Delete Lock' в контекстное меню файлов и папок")
        context_label.setWordWrap(True)
        
        # Размещаем чекбокс и лейбл в горизонтальном лейауте
        checkbox_layout = QHBoxLayout()
        checkbox_layout.addWidget(self.context_checkbox)
        checkbox_layout.addWidget(context_label, 1)  # 1 растягивает лейбл на всю доступную ширину
        checkbox_layout.setContentsMargins(0, 0, 0, 0)
        
        context_layout.addLayout(checkbox_layout)
        
        # Пояснение о правах администратора
        context_note = QLabel("Примечание: для изменения настроек контекстного меню могут потребоваться права администратора")
        context_note.setStyleSheet("color: #666; font-style: italic;")
        context_layout.addWidget(context_note)
        
        context_group.setLayout(context_layout)
        integration_layout.addWidget(context_group)
        
        # Растягиваем пустое пространство
        integration_layout.addStretch(1)
        
        # Добавляем вкладку "Интеграция"
        self.tab_widget.addTab(integration_tab, "Интеграция")
        
        # Вкладка "Обновления"
        updates_tab = QWidget()
        updates_layout = QVBoxLayout()
        updates_tab.setLayout(updates_layout)
        
        # Группа настроек обновления
        updates_group = QGroupBox("Настройки проверки обновлений")
        updates_group_layout = QVBoxLayout()
        
        # Автоматическая проверка обновлений
        self.auto_check_updates_checkbox = QCheckBox("Автоматически проверять наличие обновлений")
        updates_group_layout.addWidget(self.auto_check_updates_checkbox)
        
        # Интервал проверки
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("Интервал проверки:"))
        
        self.update_interval_combo = QComboBox()
        self.update_interval_combo.addItems(["Ежедневно", "Еженедельно", "Ежемесячно"])
        interval_layout.addWidget(self.update_interval_combo)
        interval_layout.addStretch(1)
        
        updates_group_layout.addLayout(interval_layout)
        
        # Кнопка для немедленной проверки
        check_now_layout = QHBoxLayout()
        check_now_layout.addStretch(1)
        
        self.check_updates_btn = QPushButton("Проверить обновления сейчас")
        self.check_updates_btn.clicked.connect(self.check_updates_now)
        check_now_layout.addWidget(self.check_updates_btn)
        
        updates_group_layout.addLayout(check_now_layout)
        
        updates_group.setLayout(updates_group_layout)
        updates_layout.addWidget(updates_group)
        updates_layout.addStretch(1)
        
        # Добавляем вкладку "Обновления"
        self.tab_widget.addTab(updates_tab, "Обновления")
        
        # Вкладка "Резервные копии"
        backup_tab = QWidget()
        backup_layout = QVBoxLayout()
        backup_tab.setLayout(backup_layout)
        
        # Группа резервных копий
        backup_group = QGroupBox("Управление резервными копиями настроек")
        backup_group_layout = QVBoxLayout()
        
        # Список резервных копий
        backup_label = QLabel("Доступные резервные копии:")
        backup_group_layout.addWidget(backup_label)
        
        self.backup_list = QListWidget()
        self.backup_list.setMinimumHeight(150)
        backup_group_layout.addWidget(self.backup_list)
        
        # Кнопки управления резервными копиями
        backup_buttons_layout = QHBoxLayout()
        
        self.create_backup_btn = QPushButton("Создать резервную копию")
        self.create_backup_btn.clicked.connect(self.create_backup)
        
        self.restore_backup_btn = QPushButton("Восстановить")
        self.restore_backup_btn.clicked.connect(self.restore_from_backup)
        
        backup_buttons_layout.addWidget(self.create_backup_btn)
        backup_buttons_layout.addWidget(self.restore_backup_btn)
        
        backup_group_layout.addLayout(backup_buttons_layout)
        
        # Кнопка для сброса настроек
        reset_layout = QHBoxLayout()
        
        self.reset_settings_btn = QPushButton("Сбросить настройки к значениям по умолчанию")
        self.reset_settings_btn.clicked.connect(self.reset_settings)
        
        reset_layout.addStretch(1)
        reset_layout.addWidget(self.reset_settings_btn)
        reset_layout.addStretch(1)
        
        backup_group_layout.addLayout(reset_layout)
        
        backup_group.setLayout(backup_group_layout)
        backup_layout.addWidget(backup_group)
        
        # Добавляем вкладку "Резервные копии"
        self.tab_widget.addTab(backup_tab, "Резервные копии")
        
        # Разделительная линия
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        main_layout.addWidget(line)
        
        # Кнопки
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.save_settings)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)
        
        self.setLayout(main_layout)
    
    def load_settings(self):
        """Загружает настройки из файла в элементы управления"""
        try:
            # Загружаем основные настройки
            self.autostart_checkbox.setChecked(self.settings.settings["autostart"])
            self.hotkey_checkbox.setChecked(self.settings.settings["hotkeys_enabled"])
            self.close_to_tray_checkbox.setChecked(self.settings.settings.get("close_to_tray", True))
            self.show_tray_notifications_checkbox.setChecked(self.settings.settings.get("show_tray_notifications", True))
            self.confirm_delete_checkbox.setChecked(self.settings.settings.get("confirm_delete", True))
            
            # Настройки горячих клавиш
            modifier_index = self.modifier_combo.findText(self.settings.settings["hotkey_modifier"])
            if modifier_index != -1:
                self.modifier_combo.setCurrentIndex(modifier_index)
            
            key_index = self.key_combo.findText(self.settings.settings["hotkey_key"])
            if key_index != -1:
                self.key_combo.setCurrentIndex(key_index)
            
            # Настройки интеграции
            self.context_checkbox.setChecked(self.settings.settings["context_menu_enabled"])
            
            # Загружаем настройки обновлений
            self.auto_check_updates_checkbox.setChecked(self.settings.settings.get("auto_check_updates", True))
            
            update_interval = self.settings.settings.get("update_check_interval", 7)
            if update_interval <= 1:
                self.update_interval_combo.setCurrentIndex(0)  # Ежедневно
            elif update_interval <= 7:
                self.update_interval_combo.setCurrentIndex(1)  # Еженедельно
            else:
                self.update_interval_combo.setCurrentIndex(2)  # Ежемесячно
            
            # Загружаем список резервных копий
            self.load_backup_list()
        except Exception as e:
            QMessageBox.warning(self, "Предупреждение", f"Не удалось загрузить некоторые настройки: {str(e)}")
    
    def load_backup_list(self):
        """Загружает список резервных копий настроек"""
        self.backup_list.clear()
        backups = self.settings.get_all_backups()
        
        for backup in backups:
            # Форматируем имя резервной копии для отображения
            display_name = backup.replace("settings_backup_", "").replace(".json", "")
            # Приводим к формату "ГГГГ-ММ-ДД ЧЧ:ММ:СС"
            if len(display_name) >= 15:  # Минимальная длина для формата ГГГГММДД_ЧЧММСС
                try:
                    year = display_name[:4]
                    month = display_name[4:6]
                    day = display_name[6:8]
                    hour = display_name[9:11]
                    minute = display_name[11:13]
                    second = display_name[13:15]
                    display_name = f"{year}-{month}-{day} {hour}:{minute}:{second}"
                except:
                    pass  # Если формат не подходит, оставляем как есть
            
            self.backup_list.addItem(f"{display_name} ({backup})")
    
    def create_backup(self):
        """Создает резервную копию текущих настроек"""
        if self.settings.create_backup():
            self.load_backup_list()
            QMessageBox.information(self, "Успех", "Резервная копия настроек успешно создана")
        else:
            QMessageBox.warning(self, "Ошибка", "Не удалось создать резервную копию настроек")
    
    def restore_from_backup(self):
        """Восстанавливает настройки из выбранной резервной копии"""
        selected_items = self.backup_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Предупреждение", "Выберите резервную копию для восстановления")
            return
        
        # Извлекаем имя файла из текста элемента
        item_text = selected_items[0].text()
        backup_file = item_text.split("(")[1].rstrip(")")
        
        # Запрашиваем подтверждение
        reply = QMessageBox.question(
            self,
            "Восстановление настроек",
            f"Вы действительно хотите восстановить настройки из резервной копии?\n{item_text}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if self.settings.restore_from_backup(backup_file):
                QMessageBox.information(self, "Успех", "Настройки успешно восстановлены")
                self.load_settings()  # Перезагружаем настройки в интерфейс
            else:
                QMessageBox.warning(self, "Ошибка", "Не удалось восстановить настройки из резервной копии")
    
    def reset_settings(self):
        """Сбрасывает настройки к значениям по умолчанию"""
        # Запрашиваем подтверждение
        reply = QMessageBox.question(
            self,
            "Сброс настроек",
            "Вы действительно хотите сбросить все настройки к значениям по умолчанию?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if self.settings.restore_default_settings():
                QMessageBox.information(self, "Успех", "Настройки успешно сброшены к значениям по умолчанию")
                self.load_settings()  # Перезагружаем настройки в интерфейс
            else:
                QMessageBox.warning(self, "Ошибка", "Не удалось сбросить настройки")
    
    def check_updates_now(self):
        """Запускает проверку обновлений из диалога настроек"""
        try:
            # Закрываем диалог настроек
            self.accept()
            
            # Запускаем проверку обновлений из главного окна
            if hasattr(self.parent(), "check_for_updates"):
                self.parent().check_for_updates()
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось запустить проверку обновлений: {str(e)}")
    
    def save_settings(self):
        """Сохраняет настройки из элементов управления в файл"""
        try:
            # Сохраняем настоящие значения для проверки изменений
            old_context_menu = self.settings.settings["context_menu_enabled"]
            old_hotkeys_enabled = self.settings.settings["hotkeys_enabled"]
            old_hotkey_modifier = self.settings.settings["hotkey_modifier"]
            old_hotkey_key = self.settings.settings["hotkey_key"]
            
            # Проверяем, требуются ли права администратора для настройки контекстного меню
            new_context_menu = self.context_checkbox.isChecked()
            
            # Обновляем настройки в объекте Settings
            self.settings.settings["autostart"] = self.autostart_checkbox.isChecked()
            self.settings.settings["hotkeys_enabled"] = self.hotkey_checkbox.isChecked()
            self.settings.settings["hotkey_modifier"] = self.modifier_combo.currentText()
            self.settings.settings["hotkey_key"] = self.key_combo.currentText()
            self.settings.settings["context_menu_enabled"] = new_context_menu
            self.settings.settings["close_to_tray"] = self.close_to_tray_checkbox.isChecked()
            self.settings.settings["show_tray_notifications"] = self.show_tray_notifications_checkbox.isChecked()
            self.settings.settings["confirm_delete"] = self.confirm_delete_checkbox.isChecked()
            
            # Сохраняем настройки обновлений
            self.settings.settings["auto_check_updates"] = self.auto_check_updates_checkbox.isChecked()
            
            # Устанавливаем интервал проверки в днях
            interval_index = self.update_interval_combo.currentIndex()
            if interval_index == 0:
                self.settings.settings["update_check_interval"] = 1  # Ежедневно
            elif interval_index == 1:
                self.settings.settings["update_check_interval"] = 7  # Еженедельно
            else:
                self.settings.settings["update_check_interval"] = 30  # Ежемесячно
            
            # Сохраняем настройки в файл
            if not self.settings.save_settings():
                QMessageBox.warning(self, "Предупреждение", "Не удалось сохранить настройки в файл. "
                                  "Настройки будут применены только для текущего сеанса.")
            
            # Обработка изменения настроек горячих клавиш
            hotkeys_changed = (old_hotkeys_enabled != self.settings.settings["hotkeys_enabled"] or 
                               old_hotkey_modifier != self.settings.settings["hotkey_modifier"] or 
                               old_hotkey_key != self.settings.settings["hotkey_key"])
            
            # Применяем настройки автозапуска
            # Безопасное применение настроек автозапуска
            try:
                self.settings.toggle_autostart(self.settings.settings["autostart"])
            except Exception as e:
                QMessageBox.warning(self, "Предупреждение", f"Не удалось настроить автозапуск: {str(e)}")
            
            # Проверка и настройка контекстного меню - только если изменилась
            if old_context_menu != new_context_menu:
                if not self.settings.is_admin() and new_context_menu != old_context_menu:
                    # Если настройка контекстного меню изменилась и нет прав администратора
                    reply = QMessageBox.question(
                        self,
                        "Необходимы права администратора",
                        "Для изменения настроек контекстного меню требуются права администратора. "
                        "Перезапустить программу с правами администратора?",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.Yes
                    )
                    
                    if reply == QMessageBox.Yes:
                        self.settings.run_as_admin()
                        self.accept()  # Закрываем диалог и сохраняем настройки
                        return
                
                # Применяем настройки контекстного меню
                try:
                    self.settings.toggle_context_menu(self.settings.settings["context_menu_enabled"])
                except Exception as e:
                    QMessageBox.warning(
                        self, 
                        "Предупреждение", 
                        f"Не удалось настроить контекстное меню: {str(e)}\n"
                        "Попробуйте запустить программу с правами администратора."
                    )
            
            # Информируем о необходимости перезапуска при изменении горячих клавиш
            if hotkeys_changed:
                QMessageBox.information(
                    self,
                    "Настройки горячих клавиш изменены",
                    "Изменения в настройках горячих клавиш будут применены при следующем запуске программы."
                )
            
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Произошла ошибка при сохранении настроек: {str(e)}")
            # Несмотря на ошибку, пытаемся закрыть диалог
            self.accept()
    
    def set_windows11_style(self):
        """Применяет стиль Windows 11 к диалогу настроек"""
        style = """
        QDialog, QGroupBox, QLabel, QTabWidget, QTabBar, QFrame {
            background-color: #FFFFFF;
            color: #202020;
        }
        
        QGroupBox {
            border: 1px solid #E0E0E0;
            border-radius: 8px;
            margin-top: 1.5ex;
            padding-top: 1.5ex;
            padding-bottom: 1ex;
        }
        
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top center;
            padding: 0 5px;
        }
        
        QPushButton {
            background-color: #0078D7;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
        }
        
        QPushButton:hover {
            background-color: #1683D8;
        }
        
        QPushButton:pressed {
            background-color: #006CCB;
        }
        
        QCheckBox {
            spacing: 8px;
        }
        
        QCheckBox::indicator {
            width: 18px;
            height: 18px;
            border-radius: 3px;
            border: 1px solid #CCC;
        }
        
        QCheckBox::indicator:unchecked {
            background-color: #FFF;
        }
        
        QCheckBox::indicator:checked {
            background-color: #0078D7;
            border: 1px solid #0078D7;
        }
        
        QComboBox {
            border: 1px solid #E0E0E0;
            border-radius: 4px;
            padding: 5px;
            min-width: 6em;
        }
        
        QComboBox::drop-down {
            subcontrol-origin: padding;
            subcontrol-position: center right;
            width: 20px;
            border-left: none;
        }
        
        QTabWidget::pane {
            border: 1px solid #E0E0E0;
            border-radius: 8px;
            padding: 5px;
        }
        
        QTabBar::tab {
            background-color: #F5F5F5;
            border: 1px solid #E0E0E0;
            border-bottom: none;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            padding: 6px 12px;
            margin-right: 2px;
        }
        
        QTabBar::tab:selected {
            background-color: #FFFFFF;
            border-bottom: 1px solid #FFFFFF;
        }
        
        QTabBar::tab:hover:!selected {
            background-color: #E0E0E0;
        }
        
        QListWidget {
            border: 1px solid #E0E0E0;
            border-radius: 4px;
            background-color: #FFFFFF;
        }
        
        QListWidget::item {
            padding: 5px;
            border-radius: 2px;
        }
        
        QListWidget::item:selected {
            background-color: #E0F0FF;
            color: #000000;
        }
        
        QListWidget::item:hover:!selected {
            background-color: #F0F0F0;
        }
        """
        self.setStyleSheet(style)
        
    def closeEvent(self, event):
        """Обрабатывает закрытие диалога крестиком в углу"""
        # Предотвращаем закрытие диалога через крестик, если были изменения
        event.accept()  # Всегда принимаем событие закрытия