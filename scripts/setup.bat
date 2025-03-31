@echo off
chcp 65001 >nul
title Настройка окружения JL Delete Lock

echo ===============================================================
echo            Настройка окружения JL Delete Lock
echo ===============================================================
echo.

:: Переходим в корневую директорию проекта
cd /d "%~dp0.."

:: Проверяем наличие Python
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo [ОШИБКА] Python не найден. Пожалуйста, установите Python 3.8 или новее.
    echo Вы можете скачать Python с сайта: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/3] Python обнаружен

:: Создаем и активируем виртуальное окружение
if not exist "venv" (
    echo [2/3] Создание виртуального окружения...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ОШИБКА] Не удалось создать виртуальное окружение.
        pause
        exit /b 1
    )
) else (
    echo [2/3] Виртуальное окружение уже существует
)

:: Активация виртуального окружения
call venv\Scripts\activate.bat

:: Установка зависимостей
echo [3/3] Установка необходимых библиотек...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ОШИБКА] Не удалось установить зависимости.
    pause
    exit /b 1
)

:: Проверка наличия необходимых файлов ресурсов
echo.
echo [Проверка ресурсов]

if not exist "resources" (
    echo Создание директории resources...
    mkdir resources
)

:: Создание необходимых директорий
if not exist "src" (
    mkdir src
)

echo.
echo ===============================================================
echo            Настройка окружения успешно завершена!
echo ===============================================================
echo.
echo Теперь вы можете:
echo - Запустить программу с помощью run.bat
echo - Собрать исполняемый файл с помощью scripts\build.bat
echo.

echo Хотите запустить программу сейчас? (Y/N)
set /p run_now="> "
if /i "%run_now%"=="Y" (
    call run.bat
) else (
    pause
)

:: Деактивация виртуального окружения
call venv\Scripts\deactivate.bat