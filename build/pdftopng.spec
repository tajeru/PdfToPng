# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 仕様ファイル。

ビルド:
    cd PdfToPng
    pyinstaller build/pdftopng.spec --noconfirm

成果物: dist/PdfToPng/PdfToPng.exe （onedir 形式）
"""
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

# このファイルは build/ にあるので、プロジェクトルートは1つ上。
ROOT = Path(SPECPATH).resolve().parent
ICON = ROOT / "resources" / "app.ico"

hiddenimports = collect_submodules("PIL")

# pypdfium2 は pdfium.dll と version.json を pypdfium2_raw / pypdfium2 に同梱している。
binaries = collect_dynamic_libs("pypdfium2_raw")
datas = collect_data_files("pypdfium2") + collect_data_files("pypdfium2_raw")
if ICON.exists():
    # ウィンドウアイコン用（無ければ描画ロゴにフォールバック）。
    datas.append((str(ICON), "resources"))

a = Analysis(
    [str(ROOT / "run.py")],
    pathex=[str(ROOT / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # 使わない重い Qt モジュールを除外して配布サイズを抑える。
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.Qt3DCore",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtMultimedia",
        "PySide6.QtNetwork",
        "PySide6.QtPdf",
        "PySide6.QtCharts",
        "tkinter",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PdfToPng",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # ウィンドウアプリ（コンソール非表示）
    icon=str(ICON) if ICON.exists() else None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="PdfToPng",
)
