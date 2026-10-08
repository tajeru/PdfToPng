# PdfToPng をビルドして配布物を作る一括スクリプト（PowerShell）。
#
# 使い方:  powershell -ExecutionPolicy Bypass -File build\build.ps1 [-Installer]
#
# 1) tools\setup.ps1 でフォルダ内に Python と依存パッケージを用意（PC へのインストール不要）
# 2) テスト → アイコン生成 → PyInstaller で凍結
# 3) dist\PdfToPng-<version>-portable.zip を作成（展開して PdfToPng.exe を起動するだけ）
# -Installer 指定時のみ、Inno Setup 6 があればインストーラーも生成する。

param([switch]$Installer)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot   # PdfToPng/
Set-Location $Root

# 1) 開発環境（.tools\ と .venv\）
& powershell -NoProfile -ExecutionPolicy Bypass -File "$Root\tools\setup.ps1"
if ($LASTEXITCODE -ne 0) { throw "環境の準備に失敗しました。" }
$Py = "$Root\.venv\Scripts\python.exe"

# 2) テスト
& $Py -m pytest
if ($LASTEXITCODE -ne 0) { throw "テストに失敗しました。ビルドを中止します。" }

# 3) アイコン生成（未作成の場合のみ）
if (-not (Test-Path "$Root\resources\app.ico")) {
    & $Py "resources\make_icon.py"
    if ($LASTEXITCODE -ne 0) { throw "アイコンの生成に失敗しました。" }
}

# 4) PyInstaller で凍結（dist\PdfToPng\）
& $Py -m PyInstaller "build\pdftopng.spec" --noconfirm --workpath "build\work" --distpath "dist"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller に失敗しました。" }

# 5) ポータブル版 zip
$Version = (& $Py -c "import sys; sys.path.insert(0, 'src'); import pdftopng; print(pdftopng.__version__)").Trim()
$Zip = "$Root\dist\PdfToPng-$Version-portable.zip"
if (Test-Path $Zip) { Remove-Item $Zip }
Compress-Archive -Path "$Root\dist\PdfToPng" -DestinationPath $Zip
Write-Host "完成: $Root\dist\PdfToPng\PdfToPng.exe" -ForegroundColor Green
Write-Host "      $Zip" -ForegroundColor Green

# 6) インストーラー（任意）。Inno Setup は .tools\innosetup にポータブル展開したものを使う。
if ($Installer) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File "$Root\tools\setup-inno.ps1"
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup の準備に失敗しました。" }
    & "$Root\.tools\innosetup\ISCC.exe" "/DMyAppVersion=$Version" "build\installer.iss"
    if ($LASTEXITCODE -ne 0) { throw "インストーラーの作成に失敗しました。" }
    Write-Host "      $Root\dist\PdfToPng-Setup-$Version.exe" -ForegroundColor Green
}
