@echo off
chcp 65001 >nul
title Сборка JL Delete Lock

echo ===============================================================
echo                 Сборка JL Delete Lock
echo ===============================================================
echo.

:: Переходим в корневую директорию проекта
cd /d "%~dp0.."

:: Проверяем наличие виртуального окружения
if not exist "venv" (
    echo [ОШИБКА] Виртуальное окружение не найдено.
    echo Пожалуйста, сначала запустите scripts\setup.bat для настройки окружения.
    pause
    exit /b 1
)

:: Активация виртуального окружения
call venv\Scripts\activate.bat

:: Отображаем информацию о подготовке
echo [1/3] Подготовка файлов и проверка ресурсов...

:: Проверяем наличие папки resources и необходимых файлов
if not exist "resources" (
    echo Создание директории resources...
    mkdir resources
)

:: Создаем директорию dist, если она не существует
if not exist "dist" (
    mkdir dist
)

echo [2/3] Запуск сборки исполняемого файла...
echo Это может занять некоторое время, пожалуйста, подождите...

:: Запуск сборки через Python-скрипт
python scripts\build.py
if %errorlevel% neq 0 (
    echo [ОШИБКА] Не удалось собрать исполняемый файл.
    pause
    exit /b 1
)

echo [3/3] Копирование дополнительных файлов...

:: Копируем handle.exe рядом с исполняемым файлом (для страховки)
if exist "resources\handle64.exe" (
    copy /Y "resources\handle64.exe" "dist\portable\"
)

if exist "resources\handle.exe" (
    copy /Y "resources\handle.exe" "dist\portable\"
)

if exist "resources\Eula.txt" (
    copy /Y "resources\Eula.txt" "dist\portable\"
)

if exist "resources\lock_file.ico" (
    copy /Y "resources\lock_file.ico" "dist\portable\"
)

echo.
echo ===============================================================
echo                 Сборка успешно завершена!
echo ===============================================================
echo.
echo Исполняемый файл JL_Delete_Lock.exe создан в папке "dist"
echo Портативная версия находится в папке "dist\portable"
echo Для использования просто скопируйте его на рабочий стол
echo или в любую другую папку.

:: Предложение открыть папку с готовым файлом
echo.
echo Хотите открыть папку с готовым файлом? (Y/N)
set /p open_folder="> "
if /i "%open_folder%"=="Y" (
    start explorer "%~dp0..\dist\portable"
)

:: Предложение создать установщик
echo.
echo Хотите создать установщик программы? (Y/N)
set /p create_installer="> "
if /i "%create_installer%"=="Y" (
    call scripts\create_installer.bat
)

:: Деактивация виртуального окружения
call venv\Scripts\deactivate.bat

pause