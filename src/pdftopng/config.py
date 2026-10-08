"""アプリ全体で使う既定値・設定（ExportOptions）・設定の保存/読込。

GUI 非依存。core からも GUI からも参照する。
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from . import APP_NAME

# --- DPI（書き出し解像度） ---------------------------------------------------
DEFAULT_DPI = 300
MIN_DPI = 72
# A4 を 600dpi で約 5000×7000px。これ以上はメモリ消費が大きいため上限とする。
MAX_DPI = 600

# --- プレビュー用のレンダリングサイズ（長辺ピクセル） --------------------------
THUMB_PX = 220
PREVIEW_PX = 1600


@dataclass
class ExportOptions:
    """1回の書き出しジョブのオプション。"""

    dpi: int = DEFAULT_DPI
    # None の場合は「PDF と同じ場所」に出力する。
    output_dir: Path | None = None

    def validated(self) -> "ExportOptions":
        """値域チェックして正規化した複製を返す。"""
        dpi = int(self.dpi)
        if dpi < MIN_DPI or dpi > MAX_DPI:
            raise ValueError(f"DPI は {MIN_DPI}〜{MAX_DPI} の範囲で指定してください（指定値: {dpi}）。")
        out = Path(self.output_dir) if self.output_dir else None
        return ExportOptions(dpi=dpi, output_dir=out)


# --- アプリのデータ保存先 ----------------------------------------------------
def app_data_dir() -> Path:
    """アプリのデータ保存先。

    Windows: %LOCALAPPDATA%\\PdfToPng（未設定なら %USERPROFILE%\\AppData\\Local 配下）。
    その他 : ~/.local/share/PdfToPng。
    """
    base = os.environ.get("LOCALAPPDATA") or None  # 空文字も未設定扱い。
    if base:
        root = Path(base)
    elif os.name == "nt":
        userprofile = os.environ.get("USERPROFILE") or None
        root = (Path(userprofile) / "AppData" / "Local") if userprofile else Path.home() / "AppData" / "Local"
    else:
        root = Path.home() / ".local" / "share"
    return root / APP_NAME


def logs_dir() -> Path:
    return app_data_dir() / "logs"


def settings_path() -> Path:
    return app_data_dir() / "settings.json"


# --- 設定（GUI の選択状態）の保存/読込 --------------------------------------
@dataclass
class Settings:
    """GUI の最後の選択を保存しておくための永続設定。"""

    dpi: int = DEFAULT_DPI
    use_custom_output: bool = False
    output_dir: str | None = None
    last_open_dir: str | None = None

    def to_json(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_json(data: dict) -> "Settings":
        return Settings(
            dpi=int(data.get("dpi", DEFAULT_DPI)),
            use_custom_output=bool(data.get("use_custom_output", False)),
            output_dir=data.get("output_dir") or None,
            last_open_dir=data.get("last_open_dir") or None,
        )


def load_settings() -> Settings:
    """設定を読み込む。失敗時は既定値。"""
    p = settings_path()
    try:
        if p.is_file():
            with p.open("r", encoding="utf-8") as f:
                return Settings.from_json(json.load(f))
    except Exception:
        pass
    return Settings()


def save_settings(settings: Settings) -> None:
    """設定を保存する（失敗しても例外を投げない）。"""
    try:
        app_data_dir().mkdir(parents=True, exist_ok=True)
        with settings_path().open("w", encoding="utf-8") as f:
            json.dump(settings.to_json(), f, ensure_ascii=False, indent=2)
    except Exception:
        pass
