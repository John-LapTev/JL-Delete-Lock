import os
import sys
import logging
from datetime import datetime
import traceback

# Флаг для отслеживания состояния логирования
# Глобальная переменная, чтобы избежать рекурсии
_logging_setup_active = False

# Функция для настройки логирования
def setup_logging():
    """Настраивает логирование приложения с максимальной защитой от ошибок"""
    global _logging_setup_active
    
    # Защита от рекурсии
    if _logging_setup_active:
        return None
    
    _logging_setup_active = True
    
    try:
        # Получаем путь к папке с программой
        if getattr(sys, 'frozen', False):
            # Если программа запущена из exe
            application_path = os.path.dirname(sys.executable)
        else:
            # Если программа запущена из исходников
            application_path = os.path.dirname(os.path.abspath(__file__))
            # Если запущен напрямую из src, выходим на уровень выше
            if os.path.basename(application_path) == 'src':
                application_path = os.path.dirname(application_path)
        
        # Проверяем наличие флага портативной версии
        is_portable = os.path.exists(os.path.join(application_path, "portable.flag"))
        
        # Создаем директорию для логов в AppData (работает всегда)
        appdata_log_dir = os.path.join(os.path.expanduser("~"), "AppData", "Local", "JL_Delete_Lock", "logs")
        try:
            os.makedirs(appdata_log_dir, exist_ok=True)
        except Exception as e:
            print(f"Не удалось создать директорию для логов: {e}")
            return None
            
        # Создаем путь для файла лога
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        appdata_log_file = os.path.join(appdata_log_dir, f"jl_delete_lock_{current_time}.log")
        
        # Базовая настройка логирования с минимумом обработчиков
        try:
            # Используем только один файловый обработчик для надежности
            file_handler = logging.FileHandler(appdata_log_file, mode='a', encoding='utf-8')
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            
            # Настраиваем корневой логгер
            root_logger = logging.getLogger()
            root_logger.setLevel(logging.INFO)
            # Очищаем существующие обработчики, если есть
            for handler in root_logger.handlers[:]:
                root_logger.removeHandler(handler)
            # Добавляем только наш файловый обработчик
            root_logger.addHandler(file_handler)
            
            # Не перенаправляем стандартные потоки в портативной версии
            # Это избавит нас от циклических ошибок логирования
            
            # Записываем базовую информацию о запуске
            logging.info("=" * 80)
            logging.info("ЗАПУСК ПРИЛОЖЕНИЯ JL DELETE LOCK")
            logging.info(f"Версия: 1.0.0")
            logging.info(f"Время запуска: {current_time}")
            logging.info(f"Путь к программе: {application_path}")
            logging.info(f"Режим: {'Портативный' if is_portable else 'Установленный'}")
            logging.info(f"Путь к логу в AppData: {appdata_log_file}")
            logging.info("=" * 80)
            
            # Ручной сброс логов на диск
            file_handler.flush()
            
            # Возвращаем минимальную информацию
            return {
                "appdata_log": appdata_log_file,
                "is_portable": is_portable
            }
            
        except Exception as e:
            print(f"Ошибка настройки логирования: {e}")
            return None
    except Exception as e:
        # В случае ошибки, выводим сообщение в консоль
        print(f"Критическая ошибка настройки логирования: {e}")
        return None
    finally:
        _logging_setup_active = False

def resource_path(relative_path):
    """Получить абсолютный путь к ресурсу, работает для dev и для PyInstaller"""
    try:
        # PyInstaller создает временную папку и хранит путь в _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def get_handle_exe_path():
    """Находит путь к handle.exe, проверяя различные возможные местоположения"""
    # Список мест для поиска в порядке приоритета
    possible_handle_paths = [
        # В директории resources в упакованном приложении
        resource_path(os.path.join("resources", "handle64.exe")),
        resource_path(os.path.join("resources", "handle.exe")),
        resource_path(os.path.join("resources", "handle64a.exe")),
        # Рядом с exe-файлом
        os.path.join(os.path.dirname(sys.executable), "handle64.exe"),
        os.path.join(os.path.dirname(sys.executable), "handle.exe"),
        os.path.join(os.path.dirname(sys.executable), "handle64a.exe"),
        # В корневой директории
        "handle64.exe",
        "handle.exe",
        "handle64a.exe",
    ]
    
    # Ищем первый существующий файл
    for handle_path in possible_handle_paths:
        if os.path.exists(handle_path):
            print(f"Найдена утилита handle: {handle_path}")
            return handle_path
            
    print("ОШИБКА: Не найдена утилита handle.exe")
    return None

def main():
    # Настраиваем логирование с минимальной функциональностью
    log_info = setup_logging()
    
    try:
        # Записываем базовую системную информацию
        if log_info:
            logging.info(f"Версия Python: {sys.version}")
            logging.info(f"Операционная система: {sys.platform}")
            logging.info(f"Аргументы командной строки: {sys.argv}")
        
        logging.info("Запуск программы JL Delete Lock")
        
        # Определяем пути приложения
        if getattr(sys, 'frozen', False):
            # Если программа запущена из exe
            application_path = os.path.dirname(sys.executable)
            logging.info(f"Путь к исполняемому файлу: {application_path}")
            # Добавляем путь к exe в sys.path
            if application_path not in sys.path:
                sys.path.insert(0, application_path)
    
        # Импортируем локальные модули
        try:
            from file_handler import get_blocking_processes, unlock_file, delete_file, clear_cache
            from settings import Settings
            from hotkey_manager import HotkeyManager
            from settings_dialog import SettingsDialog
            from gui import MainWindow
        except ImportError as e:
            logging.error(f"Ошибка импорта модулей: {e}", exc_info=True)
            from PyQt5.QtWidgets import QApplication, QMessageBox
            app = QApplication(sys.argv)
            QMessageBox.critical(None, "Ошибка", f"Не удалось загрузить необходимые модули: {e}")
            return 1
        
        # Ищем утилиту handle в различных местах
        handle_path = get_handle_exe_path()
        if not handle_path:
            logging.error("Утилита handle.exe не найдена в известных местах")
            from PyQt5.QtWidgets import QApplication, QMessageBox
            app = QApplication(sys.argv)
            QMessageBox.critical(None, "Ошибка", "Утилита handle.exe не найдена в директории программы!")
            return 1
    
        # Создаем приложение
        from PyQt5.QtWidgets import QApplication
        from PyQt5.QtGui import QIcon
        app = QApplication(sys.argv)
        app.setStyle("Fusion")  # Более современный стиль
        app.setApplicationName("JL Delete Lock")
        app.setApplicationDisplayName("JL Delete Lock")
        
        # Устанавливаем обработчик исключений для Qt - упрощенный
        def qt_exception_handler(exc_type, exc_value, exc_traceback):
            logging.error("***** ИСКЛЮЧЕНИЕ В QT *****", exc_info=(exc_type, exc_value, exc_traceback))
            # Вызываем стандартный обработчик
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
        
        # Устанавливаем наш обработчик
        sys.excepthook = qt_exception_handler
        
        # Пытаемся загрузить иконку
        try:
            icon_path = resource_path(os.path.join("resources", "lock_file.ico"))
            if os.path.exists(icon_path):
                app.setWindowIcon(QIcon(icon_path))
                logging.info(f"Загружена иконка из {icon_path}")
            else:
                logging.warning(f"Иконка не найдена по пути {icon_path}")
        except Exception as e:
            logging.error(f"Ошибка при загрузке иконки: {str(e)}")
        
        try:
            window = MainWindow()
            logging.info("Создано главное окно приложения")
            
            # Если запущена с аргументом (перетаскивание на exe или из контекстного меню)
            if len(sys.argv) > 1:
                file_path = sys.argv[1]
                logging.info(f"Получен аргумент командной строки: {file_path}")
                window.check_file(file_path)
            
            window.show()
            logging.info("Запуск цикла событий приложения")
            
            # Запуск цикла событий Qt
            result = app.exec_()
            logging.info(f"Приложение завершило работу с кодом: {result}")
            return result
        except Exception as e:
            logging.error(f"Ошибка при запуске приложения: {str(e)}", exc_info=True)
            from PyQt5.QtWidgets import QApplication, QMessageBox
            app = QApplication(sys.argv)
            QMessageBox.critical(None, "Ошибка", f"Не удалось запустить приложение: {str(e)}")
            return 1
    except Exception as e:
        # В случае любой ошибки, просто выводим сообщение
        print(f"Критическая ошибка: {e}")
        print(traceback.format_exc())
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except Exception as e:
        # Финальная защита от необработанных исключений
        print(f"Фатальная ошибка в точке входа: {e}")
        traceback.print_exc()
        sys.exit(1)