@echo off
chcp 65001 >nul
title Создание установщика JL Delete Lock

echo ===============================================================
echo           Создание установщика JL Delete Lock
echo ===============================================================
echo.

:: Переходим в корневую директорию проекта
cd /d "%~dp0.."

echo [1/4] Проверка наличия необходимых файлов...

:: Проверяем наличие файлов для установщика в новой директории
if not exist "dist\JL_Delete_Lock_Installer\JL_Delete_Lock.exe" (
    echo [ОШИБКА] Файл dist\JL_Delete_Lock_Installer\JL_Delete_Lock.exe не найден.
    echo Пожалуйста, сначала соберите программу с помощью scripts\build.bat.
    pause
    exit /b 1
)

:: Проверяем наличие скрипта Inno Setup
if not exist "scripts\install-script.iss" (
    echo [ОШИБКА] Скрипт установки scripts\install-script.iss не найден.
    pause
    exit /b 1
)

echo [2/4] Проверка наличия необходимых ресурсов...

:: Проверяем наличие основных ресурсов
if not exist "resources\lock_file.ico" (
    echo [ПРЕДУПРЕЖДЕНИЕ] Файл resources\lock_file.ico не найден.
    echo Установщик будет создан без иконки программы.
)

if not exist "resources\handle64.exe" (
    if not exist "resources\handle.exe" (
        echo [ПРЕДУПРЕЖДЕНИЕ] Утилиты handle.exe или handle64.exe не найдены в папке resources.
        echo Программа может работать некорректно без этих утилит.
    )
)

:: Создаем директорию output, если она не существует
if not exist "output" (
    echo Создание директории output для установщика...
    mkdir "output"
)

echo [3/4] Поиск программы Inno Setup...

:: Проверяем наличие Inno Setup в различных местах
set "INNO_COMPILER="

:: Извлекаем значения переменных окружения в промежуточные переменные
set "PROG_FILES_X86=%ProgramFiles(x86)%"
set "PROG_FILES=%ProgramFiles%"

:: Проверяем стандартный путь установки Inno Setup
if exist "%PROG_FILES_X86%\Inno Setup 6\ISCC.exe" (
    set "INNO_COMPILER=%PROG_FILES_X86%\Inno Setup 6\ISCC.exe"
    echo Найден Inno Setup 6 в папке "Program Files (x86)"
) else if exist "%PROG_FILES%\Inno Setup 6\ISCC.exe" (
    set "INNO_COMPILER=%PROG_FILES%\Inno Setup 6\ISCC.exe"
    echo Найден Inno Setup 6 в папке "Program Files"
) else if exist "%PROG_FILES_X86%\Inno Setup 5\ISCC.exe" (
    set "INNO_COMPILER=%PROG_FILES_X86%\Inno Setup 5\ISCC.exe"
    echo Найден Inno Setup 5 в папке "Program Files (x86)"
) else if exist "%PROG_FILES%\Inno Setup 5\ISCC.exe" (
    set "INNO_COMPILER=%PROG_FILES%\Inno Setup 5\ISCC.exe"
    echo Найден Inno Setup 5 в папке "Program Files"
)

if "%INNO_COMPILER%"=="" (
    echo [ОШИБКА] Inno Setup не найден.
    echo Пожалуйста, установите Inno Setup с сайта https://jrsoftware.org/isdl.php
    pause
    exit /b 1
)

echo [OK] Найден компилятор Inno Setup: %INNO_COMPILER%

echo [4/4] Создание установщика...

:: Изменяем файл install-script.iss для использования новой директории
(
    echo #define MyAppSourceDir "dist\JL_Delete_Lock_Installer"
) > temp_define.iss

:: Копируем временную версию install-script.iss в корень
copy /Y "scripts\install-script.iss" "install-script.temp.iss"

:: Объединяем файлы
copy /b temp_define.iss + install-script.temp.iss combined_script.iss

:: Компилируем скрипт Inno Setup, указывая абсолютный путь к output
echo Выполняется команда: "%INNO_COMPILER%" "combined_script.iss" /O"%CD%\output"
"%INNO_COMPILER%" "combined_script.iss" /O"%CD%\output"

:: Проверяем код возврата
if %errorlevel% neq 0 (
    echo [ОШИБКА] Не удалось создать установщик. Код ошибки: %errorlevel%
    echo Проверьте наличие всех необходимых файлов и правильность путей.
    del "temp_define.iss" >nul 2>&1
    del "install-script.temp.iss" >nul 2>&1
    del "combined_script.iss" >nul 2>&1
    pause
    exit /b 1
)

:: Удаляем временные файлы
del "temp_define.iss" >nul 2>&1
del "install-script.temp.iss" >nul 2>&1
del "combined_script.iss" >nul 2>&1

echo.
echo ===============================================================
echo           Установщик успешно создан!
echo ===============================================================
echo.
echo Файл установщика находится в директории: output\JL_Delete_Lock_Setup.exe
echo.

:: Предложение открыть папку с установщиком
echo Хотите открыть папку с установщиком? (Y/N)
set /p open_folder="> "
if /i "%open_folder%"=="Y" (
    start explorer "%CD%\output"
)

exit /b 0