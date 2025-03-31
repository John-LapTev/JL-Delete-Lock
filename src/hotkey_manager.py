import logging
import threading
import time
from PyQt5.QtCore import QObject, pyqtSignal

# Импортируем библиотеку keyboard для работы с горячими клавишами
try:
    import keyboard
except ImportError:
    # Добавим в requirements.txt
    logging.error("Библиотека keyboard не установлена. Выполните pip install keyboard")
    
class HotkeySignals(QObject):
    """Класс для испускания сигналов при нажатии горячих клавиш"""
    hotkey_pressed = pyqtSignal()

class HotkeyManager:
    """Класс для управления глобальными горячими клавишами"""
    def __init__(self, settings):
        self.settings = settings
        self.active = False
        self.registered_hotkey = None
        self.signals = HotkeySignals()
        self._last_trigger_time = 0
        self._lock = threading.Lock()
        
        # Словарь модификаторов для преобразования в формат библиотеки keyboard
        self.modifier_map = {
            "ALT": "alt",
            "CTRL": "ctrl",
            "SHIFT": "shift",
            "WIN": "windows"
        }
        
        # Словарь клавиш для преобразования в формат библиотеки keyboard
        self.key_map = {
            "DELETE": "delete",
            "F1": "f1",
            "F2": "f2",
            "F3": "f3",
            "F4": "f4",
            "F5": "f5",
            "F6": "f6",
            "F7": "f7",
            "F8": "f8",
            "F9": "f9",
            "F10": "f10",
            "F11": "f11",
            "F12": "f12",
            "A": "a",
            "B": "b",
            "D": "d",
            "L": "l",
            "O": "o",
            "P": "p",
            "R": "r",
            "S": "s",
            "U": "u",
            "Z": "z"
        }
        
        logging.info(f"Инициализация HotkeyManager")
        logging.info(f"Горячие клавиши включены: {self.settings.settings.get('hotkeys_enabled', False)}")
        logging.info(f"Настроенная комбинация: {self.settings.settings.get('hotkey_modifier', 'ALT')}+"
                    f"{self.settings.settings.get('hotkey_key', 'DELETE')}")
    
    def start(self):
        """Запускает отслеживание горячих клавиш"""
        if not self.settings.settings["hotkeys_enabled"]:
            logging.info("Горячие клавиши отключены в настройках")
            return False
        
        if self.active:
            logging.info("Отслеживание горячих клавиш уже запущено")
            return True
        
        try:
            # Сначала отключаем предыдущую регистрацию, если была
            if self.registered_hotkey:
                self.stop()
            
            # Получаем модификатор и клавишу из настроек
            modifier = self.settings.settings["hotkey_modifier"]
            key = self.settings.settings["hotkey_key"]
            
            # Преобразуем в формат библиотеки keyboard
            keyboard_modifier = self.modifier_map.get(modifier, "alt").lower()
            keyboard_key = self.key_map.get(key, "delete").lower()
            
            # Формируем строку горячей клавиши
            hotkey_string = f"{keyboard_modifier}+{keyboard_key}"
            
            # Регистрируем обработчик горячей клавиши
            keyboard.add_hotkey(hotkey_string, self._on_hotkey_triggered, suppress=False)
            
            self.registered_hotkey = hotkey_string
            self.active = True
            
            logging.info(f"Горячая клавиша {hotkey_string} успешно зарегистрирована")
            return True
        except Exception as e:
            logging.error(f"Ошибка при регистрации горячей клавиши: {str(e)}", exc_info=True)
            return False
    
    def stop(self):
        """Останавливает отслеживание горячих клавиш"""
        if not self.active:
            return
        
        try:
            if self.registered_hotkey:
                keyboard.remove_hotkey(self.registered_hotkey)
                logging.info(f"Горячая клавиша {self.registered_hotkey} отменена")
                self.registered_hotkey = None
        except Exception as e:
            logging.error(f"Ошибка при отмене горячей клавиши: {str(e)}", exc_info=True)
        
        self.active = False
    
    def _on_hotkey_triggered(self):
        """Вызывается при нажатии горячей клавиши"""
        with self._lock:
            # Предотвращаем двойные срабатывания
            current_time = time.time()
            if current_time - self._last_trigger_time < 0.5:  # 500 мс
                return
                
            self._last_trigger_time = current_time
            
        try:
            logging.info(f"Обнаружено нажатие горячей клавиши {self.registered_hotkey}")
            self.signals.hotkey_pressed.emit()
        except Exception as e:
            logging.error(f"Ошибка при обработке горячей клавиши: {str(e)}", exc_info=True)
    
    def get_current_hotkey_text(self):
        """Возвращает текстовое представление текущей горячей клавиши"""
        modifier = self.settings.settings["hotkey_modifier"]
        key = self.settings.settings["hotkey_key"]
        return f"{modifier}+{key}"
        
    def get_available_modifiers(self):
        """Возвращает список доступных модификаторов клавиш"""
        return list(self.modifier_map.keys())
        
    def get_available_keys(self):
        """Возвращает список доступных клавиш"""
        return list(self.key_map.keys())