import logging
from PyQt5.QtWidgets import QMessageBox, QCheckBox

def check_admin_requirements(settings):
    """Проверяет, требуются ли права администратора для текущих настроек
    
    Args:
        settings: Объект настроек программы
        
    Returns:
        list: Список функций, требующих права администратора
    """
    # Список настроек, требующих прав администратора
    admin_settings = []
    
    # Проверяем, включено ли контекстное меню
    if settings.settings.get("context_menu_enabled", False):
        admin_settings.append("Интеграция с контекстным меню Windows")
    
    # Проверяем другие функции, требующие прав администратора
    if settings.settings.get("check_system_files", False):
        admin_settings.append("Доступ к системным файлам")
    
    if settings.settings.get("check_system_processes", False):
        admin_settings.append("Управление системными процессами")
    
    return admin_settings

def show_admin_requirements_dialog(parent, required_features):
    """Показывает диалог с информацией о требуемых правах администратора
    
    Args:
        parent: Родительское окно для диалога
        required_features: Список функций, требующих права администратора
        
    Returns:
        bool: True, если пользователь выбрал перезапуск с правами администратора
    """
    if not required_features:
        return False
    
    # Создаем сообщение
    message = "Для работы следующих функций требуются права администратора:\n\n"
    for feature in required_features:
        message += f"• {feature}\n"
    
    message += "\nХотите перезапустить программу с правами администратора?"
    
    # Создаем диалог с чекбоксом "Больше не спрашивать"
    msg_box = QMessageBox(parent)
    msg_box.setWindowTitle("Требуются права администратора")
    msg_box.setText(message)
    msg_box.setIcon(QMessageBox.Question)
    
    # Добавляем кнопки
    yes_button = msg_box.addButton("Да", QMessageBox.YesRole)
    no_button = msg_box.addButton("Нет", QMessageBox.NoRole)
    
    # Добавляем чекбокс "Больше не спрашивать"
    dont_ask_checkbox = QCheckBox("Больше не спрашивать")
    msg_box.setCheckBox(dont_ask_checkbox)
    
    # Показываем диалог
    msg_box.exec_()
    
    # Обрабатываем результат
    clicked_button = msg_box.clickedButton()
    dont_ask = dont_ask_checkbox.isChecked()
    
    # Сохраняем настройку "Больше не спрашивать"
    if dont_ask:
        parent.settings.settings["dont_ask_for_admin"] = True
        parent.settings.save_settings()
    
    # Возвращаем True, если пользователь выбрал "Да"
    return clicked_button == yes_button