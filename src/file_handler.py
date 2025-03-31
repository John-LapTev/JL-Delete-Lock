import subprocess
import os
import re
import sys
import logging
import time
import ctypes
import shutil
import locale
from pathlib import Path

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
            logging.info(f"Найдена утилита handle: {handle_path}")
            return handle_path
            
    logging.error("Не найдена утилита handle.exe")
    return None

def get_blocking_processes(path, progress_callback=None):
    """
    Использует утилиту handle для определения процессов, блокирующих файл или папку
    """
    if not path or not os.path.exists(path):
        logging.error(f"Путь не существует: {path}")
        return {"error": f"Путь не существует: {path}"}
    
    path = os.path.abspath(path)
    logging.info(f"Проверка блокировок для: {path}")
    
    # Находим handle.exe
    handle_exe = get_handle_exe_path()
    if not handle_exe:
        logging.error("Не найдена утилита handle.exe")
        return {"error": "Не найдена утилита handle.exe. Убедитесь, что она находится в директории программы или в папке resources."}
    
    # Если это папка, проверяем размер директории
    if os.path.isdir(path):
        # Подсчитываем файлы для определения необходимости прогресса
        file_count = 0
        for root, _, files in os.walk(path):
            file_count += len(files)
            # Если более 100 файлов, предупреждаем о возможной длительности
            if file_count > 100:
                logging.info(f"Крупная директория: {path}, содержит более 100 файлов")
                break
        
        # Для крупных директорий используем оптимизированный метод
        if file_count > 100:
            return check_large_directory(path, handle_exe, progress_callback)
    
    # Сначала попробуем использовать встроенное API Windows для проверки
    if os.path.isfile(path):
        is_locked = check_file_locked_windows_api(path)
        if is_locked:
            logging.info(f"Файл заблокирован (проверка через Windows API): {path}")
    
    # Запускаем утилиту handle и получаем вывод
    try:
        # Подготовка пути к файлу для использования в командной строке
        # Обработка имен с пробелами и кириллицей
        search_path = path
        
        # Определяем текущую кодировку системы
        system_encoding = locale.getpreferredencoding()
        
        # Сначала попробуем запустить с auto-accept EULA
        result = subprocess.run([handle_exe, "-accepteula", "-nobanner", search_path], 
                            capture_output=True, 
                            text=False,  # Получаем байты вместо текста для корректной обработки кодировки
                            creationflags=subprocess.CREATE_NO_WINDOW)
        
        # Пробуем разные кодировки для декодирования вывода
        for encoding in [system_encoding, 'utf-8', 'cp1251', 'cp866', 'latin-1']:
            try:
                output = result.stdout.decode(encoding)
                error_output = result.stderr.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            # Если ни одна кодировка не сработала, используем latin-1 (всегда работает, даже если с искажениями)
            output = result.stdout.decode('latin-1')
            error_output = result.stderr.decode('latin-1')
        
        # Логируем вывод для отладки
        logging.debug(f"Вывод handle.exe: {output}")
        if error_output:
            logging.debug(f"Ошибки handle.exe: {error_output}")
        
        # Проверяем на ошибки
        if result.returncode != 0 and "No matching handles found" not in output:
            if "EULA" in error_output or "EULA" in output:
                # Если проблема с EULA, пробуем еще раз с флагом -accepteula
                logging.warning("Обнаружена проблема с EULA, повторный запуск с -accepteula")
                result = subprocess.run([handle_exe, "-accepteula", "-nobanner", search_path], 
                                    capture_output=True, 
                                    text=False,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
                
                # Декодируем с учетом разных кодировок
                for encoding in [system_encoding, 'utf-8', 'cp1251', 'cp866', 'latin-1']:
                    try:
                        output = result.stdout.decode(encoding)
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    output = result.stdout.decode('latin-1')
            else:
                logging.error(f"Ошибка выполнения handle.exe: {error_output}")
                return {"error": f"Ошибка выполнения handle.exe: {error_output}"}
        
        # Если нет результатов и это файл, пробуем использовать только имя файла
        if "No matching handles found" in output and os.path.isfile(path):
            basename = os.path.basename(path)
            logging.info(f"Не найдены блокировки по полному пути, пробуем по имени файла: {basename}")
            result = subprocess.run([handle_exe, "-accepteula", "-nobanner", basename], 
                                   capture_output=True, 
                                   text=False,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
            
            # Декодируем с учетом разных кодировок
            for encoding in [system_encoding, 'utf-8', 'cp1251', 'cp866', 'latin-1']:
                try:
                    output = result.stdout.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                output = result.stdout.decode('latin-1')
        
        # Если это папка и не найдены блокировки, проверяем все файлы в ней
        if os.path.isdir(path) and "No matching handles found" in output:
            logging.info(f"Проверка всех файлов в папке: {path}")
            return check_directory_files(path, handle_exe, progress_callback)
            
    except Exception as e:
        logging.error(f"Ошибка при выполнении handle.exe: {str(e)}")
        return {"error": f"Не удалось выполнить проверку: {str(e)}"}
    
    # Парсим вывод handle
    blocking_processes = []
    
    # Проходим по каждой строке вывода handle.exe
    for line in output.splitlines():
        # Ищем строку, которая содержит "pid:" и "type: File"
        if "pid:" in line and "type:" in line and "File" in line:
            try:
                # Разделяем строку на части, чтобы извлечь имя процесса и pid
                parts = line.split("pid:")
                if len(parts) < 2:
                    continue
                
                process_name = parts[0].strip()
                
                # Находим pid между "pid:" и "type:"
                pid_parts = parts[1].split("type:")
                if len(pid_parts) < 2:
                    continue
                
                pid_str = pid_parts[0].strip()
                try:
                    pid = int(pid_str)
                except ValueError:
                    continue
                
                # Извлекаем тип (должен быть "File")
                handle_type = "File"  # Мы уже проверили, что строка содержит "File"
                
                # Пытаемся найти путь к файлу
                colon_index = parts[1].find(":", parts[1].find("type:"))
                if colon_index != -1:
                    file_path = parts[1][colon_index + 1:].strip()
                else:
                    # Если не удалось извлечь путь, используем исходный путь
                    file_path = path
                
                # Добавляем найденный процесс в список
                if pid > 0:  # Проверяем, что pid больше 0
                    blocking_processes.append({
                        "process_name": process_name,
                        "pid": pid,
                        "handle_type": handle_type,
                        "file_path": file_path
                    })
            except Exception as e:
                logging.error(f"Ошибка при парсинге строки handle: {line}, ошибка: {str(e)}")
                # Продолжаем со следующей строкой, если произошла ошибка
                continue
    
    # Логируем результаты
    if blocking_processes:
        logging.info(f"Найдено {len(blocking_processes)} блокирующих процессов")
        for proc in blocking_processes:
            logging.debug(f"Блокирующий процесс: {proc['process_name']} (PID: {proc['pid']})")
    else:
        logging.info("Блокирующие процессы не найдены")
        
        # Дополнительная проверка файлов через Windows API
        if os.path.isfile(path) and check_file_locked_windows_api(path):
            logging.warning(f"Файл заблокирован, но handle.exe не определил блокирующие процессы: {path}")
            # Возвращаем универсальный процесс-заглушку для Explorer
            return [{
                "process_name": "explorer.exe (предположительно)",
                "pid": 0,  # Фиктивный PID
                "handle_type": "File",
                "file_path": path
            }]
    
    return blocking_processes

def check_large_directory(directory_path, handle_exe, progress_callback=None):
    """Оптимизированная проверка большой директории - сначала ищем заблокированные файлы"""
    logging.info(f"Оптимизированная проверка большой директории: {directory_path}")
    
    # Собираем все файлы
    all_files = []
    for root, _, files in os.walk(directory_path):
        for file in files:
            all_files.append(os.path.join(root, file))
    
    total_files = len(all_files)
    logging.info(f"Общее количество файлов в директории: {total_files}")
    
    # Определяем максимальное количество файлов для проверки
    max_files_to_check = min(100, total_files)  # Не более 100 файлов для проверки
    
    # Выбираем случайные файлы для проверки
    import random
    files_to_check = random.sample(all_files, max_files_to_check) if total_files > max_files_to_check else all_files
    
    # Сначала пробуем определить, есть ли заблокированные файлы через Windows API
    locked_files = []
    for i, file_path in enumerate(files_to_check):
        # Проверяем, не отменена ли операция
        if progress_callback and not progress_callback(i, len(files_to_check)):
            return {"error": "Операция отменена пользователем"}
            
        try:
            if check_file_locked_windows_api(file_path):
                locked_files.append(file_path)
                # Если нашли блокировку, не проверяем все файлы
                if len(locked_files) >= 5:  # Ограничиваем количество поиска для скорости
                    break
        except Exception as e:
            logging.debug(f"Ошибка при проверке файла {file_path}: {str(e)}")
    
    # Если не нашли заблокированных файлов, пробуем проверить саму директорию
    if not locked_files:
        try:
            # Определяем текущую кодировку системы
            system_encoding = locale.getpreferredencoding()
            
            # Проверяем директорию с помощью handle.exe
            result = subprocess.run([handle_exe, "-accepteula", "-nobanner", directory_path], 
                                capture_output=True, 
                                text=False,
                                creationflags=subprocess.CREATE_NO_WINDOW)
            
            # Декодируем вывод
            for encoding in [system_encoding, 'utf-8', 'cp1251', 'cp866', 'latin-1']:
                try:
                    output = result.stdout.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                output = result.stdout.decode('latin-1')
            
            # Если нашли что-то, парсим и возвращаем результаты
            if "No matching handles found" not in output:
                # Проходим по каждой строке вывода handle.exe
                blocking_processes = []
                for line in output.splitlines():
                    # Ищем строку, которая содержит "pid:" и "type: File"
                    if "pid:" in line and "type:" in line and "File" in line:
                        try:
                            # Разделяем строку на части, чтобы извлечь имя процесса и pid
                            parts = line.split("pid:")
                            if len(parts) < 2:
                                continue
                            
                            process_name = parts[0].strip()
                            
                            # Находим pid между "pid:" и "type:"
                            pid_parts = parts[1].split("type:")
                            if len(pid_parts) < 2:
                                continue
                            
                            pid_str = pid_parts[0].strip()
                            try:
                                pid = int(pid_str)
                            except ValueError:
                                continue
                            
                            # Извлекаем тип (должен быть "File")
                            handle_type = "File"  # Мы уже проверили, что строка содержит "File"
                            
                            # Пытаемся найти путь к файлу
                            colon_index = parts[1].find(":", parts[1].find("type:"))
                            if colon_index != -1:
                                file_path = parts[1][colon_index + 1:].strip()
                            else:
                                # Если не удалось извлечь путь, используем исходный путь
                                file_path = directory_path
                            
                            # Добавляем найденный процесс в список
                            blocking_processes.append({
                                "process_name": process_name,
                                "pid": pid,
                                "handle_type": handle_type,
                                "file_path": file_path
                            })
                        except Exception as e:
                            logging.error(f"Ошибка при парсинге строки handle: {line}, ошибка: {str(e)}")
                            continue
                
                if blocking_processes:
                    logging.info(f"Найдено {len(blocking_processes)} блокирующих процессов для директории")
                    return blocking_processes
        except Exception as e:
            logging.error(f"Ошибка при проверке директории {directory_path}: {str(e)}")
    
    # Теперь проверяем найденные заблокированные файлы
    blocking_processes = []
    
    for i, file_path in enumerate(locked_files):
        # Проверяем, не отменена ли операция
        if progress_callback and not progress_callback(i, len(locked_files)):
            return {"error": "Операция отменена пользователем"}
            
        try:
            # Определяем текущую кодировку системы
            system_encoding = locale.getpreferredencoding()
            
            # Проверяем файл с помощью handle.exe
            result = subprocess.run([handle_exe, "-accepteula", "-nobanner", file_path], 
                                capture_output=True, 
                                text=False,
                                creationflags=subprocess.CREATE_NO_WINDOW)
            
            # Декодируем вывод
            for encoding in [system_encoding, 'utf-8', 'cp1251', 'cp866', 'latin-1']:
                try:
                    output = result.stdout.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                output = result.stdout.decode('latin-1')
            
            # Проходим по каждой строке вывода handle.exe
            for line in output.splitlines():
                # Ищем строку, которая содержит "pid:" и "type: File"
                if "pid:" in line and "type:" in line and "File" in line:
                    try:
                        # Разделяем строку на части, чтобы извлечь имя процесса и pid
                        parts = line.split("pid:")
                        if len(parts) < 2:
                            continue
                        
                        process_name = parts[0].strip()
                        
                        # Находим pid между "pid:" и "type:"
                        pid_parts = parts[1].split("type:")
                        if len(pid_parts) < 2:
                            continue
                        
                        pid_str = pid_parts[0].strip()
                        try:
                            pid = int(pid_str)
                        except ValueError:
                            continue
                        
                        # Извлекаем тип (должен быть "File")
                        handle_type = "File"  # Мы уже проверили, что строка содержит "File"
                        
                        # Пытаемся найти путь к файлу
                        colon_index = parts[1].find(":", parts[1].find("type:"))
                        if colon_index != -1:
                            found_path = parts[1][colon_index + 1:].strip()
                        else:
                            # Если не удалось извлечь путь, используем текущий файл
                            found_path = file_path
                        
                        # Добавляем найденный процесс в список, если такого процесса еще нет
                        if not any(p["pid"] == pid and p["process_name"] == process_name for p in blocking_processes):
                            blocking_processes.append({
                                "process_name": process_name,
                                "pid": pid,
                                "handle_type": handle_type,
                                "file_path": found_path
                            })
                    except Exception as e:
                        logging.error(f"Ошибка при парсинге строки handle: {line}, ошибка: {str(e)}")
                        continue
        except Exception as e:
            logging.error(f"Ошибка при проверке файла {file_path}: {str(e)}")
    
    # Если handle.exe не нашел процессы, но файлы заблокированы
    if locked_files and not blocking_processes:
        logging.warning(f"Найдены заблокированные файлы, но handle.exe не определил процессы")
        # Возвращаем универсальный процесс-заглушку для Explorer
        return [{
            "process_name": "explorer.exe (предположительно)",
            "pid": 0,  # Фиктивный PID
            "handle_type": "File",
            "file_path": locked_files[0]  # Используем первый заблокированный файл
        }]
    
    return blocking_processes

def check_directory_files(directory_path, handle_exe, progress_callback=None):
    """Проверяет все файлы в директории на блокировки"""
    blocking_processes = []
    
    try:
        # Собираем все файлы
        files_to_check = []
        for root, dirs, files in os.walk(directory_path):
            for file in files:
                files_to_check.append(os.path.join(root, file))
        
        total_files = len(files_to_check)
        processed = 0
        
        for file_path in files_to_check:
            # Обновляем прогресс
            if progress_callback:
                if not progress_callback(processed, total_files):
                    return {"error": "Операция отменена пользователем"}
            
            processed += 1
            
            # Проверяем каждый файл с помощью Windows API
            if check_file_locked_windows_api(file_path):
                logging.info(f"Файл в директории заблокирован: {file_path}")
                
                # Проверяем его с помощью handle.exe
                try:
                    # Определяем текущую кодировку системы
                    system_encoding = locale.getpreferredencoding()
                    
                    result = subprocess.run([handle_exe, "-accepteula", "-nobanner", file_path], 
                                        capture_output=True, 
                                        text=False,
                                        creationflags=subprocess.CREATE_NO_WINDOW)
                    
                    # Декодируем с учетом разных кодировок
                    for encoding in [system_encoding, 'utf-8', 'cp1251', 'cp866', 'latin-1']:
                        try:
                            output = result.stdout.decode(encoding)
                            break
                        except UnicodeDecodeError:
                            continue
                    else:
                        output = result.stdout.decode('latin-1')
                    
                    # Проходим по каждой строке вывода handle.exe
                    for line in output.splitlines():
                        # Ищем строку, которая содержит "pid:" и "type: File"
                        if "pid:" in line and "type:" in line and "File" in line:
                            try:
                                # Разделяем строку на части, чтобы извлечь имя процесса и pid
                                parts = line.split("pid:")
                                if len(parts) < 2:
                                    continue
                                
                                process_name = parts[0].strip()
                                
                                # Находим pid между "pid:" и "type:"
                                pid_parts = parts[1].split("type:")
                                if len(pid_parts) < 2:
                                    continue
                                
                                pid_str = pid_parts[0].strip()
                                try:
                                    pid = int(pid_str)
                                except ValueError:
                                    continue
                                
                                # Извлекаем тип (должен быть "File")
                                handle_type = "File"  # Мы уже проверили, что строка содержит "File"
                                
                                # Пытаемся найти путь к файлу
                                colon_index = parts[1].find(":", parts[1].find("type:"))
                                if colon_index != -1:
                                    found_path = parts[1][colon_index + 1:].strip()
                                else:
                                    # Если не удалось извлечь путь, используем текущий файл
                                    found_path = file_path
                                
                                # Добавляем найденный процесс в список
                                blocking_processes.append({
                                    "process_name": process_name,
                                    "pid": pid,
                                    "handle_type": handle_type,
                                    "file_path": found_path
                                })
                            except Exception as e:
                                logging.error(f"Ошибка при парсинге строки handle: {line}, ошибка: {str(e)}")
                                continue
                except Exception as e:
                    logging.error(f"Ошибка при проверке файла {file_path}: {str(e)}")
                    
                # Если handle.exe не нашел процессы, но файл заблокирован
                if check_file_locked_windows_api(file_path) and not any(p["file_path"].lower() == file_path.lower() for p in blocking_processes):
                    logging.warning(f"Файл заблокирован, но handle.exe не определил процесс: {file_path}")
                    blocking_processes.append({
                        "process_name": "explorer.exe (предположительно)",
                        "pid": 0,  # Фиктивный PID
                        "handle_type": "File",
                        "file_path": file_path
                    })
    except Exception as e:
        logging.error(f"Ошибка при сканировании файлов в директории: {str(e)}")
    
    return blocking_processes

def check_file_locked_windows_api(file_path):
    """Проверяет, заблокирован ли файл, с помощью Windows API"""
    try:
        # Сначала пробуем открыть файл только для чтения
        try:
            with open(file_path, "rb") as f:
                pass
            # Если удалось открыть для чтения, проверяем запись
            try:
                with open(file_path, "ab") as f:
                    pass
                return False  # Если удалось открыть для чтения и записи, файл не заблокирован
            except IOError:
                # Файл заблокирован для записи, но доступен для чтения
                return True
        except IOError:
            # Файл заблокирован даже для чтения
            return True
    except Exception as e:
        logging.debug(f"Ошибка при проверке блокировки файла {file_path}: {str(e)}")
        return True  # В случае любой ошибки считаем файл заблокированным

def is_system_critical_process(process_name, pid):
    """Проверяет, является ли процесс критически важным для системы"""
    # Список критических системных процессов, которые не следует убивать
    critical_processes = [
        "System", "smss.exe", "csrss.exe", "wininit.exe", "winlogon.exe", 
        "services.exe", "lsass.exe", "svchost.exe", "dwm.exe", "explorer.exe"
    ]
    
    # Если процесс в списке критических, проверяем дополнительные условия
    if process_name.lower() in [p.lower() for p in critical_processes]:
        # Для explorer.exe и svchost.exe разрешаем завершение только если они не первичные экземпляры
        if process_name.lower() == "explorer.exe" or process_name.lower() == "svchost.exe":
            try:
                # Получаем количество запущенных экземпляров этого процесса
                import subprocess
                result = subprocess.run(
                    ["tasklist", "/fi", f"imagename eq {process_name}", "/fo", "csv"], 
                    capture_output=True, text=True
                )
                # Подсчитываем количество экземпляров (строк минус заголовок)
                count = len(result.stdout.strip().split('\n')) - 1
                # Если больше одного экземпляра, можно завершить
                return count <= 1
            except:
                # В случае ошибки считаем процесс критическим
                return True
        # Для других процессов из списка - всегда критично
        return True
    
    # Не в списке критических процессов
    return False

def is_process_running(pid):
    """Проверяет, запущен ли процесс с указанным PID"""
    try:
        process = subprocess.run(
            ["tasklist", "/fi", f"pid eq {pid}", "/fo", "csv"], 
            capture_output=True, 
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        # Если PID найден, в выводе будет строка с PID
        return str(pid) in process.stdout
    except Exception as e:
        logging.error(f"Ошибка при проверке процесса {pid}: {str(e)}")
        # В случае ошибки предполагаем, что процесс запущен
        return True

def unlock_file(path, processes):
    """
    Разблокирует файл, закрывая указанные процессы
    """
    if not processes:
        logging.info(f"Нет процессов для завершения при разблокировке {path}")
        return {"success": True, "message": "Нет процессов для завершения"}
    
    failed_processes = []
    successful_processes = []
    skipped_processes = []
    
    for process in processes:
        pid = process["pid"]
        try:
            # Пропускаем фиктивные процессы с PID=0
            if pid == 0:
                logging.info(f"Пропуск фиктивного процесса: {process['process_name']}")
                # Пытаемся разблокировать файл альтернативным способом
                try_alternative_unlock(process["file_path"])
                continue
            
            # Проверяем, запущен ли процесс с указанным PID
            if not is_process_running(pid):
                logging.info(f"Процесс {process['process_name']} (PID: {pid}) уже не запущен")
                successful_processes.append(f"{process['process_name']} (PID: {pid}) [уже не запущен]")
                continue
                
            # Проверка на критичный системный процесс
            if is_system_critical_process(process['process_name'], pid):
                logging.warning(f"Пропуск критического системного процесса: {process['process_name']} (PID: {pid})")
                skipped_processes.append(f"{process['process_name']} (PID: {pid}) - критический процесс")
                # Пытаемся разблокировать файл альтернативным способом
                if try_alternative_unlock(process.get("file_path", "")):
                    logging.info(f"Файл успешно разблокирован альтернативным способом: {process['file_path']}")
                continue
                
            logging.info(f"Попытка завершения процесса {process['process_name']} (PID: {pid})")
            
            # Используем taskkill для завершения процесса
            result = subprocess.run(["taskkill", "/F", "/PID", str(pid)], 
                          capture_output=True, 
                          text=True,
                          creationflags=subprocess.CREATE_NO_WINDOW)
            
            if result.returncode != 0:
                error_msg = result.stderr.strip() or "Неизвестная ошибка"
                logging.error(f"Не удалось завершить процесс {pid}: {error_msg}")
                failed_processes.append(f"{process['process_name']} (PID: {pid})")
                
                # Если не удалось завершить процесс, пробуем альтернативный метод разблокировки
                if os.path.isfile(process.get("file_path", "")):
                    if try_alternative_unlock(process["file_path"]):
                        logging.info(f"Файл успешно разблокирован альтернативным способом: {process['file_path']}")
                        successful_processes.append(f"{process['process_name']} (PID: {pid}) [альтернативный метод]")
            else:
                logging.info(f"Процесс {process['process_name']} (PID: {pid}) успешно завершен")
                successful_processes.append(f"{process['process_name']} (PID: {pid})")
        except Exception as e:
            logging.error(f"Исключение при завершении процесса {pid}: {str(e)}")
            failed_processes.append(f"{process['process_name']} (PID: {pid})")
    
    # Формируем сообщение о результатах
    if skipped_processes:
        skipped_message = f"Пропущены критические процессы: {', '.join(skipped_processes)}"
        logging.warning(skipped_message)
    
    if failed_processes:
        error_message = f"Не удалось завершить следующие процессы: {', '.join(failed_processes)}"
        logging.error(error_message)
        
        if successful_processes:
            error_message += f"\nУспешно завершены: {', '.join(successful_processes)}"
        
        if skipped_processes:
            error_message += f"\n{skipped_message}"
            
        return {"error": error_message}
    
    success_message = f"Успешно завершено {len(successful_processes)} процессов"
    if skipped_processes:
        success_message += f"\n{skipped_message}"
    
    return {"success": True, "message": success_message}

def try_alternative_unlock(file_path):
    """Пытается разблокировать файл альтернативными методами"""
    if not file_path or not os.path.exists(file_path):
        return False
        
    try:
        # Метод 1: Попытка копирования файла и замены оригинала
        temp_file = file_path + ".temp"
        
        try:
            # Копируем файл с чтением и записью в двоичном режиме
            with open(file_path, "rb") as src:
                with open(temp_file, "wb") as dst:
                    dst.write(src.read())
                    
            # Пытаемся удалить оригинальный файл
            os.remove(file_path)
            
            # Переименовываем временный файл обратно
            os.rename(temp_file, file_path)
            
            return True
        except:
            # Если не удалось, удаляем временный файл если он был создан
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
            
            # Метод 2: Используем атрибуты файла для временного переименования
            try:
                path_obj = Path(file_path)
                new_name = path_obj.parent / (path_obj.stem + "_unlocked" + path_obj.suffix)
                
                os.rename(file_path, new_name)
                time.sleep(0.5)  # Даем системе время на обработку
                os.rename(new_name, file_path)
                
                return True
            except:
                pass
                
            # Метод 3: Попытка использовать shutil вместо os функций
            try:
                temp_file2 = file_path + ".temp2"
                shutil.copy2(file_path, temp_file2)
                os.remove(file_path)
                shutil.move(temp_file2, file_path)
                
                return True
            except:
                if os.path.exists(temp_file2):
                    try:
                        os.remove(temp_file2)
                    except:
                        pass
                        
            # Метод 4: Пытаемся использовать API Windows для удаления с помощью cmd
            try:
                cmd_result = subprocess.run(
                    ["cmd", "/c", "del", "/F", "/Q", file_path],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                if cmd_result.returncode == 0:
                    return True
            except:
                pass
        
        # Если ни один метод не сработал
        return False
    except Exception as e:
        logging.error(f"Ошибка при альтернативной разблокировке {file_path}: {str(e)}")
        return False

def delete_file(path):
    """
    Удаляет файл или папку с многократными попытками
    """
    if not path or not os.path.exists(path):
        logging.error(f"Путь не существует при попытке удаления: {path}")
        return {"error": f"Путь не существует: {path}"}
    
    try:
        logging.info(f"Попытка удаления: {path}")
        
        # Нормализуем путь для Windows
        normalized_path = os.path.normpath(path).replace('/', '\\')
        
        # Увеличиваем паузу перед удалением
        time.sleep(3.0)  # Увеличиваем паузу до 3 секунд
        
        # Функция для повторных попыток
        def try_delete_with_retries(delete_func, max_attempts=5):
            for attempt in range(1, max_attempts + 1):
                try:
                    delete_func()
                    if not os.path.exists(path):
                        return True
                    logging.info(f"Попытка {attempt} не удалась, файл всё ещё существует")
                    # Увеличиваем паузу с каждой попыткой
                    time.sleep(attempt * 1.0)
                except Exception as e:
                    logging.warning(f"Ошибка при попытке {attempt}: {str(e)}")
                    time.sleep(attempt * 1.0)
            return False
        
        # Специальное удаление для файлов с кириллицей
        def try_delete_all_methods():
            success = False
            
            # 1. Попытка удаления через различные методы
            methods = []
            
            # Стандартное удаление через os
            if os.path.isfile(path):
                methods.append(("os.remove", lambda: os.remove(path)))
            else:
                methods.append(("shutil.rmtree", lambda: shutil.rmtree(path, ignore_errors=True)))
            
            # PowerShell с экранированными кавычками для кириллицы
            ps_path = normalized_path.replace('"', '`"')
            if os.path.isfile(path):
                methods.append(("PowerShell file", lambda: subprocess.run(
                    ["powershell", "-Command", f'Remove-Item -LiteralPath "{ps_path}" -Force'],
                    capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, check=False
                )))
            else:
                methods.append(("PowerShell dir", lambda: subprocess.run(
                    ["powershell", "-Command", f'Remove-Item -LiteralPath "{ps_path}" -Recurse -Force'],
                    capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, check=False
                )))
            
            # CMD с кавычками для путей
            cmd_path = f'"{normalized_path}"'
            if os.path.isfile(path):
                methods.append(("CMD del", lambda: subprocess.run(
                    ["cmd", "/c", "del", "/F", "/Q", cmd_path],
                    capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, check=False
                )))
            else:
                methods.append(("CMD rd", lambda: subprocess.run(
                    ["cmd", "/c", "rd", "/s", "/q", cmd_path],
                    capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, check=False
                )))
            
            # Проходим по всем методам
            for method_name, method_func in methods:
                try:
                    logging.info(f"Попытка удаления через {method_name}")
                    method_func()
                    if not os.path.exists(path):
                        logging.info(f"Метод {method_name} успешно удалил {path}")
                        success = True
                        break
                except Exception as e:
                    logging.warning(f"Метод {method_name} завершился с ошибкой: {str(e)}")
            
            return success
        
        # Проверка на блокировки
        if os.path.isfile(path) and check_file_locked_windows_api(path):
            logging.warning(f"Файл все еще заблокирован перед удалением: {path}")
            
            # Многократные попытки разблокировки
            for attempt in range(1, 4):
                logging.info(f"Попытка разблокировки #{attempt}")
                try_alternative_unlock(path)
                time.sleep(attempt * 1.0)
                
                if not check_file_locked_windows_api(path):
                    logging.info(f"Файл успешно разблокирован после попытки #{attempt}")
                    break
            
            # Если файл всё ещё заблокирован, пробуем принудительные методы
            if check_file_locked_windows_api(path):
                logging.warning("Файл всё ещё заблокирован, пробуем принудительные методы")
                if try_delete_all_methods():
                    return {"success": True}
                else:
                    return {"error": f"Не удалось удалить заблокированный файл '{path}'. Попробуйте перезагрузить компьютер."}
        
        # Если это директория, используем специализированные методы
        if os.path.isdir(path):
            # Для папок иногда помогает сначала удалить все файлы внутри
            try:
                # Удаляем все файлы внутри директории перед удалением самой директории
                for root, dirs, files in os.walk(path, topdown=False):
                    for file in files:
                        file_path = os.path.join(root, file)
                        try:
                            if check_file_locked_windows_api(file_path):
                                try_alternative_unlock(file_path)
                                time.sleep(0.5)
                            os.remove(file_path)
                        except Exception as file_e:
                            logging.warning(f"Не удалось удалить файл {file_path}: {str(file_e)}")
                    
                    # После удаления файлов пытаемся удалить поддиректории
                    for dir_name in dirs:
                        dir_path = os.path.join(root, dir_name)
                        try:
                            os.rmdir(dir_path)
                        except Exception as dir_e:
                            logging.warning(f"Не удалось удалить поддиректорию {dir_path}: {str(dir_e)}")
            except Exception as walk_e:
                logging.warning(f"Ошибка при обходе директории: {str(walk_e)}")
            
            # Теперь пытаемся удалить саму директорию
            if try_delete_all_methods():
                return {"success": True}
            else:
                # Последняя попытка через PowerShell с другим синтаксисом
                try:
                    subprocess.run(
                        ["powershell", "-Command", f'$path = "{ps_path}"; if (Test-Path $path) {{ Remove-Item -Path $path -Recurse -Force -ErrorAction SilentlyContinue }}'],
                        capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, check=False
                    )
                    
                    if not os.path.exists(path):
                        return {"success": True}
                except Exception:
                    pass
                
                return {"error": f"Не удалось удалить папку '{path}'. Возможно, некоторые файлы всё ещё заблокированы."}
        else:
            # Для файлов пробуем различные методы
            if try_delete_all_methods():
                return {"success": True}
            else:
                # Если не удалось, сообщаем об ошибке
                return {"error": f"Не удалось удалить файл '{path}'. Попробуйте перезагрузить компьютер."}
            
    except PermissionError as e:
        logging.error(f"Ошибка доступа при удалении: {path}. {str(e)}")
        
        # Последняя попытка через PowerShell с особыми правами
        try:
            # Используем Start-Process для запуска процесса с повышенными правами
            ps_script = f'''
            $path = "{normalized_path.replace('"', '`"')}"
            if (Test-Path -LiteralPath $path) {{
                if ((Get-Item -LiteralPath $path) -is [System.IO.DirectoryInfo]) {{
                    Remove-Item -LiteralPath $path -Recurse -Force -ErrorAction SilentlyContinue
                }} else {{
                    Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
                }}
            }}
            '''
            
            result = subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, check=False
            )
            
            if not os.path.exists(path):
                return {"success": True}
        except Exception as ps_e:
            logging.error(f"Ошибка при PowerShell удалении: {str(ps_e)}")
        
        return {"error": f"Нет прав для удаления '{path}'. Попробуйте запустить программу с правами администратора."}
    except OSError as e:
        logging.error(f"Ошибка OS при удалении {path}: {str(e)}")
        
        # Определяем конкретную причину ошибки
        if "being used by another process" in str(e):
            return {"error": f"Не удалось удалить '{path}': файл используется другим процессом."}
        elif "Access is denied" in str(e):
            return {"error": f"Не удалось удалить '{path}': доступ запрещен. Попробуйте запустить программу от имени администратора."}
        else:
            return {"error": f"Не удалось удалить '{path}': {str(e)}"}
    except Exception as e:
        logging.error(f"Непредвиденная ошибка при удалении {path}: {str(e)}")
        return {"error": f"Не удалось удалить '{path}': {str(e)}"}

def unlock_and_delete_file(path, processes):
    """
    Комплексно разблокирует и удаляет файл или директорию
    Объединяет логику разблокировки и удаления для более надежного результата
    
    Args:
        path: Путь к файлу или директории
        processes: Список блокирующих процессов
        
    Returns:
        dict: Результат операции
    """
    if not path or not os.path.exists(path):
        logging.error(f"Путь не существует: {path}")
        return {"error": f"Путь не существует: {path}"}
    
    # Шаг 1: Разблокировка файла
    # Сначала пробуем завершить блокирующие процессы
    unlock_result = unlock_file(path, processes)
    if "error" in unlock_result:
        logging.warning(f"Проблемы при разблокировке: {unlock_result['error']}")
        # Продолжаем, даже если были проблемы
    
    # Шаг 2: Ожидание освобождения файла системой
    max_wait_seconds = 6  # Максимальное время ожидания в секундах
    wait_interval = 0.5    # Интервал проверки в секундах
    
    logging.info(f"Ожидание освобождения файла системой (макс. {max_wait_seconds} сек)...")
    
    file_unlocked = False
    wait_iterations = int(max_wait_seconds / wait_interval)
    
    # Ожидаем освобождения файла с периодическими проверками
    for i in range(wait_iterations):
        logging.info(f"Проверка блокировки #{i+1}")
        
        if os.path.isfile(path):
            if not check_file_locked_windows_api(path):
                file_unlocked = True
                logging.info(f"Файл полностью освобожден после {(i+1)*wait_interval:.1f} секунд")
                break
        else:  # Для директорий проверяем основные файлы внутри
            all_files_unlocked = True
            for root, _, files in os.walk(path):
                for file in files:
                    file_path = os.path.join(root, file)
                    if check_file_locked_windows_api(file_path):
                        all_files_unlocked = False
                        break
                if not all_files_unlocked:
                    break
            
            if all_files_unlocked:
                file_unlocked = True
                logging.info(f"Директория полностью освобождена после {(i+1)*wait_interval:.1f} секунд")
                break
        
        # Пробуем дополнительную разблокировку на каждой итерации
        try_alternative_unlock(path)
        time.sleep(wait_interval)
    
    # Шаг 3: Удаление файла/директории с несколькими попытками
    logging.info("Начало процесса удаления файла...")
    
    # Нормализуем путь для Windows
    normalized_path = os.path.normpath(path).replace('/', '\\')
    
    # Функция для попыток удаления различными методами
    def try_delete_with_methods():
        # Список методов удаления для тестирования
        deletion_methods = []
        
        # 1. Стандартные методы Python
        if os.path.isfile(path):
            deletion_methods.append(("Standard Python remove", lambda: os.remove(path)))
        else:
            deletion_methods.append(("Standard Python rmtree", lambda: shutil.rmtree(path, ignore_errors=True)))
        
        # 2. PowerShell методы
        ps_path = normalized_path.replace('"', '`"')
        if os.path.isfile(path):
            deletion_methods.append(("PowerShell file", lambda: subprocess.run(
                ["powershell", "-Command", f'Remove-Item -LiteralPath "{ps_path}" -Force -ErrorAction Stop'],
                capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, check=False
            )))
        else:
            deletion_methods.append(("PowerShell directory", lambda: subprocess.run(
                ["powershell", "-Command", f'Remove-Item -LiteralPath "{ps_path}" -Recurse -Force -ErrorAction Stop'],
                capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, check=False
            )))
        
        # 3. CMD методы
        cmd_path = f'"{normalized_path}"'
        if os.path.isfile(path):
            deletion_methods.append(("CMD del", lambda: subprocess.run(
                ["cmd", "/c", "del", "/F", "/S", "/Q", cmd_path],
                capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, check=False
            )))
        else:
            deletion_methods.append(("CMD rd", lambda: subprocess.run(
                ["cmd", "/c", "rd", "/s", "/q", cmd_path],
                capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, check=False
            )))
        
        # 4. Альтернативный метод PowerShell
        ps_script = f'''
        $ErrorActionPreference = "SilentlyContinue"
        $path = "{ps_path}"
        if (Test-Path -LiteralPath $path) {{
            if ((Get-Item -LiteralPath $path -Force) -is [System.IO.DirectoryInfo]) {{
                Get-ChildItem -Path $path -Recurse -Force | Remove-Item -Force -Recurse
                Remove-Item -LiteralPath $path -Force -Recurse
            }} else {{
                Remove-Item -LiteralPath $path -Force
            }}
        }}
        '''
        deletion_methods.append(("PowerShell script", lambda: subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, check=False
        )))
        
        # Если директория, добавим опцию удаления содержимого
        if os.path.isdir(path):
            deletion_methods.append(("Delete directory contents", delete_directory_contents))
        
        # Пробуем каждый метод с несколькими попытками
        for method_name, method_func in deletion_methods:
            for attempt in range(1, 4):
                try:
                    logging.info(f"Метод удаления: {method_name}, попытка {attempt}")
                    method_func()
                    
                    # Проверяем, удалось ли удалить
                    if not os.path.exists(path):
                        logging.info(f"Успешное удаление с помощью метода {method_name}, попытка {attempt}")
                        return True
                    
                    # Ждем немного перед следующей попыткой
                    time.sleep(attempt * 0.5)
                except Exception as e:
                    logging.warning(f"Ошибка при методе {method_name}, попытка {attempt}: {str(e)}")
                    time.sleep(attempt * 0.5)
        
        return False
    
    # Вспомогательная функция для удаления содержимого директории
    def delete_directory_contents():
        if not os.path.isdir(path):
            return
        
        try:
            # Удаляем все файлы в директории
            for root, dirs, files in os.walk(path, topdown=False):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        if check_file_locked_windows_api(file_path):
                            try_alternative_unlock(file_path)
                        os.remove(file_path)
                    except Exception as e:
                        logging.warning(f"Не удалось удалить файл {file_path}: {str(e)}")
                
                # Удаляем поддиректории
                for dir_name in dirs:
                    dir_path = os.path.join(root, dir_name)
                    try:
                        os.rmdir(dir_path)
                    except Exception as e:
                        logging.warning(f"Не удалось удалить директорию {dir_path}: {str(e)}")
        except Exception as e:
            logging.warning(f"Ошибка при очистке директории: {str(e)}")
    
    # Выполняем удаление
    delete_successful = try_delete_with_methods()
    
    if delete_successful:
        return {"success": True, "message": f"Файл/директория '{path}' успешно удален"}
    else:
        return {"error": f"Не удалось удалить '{path}' после разблокировки. Попробуйте перезагрузить компьютер."}

def user_friendly_error(technical_error):
    """Преобразует технические сообщения об ошибках в понятные пользователю"""
    # Словарь с шаблонами ошибок и их пользовательскими описаниями
    error_patterns = {
        "Access is denied": "Доступ запрещен. У программы недостаточно прав для выполнения этой операции.",
        "being used by another process": "Файл используется другим приложением и не может быть изменен.",
        "No such file or directory": "Файл не найден. Возможно, он был перемещен или удален.",
        "Cannot delete": "Не удается удалить файл. Убедитесь, что файл не используется другими программами.",
        "Cannot find the file": "Не удается найти файл. Возможно, он был перемещен или удален.",
        "Permission denied": "Отказано в доступе. У программы недостаточно прав для выполнения операции.",
        "Not enough memory": "Недостаточно памяти для выполнения операции. Попробуйте закрыть другие программы.",
        "handle.exe не найдена": "Не найден инструмент для анализа заблокированных файлов. Переустановите программу.",
        "Не удалось запустить": "Не удалось запустить необходимые компоненты программы. Попробуйте перезапустить программу.",
        "Error reading process information": "Ошибка при получении информации о процессе. Попробуйте перезапустить программу.",
        "Не удалось зарегистрировать горячую клавишу": "Не удалось настроить горячие клавиши. Возможно, они уже используются другой программой.",
        "HTTP": "Ошибка при проверке обновлений. Проверьте подключение к интернету.",
        "URL": "Ошибка при подключении к серверу обновлений. Проверьте подключение к интернету.",
        "SSL": "Ошибка безопасного подключения при проверке обновлений."
    }
    
    # Проверяем, есть ли в сообщении об ошибке известные шаблоны
    error_str = str(technical_error)
    for pattern, user_message in error_patterns.items():
        if pattern.lower() in error_str.lower():
            return user_message
    
    # Если шаблон не найден, возвращаем более общее сообщение
    if "file" in error_str.lower() or "файл" in error_str.lower():
        return "Ошибка при работе с файлом. Убедитесь, что у вас есть необходимые права доступа."
    elif "process" in error_str.lower() or "процесс" in error_str.lower():
        return "Ошибка при работе с процессом. Возможно, процесс был завершен или имеет системную защиту."
    
    # Если не удалось определить тип ошибки, возвращаем оригинальное сообщение
    # но без технических деталей, которые обычно идут после двоеточия
    if ":" in error_str:
        return error_str.split(":", 1)[0] + "."
    
    return error_str

def clear_cache():
    """Очищает кэш результатов анализа"""
    # В оригинальной версии этой функции нет, так как не было кэширования
    pass