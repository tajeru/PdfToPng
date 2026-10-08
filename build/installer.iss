; Inno Setup スクリプト — PdfToPng
;
; 通常は build\build.ps1 -Installer から呼ばれる（バージョンは /DMyAppVersion=... で渡される）。
; 前提: PyInstaller で dist\PdfToPng\ を生成済みであること。
; 成果物: dist\PdfToPng-Setup-<version>.exe

#define MyAppName "PdfToPng"
#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#define MyAppPublisher "PdfToPng project"
#define MyAppExeName "PdfToPng.exe"

[Setup]
; AppId はアップデート時の同一アプリ判定に使うので変更しないこと。
AppId={{4F2A9C61-3B7E-4D58-A1C2-5E8B7D0F6A13}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
VersionInfoVersion={#MyAppVersion}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=PdfToPng-Setup-{#MyAppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\resources\app.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; 既定は管理者権限不要のユーザー単位インストール（%LOCALAPPDATA%\Programs\PdfToPng）。
; ダイアログで「すべてのユーザー」を選べば Program Files に入れることもできる。
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
; 起動中のアプリがあれば閉じてから上書きする（アップデート時）。
CloseApplications=yes

[Languages]
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[InstallDelete]
; 旧バージョンの残骸で動作がおかしくならないよう、本体フォルダは入れ替える。
Type: filesandordirs; Name: "{app}\_internal"

[Files]
; PyInstaller の onedir 出力をまるごと取り込む。
Source: "..\dist\PdfToPng\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
