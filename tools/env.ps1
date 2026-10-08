# uv がプロジェクトフォルダの外（ユーザー領域・レジストリ）に書き込まないための設定。
# setup.ps1 / build.ps1 から dot-source して使う。

$Root = Split-Path -Parent $PSScriptRoot
$ToolsDir = Join-Path $Root ".tools"
$UvVersion = "0.8.0"
$PythonVersion = "3.12"
$UvExe = Join-Path $ToolsDir "uv\uv.exe"

$env:UV_PYTHON_INSTALL_DIR = Join-Path $ToolsDir "python"
$env:UV_CACHE_DIR = Join-Path $ToolsDir "uv-cache"
$env:UV_TOOL_DIR = Join-Path $ToolsDir "uv-tools"
$env:UV_PYTHON_BIN_DIR = Join-Path $ToolsDir "python-bin"
$env:UV_PYTHON_INSTALL_BIN = "0"
$env:UV_PYTHON_INSTALL_REGISTRY = "0"
$env:UV_NO_CONFIG = "1"
