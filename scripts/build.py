import os
import sys
import subprocess
import shutil
import logging
import glob

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Определяем корневую директорию проекта
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP_VERSION = "1.0.0"

def quote_path(path):
    """Добавляет кавычки к пути, если в нем есть пробелы"""
    if " " in path:
        return f'"{path}"'
    return path

def main():
    # Определяем пути к директориям
    src_dir = os.path.join(ROOT_DIR, "src")
    resources_dir = os.path.join(ROOT_DIR, "resources")
    dist_dir = os.path.join(ROOT_DIR, "dist")
    build_dir = os.path.join(ROOT_DIR, "build")
    
    # Меняем текущую директорию на корневую директорию проекта
    os.chdir(ROOT_DIR)
    
    # Очищаем предыдущие сборки
    logging.info("Очистка предыдущих сборок...")
    for cleanup_dir in [dist_dir, build_dir]:
        if os.path.exists(cleanup_dir):
            try:
                shutil.rmtree(cleanup_dir)
                logging.info(f"Удалена директория: {cleanup_dir}")
            except Exception as e:
                logging.warning(f"Не удалось очистить директорию {cleanup_dir}: {str(e)}")
    
    # Создаем директории, если они не существуют
    os.makedirs(build_dir, exist_ok=True)
    os.makedirs(dist_dir, exist_ok=True)
    
    # Собираем список файлов ресурсов вручную
    datas_list = []
    
    # Добавляем все exe файлы
    for file in glob.glob(os.path.join(resources_dir, "*.exe")):
        datas_list.append(f"(r'{file}', 'resources')")
    
    # Добавляем все ico файлы
    for file in glob.glob(os.path.join(resources_dir, "*.ico")):
        datas_list.append(f"(r'{file}', 'resources')")
    
    # Добавляем все txt файлы
    for file in glob.glob(os.path.join(resources_dir, "*.txt")):
        datas_list.append(f"(r'{file}', 'resources')")
    
    # Добавляем все png файлы
    for file in glob.glob(os.path.join(resources_dir, "*.png")):
        datas_list.append(f"(r'{file}', 'resources')")
    
    # Преобразуем список в строку для spec файла
    datas_str = ",\n        ".join(datas_list)
    
    # Создаем файл specfile для PyInstaller
    spec_content = f"""# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    [r'{os.path.join(src_dir, "main.py")}'],
    pathex=[r'{src_dir}', r'{ROOT_DIR}'],
    binaries=[],
    datas=[
        {datas_str}
    ],
    hiddenimports=[
        'file_handler', 
        'gui', 
        'settings', 
        'hotkey_manager', 
        'settings_dialog', 
        'update_checker',
        'json',
        'threading',
        'webbrowser',
        'datetime',
        'shutil',
        'winreg',
        'ctypes',
        'keyboard'
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Исправление путей к ресурсам
for d in a.datas:
    if 'resources' in d[0]:
        parts = d[0].split('/')
        d = (parts[-1], d[1], d[2])

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: создаем единый exe-файл вместо директории
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,        # Включаем бинарные файлы в exe
    a.zipfiles,        # Включаем zip-файлы в exe
    a.datas,           # Включаем ресурсы в exe
    [],
    name='JL_Delete_Lock',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,  # Предотвращаем распаковку во временную директорию
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=r'{os.path.join(resources_dir, "lock_file.ico")}',
)

# Также создаем версию с директорией для установщика
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='JL_Delete_Lock_Installer',
)
"""
    
    spec_file = os.path.join(ROOT_DIR, "custom_build.spec")
    with open(spec_file, "w", encoding="utf-8") as f:
        f.write(spec_content)
    
    logging.info(f"Создан специализированный spec-файл: {spec_file}")
    
    # Формируем команду для PyInstaller - используем созданный spec-файл
    cmd = [
        "pyinstaller",
        "--noconfirm",  # Не спрашивать подтверждения
        "--clean",      # Очистить временные файлы перед сборкой
        "--distpath", dist_dir,
        "--workpath", build_dir,
        spec_file
    ]
    
    # Запускаем сборку
    logging.info("Запуск PyInstaller для сборки исполняемого файла...")
    logging.info(f"Команда: {' '.join(cmd)}")
    
    try:
        proc = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )
        
        # Выводим процесс сборки в реальном времени
        for line in proc.stdout:
            line = line.strip()
            if line:
                logging.info(line)
        
        proc.wait()
        
        if proc.returncode != 0:
            logging.error(f"PyInstaller завершился с ошибкой: код {proc.returncode}")
            return False
            
        logging.info("Сборка завершена успешно!")
        
        # После сборки проверяем, что файлы созданы успешно
        exe_file = os.path.join(dist_dir, "JL_Delete_Lock.exe")
        installer_dir = os.path.join(dist_dir, "JL_Delete_Lock_Installer")
        
        if os.path.exists(exe_file):
            logging.info(f"Портативный файл создан успешно: {exe_file}")
            # Создаем папку portable для копирования
            portable_dir = os.path.join(dist_dir, "portable")
            os.makedirs(portable_dir, exist_ok=True)
            
            # Копируем exe в папку portable
            shutil.copy2(exe_file, os.path.join(portable_dir, "JL_Delete_Lock.exe"))
            
            # Создаем файл-флаг portable.flag
            with open(os.path.join(portable_dir, "portable.flag"), "w", encoding="utf-8") as f:
                f.write("This file indicates that this is a portable version of the application.\n")
                f.write("Do not delete this file if you want to keep the application portable.\n")
            
            # Копируем handle.exe рядом с портативным exe для страховки
            for handle_file in ["handle.exe", "handle64.exe", "handle64a.exe"]:
                src_path = os.path.join(resources_dir, handle_file)
                if os.path.exists(src_path):
                    shutil.copy2(src_path, os.path.join(portable_dir, handle_file))
            
            logging.info(f"Портативная версия создана в папке: {portable_dir}")
        else:
            logging.error(f"Ошибка: Портативный exe-файл не найден: {exe_file}")
            
        if os.path.exists(installer_dir):
            logging.info(f"Файлы для установщика созданы в: {installer_dir}")
        else:
            logging.error(f"Ошибка: Директория для установщика не найдена: {installer_dir}")
            
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Ошибка при выполнении PyInstaller: {e}")
        return False
    except Exception as e:
        logging.error(f"Непредвиденная ошибка: {e}")
        return False

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)