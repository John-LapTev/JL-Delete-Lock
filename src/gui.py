from PyQt5.QtWidgets import (QApplication, QMainWindow, QLabel, QVBoxLayout, 
                            QHBoxLayout, QWidget, QPushButton, QTableWidget,
                            QTableWidgetItem, QHeaderView, QMessageBox, QProgressBar,
                            QAction, QMenu, QSystemTrayIcon, QFileDialog, QCheckBox)
from PyQt5.QtGui import QIcon, QFont, QDragEnterEvent, QDropEvent
from PyQt5.QtCore import Qt, QSize, QThread, pyqtSignal, QTimer, QMutex, QMutexLocker
import os
import sys
import logging
import traceback
import time

# Пробуем импортировать абсолютно (для работы в PyInstaller)
try:
    import file_handler
    import settings
    import hotkey_manager
    import settings_dialog
    import update_checker as update_checker_module
    import admin_utils
    update_checker_available = True
except ImportError:
    # Если не удалось, настраиваем пути и пробуем относительные импорты 
    # (для работы в режиме разработки)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    
    # Теперь пробуем импортировать
    from file_handler import get_blocking_processes, unlock_file, delete_file, clear_cache, resource_path, user_friendly_error, unlock_and_delete_file
    from settings import Settings
    from hotkey_manager import HotkeyManager
    from settings_dialog import SettingsDialog
    from admin_utils import check_admin_requirements, show_admin_requirements_dialog
    
    try:
        from update_checker import UpdateChecker, UpdateDialog
        update_checker_available = True
    except ImportError:
        update_checker_available = False
        logging.warning("Модуль проверки обновлений недоступен")
else:
    # Если абсолютный импорт сработал, создаем ссылки на нужные функции
    get_blocking_processes = file_handler.get_blocking_processes
    unlock_file = file_handler.unlock_file
    delete_file = file_handler.delete_file
    clear_cache = file_handler.clear_cache
    resource_path = file_handler.resource_path
    user_friendly_error = file_handler.user_friendly_error
    unlock_and_delete_file = file_handler.unlock_and_delete_file
    Settings = settings.Settings
    HotkeyManager = hotkey_manager.HotkeyManager
    SettingsDialog = settings_dialog.SettingsDialog
    check_admin_requirements = admin_utils.check_admin_requirements
    show_admin_requirements_dialog = admin_utils.show_admin_requirements_dialog
    if update_checker_available:
        UpdateChecker = update_checker_module.UpdateChecker
        UpdateDialog = update_checker_module.UpdateDialog

# Глобальный мьютекс для предотвращения запуска нескольких экземпляров анализа
analysis_mutex = QMutex()

# Класс Worker для выполнения операций в отдельном потоке
class FileAnalysisWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    progress = pyqtSignal(int, int)  # Прогресс: текущий, всего
    
    def __init__(self, path):
        super().__init__()
        self.path = path
        self._is_cancelled = False
    
    def cancel(self):
        """Отмена операции"""
        self._is_cancelled = True
    
    def run(self):
        try:
            # Блокируем мьютекс, чтобы предотвратить параллельный анализ
            locker = QMutexLocker(analysis_mutex)
            
            # Получаем процессы, блокирующие файл
            if os.path.isdir(self.path):
                # Для директорий показываем прогресс
                total_files = sum([len(files) for _, _, files in os.walk(self.path)])
                processed = 0
                
                def progress_callback(current, total):
                    if not self._is_cancelled:
                        self.progress.emit(current, total)
                    return not self._is_cancelled  # Возвращаем False для отмены операции
                
                processes = get_blocking_processes(self.path, progress_callback)
            else:
                processes = get_blocking_processes(self.path)
            
            if self._is_cancelled:
                return
                
            if isinstance(processes, dict) and "error" in processes:
                self.error.emit(user_friendly_error(processes['error']))
                return
            
            self.finished.emit(processes)
        except Exception as e:
            logging.error(f"Ошибка в FileAnalysisWorker: {str(e)}", exc_info=True)
            self.error.emit(user_friendly_error(str(e)))
        finally:
            # Убедимся, что мьютекс разблокирован в случае ошибки
            if 'locker' in locals():
                del locker  # Это разблокирует мьютекс


class UnlockWorker(QThread):
    finished = pyqtSignal(dict)
    progress = pyqtSignal(int, int)  # Прогресс: текущий, всего
    
    def __init__(self, path, processes):
        super().__init__()
        self.path = path
        self.processes = processes
        self._is_cancelled = False
    
    def cancel(self):
        """Отмена операции"""
        self._is_cancelled = True
    
    def run(self):
        try:
            # Индикация прогресса
            total = len(self.processes)
            
            # Создаем локальную копию процессов для обработки
            # чтобы избежать гонки данных, если основной список изменится
            processes_to_handle = list(self.processes)
            
            processed_list = []
            for i, process in enumerate(processes_to_handle):
                if self._is_cancelled:
                    break
                    
                # Обновляем прогресс
                self.progress.emit(i, total)
                
                # Обрабатываем один процесс за раз
                result = unlock_file(self.path, [process])
                
                # Добавляем результат в итоговый список
                if "success" in result:
                    if "message" in result and process.get("process_name"):
                        process_info = {
                            "success": True,
                            "process_name": process.get("process_name", ""),
                            "pid": process.get("pid", 0),
                            "message": result["message"]
                        }
                        processed_list.append(process_info)
                else:
                    # Если ошибка, добавляем информацию об ошибке
                    process_info = {
                        "success": False,
                        "process_name": process.get("process_name", ""),
                        "pid": process.get("pid", 0),
                        "error": result.get("error", "Неизвестная ошибка")
                    }
                    processed_list.append(process_info)
            
            # Формируем итоговый результат
            if self._is_cancelled:
                self.finished.emit({"cancelled": True})
            else:
                # Определяем, успешно ли выполнена вся операция
                all_success = all(item.get("success", False) for item in processed_list)
                
                if all_success:
                    self.finished.emit({"success": True, "processed": processed_list})
                else:
                    # Формируем понятное сообщение об ошибке
                    error_processes = [p for p in processed_list if not p.get("success", False)]
                    error_names = [f"{p.get('process_name', '')} (PID: {p.get('pid', 0)})" for p in error_processes]
                    error_message = f"Не удалось завершить следующие процессы: {', '.join(error_names)}"
                    
                    self.finished.emit({"error": error_message, "processed": processed_list})
                
        except Exception as e:
            logging.error(f"Ошибка в UnlockWorker: {str(e)}", exc_info=True)
            self.finished.emit({"error": user_friendly_error(str(e))})


class DeleteWorker(QThread):
    finished = pyqtSignal(dict)
    progress = pyqtSignal(int, int)  # Прогресс: текущий, всего
    
    def __init__(self, path):
        super().__init__()
        self.path = path
        self._is_cancelled = False
    
    def cancel(self):
        """Отмена операции"""
        self._is_cancelled = True
    
    def run(self):
        try:
            # Для директорий показываем прогресс удаления
            if os.path.isdir(self.path):
                files_to_delete = []
                total_dirs = 0
                
                # Сначала считаем общее количество файлов и папок
                for root, dirs, files in os.walk(self.path, topdown=False):
                    for file in files:
                        files_to_delete.append(os.path.join(root, file))
                    total_dirs += len(dirs)
                
                total_items = len(files_to_delete) + total_dirs + 1  # +1 для корневой директории
                processed = 0
                
                # Теперь удаляем каждый файл по очереди
                for file_path in files_to_delete:
                    if self._is_cancelled:
                        self.finished.emit({"cancelled": True})
                        return
                        
                    try:
                        os.remove(file_path)
                        processed += 1
                        self.progress.emit(processed, total_items)
                    except Exception as e:
                        logging.error(f"Ошибка при удалении файла {file_path}: {str(e)}")
                
                # Удаляем пустые директории
                for root, dirs, files in os.walk(self.path, topdown=False):
                    for dir_name in dirs:
                        if self._is_cancelled:
                            self.finished.emit({"cancelled": True})
                            return
                            
                        try:
                            dir_path = os.path.join(root, dir_name)
                            os.rmdir(dir_path)
                            processed += 1
                            self.progress.emit(processed, total_items)
                        except Exception as e:
                            logging.error(f"Ошибка при удалении директории {dir_path}: {str(e)}")
                
                # Наконец, удаляем корневую директорию
                try:
                    os.rmdir(self.path)
                    processed += 1
                    self.progress.emit(processed, total_items)
                    self.finished.emit({"success": True})
                except Exception as e:
                    error_msg = f"Не удалось удалить директорию {self.path}: {str(e)}"
                    logging.error(error_msg)
                    self.finished.emit({"error": user_friendly_error(error_msg)})
            else:
                # Для обычных файлов просто удаляем
                result = delete_file(self.path)
                
                if self._is_cancelled:
                    self.finished.emit({"cancelled": True})
                else:
                    self.finished.emit(result)
                    
        except Exception as e:
            logging.error(f"Ошибка в DeleteWorker: {str(e)}", exc_info=True)
            self.finished.emit({"error": user_friendly_error(str(e))})


class MainWindow(QMainWindow):
    def __init__(self):
        try:
            super().__init__()
            
            self.setWindowTitle("JL Delete Lock")
            
            # Используем resource_path для иконки
            icon_path = resource_path("lock_file.ico")
            if not os.path.exists(icon_path):
                icon_path = resource_path(os.path.join("resources", "lock_file.ico"))
            
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
                logging.info(f"Установлена иконка: {icon_path}")
            else:
                logging.warning("Не удалось найти иконку приложения")
                
            self.setMinimumSize(600, 400)
            
            # Текущий путь к файлу/папке
            self.current_path = None
            self.blocking_processes = []
            
            # Загружаем настройки
            self.settings = Settings()

            # Защитный флаг для предотвращения повторной инициализации
            self.hotkey_manager_initialized = False
            
            # Сохраняем локальный флаг доступности проверки обновлений
            # ВАЖНО: Этот атрибут должен быть инициализирован до создания UI
            self.updates_enabled = update_checker_available
            
            # Инициализируем систему проверки обновлений
            if self.updates_enabled:
                try:
                    self.update_checker = UpdateChecker(self.settings, self)
                    self.update_dialog = UpdateDialog(self)
                    # Изменяем URL для проверки обновлений, чтобы он указывал на ваш хостинг
                    self.update_checker.update_url = "https://jl-studio.art/my_apps/JL_Delete_Lock/updates.json"
                    self.update_checker.download_url = "https://jl-studio.art/my_apps/JL_Delete_Lock/downloads/"
                except Exception as e:
                    logging.error(f"Ошибка при инициализации UpdateChecker: {str(e)}", exc_info=True)
                    self.updates_enabled = False

            # Создаем интерфейс (важно: вызывается после установки self.updates_enabled)
            self.create_ui()
            
            # Создаем системный трей
            self.create_tray_icon()
            
            # Применяем стиль Windows 11
            self.set_windows11_style()
            
            # Включаем поддержку drag and drop
            self.setAcceptDrops(True)
            
            # Центрируем окно
            self.center_window()

            # Инициализируем менеджер горячих клавиш
            try:
                if not self.hotkey_manager_initialized:
                    self.hotkey_manager = HotkeyManager(self.settings)
                    self.hotkey_manager.signals.hotkey_pressed.connect(self.safe_show_and_activate)
                    self.hotkey_manager_initialized = True
                
                # Если горячие клавиши включены, запускаем их отслеживание
                if self.settings.settings["hotkeys_enabled"]:
                    self.hotkey_manager.start()
                    logging.info("Горячие клавиши запущены при инициализации")
                else:
                    logging.info("Горячие клавиши отключены в настройках")
            except Exception as e:
                logging.error(f"Ошибка при инициализации горячих клавиш: {str(e)}", exc_info=True)
            
            # Таймер для проверки работы горячих клавиш
            self.hotkey_timer = QTimer(self)
            self.hotkey_timer.timeout.connect(self.check_hotkey_state)
            self.hotkey_timer.start(10000)  # Проверяем каждые 10 секунд
            
            # Проверяем требования прав администратора при запуске - ТОЛЬКО если включено контекстное меню
            if not self.settings.settings.get("dont_ask_for_admin", False):
                # Проверяем только если контекстное меню включено и нет прав администратора
                if self.settings.settings.get("context_menu_enabled", False) and not self.settings.is_admin():
                    admin_features = ["Интеграция с контекстным меню Windows"]
                    if show_admin_requirements_dialog(self, admin_features):
                        self.settings.run_as_admin()
            
        except Exception as e:
            logging.critical(f"Критическая ошибка при инициализации главного окна: {str(e)}", exc_info=True)
            raise
    
    def check_hotkey_state(self):
        """Периодически проверяет состояние горячих клавиш"""
        try:
            if hasattr(self, 'hotkey_manager') and self.hotkey_manager and self.hotkey_manager_initialized:
                if not self.hotkey_manager.active and self.settings.settings["hotkeys_enabled"]:
                    logging.warning("Обнаружена остановка горячих клавиш - перезапуск")
                    
                    # Останавливаем старый менеджер, если он есть
                    try:
                        self.hotkey_manager.stop()
                    except Exception as e:
                        logging.error(f"Ошибка при остановке менеджера горячих клавиш: {str(e)}")
                    
                    # Создаем новый менеджер
                    self.hotkey_manager = HotkeyManager(self.settings)
                    self.hotkey_manager.signals.hotkey_pressed.connect(self.safe_show_and_activate)
                    self.hotkey_manager.start()
                    logging.info("Горячие клавиши перезапущены")
        except Exception as e:
            logging.error(f"Ошибка при проверке состояния горячих клавиш: {str(e)}", exc_info=True)
    
    def center_window(self):
        screen_geometry = QApplication.primaryScreen().geometry()
        x = (screen_geometry.width() - self.width()) // 2
        y = (screen_geometry.height() - self.height()) // 2
        self.move(x, y)
    
    def create_ui(self):
        # Главный виджет и макет
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)
        
        # Шрифты и стили
        title_font = QFont("Segoe UI", 11)
        button_font = QFont("Segoe UI", 10)
        
        # Создаем меню
        self.create_menu()
        
        # Верхняя панель с информацией
        self.path_label = QLabel("Перетащите файл или папку на это окно")
        self.path_label.setFont(title_font)
        self.path_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.path_label)
        
        # Добавляем прогресс-бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Бесконечная анимация
        self.progress_bar.setVisible(False)  # Скрываем до начала операции
        main_layout.addWidget(self.progress_bar)
        
        # Статус-лейбл
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.status_label)
        
        # Таблица для отображения процессов
        self.process_table = QTableWidget(0, 3)  # 0 строк, 3 столбца
        self.process_table.setHorizontalHeaderLabels(["Процесс", "PID", "Тип"])
        
        # Настраиваем внешний вид таблицы
        self.process_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.process_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.process_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.process_table.setColumnWidth(1, 70)
        self.process_table.setColumnWidth(2, 100)
        self.process_table.setSortingEnabled(True)  # Включаем сортировку
        
        main_layout.addWidget(self.process_table)
        
        # Нижняя панель с кнопками
        button_layout = QHBoxLayout()
        
        # Кнопки
        self.unlock_btn = QPushButton("Разблокировать")
        self.unlock_btn.setFont(button_font)
        self.unlock_btn.setEnabled(False)
        self.unlock_btn.clicked.connect(self.unlock_file_action)
        
        self.unlock_delete_btn = QPushButton("Разблокировать и удалить")
        self.unlock_delete_btn.setFont(button_font)
        self.unlock_delete_btn.setEnabled(False)
        self.unlock_delete_btn.clicked.connect(self.unlock_and_delete_action)
        
        # Добавляем кнопку повторного анализа
        self.refresh_btn = QPushButton("Обновить анализ")
        self.refresh_btn.setFont(button_font)
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.clicked.connect(self.refresh_analysis)
        
        # Добавляем кнопку отмены операции
        self.cancel_btn = QPushButton("Отмена операции")
        self.cancel_btn.setFont(button_font)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_current_operation)
        self.cancel_btn.setVisible(False)  # По умолчанию скрыта
        
        button_layout.addWidget(self.refresh_btn)
        button_layout.addWidget(self.unlock_btn)
        button_layout.addWidget(self.unlock_delete_btn)
        button_layout.addWidget(self.cancel_btn)
        
        main_layout.addLayout(button_layout)
        
        # Добавляем информацию о горячих клавишах, если они включены
        if self.settings.settings["hotkeys_enabled"] and hasattr(self, 'hotkey_manager'):
            hotkey_info = QLabel(f"Горячие клавиши: {self.hotkey_manager.get_current_hotkey_text()}")
            hotkey_info.setAlignment(Qt.AlignCenter)
            hotkey_info.setStyleSheet("color: #666; font-style: italic;")
            main_layout.addWidget(hotkey_info)
        
        # Устанавливаем главный виджет
        self.setCentralWidget(main_widget)
    
    def create_menu(self):
        """Создает главное меню программы"""
        menubar = self.menuBar()
        
        # Меню "Файл"
        file_menu = menubar.addMenu("Файл")
        
        open_action = QAction("Открыть файл...", self)
        open_action.triggered.connect(self.open_file_dialog)
        file_menu.addAction(open_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Выход", self)
        exit_action.triggered.connect(self.exit_application)
        file_menu.addAction(exit_action)
        
        # Меню "Настройки"
        settings_menu = menubar.addMenu("Настройки")
        
        preferences_action = QAction("Параметры", self)
        preferences_action.triggered.connect(self.show_settings_dialog)
        settings_menu.addAction(preferences_action)
        
        # Меню "Справка"
        help_menu = menubar.addMenu("Справка")
        
        if self.updates_enabled:
            check_updates_action = QAction("Проверить обновления", self)
            check_updates_action.triggered.connect(self.check_for_updates)
            help_menu.addAction(check_updates_action)
            
            help_menu.addSeparator()
        
        about_action = QAction("О программе", self)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)
    
    def open_file_dialog(self):
        """Открывает диалог выбора файла"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Выберите файл для анализа",
                "",
                "Все файлы (*.*)"
            )
            
            if file_path:
                self.check_file(file_path)
        except Exception as e:
            logging.error(f"Ошибка при открытии файлового диалога: {str(e)}", exc_info=True)
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть файловый диалог: {user_friendly_error(str(e))}")
    
    def create_tray_icon(self):
        """Создает иконку в системном трее"""
        try:
            self.tray_icon = QSystemTrayIcon(self)
            
            # Используем resource_path для иконки
            icon_path = resource_path("lock_file.ico")
            if not os.path.exists(icon_path):
                icon_path = resource_path(os.path.join("resources", "lock_file.ico"))
            
            if os.path.exists(icon_path):
                self.tray_icon.setIcon(QIcon(icon_path))
            else:
                # Используем стандартную иконку, если наша не найдена
                self.tray_icon.setIcon(QIcon.fromTheme("document-properties"))
                logging.warning("Не удалось найти иконку для системного трея")
            
            # Создаем контекстное меню для трея
            tray_menu = QMenu()
            
            open_action = QAction("Открыть", self)
            open_action.triggered.connect(self.safe_show_and_activate)
            tray_menu.addAction(open_action)
            
            settings_action = QAction("Настройки", self)
            settings_action.triggered.connect(self.show_settings_dialog)
            tray_menu.addAction(settings_action)
            
            tray_menu.addSeparator()
            
            exit_action = QAction("Выход", self)
            # Вместо self.close() используем новый метод exit_application
            exit_action.triggered.connect(self.exit_application)
            tray_menu.addAction(exit_action)
            
            self.tray_icon.setContextMenu(tray_menu)
            self.tray_icon.activated.connect(self.tray_icon_activated)
            
            # Показываем иконку в трее
            self.tray_icon.show()
        except Exception as e:
            logging.error(f"Ошибка при создании иконки трея: {str(e)}", exc_info=True)
    
    def exit_application(self):
        """Полностью завершает работу приложения без сворачивания в трей"""
        try:
            logging.info("Вызван метод exit_application для полного закрытия приложения")
            
            # Останавливаем таймер проверки
            if hasattr(self, 'hotkey_timer') and self.hotkey_timer:
                self.hotkey_timer.stop()
                logging.info("Таймер проверки горячих клавиш остановлен")
            
            # Останавливаем отслеживание горячих клавиш
            if hasattr(self, 'hotkey_manager') and self.hotkey_manager and self.hotkey_manager_initialized:
                try:
                    self.hotkey_manager.stop()
                    logging.info("Горячие клавиши остановлены при выходе")
                except Exception as e:
                    logging.error(f"Ошибка при остановке горячих клавиш: {str(e)}")
            
            # Отменяем текущие операции, если они выполняются
            try:
                self.cancel_current_operation()
            except Exception as e:
                logging.error(f"Ошибка при отмене операций: {str(e)}")
            
            # Скрываем иконку трея перед закрытием
            if hasattr(self, 'tray_icon') and self.tray_icon:
                self.tray_icon.hide()
                logging.info("Иконка трея скрыта")
            
            # Закрываем приложение после небольшой паузы
            QTimer.singleShot(200, lambda: QApplication.quit())
            logging.info("Завершение работы приложения")
        except Exception as e:
            logging.error(f"Ошибка при закрытии приложения: {str(e)}", exc_info=True)
            # В случае ошибки принудительно завершаем программу
            QApplication.quit()
    
    def show_settings_dialog(self):
        """Показывает диалог настроек"""
        try:
            # Запоминаем текущие настройки для обнаружения изменений
            old_hotkeys_enabled = self.settings.settings["hotkeys_enabled"]
            old_hotkey_modifier = self.settings.settings["hotkey_modifier"]
            old_hotkey_key = self.settings.settings["hotkey_key"]
            
            dialog = SettingsDialog(self.settings, self)
            result = dialog.exec_()
            
            if result:
                # Проверяем, изменились ли настройки горячих клавиш
                hotkeys_changed = (old_hotkeys_enabled != self.settings.settings["hotkeys_enabled"] or
                               old_hotkey_modifier != self.settings.settings["hotkey_modifier"] or 
                               old_hotkey_key != self.settings.settings["hotkey_key"])
                
                # Если настройки горячих клавиш изменились, обновляем их
                if hotkeys_changed:
                    try:
                        # Останавливаем текущие горячие клавиши
                        if hasattr(self, 'hotkey_manager') and self.hotkey_manager:
                            logging.info("Останавливаем старые горячие клавиши")
                            self.hotkey_manager.stop()
                        
                        # Создаем новый экземпляр менеджера горячих клавиш
                        logging.info("Создаем новый менеджер горячих клавиш")
                        self.hotkey_manager = HotkeyManager(self.settings)
                        self.hotkey_manager_initialized = True
                        
                        # Подключаем сигнал
                        self.hotkey_manager.signals.hotkey_pressed.connect(self.safe_show_and_activate)
                        
                        # Запускаем горячие клавиши, если они включены
                        if self.settings.settings["hotkeys_enabled"]:
                            logging.info("Запускаем новые горячие клавиши")
                            self.hotkey_manager.start()
                        
                        logging.info("Горячие клавиши обновлены успешно")
                    except Exception as e:
                        logging.error(f"Ошибка при обновлении горячих клавиш: {str(e)}", exc_info=True)
                        QMessageBox.warning(self, "Предупреждение", f"Не удалось обновить горячие клавиши: {str(e)}")
                
                # Обновляем интерфейс в соответствии с новыми настройками
                QTimer.singleShot(0, self.update_ui_after_settings_change)
        except Exception as e:
            logging.error(f"Ошибка при открытии настроек: {str(e)}", exc_info=True)
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть настройки: {user_friendly_error(str(e))}")
    
    def show_about_dialog(self):
        """Показывает диалог 'О программе'"""
        QMessageBox.about(
            self,
            "О программе JL Delete Lock",
            "<h2>JL Delete Lock</h2>"
            "<p>Версия 1.0</p>"
            "<p>Программа для разблокировки и удаления заблокированных файлов и папок в Windows.</p>"
            "<p>Особенности программы:</p>"
            "<ul>"
            "<li>Определение процессов, блокирующих файл</li>"
            "<li>Разблокировка файлов путем завершения блокирующих процессов</li>"
            "<li>Удаление разблокированных файлов</li>"
            "<li>Поддержка перетаскивания файлов</li>"
            "<li>Интеграция с контекстным меню Windows</li>"
            "<li>Поддержка горячих клавиш</li>"
            "</ul>"
        )
    
    def check_for_updates(self):
        """Проверяет наличие обновлений программы"""
        if self.updates_enabled:
            self.status_label.setText("Проверка обновлений...")
            
            def on_check_complete(result):
                self.status_label.setText("")
                
                if "error" in result:
                    self.update_dialog.show_check_error(result)
                elif result.get("update_available", False):
                    self.update_dialog.show_update_available(result)
                else:
                    self.update_dialog.show_no_updates()
            
            self.update_checker.check_for_updates_async(force=True, on_complete=on_check_complete)
        else:
            QMessageBox.information(self, "Информация", "Функция проверки обновлений недоступна.")
    
    def tray_icon_activated(self, reason):
        """Обрабатывает активацию иконки в трее"""
        try:
            if reason == QSystemTrayIcon.DoubleClick or reason == QSystemTrayIcon.Trigger:
                # Простой подход - просто показываем и активируем окно без сложной логики
                if not self.isVisible():
                    self.show()
                
                if self.isMinimized():
                    self.showNormal()
                    
                # Используем более простую схему отложенной активации
                QTimer.singleShot(150, self._simple_activation)
        except Exception as e:
            logging.error(f"Ошибка при активации из трея: {str(e)}", exc_info=True)
            # В случае ошибки просто показываем окно
            self.show()
    
    def _simple_activation(self):
        """Упрощенная активация окна без сложной логики"""
        try:
            self.activateWindow()
        except Exception as e:
            logging.error(f"Ошибка при активации окна: {str(e)}")
    
    def safe_show_and_activate(self):
        """Безопасно показывает и активирует окно с обработкой исключений"""
        try:
            logging.info("Вызов safe_show_and_activate")
            
            # Просто показываем окно
            if not self.isVisible():
                self.show()
                logging.info("Окно показано")
            
            if self.isMinimized():
                self.showNormal()
                logging.info("Окно восстановлено из свернутого состояния")
            
            # Используем упрощенную схему отложенной активации
            QTimer.singleShot(150, self._simple_activation)
        except Exception as e:
            logging.error(f"Ошибка в safe_show_and_activate: {str(e)}", exc_info=True)
            # Самый простой подход в случае ошибки
            try:
                self.show()
            except Exception as sub_e:
                logging.error(f"Критическая ошибка при показе окна: {str(sub_e)}", exc_info=True)
    
    def show_and_activate(self):
        """Показывает и активирует окно программы"""
        # Используем более надежный метод вместо прямого
        self.safe_show_and_activate()
    
    def update_ui_after_settings_change(self):
        """Обновляет элементы интерфейса после изменения настроек"""
        try:
            # Обновляем информацию о горячих клавишах
            for i in range(self.centralWidget().layout().count()):
                item = self.centralWidget().layout().itemAt(i)
                if item and item.widget() and isinstance(item.widget(), QLabel):
                    if "Горячие клавиши:" in item.widget().text():
                        item.widget().deleteLater()  # Удаляем старый лейбл
            
            # Добавляем новый лейбл с горячими клавишами, если они включены
            if self.settings.settings["hotkeys_enabled"] and hasattr(self, 'hotkey_manager'):
                layout = self.centralWidget().layout()
                hotkey_info = QLabel(f"Горячие клавиши: {self.hotkey_manager.get_current_hotkey_text()}")
                hotkey_info.setAlignment(Qt.AlignCenter)
                hotkey_info.setStyleSheet("color: #666; font-style: italic;")
                layout.addWidget(hotkey_info)
        except Exception as e:
            logging.error(f"Ошибка при обновлении интерфейса: {str(e)}", exc_info=True)
    
    def set_windows11_style(self):
        """Применяет стиль Windows 11 к интерфейсу"""
        style = """
        QMainWindow, QWidget {
            background-color: #FFFFFF;
            color: #202020;
        }
        
        QLabel {
            padding: 8px;
            border-radius: 8px;
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
        
        QPushButton:disabled {
            background-color: #CCCCCC;
            color: #666666;
        }
        
        QTableWidget {
            border: 1px solid #E0E0E0;
            border-radius: 8px;
            gridline-color: #F0F0F0;
        }
        
        QHeaderView::section {
            background-color: #F5F5F5;
            padding: 4px;
            border: none;
            border-bottom: 1px solid #E0E0E0;
        }
        
        QProgressBar {
            border: 1px solid #E0E0E0;
            border-radius: 4px;
            text-align: center;
        }
        
        QProgressBar::chunk {
            background-color: #0078D7;
            width: 20px;
        }
        
        QMenuBar {
            background-color: #F5F5F5;
            border-bottom: 1px solid #E0E0E0;
        }
        
        QMenuBar::item {
            background-color: transparent;
            padding: 6px 10px;
        }
        
        QMenuBar::item:selected {
            background-color: #E0E0E0;
            border-radius: 4px;
        }
        
        QMenu {
            background-color: #FFFFFF;
            border: 1px solid #E0E0E0;
            border-radius: 6px;
            padding: 5px;
        }
        
        QMenu::item {
            padding: 6px 15px;
            border-radius: 4px;
        }
        
        QMenu::item:selected {
            background-color: #F0F0F0;
        }
        """
        self.setStyleSheet(style)
    
    # Обработка drag and drop
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event: QDropEvent):
        try:
            if event.mimeData().hasUrls():
                path = event.mimeData().urls()[0].toLocalFile()
                self.check_file(path)
        except Exception as e:
            logging.error(f"Ошибка при обработке перетаскивания файла: {str(e)}", exc_info=True)
    
    def refresh_analysis(self):
        """Повторно анализирует текущий файл/папку"""
        try:
            if self.current_path and os.path.exists(self.current_path):
                self.check_file(self.current_path)
        except Exception as e:
            logging.error(f"Ошибка при обновлении анализа: {str(e)}", exc_info=True)
            QMessageBox.critical(self, "Ошибка", f"Не удалось обновить анализ: {user_friendly_error(str(e))}")
    
    def cancel_current_operation(self):
        """Отменяет текущую операцию"""
        try:
            # Отменяем все активные потоки
            for thread_attr in ['analysis_thread', 'unlock_thread', 'delete_thread', 'unlock_delete_thread']:
                if hasattr(self, thread_attr) and getattr(self, thread_attr, None):
                    thread = getattr(self, thread_attr)
                    if hasattr(thread, 'cancel'):
                        thread.cancel()
                    # Ждем завершения потока максимум 1 секунду
                    if thread.isRunning():
                        thread.wait(1000)
            
            # Восстанавливаем состояние интерфейса
            self.progress_bar.setVisible(False)
            self.status_label.setText("Операция отменена")
            
            # Восстанавливаем кнопки
            self.cancel_btn.setVisible(False)
            self.cancel_btn.setEnabled(False)
            
            if self.current_path:
                self.refresh_btn.setEnabled(True)
                # Исправленная строка - передаем булево значение
                self.unlock_btn.setEnabled(bool(self.blocking_processes))
                self.unlock_delete_btn.setEnabled(bool(self.current_path))
            
            logging.info("Текущая операция отменена пользователем")
        except Exception as e:
            logging.error(f"Ошибка при отмене операции: {str(e)}", exc_info=True)
    
    def check_file(self, path):
        try:
            if not os.path.exists(path):
                QMessageBox.critical(self, "Ошибка", f"Путь не существует: {path}")
                return
            
            # Активируем окно программы и выводим его на передний план
            self.show()
            self.setWindowState(self.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
            self.activateWindow()
            
            self.current_path = path
            
            # Если путь слишком длинный, сокращаем его для отображения
            display_path = path
            if len(path) > 60:
                # Сокращаем путь, оставляя начало и конец
                display_path = path[:30] + "..." + path[-27:]
                
            self.path_label.setText(f"Путь: {display_path}")
            self.path_label.setToolTip(path)  # Показываем полный путь при наведении
            
            # Очищаем предыдущие данные
            self.process_table.setRowCount(0)
            
            # Показываем прогресс-бар и статус
            self.progress_bar.setVisible(True)
            self.status_label.setText("Анализ файла...")
            
            # Отключаем стандартные кнопки на время анализа
            self.unlock_btn.setEnabled(False)
            self.unlock_delete_btn.setEnabled(False)
            self.refresh_btn.setEnabled(False)
            
            # Включаем кнопку отмены
            self.cancel_btn.setVisible(True)
            self.cancel_btn.setEnabled(True)
            
            # Обрабатываем сразу интерфейс, чтобы показать индикатор загрузки
            QApplication.processEvents()
            
            # Создаем и запускаем поток для анализа файла
            self.analysis_thread = FileAnalysisWorker(path)
            self.analysis_thread.finished.connect(self.on_analysis_complete)
            self.analysis_thread.error.connect(self.on_analysis_error)
            self.analysis_thread.progress.connect(self.update_progress)
            self.analysis_thread.start()
        except Exception as e:
            logging.error(f"Ошибка при анализе файла: {str(e)}", exc_info=True)
            QMessageBox.critical(self, "Ошибка", f"Не удалось проанализировать файл: {user_friendly_error(str(e))}")
    
    def update_progress(self, current, total):
        """Обновляет прогресс-бар"""
        if total > 0:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(current)
            percent = int(current / total * 100)
            self.status_label.setText(f"Обработка... {percent}% ({current}/{total})")
        else:
            # Используем бесконечную анимацию, если total = 0
            self.progress_bar.setRange(0, 0)
    
    def on_analysis_complete(self, processes):
        try:
            # Сохраняем результаты
            self.blocking_processes = processes
            
            # Скрываем прогресс-бар и очищаем статус
            self.progress_bar.setVisible(False)
            self.status_label.setText("")
            
            # Скрываем кнопку отмены
            self.cancel_btn.setVisible(False)
            self.cancel_btn.setEnabled(False)
            
            # Активируем кнопку обновления
            self.refresh_btn.setEnabled(True)
            
            if not self.blocking_processes:
                self.process_table.setRowCount(1)
                self.process_table.setItem(0, 0, QTableWidgetItem("Файл/папка не заблокирован"))
                self.process_table.setItem(0, 1, QTableWidgetItem(""))
                self.process_table.setItem(0, 2, QTableWidgetItem(""))
                
                self.unlock_btn.setEnabled(False)
                self.unlock_delete_btn.setEnabled(True)  # Можно удалить без разблокировки
            else:
                # Добавляем процессы в таблицу
                self.process_table.setRowCount(len(self.blocking_processes))
                
                for i, process in enumerate(self.blocking_processes):
                    process_item = QTableWidgetItem(process["process_name"])
                    pid_item = QTableWidgetItem(str(process["pid"]))
                    type_item = QTableWidgetItem(process["handle_type"])
                    
                    # Настраиваем выравнивание и сортировку
                    pid_item.setTextAlignment(Qt.AlignCenter)
                    type_item.setTextAlignment(Qt.AlignCenter)
                    
                    # Добавляем всплывающие подсказки
                    process_item.setToolTip(f"Полный путь: {process.get('file_path', '')}")
                    
                    self.process_table.setItem(i, 0, process_item)
                    self.process_table.setItem(i, 1, pid_item)
                    self.process_table.setItem(i, 2, type_item)
                
                # Активируем кнопки
                self.unlock_btn.setEnabled(True)
                self.unlock_delete_btn.setEnabled(True)
        except Exception as e:
            logging.error(f"Ошибка при завершении анализа: {str(e)}", exc_info=True)
    
    def on_analysis_error(self, error_msg):
        try:
            # Скрываем прогресс-бар и очищаем статус
            self.progress_bar.setVisible(False)
            self.status_label.setText("")
            
            # Скрываем кнопку отмены
            self.cancel_btn.setVisible(False)
            self.cancel_btn.setEnabled(False)
            
            # Активируем кнопку обновления, если есть путь
            if self.current_path:
                self.refresh_btn.setEnabled(True)
            
            # Показываем ошибку пользователю
            QMessageBox.critical(self, "Ошибка", error_msg)
        except Exception as e:
            logging.error(f"Ошибка при обработке ошибки анализа: {str(e)}", exc_info=True)
    
    def unlock_file_action(self):
        try:
            if not self.current_path or not self.blocking_processes:
                return
            
            # Показываем прогресс-бар и статус
            self.progress_bar.setVisible(True)
            self.status_label.setText("Разблокировка файла...")
            
            # Отключаем кнопки на время операции
            self.unlock_btn.setEnabled(False)
            self.unlock_delete_btn.setEnabled(False)
            self.refresh_btn.setEnabled(False)
            
            # Включаем кнопку отмены
            self.cancel_btn.setVisible(True)
            self.cancel_btn.setEnabled(True)
            
            # Запускаем задачу разблокировки в отдельном потоке
            self.unlock_thread = UnlockWorker(self.current_path, self.blocking_processes)
            self.unlock_thread.finished.connect(self.on_unlock_complete)
            self.unlock_thread.progress.connect(self.update_progress)
            self.unlock_thread.start()
        except Exception as e:
            logging.error(f"Ошибка при разблокировке файла: {str(e)}", exc_info=True)
            QMessageBox.critical(self, "Ошибка", f"Не удалось начать разблокировку: {user_friendly_error(str(e))}")
    
    def on_unlock_complete(self, result):
        try:
            # Скрываем прогресс-бар и очищаем статус
            self.progress_bar.setVisible(False)
            self.status_label.setText("")
            
            # Скрываем кнопку отмены
            self.cancel_btn.setVisible(False)
            self.cancel_btn.setEnabled(False)
            
            # Активируем кнопку обновления
            self.refresh_btn.setEnabled(True)
            
            if "cancelled" in result:
                self.status_label.setText("Операция отменена")
                # Активируем кнопки снова
                if self.blocking_processes:
                    self.unlock_btn.setEnabled(True)
                    self.unlock_delete_btn.setEnabled(True)
                return
            
            if "error" in result:
                QMessageBox.critical(self, "Ошибка", f"Не удалось разблокировать: {result['error']}")
                
                # Активируем кнопки снова
                if self.blocking_processes:
                    self.unlock_btn.setEnabled(True)
                    self.unlock_delete_btn.setEnabled(True)
            else:
                if "message" in result:
                    QMessageBox.information(self, "Успех", result["message"])
                else:
                    QMessageBox.information(self, "Успех", "Файл/папка успешно разблокирован!")
                    
                self.check_file(self.current_path)  # Обновляем информацию
        except Exception as e:
            logging.error(f"Ошибка при завершении разблокировки: {str(e)}", exc_info=True)
    
    def unlock_and_delete_action(self):
        try:
            if not self.current_path:
                return
            
            # Запрашиваем подтверждение, если это настроено в параметрах
            if self.settings.settings.get("confirm_delete", True):
                reply = QMessageBox.question(
                    self,
                    "Подтверждение удаления",
                    f"Вы уверены, что хотите удалить '{os.path.basename(self.current_path)}'?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                
                if reply != QMessageBox.Yes:
                    return
            
            # Показываем прогресс-бар и статус
            self.progress_bar.setVisible(True)
            self.status_label.setText("Разблокировка и удаление...")
            
            # Включаем кнопку отмены
            self.cancel_btn.setVisible(True)
            self.cancel_btn.setEnabled(True)
            
            # Отключаем кнопки на время операции
            self.unlock_btn.setEnabled(False)
            self.unlock_delete_btn.setEnabled(False)
            self.refresh_btn.setEnabled(False)
            
            # Создаем рабочий объект, который будет выполнять операцию
            class UnlockDeleteWorker(QThread):
                finished = pyqtSignal(dict)
                progress = pyqtSignal(int, int)
                
                def __init__(self, path, processes):
                    super().__init__()
                    self.path = path
                    self.processes = processes
                    self._is_cancelled = False
                
                def cancel(self):
                    self._is_cancelled = True
                
                def run(self):
                    try:
                        if self._is_cancelled:
                            self.finished.emit({"cancelled": True})
                            return
                        
                        # Используем новую интегрированную функцию для разблокировки и удаления
                        from file_handler import unlock_and_delete_file
                        
                        # Периодически обновляем прогресс
                        self.progress.emit(0, 4)  # Начало процесса
                        time.sleep(0.5)
                        
                        if self._is_cancelled:
                            self.finished.emit({"cancelled": True})
                            return
                        
                        # Выполняем разблокировку и удаление как единый процесс
                        result = unlock_and_delete_file(self.path, self.processes)
                        
                        # Завершаем прогресс
                        self.progress.emit(4, 4)  # Конец процесса
                        
                        self.finished.emit(result)
                    except Exception as e:
                        logging.error(f"Ошибка в UnlockDeleteWorker: {str(e)}", exc_info=True)
                        self.finished.emit({"error": f"Ошибка при удалении: {str(e)}"})
            
            # Запускаем задачу в отдельном потоке
            self.unlock_delete_thread = UnlockDeleteWorker(self.current_path, self.blocking_processes)
            self.unlock_delete_thread.finished.connect(self.on_unlock_delete_complete)
            self.unlock_delete_thread.progress.connect(self.update_progress)
            self.unlock_delete_thread.start()
            
        except Exception as e:
            logging.error(f"Ошибка при разблокировке и удалении: {str(e)}", exc_info=True)
            QMessageBox.critical(self, "Ошибка", f"Не удалось начать разблокировку и удаление: {user_friendly_error(str(e))}")
    
    def on_unlock_delete_complete(self, result):
        try:
            # Скрываем прогресс-бар и очищаем статус
            self.progress_bar.setVisible(False)
            self.status_label.setText("")
            
            # Скрываем кнопку отмены
            self.cancel_btn.setVisible(False)
            self.cancel_btn.setEnabled(False)
            
            if "cancelled" in result:
                self.status_label.setText("Операция отменена")
                
                # Активируем кнопки снова
                if self.blocking_processes:
                    self.unlock_btn.setEnabled(True)
                self.unlock_delete_btn.setEnabled(True)
                self.refresh_btn.setEnabled(True)
                return
            
            if "error" in result:
                QMessageBox.critical(self, "Ошибка", result["error"])
                
                # Активируем кнопки снова и обновляем анализ
                self.check_file(self.current_path)
                return
            
            # Операция успешна
            success_message = result.get("message", f"Файл/папка {self.current_path} успешно удален!")
            QMessageBox.information(self, "Успех", success_message)
            
            # Сбрасываем состояние
            self.current_path = None
            self.blocking_processes = []
            self.path_label.setText("Перетащите файл или папку на это окно")
            
            # Очищаем таблицу
            self.process_table.setRowCount(0)
            
            # Деактивируем кнопки
            self.unlock_btn.setEnabled(False)
            self.unlock_delete_btn.setEnabled(False)
            self.refresh_btn.setEnabled(False)
        except Exception as e:
            logging.error(f"Ошибка при завершении разблокировки и удаления: {str(e)}", exc_info=True)
    
    def delete_file_action(self):
        """
        Удаляет файл или папку
        """
        try:
            self.status_label.setText("Удаление файла...")
            
            # Запускаем задачу удаления в отдельном потоке
            self.delete_thread = DeleteWorker(self.current_path)
            self.delete_thread.finished.connect(self.on_delete_complete)
            self.delete_thread.progress.connect(self.update_progress)
            self.delete_thread.start()
        except Exception as e:
            logging.error(f"Ошибка при удалении файла: {str(e)}", exc_info=True)
            QMessageBox.critical(self, "Ошибка", f"Не удалось начать удаление: {user_friendly_error(str(e))}")
    
    def on_delete_complete(self, result):
        try:
            # Скрываем прогресс-бар и очищаем статус
            self.progress_bar.setVisible(False)
            self.status_label.setText("")
            
            # Скрываем кнопку отмены
            self.cancel_btn.setVisible(False)
            self.cancel_btn.setEnabled(False)
            
            if "cancelled" in result:
                self.status_label.setText("Операция отменена")
                
                # Активируем кнопки снова
                if self.blocking_processes:
                    self.unlock_btn.setEnabled(True)
                self.unlock_delete_btn.setEnabled(True)
                self.refresh_btn.setEnabled(True)
                return
            
            if "error" in result:
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить: {result['error']}")
                
                # Активируем кнопки снова
                if self.blocking_processes:
                    self.unlock_btn.setEnabled(True)
                self.unlock_delete_btn.setEnabled(True)
                self.refresh_btn.setEnabled(True)
            else:
                QMessageBox.information(self, "Успех", f"Файл/папка {self.current_path} успешно удален!")
                
                # Сбрасываем состояние
                self.current_path = None
                self.blocking_processes = []
                self.path_label.setText("Перетащите файл или папку на это окно")
                
                # Очищаем таблицу
                self.process_table.setRowCount(0)
                
                # Деактивируем кнопки
                self.unlock_btn.setEnabled(False)
                self.unlock_delete_btn.setEnabled(False)
                self.refresh_btn.setEnabled(False)
        except Exception as e:
            logging.error(f"Ошибка при завершении удаления: {str(e)}", exc_info=True)
    
    def closeEvent(self, event):
        """Обрабатывает закрытие окна программы"""
        try:
            # Проверяем настройки для закрытия в трей
            close_to_tray = self.settings.settings.get("close_to_tray", True)
            show_notifications = self.settings.settings.get("show_tray_notifications", True)
            
            # Сворачиваем в трей, если это настроено или включены горячие клавиши/автозапуск
            if close_to_tray or self.settings.settings.get("hotkeys_enabled", False) or self.settings.settings.get("autostart", False):
                # Скрываем окно вместо закрытия программы
                event.ignore()
                self.hide()
                
                # Показываем уведомление в трее, если это настроено
                if hasattr(self, 'tray_icon') and self.tray_icon and self.tray_icon.isVisible() and show_notifications:
                    self.tray_icon.showMessage(
                        "JL Delete Lock",
                        "Программа продолжает работать в фоновом режиме. "
                        "Нажмите на иконку в трее для открытия программы.",
                        QSystemTrayIcon.Information,
                        2000
                    )
            else:
                # Если настроено закрытие программы вместо сворачивания в трей
                # Останавливаем отслеживание горячих клавиш
                if hasattr(self, 'hotkey_manager') and self.hotkey_manager and self.hotkey_manager_initialized:
                    try:
                        self.hotkey_manager.stop()
                    except Exception as e:
                        logging.error(f"Ошибка при остановке горячих клавиш: {str(e)}")
                
                # Закрываем программу
                event.accept()
        except Exception as e:
            logging.error(f"Ошибка при закрытии окна: {str(e)}", exc_info=True)
            # При ошибке всё равно принимаем событие закрытия
            event.accept()