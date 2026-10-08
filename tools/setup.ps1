# 開発環境をプロジェクトフォルダ内だけで用意するスクリプト。
#
# PC に Python をインストールせず、.tools\ に uv と Python 本体を置き、
# .venv に依存パッケージを入れる。PATH・レジストリは変更しない。
# 不要になったら .tools\ と .venv\ を削除すれば元通り。
#
# 使い方:  powershell -ExecutionPolicy Bypass -File tools\setup.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot   # PdfToPng/
Set-Location $Root

. "$PSScriptRoot\env.ps1"

# 1) uv（単体 exe）をダウンロード
if (-not (Test-Path $UvExe)) {
    $zip = Join-Path $ToolsDir "uv.zip"
    New-Item -ItemType Directory -Force $ToolsDir | Out-Null
    $url = "https://github.com/astral-sh/uv/releases/download/$UvVersion/uv-x86_64-pc-windows-msvc.zip"
    Write-Host "uv $UvVersion をダウンロード中..."
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
    Expand-Archive -Path $zip -DestinationPath (Join-Path $ToolsDir "uv") -Force
    Remove-Item $zip
}

# 2) Python 本体（.tools\python）と仮想環境（.venv）
if (-not (Test-Path "$Root\.venv\Scripts\python.exe")) {
    & $UvExe venv "$Root\.venv" --python $PythonVersion --managed-python
    if ($LASTEXITCODE -ne 0) { throw "仮想環境の作成に失敗しました。" }
}

# 3) 依存パッケージ
& $UvExe pip install --python "$Root\.venv\Scripts\python.exe" -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw "パッケージのインストールに失敗しました。" }

Write-Host "準備完了: .venv\Scripts\python.exe run.py で起動できます。" -ForegroundColor Green
