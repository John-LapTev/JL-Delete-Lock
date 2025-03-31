import os
import json
import winreg
import sys
import ctypes
import logging
import shutil
from datetime import datetime

class Settings:
    def __init__(self):
        # Определяем директорию для хранения настроек
        self.app_data_dir = os.path.join(os.path.expanduser("~"), "AppData", "Local", "JL_Delete_Lock")
        self.settings_file = os.path.join(self.app_data_dir, "settings.json")
        self.backup_dir = os.path.join(self.app_data_dir, "backups")
        
        # Настройки по умолчанию
        self.default_settings = {
            "autostart": False,
            "hotkeys_enabled": True,
            "hotkey_key": "DELETE",
            "hotkey_modifier": "ALT",
            "context_menu_enabled": False,  # По умолчанию выключено для избежания ошибок доступа
            "close_to_tray": True,  # Новая опция: закрывать в трей вместо выхода
            "show_tray_notifications": True,  # Новая опция: показывать уведомления в трее
            "confirm_delete": True,  # Новая опция: запрашивать подтверждение при удалении
            "last_update_check": None  # Дата последней проверки обновлений
        }
        
        # Создаем директорию для настроек и бэкапов, если она не существует
        os.makedirs(self.app_data_dir, exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)
        
        # Загружаем настройки или создаем файл с настройками по умолчанию
        self.load_settings()
    
    def load_settings(self):
        """Загружает настройки из файла или создает настройки по умолчанию"""
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    self.settings = json.load(f)
                    
                # Дополняем настройки, если добавились новые параметры
                settings_updated = False
                for key, value in self.default_settings.items():
                    if key not in self.settings:
                        self.settings[key] = value
                        settings_updated = True
                
                # Если добавились новые параметры, сохраняем обновленные настройки
                if settings_updated:
                    self.save_settings()
                    
                logging.info("Настройки успешно загружены")
            except json.JSONDecodeError:
                logging.error(f"Ошибка в формате файла настроек: {self.settings_file}")
                self.backup_corrupted_settings()
                self.settings = self.default_settings.copy()
                self.save_settings()
            except Exception as e:
                logging.error(f"Ошибка при загрузке настроек: {str(e)}")
                self.backup_corrupted_settings()
                self.settings = self.default_settings.copy()
                self.save_settings()
        else:
            logging.info("Файл настроек не найден, создаем настройки по умолчанию")
            self.settings = self.default_settings.copy()
            self.save_settings()
    
    def backup_corrupted_settings(self):
        """Создает резервную копию поврежденного файла настроек"""
        if os.path.exists(self.settings_file):
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_file = os.path.join(self.backup_dir, f"settings_corrupted_{timestamp}.json")
                shutil.copy2(self.settings_file, backup_file)
                logging.info(f"Создана резервная копия поврежденного файла настроек: {backup_file}")
            except Exception as e:
                logging.error(f"Ошибка при создании резервной копии настроек: {str(e)}")
    
    def create_backup(self):
        """Создает резервную копию текущих настроек"""
        if os.path.exists(self.settings_file):
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_file = os.path.join(self.backup_dir, f"settings_backup_{timestamp}.json")
                shutil.copy2(self.settings_file, backup_file)
                
                # Удаляем старые резервные копии (оставляем только 5 последних)
                backup_files = [os.path.join(self.backup_dir, f) for f in os.listdir(self.backup_dir) 
                               if f.startswith("settings_backup_")]
                if len(backup_files) > 5:
                    backup_files.sort()
                    for old_backup in backup_files[:-5]:
                        os.remove(old_backup)
                        
                return True
            except Exception as e:
                logging.error(f"Ошибка при создании резервной копии настроек: {str(e)}")
                return False
        return False
    
    def save_settings(self):
        """Сохраняет настройки в файл"""
        try:
            # Создаем резервную копию текущих настроек перед сохранением
            if os.path.exists(self.settings_file):
                self.create_backup()
                
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4)
            logging.info("Настройки успешно сохранены")
            return True
        except Exception as e:
            logging.error(f"Ошибка при сохранении настроек: {str(e)}")
            return False
    
    def toggle_autostart(self, enable):
        """Включает или выключает автозапуск программы"""
        try:
            key = None
            try:
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Run",
                    0, winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE
                )
                
                app_path = self.get_app_path()
                
                if enable:
                    winreg.SetValueEx(key, "JL_Delete_Lock", 0, winreg.REG_SZ, f'"{app_path}"')
                    logging.info(f"Добавлен автозапуск в реестр: {app_path}")
                else:
                    try:
                        winreg.DeleteValue(key, "JL_Delete_Lock")
                        logging.info("Удален автозапуск из реестра")
                    except FileNotFoundError:
                        # Если ключа уже нет, это не ошибка
                        pass
                    except Exception as e:
                        logging.error(f"Ошибка при удалении ключа из реестра: {str(e)}")
                        return False
                
                self.settings["autostart"] = enable
                self.save_settings()
                return True
            finally:
                if key:
                    winreg.CloseKey(key)
        except Exception as e:
            logging.error(f"Ошибка при настройке автозапуска: {str(e)}")
            return False
    
    def toggle_context_menu(self, enable):
        """Включает или выключает интеграцию в контекстное меню"""
        if not self.is_admin() and enable and enable != self.settings["context_menu_enabled"]:
            logging.warning("Попытка изменить контекстное меню без прав администратора")
            self.settings["context_menu_enabled"] = False  # Сбрасываем настройку для безопасности
            return False
            
        try:
            app_path = self.get_app_path()
            
            # Регистрация для файлов
            result1 = self._set_context_menu_for_files(enable, app_path)
            
            # Регистрация для папок
            result2 = self._set_context_menu_for_folders(enable, app_path)
            
            if result1 and result2:
                self.settings["context_menu_enabled"] = enable
                self.save_settings()
                return True
                
            # Если не удалось, возвращаем предыдущее состояние
            self.settings["context_menu_enabled"] = not enable
            return False
        except Exception as e:
            logging.error(f"Ошибка при настройке контекстного меню: {str(e)}")
            return False
    
    def _set_context_menu_for_files(self, enable, app_path):
        """Настраивает контекстное меню для файлов"""
        try:
            if enable:
                # Создаем ключ для всех файлов
                key = None
                try:
                    key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, r"*\shell\JL_Delete_Lock")
                    winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "Проверить через JL Delete Lock")
                    winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, app_path)
                finally:
                    if key:
                        winreg.CloseKey(key)
                
                # Создаем ключ для команды
                key = None
                try:
                    key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, r"*\shell\JL_Delete_Lock\command")
                    winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f'"{app_path}" "%1"')
                finally:
                    if key:
                        winreg.CloseKey(key)
                        
                logging.info("Добавлено контекстное меню для файлов")
            else:
                # Удаляем ключи
                try:
                    winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, r"*\shell\JL_Delete_Lock\command")
                    winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, r"*\shell\JL_Delete_Lock")
                    logging.info("Удалено контекстное меню для файлов")
                except FileNotFoundError:
                    # Если ключа уже нет, это не ошибка
                    pass
                except Exception as e:
                    logging.error(f"Ошибка при удалении контекстного меню для файлов: {str(e)}")
                    return False
            return True
        except Exception as e:
            logging.error(f"Ошибка при настройке контекстного меню для файлов: {str(e)}")
            return False
    
    def _set_context_menu_for_folders(self, enable, app_path):
        """Настраивает контекстное меню для папок"""
        try:
            if enable:
                # Создаем ключ для папок
                key = None
                try:
                    key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, r"Directory\shell\JL_Delete_Lock")
                    winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "Проверить через JL Delete Lock")
                    winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, app_path)
                finally:
                    if key:
                        winreg.CloseKey(key)
                
                # Создаем ключ для команды
                key = None
                try:
                    key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, r"Directory\shell\JL_Delete_Lock\command")
                    winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f'"{app_path}" "%1"')
                finally:
                    if key:
                        winreg.CloseKey(key)
                        
                logging.info("Добавлено контекстное меню для папок")
            else:
                # Удаляем ключи
                try:
                    winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, r"Directory\shell\JL_Delete_Lock\command")
                    winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, r"Directory\shell\JL_Delete_Lock")
                    logging.info("Удалено контекстное меню для папок")
                except FileNotFoundError:
                    # Если ключа уже нет, это не ошибка
                    pass
                except Exception as e:
                    logging.error(f"Ошибка при удалении контекстного меню для папок: {str(e)}")
                    return False
            return True
        except Exception as e:
            logging.error(f"Ошибка при настройке контекстного меню для папок: {str(e)}")
            return False
    
    def get_app_path(self):
        """Получает путь к исполняемому файлу программы"""
        if getattr(sys, 'frozen', False):
            # Если программа запущена как .exe (PyInstaller)
            return sys.executable
        else:
            # Если программа запущена как скрипт Python
            return os.path.abspath(sys.argv[0])
    
    def is_admin(self):
        """Проверяет, запущена ли программа с правами администратора"""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception as e:
            logging.error(f"Ошибка при проверке прав администратора: {str(e)}")
            return False
    
    def run_as_admin(self):
        """Перезапускает программу с правами администратора"""
        if not self.is_admin():
            try:
                # Сначала сохраняем настройки
                self.save_settings()
                
                # Формируем параметры командной строки
                params = " ".join([f'"{arg}"' for arg in sys.argv[1:]])
                
                # Запускаем программу с правами администратора
                result = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
                
                # Результат больше 32 означает успешный запуск
                if result > 32:
                    logging.info("Программа успешно перезапущена с правами администратора")
                    return True
                else:
                    logging.error(f"Ошибка при перезапуске с правами администратора. Код: {result}")
                    return False
            except Exception as e:
                logging.error(f"Ошибка при запуске с правами администратора: {str(e)}")
                return False
        return False
    
    def restore_default_settings(self):
        """Восстанавливает настройки по умолчанию"""
        self.create_backup()  # Сохраняем текущие настройки
        self.settings = self.default_settings.copy()
        return self.save_settings()
    
    def get_all_backups(self):
        """Возвращает список всех резервных копий настроек"""
        if not os.path.exists(self.backup_dir):
            return []
            
        backups = []
        for file in os.listdir(self.backup_dir):
            if file.startswith("settings_backup_"):
                backup_path = os.path.join(self.backup_dir, file)
                backup_time = os.path.getmtime(backup_path)
                backups.append((file, backup_time))
                
        # Сортируем по времени (самые новые первыми)
        backups.sort(key=lambda x: x[1], reverse=True)
        return [b[0] for b in backups]
    
    def restore_from_backup(self, backup_filename):
        """Восстанавливает настройки из резервной копии"""
        backup_path = os.path.join(self.backup_dir, backup_filename)
        if not os.path.exists(backup_path):
            logging.error(f"Резервная копия не найдена: {backup_path}")
            return False
            
        try:
            # Создаем резервную копию текущих настроек
            self.create_backup()
            
            # Копируем резервную копию в файл настроек
            shutil.copy2(backup_path, self.settings_file)
            
            # Перезагружаем настройки
            self.load_settings()
            
            logging.info(f"Настройки успешно восстановлены из резервной копии: {backup_filename}")
            return True
        except Exception as e:
            logging.error(f"Ошибка при восстановлении из резервной копии: {str(e)}")
            return False