import os
import sys
import json
import logging
import time
import threading
from datetime import datetime, timedelta
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import ssl

# Импортируем версию из файла version.py
try:
    from version import __version__
except ImportError:
    __version__ = "1.0.0"  # Значение по умолчанию, если не удалось импортировать

class UpdateChecker:
    """Класс для проверки наличия обновлений программы"""
    
    def __init__(self, settings, parent=None):
        self.settings = settings
        self.parent = parent
        # URL для вашего хостинга
        self.update_url = "https://jl-studio.art/my_apps/JL_Delete_Lock/updates.json"
        self.download_url = "https://jl-studio.art/my_apps/JL_Delete_Lock/downloads/"
        self.current_version = __version__
        self.latest_version = None
        self.update_info = None
        self.is_checking = False
        self.auto_check_enabled = self.settings.settings.get("auto_check_updates", True)
        self.check_interval_days = self.settings.settings.get("update_check_interval", 7)  # Проверять раз в неделю
        
    def should_check_for_updates(self):
        """Проверяет, нужно ли выполнять проверку обновлений"""
        if not self.auto_check_enabled:
            return False
            
        last_check = self.settings.settings.get("last_update_check")
        if not last_check:
            return True
            
        try:
            # Преобразуем строку даты в объект datetime
            last_check_date = datetime.strptime(last_check, "%Y-%m-%d %H:%M:%S")
            now = datetime.now()
            
            # Проверяем, прошло ли достаточно времени с момента последней проверки
            return (now - last_check_date) > timedelta(days=self.check_interval_days)
        except Exception as e:
            logging.warning(f"Ошибка при проверке даты последней проверки обновлений: {str(e)}")
            return True
    
    def check_for_updates_async(self, force=False, on_complete=None):
        """Запускает асинхронную проверку обновлений"""
        if self.is_checking:
            logging.info("Проверка обновлений уже выполняется")
            return
            
        if not force and not self.should_check_for_updates():
            logging.info("Пропуск проверки обновлений (выполнялась недавно)")
            return
        
        self.is_checking = True
        
        def check_thread():
            """Внутренняя функция для выполнения проверки в отдельном потоке"""
            result = self.check_for_updates()
            self.is_checking = False
            
            # Обновляем дату последней проверки
            self.settings.settings["last_update_check"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.settings.save_settings()
            
            # Вызываем callback-функцию с результатом проверки
            if on_complete:
                on_complete(result)
        
        thread = threading.Thread(target=check_thread)
        thread.daemon = True
        thread.start()
    
    def check_for_updates(self):
        """Проверяет наличие обновлений программы"""
        try:
            logging.info("Проверка наличия обновлений...")
            
            # Создаем заголовки запроса
            headers = {
                'User-Agent': f'JL_Delete_Lock/{self.current_version}',
                'Accept': 'application/json'
            }
            
            req = Request(self.update_url, headers=headers)
            
            # Используем стандартное SSL-соединение с проверкой сертификатов
            try:
                with urlopen(req, timeout=10) as response:
                    data = response.read().decode('utf-8')
                    update_data = json.loads(data)
                    
                    # Получаем информацию о последней версии
                    self.latest_version = update_data.get("latest_version")
                    self.update_info = update_data
                    
                    if self._is_newer_version(self.latest_version, self.current_version):
                        logging.info(f"Доступно обновление: {self.latest_version}")
                        return {
                            "update_available": True,
                            "current_version": self.current_version,
                            "latest_version": self.latest_version,
                            "release_notes": update_data.get("release_notes", ""),
                            "download_url": update_data.get("download_url", self.download_url)
                        }
                    else:
                        logging.info("Обновления не требуются")
                        return {
                            "update_available": False,
                            "current_version": self.current_version,
                            "latest_version": self.latest_version
                        }
            except Exception as ssl_error:
                logging.warning(f"Не удалось выполнить защищенное соединение: {str(ssl_error)}")
                # Только для совместимости со старыми системами, но с предупреждением в логе
                logging.warning("Выполняем запрос без проверки сертификата (небезопасно)")
                context = ssl._create_unverified_context()
                with urlopen(req, context=context, timeout=10) as response:
                    data = response.read().decode('utf-8')
                    update_data = json.loads(data)
                    
                    # Те же действия, что и выше
                    self.latest_version = update_data.get("latest_version")
                    self.update_info = update_data
                    
                    if self._is_newer_version(self.latest_version, self.current_version):
                        logging.info(f"Доступно обновление: {self.latest_version}")
                        return {
                            "update_available": True,
                            "current_version": self.current_version,
                            "latest_version": self.latest_version,
                            "release_notes": update_data.get("release_notes", ""),
                            "download_url": update_data.get("download_url", self.download_url)
                        }
                    else:
                        logging.info("Обновления не требуются")
                        return {
                            "update_available": False,
                            "current_version": self.current_version,
                            "latest_version": self.latest_version
                        }
                
        except HTTPError as e:
            logging.error(f"Ошибка HTTP при проверке обновлений: {e.code} {e.reason}")
            return {"error": f"Ошибка HTTP: {e.code} {e.reason}"}
        except URLError as e:
            logging.error(f"Ошибка URL при проверке обновлений: {str(e)}")
            return {"error": f"Ошибка соединения: {str(e)}"}
        except Exception as e:
            logging.error(f"Ошибка при проверке обновлений: {str(e)}")
            return {"error": f"Ошибка: {str(e)}"}
    
    def _is_newer_version(self, version1, version2):
        """Сравнивает версии и возвращает True, если version1 новее version2"""
        try:
            # Разбиваем версии на компоненты
            v1_parts = [int(x) for x in version1.split('.')]
            v2_parts = [int(x) for x in version2.split('.')]
            
            # Дополняем нулями, если длина разная
            while len(v1_parts) < len(v2_parts):
                v1_parts.append(0)
            while len(v2_parts) < len(v1_parts):
                v2_parts.append(0)
            
            # Сравниваем по компонентам
            for i in range(len(v1_parts)):
                if v1_parts[i] > v2_parts[i]:
                    return True
                elif v1_parts[i] < v2_parts[i]:
                    return False
            
            # Если все компоненты равны, версии одинаковые
            return False
        except Exception as e:
            logging.error(f"Ошибка при сравнении версий: {str(e)}")
            return False
    
    def download_update(self, download_url, on_complete=None):
        """Скачивает обновление с указанного URL"""
        # В данной реализации просто открываем URL в браузере по умолчанию
        try:
            import webbrowser
            webbrowser.open(download_url)
            logging.info(f"Открыт URL для скачивания обновления: {download_url}")
            
            if on_complete:
                on_complete(True)
                
            return True
        except Exception as e:
            logging.error(f"Ошибка при открытии URL: {str(e)}")
            
            if on_complete:
                on_complete(False)
                
            return False
    
    def toggle_auto_check(self, enabled):
        """Включает или выключает автоматическую проверку обновлений"""
        self.auto_check_enabled = enabled
        self.settings.settings["auto_check_updates"] = enabled
        self.settings.save_settings()
    
    def set_check_interval(self, days):
        """Устанавливает интервал проверки обновлений в днях"""
        self.check_interval_days = days
        self.settings.settings["update_check_interval"] = days
        self.settings.save_settings()


class UpdateDialog:
    """Класс для отображения диалога обновления программы"""
    
    def __init__(self, parent=None):
        """Инициализация класса"""
        self.parent = parent
        
    def show_update_available(self, update_info):
        """Показывает диалог о доступном обновлении"""
        from PyQt5.QtWidgets import QMessageBox, QDialog, QVBoxLayout, QLabel, QTextEdit, QPushButton
        from PyQt5.QtCore import Qt
        
        if self.parent:
            # Создаем диалог с информацией об обновлении
            dialog = QDialog(self.parent)
            dialog.setWindowTitle("Доступно обновление")
            dialog.setMinimumWidth(400)
            dialog.setMinimumHeight(300)
            
            layout = QVBoxLayout()
            
            # Заголовок
            header_label = QLabel(f"Доступно обновление программы JL Delete Lock")
            header_label.setStyleSheet("font-size: 14px; font-weight: bold;")
            layout.addWidget(header_label)
            
            # Информация о версиях
            version_label = QLabel(f"Текущая версия: {update_info['current_version']}\nНовая версия: {update_info['latest_version']}")
            layout.addWidget(version_label)
            
            # Информация о изменениях
            changes_label = QLabel("Список изменений:")
            layout.addWidget(changes_label)
            
            changes_text = QTextEdit()
            changes_text.setReadOnly(True)
            changes_text.setText(update_info.get('release_notes', 'Информация о изменениях недоступна.'))
            layout.addWidget(changes_text)
            
            # Кнопки
            button_layout = QVBoxLayout()
            
            download_button = QPushButton("Скачать обновление")
            download_button.clicked.connect(lambda: self._download_update(update_info.get('download_url')))
            button_layout.addWidget(download_button)
            
            remind_button = QPushButton("Напомнить позже")
            remind_button.clicked.connect(dialog.reject)
            button_layout.addWidget(remind_button)
            
            skip_button = QPushButton("Пропустить это обновление")
            skip_button.clicked.connect(lambda: self._skip_update(update_info['latest_version'], dialog))
            button_layout.addWidget(skip_button)
            
            layout.addLayout(button_layout)
            
            dialog.setLayout(layout)
            dialog.exec_()
        else:
            # Если родительское окно не указано, используем стандартный QMessageBox
            msg_box = QMessageBox()
            msg_box.setWindowTitle("Доступно обновление")
            msg_box.setText(f"Доступно обновление JL Delete Lock до версии {update_info['latest_version']}")
            msg_box.setInformativeText("Хотите перейти на страницу загрузки?")
            msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg_box.setDefaultButton(QMessageBox.Yes)
            
            if msg_box.exec_() == QMessageBox.Yes:
                self._download_update(update_info.get('download_url'))
    
    def show_check_error(self, error_info):
        """Показывает диалог об ошибке при проверке обновлений"""
        from PyQt5.QtWidgets import QMessageBox
        
        error_message = error_info.get("error", "Неизвестная ошибка")
        
        QMessageBox.warning(
            self.parent,
            "Ошибка проверки обновлений",
            f"Не удалось проверить наличие обновлений.\n\nПричина: {error_message}"
        )
    
    def show_no_updates(self):
        """Показывает диалог об отсутствии обновлений"""
        from PyQt5.QtWidgets import QMessageBox
        
        QMessageBox.information(
            self.parent,
            "Обновления не найдены",
            "У вас установлена последняя версия программы."
        )
    
    def _download_update(self, download_url):
        """Скачивает обновление"""
        import webbrowser
        webbrowser.open(download_url or "https://jl-studio.art/my_apps/JL_Delete_Lock/downloads/")
    
    def _skip_update(self, version, dialog):
        """Пропускает это обновление"""
        from PyQt5.QtWidgets import QMessageBox
        
        reply = QMessageBox.question(
            self.parent,
            "Пропустить обновление",
            f"Вы уверены, что хотите пропустить обновление до версии {version}?\n\n"
            "Программа не будет предлагать это обновление до выхода следующей версии.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Сохраняем информацию о пропущенной версии
            try:
                from PyQt5.QtCore import QSettings
                settings = QSettings("JL Software", "JL Delete Lock")
                settings.setValue("skipped_version", version)
                dialog.accept()
            except Exception as e:
                logging.error(f"Ошибка при сохранении информации о пропущенной версии: {str(e)}")
                QMessageBox.warning(
                    self.parent,
                    "Ошибка",
                    "Не удалось сохранить информацию о пропущенной версии."
                )