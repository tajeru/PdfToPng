# PdfToPng

PDF をページごとに PNG へ分解する Windows 向け GUI アプリ。
スキャン PDF はページが上下逆さま・90° 傾きになっていることがあるため、
**書き出し前にサムネイルでプレビューし、ページごとに向きを直せる**ことが最重要機能。

姉妹アプリ `ImageToPdf`（`..\ImageToPdf-main\ImageToPdf-main`）と技術スタック・構成・UI の
見た目をそろえる。迷ったらそちらの実装（特に `ui/theme.py`・`ui/widgets.py`・`worker.py`・`build/`）を参考にする。

## 要件

### 必須（初版）
- PDF を **ファイル選択 / ドラッグ＆ドロップ** で読み込む（複数 PDF も可）
- 全ページを**サムネイル一覧**で表示（グリッド表示）
- ページごとの回転操作：**左 90° / 右 90° / 180°**
  - 複数選択して一括回転できる
  - キーボード操作：`←`/`→` で 90° 回転、`R` で 180°、`↑`/`↓` で前後のページへ移動、
    `Enter`/`Space` で拡大、`Ctrl+A` で全選択
  - ダブルクリックで大きなプレビューを表示（その画面でも回転できる）
  - 回転済みのページはサムネイル上で分かるようにする（バッジ等）
  - 「回転をリセット」で元に戻せる
- PNG として書き出し
  - **DPI 設定**（既定 300。ImageToPdf と同じ）
  - 出力先：既定は「PDF と同じ場所に `<PDF名>` フォルダを作成」。任意フォルダも選択可
  - ファイル名：`<PDF名>_001.png` 形式の**ゼロ埋め連番**（ページ数に応じて桁数を決める、最低 3 桁）
  - 既存ファイル・フォルダは**上書きしない**（`<PDF名>_1` のように連番で回避）。元 PDF は変更・削除しない
- 書き出しは別スレッドで実行し、進捗表示とキャンセルが可能
- パスワード付き・破損 PDF は分かりやすいエラーを出して続行（他の PDF は処理する）

### 将来（初版ではやらない）
- 向きの自動判定（Tesseract OSD 等）による回転候補の提案
- 任意角度の傾き補正（デスキュー）
- ページの削除・並べ替え、JPEG/WEBP 出力
- 書き出した PNG をそのまま ImageToPdf に渡す連携

## 技術スタック

- Python 3.12 / **PySide6**（GUI）/ **Pillow**（回転・PNG 保存）
- **pypdfium2**（PDF のラスタライズ）
  - 外部 exe（poppler 等）不要で PyInstaller に同梱しやすい
  - ライセンスが Apache-2.0/BSD で配布しやすい。**PyMuPDF は AGPL のため使わない**
- テスト：pytest（テスト用 PDF は img2pdf や Pillow でテスト内で生成する）
- 配布：PyInstaller（onedir）+ Inno Setup、未署名配布（ImageToPdf と同じ方針）

## 設計方針

- **回転は「メタデータ」として保持し、書き出し時にだけ適用する**
  - ページの状態は `PageItem(pdf_path, page_index, rotation)`（rotation は 0/90/180/270、時計回り）
  - プレビュー表示はサムネイル画像を回転して描画するだけ。元 PDF は書き換えない
  - 書き出し時：`pdfium でレンダリング → Image.rotate(-rotation, expand=True) → PNG 保存`
  - PDF 側の `/Rotate` 属性は pdfium のレンダリングで反映済みのものを「0°」とみなす
- **サムネイルは低 DPI（約 50〜72）でレンダリング**し、バックグラウンドで順次生成してキャッシュする。
  ページ数が多い PDF でも UI が固まらないこと。本番 DPI のレンダリングは書き出し時のみ
- `core/` は GUI 非依存（PySide6 を import しない）にして pytest で単体テストする
- **PDFium はスレッドセーフではない**（別ドキュメントでも同時呼び出し不可）。
  PDFium を触る処理は必ず `core/document.py` の `PdfFile` 経由にし、`PDFIUM_LOCK` の内側で行う。
  ドキュメントオブジェクトはスレッドをまたいで共有しない（スレッドごとに開く）
- メモリ：高 DPI レンダリングは 1 ページずつ処理して保存後すぐ解放する

## 想定ディレクトリ構成

```
PdfToPng/
├── CLAUDE.md
├── README.md
├── run.py                      # 起動エントリ（PyInstaller のターゲット）
├── pyproject.toml / requirements*.txt
├── src/pdftopng/
│   ├── app.py                  # QApplication 起動
│   ├── config.py               # 既定値・ExportOptions・設定の保存/読込
│   ├── logging_setup.py        # ログ（%LOCALAPPDATA%\PdfToPng\logs）
│   ├── worker.py               # QThread ワーカー（サムネイル生成・書き出し）
│   ├── core/                   # GUI 非依存ロジック
│   │   ├── document.py         # PdfFile（開く・レンダリング）・PageItem・PDFIUM_LOCK・PDF 収集
│   │   ├── rotation.py         # 回転値の正規化・適用
│   │   ├── naming.py           # 出力フォルダ/ファイル名の決定（連番・上書き回避）
│   │   └── exporter.py         # 上記を束ねる・進捗/キャンセル
│   └── ui/
│       ├── theme.py            # ImageToPdf と共通のダークテーマ
│       ├── strings.py          # UI 文言の一元管理
│       ├── widgets.py          # ドロップ領域・アイコン描画など
│       ├── imaging.py          # PIL → QImage 変換
│       ├── page_grid.py        # サムネイル一覧（PageModel + 描画デリゲート + QListView）
│       ├── preview_dialog.py   # 拡大プレビュー
│       └── main_window.py
├── tests/
├── build/                      # *.spec / installer.iss / build.ps1
└── resources/                  # app.ico
```

## 開発コマンド

**PC に Python をインストールしない方針。** Python 本体は `tools\setup.ps1` が uv 経由で
プロジェクト内の `.tools\` に置き、`.venv\` を作る（PATH・レジストリは変更しない）。
`py` / `python` コマンドは PC に無いので、必ず `.venv\Scripts\python.exe` を直接使う。
uv を直接呼ぶときは先に `tools\env.ps1` を dot-source して、書き込み先を `.tools\` に向けること。

```powershell
powershell -ExecutionPolicy Bypass -File tools\setup.ps1   # 環境準備（初回）
.\.venv\Scripts\python.exe run.py                          # 起動
.\.venv\Scripts\python.exe -m pytest                       # テスト
powershell -ExecutionPolicy Bypass -File build\build.ps1   # dist\ に exe とポータブル版 zip
```

配布物は `build.ps1 -Installer` で `dist\` にインストーラー（`PdfToPng-Setup-<ver>.exe`）と
ポータブル版 zip の両方を作る。Inno Setup も `tools\setup-inno.ps1` で `.tools\innosetup` に
ポータブル展開したものを使う（PC にはインストールしない）。
インストーラーの AppId（`build\installer.iss`）は上書きアップデートの判定に使うので変更しない。
バージョンは `src\pdftopng\__init__.py` の `__version__` が唯一の正（pyproject.toml も合わせて更新）。

## コーディング規約

- コメント・docstring・UI 文言は日本語。UI 文言は `ui/strings.py` に集約する
- 型ヒントを付ける。パスは `pathlib.Path` で扱う
- Windows の日本語パス・スペースを含むパスで動作すること
- ソースファイルは UTF-8（BOM なし）で保存する
- `core/` に変更を入れたら対応する pytest を追加・更新し、`pytest` が通ることを確認する
