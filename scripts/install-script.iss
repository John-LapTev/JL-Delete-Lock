#ifndef MyAppSourceDir
  #define MyAppSourceDir "dist\JL_Delete_Lock_Installer"
#endif

#define MyAppName "JL Delete Lock"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "JL Software"
#define MyAppURL "https://example.com"
#define MyAppExeName "JL_Delete_Lock.exe"

[Setup]
; Уникальный идентификатор для инсталлятора
AppId={{B501C8F3-9C82-42A1-914D-6E8AC2B7F7B0}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
; "OutputDir" указывается в командной строке через /O
; OutputDir=output
OutputBaseFilename=JL_Delete_Lock_{#MyAppVersion}_Setup
Compression=lzma2
SolidCompression=yes
; Требуем права администратора для установки
PrivilegesRequired=admin
; Включаем поддержку перезапуска Windows
RestartIfNeededByRun=yes
; Иконка инсталлятора
SetupIconFile=resources\lock_file.ico
; Ограничение на минимальную версию Windows
MinVersion=0,6.1
; Добавляем информацию о версии установщика
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Installer
VersionInfoTextVersion={#MyAppVersion}
VersionInfoCopyright={#MyAppPublisher}
; Улучшенная визуальная тема установки
WizardStyle=modern
; Масштабирование для экранов высокого разрешения (HiDPI)
WizardSizePercent=120
; Показать индикатор выполнения в панели задач в Windows 7 и выше
ShowTasksTreeLines=yes

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
russian.WelcomeLabel1=Вас приветствует мастер установки [name]
russian.WelcomeLabel2=Это программа установит [name/ver] на ваш компьютер.%n%nРекомендуется закрыть все другие приложения перед тем, как продолжить.
english.WelcomeLabel1=Welcome to the [name] Setup
english.WelcomeLabel2=This will install [name/ver] on your computer.%n%nIt is recommended that you close all other applications before continuing.

[CustomMessages]
russian.AppDescription=Программа для разблокировки и удаления заблокированных файлов и папок в Windows
english.AppDescription=A tool for unlocking and deleting locked files and folders in Windows
russian.AutostartApp=Запускать программу вместе с Windows
english.AutostartApp=Launch on Windows startup
russian.ContextMenuIntegration=Добавить в контекстное меню проводника
english.ContextMenuIntegration=Add to Windows Explorer context menu
russian.CreateDesktopIcon=Создать значок на рабочем столе
english.CreateDesktopIcon=Create desktop icon
russian.LaunchAfterInstall=Запустить программу после установки
english.LaunchAfterInstall=Launch the program after installation
russian.MinimizeToTray=Сворачивать программу в трей при закрытии
english.MinimizeToTray=Minimize to tray when closing

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 0,6.1
Name: "autostart"; Description: "{cm:AutostartApp}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "contextmenu"; Description: "{cm:ContextMenuIntegration}"; GroupDescription: "Интеграция с Windows:"; Flags: unchecked
Name: "minimizeTray"; Description: "{cm:MinimizeToTray}"; GroupDescription: "Настройки приложения:"; Flags: checkedonce

[Files]
; Главный исполняемый файл
Source: "{#MyAppSourceDir}\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; Прочие файлы из папки сборки
Source: "{#MyAppSourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Ресурсы программы (на всякий случай также копируем)
Source: "resources\lock_file.ico"; DestDir: "{app}\resources"; Flags: ignoreversion
Source: "resources\handle.exe"; DestDir: "{app}\resources"; Flags: ignoreversion
Source: "resources\handle64.exe"; DestDir: "{app}\resources"; Flags: ignoreversion
Source: "resources\handle64a.exe"; DestDir: "{app}\resources"; Flags: ignoreversion
Source: "resources\Eula.txt"; DestDir: "{app}\resources"; Flags: ignoreversion
Source: "resources\splash.png"; DestDir: "{app}\resources"; Flags: ignoreversion

; Лицензионное соглашение
Source: "LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion

[Dirs]
; Создаем директорию для хранения логов и настроек
Name: "{localappdata}\JL_Delete_Lock"; Permissions: users-full
Name: "{localappdata}\JL_Delete_Lock\logs"; Permissions: users-full
Name: "{localappdata}\JL_Delete_Lock\backups"; Permissions: users-full

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Comment: "{cm:AppDescription}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; Comment: "{cm:AppDescription}"
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

[Run]
; Запуск программы после установки с правами пользователя
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchAfterInstall}"; Flags: nowait postinstall skipifsilent shellexec runasoriginaluser

[Registry]
; Добавление программы в автозапуск
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "JL_Delete_Lock"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue; Tasks: autostart

; Установка настроек программы
Root: HKCU; Subkey: "Software\JL Software\JL Delete Lock"; ValueType: dword; ValueName: "autostart"; ValueData: "1"; Flags: createvalueifdoesntexist; Tasks: autostart
Root: HKCU; Subkey: "Software\JL Software\JL Delete Lock"; ValueType: dword; ValueName: "hotkeys_enabled"; ValueData: "1"; Flags: createvalueifdoesntexist
Root: HKCU; Subkey: "Software\JL Software\JL Delete Lock"; ValueType: dword; ValueName: "close_to_tray"; ValueData: "1"; Flags: createvalueifdoesntexist; Tasks: minimizeTray
Root: HKCU; Subkey: "Software\JL Software\JL Delete Lock"; ValueType: dword; ValueName: "show_tray_notifications"; ValueData: "1"; Flags: createvalueifdoesntexist

; Добавление в контекстное меню для файлов
Root: HKCR; Subkey: "*\shell\JL_Delete_Lock"; ValueType: string; ValueName: ""; ValueData: "Проверить через JL Delete Lock"; Flags: uninsdeletekey; Tasks: contextmenu
Root: HKCR; Subkey: "*\shell\JL_Delete_Lock"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""; Tasks: contextmenu
Root: HKCR; Subkey: "*\shell\JL_Delete_Lock\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: contextmenu

; Добавление в контекстное меню для папок
Root: HKCR; Subkey: "Directory\shell\JL_Delete_Lock"; ValueType: string; ValueName: ""; ValueData: "Проверить через JL Delete Lock"; Flags: uninsdeletekey; Tasks: contextmenu
Root: HKCR; Subkey: "Directory\shell\JL_Delete_Lock"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""; Tasks: contextmenu
Root: HKCR; Subkey: "Directory\shell\JL_Delete_Lock\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: contextmenu

[UninstallDelete]
; Удаление файла настроек при удалении программы
Type: files; Name: "{localappdata}\JL_Delete_Lock\settings.json"
Type: dirifempty; Name: "{localappdata}\JL_Delete_Lock\logs"
Type: dirifempty; Name: "{localappdata}\JL_Delete_Lock\backups"
Type: dirifempty; Name: "{localappdata}\JL_Delete_Lock"