"""UI 文言の一元管理。"""

TAGLINE = "PDF をページごとに PNG へ。スキャンで逆さま・横向きになったページもここで直せます。"

# --- ドロップ領域 ----------------------------------------------------------
DROP_TITLE = "PDF をドロップ"
DROP_SUB = "またはクリックしてファイルを選択（フォルダのドロップも可）"
DROP_FORMATS = "PDF ・ 複数ファイル対応"

# --- ツールバー ------------------------------------------------------------
BTN_ADD = "PDF を追加…"
BTN_CLEAR = "すべてクリア"
BTN_ROT_LEFT = "左に90°"
BTN_ROT_RIGHT = "右に90°"
BTN_ROT_180 = "180°"
BTN_ROT_RESET = "回転をリセット"
TIP_ROT_LEFT = "選択ページを左（反時計回り）に 90° 回転  [←]"
TIP_ROT_RIGHT = "選択ページを右（時計回り）に 90° 回転  [→]"
TIP_ROT_180 = "選択ページを 180° 回転  [R]"
TIP_ROT_RESET = "選択ページの回転を元に戻す"

COUNT_PAGES = "{n} ページ"
COUNT_ROTATED = "回転 {n}"
COUNT_SELECTED = "{n} 選択中"

# --- コンテキストメニュー --------------------------------------------------
MENU_PREVIEW = "拡大表示"
MENU_SELECT_ALL = "すべて選択"

# --- 設定 ------------------------------------------------------------------
FIELD_DPI = "解像度"
DPI_HINT = "300dpi 推奨（数値が大きいほど高精細・大容量）"
FIELD_OUTPUT = "出力先"
OUT_SAME = "PDF と同じ場所"
OUT_CUSTOM = "フォルダを指定"
BTN_PICK_OUT = "選択…"
OUT_PREFIX = "出力先: {path}"
OUT_SAME_HINT = "PDF と同じ場所に「PDF 名」のフォルダを作って保存します（既存フォルダは上書きしません）"

# --- アクション ------------------------------------------------------------
BTN_OPEN_OUTPUT = "出力フォルダを開く"
BTN_CANCEL = "キャンセル"
BTN_START = "PNG に書き出す"

# --- プレビュー ------------------------------------------------------------
PREVIEW_TITLE = "プレビュー"
PREVIEW_PAGE = "{name}   {page} / {count} ページ"
PREVIEW_ROTATION = "回転 {deg}°"
PREVIEW_PREV = "前へ"
PREVIEW_NEXT = "次へ"
PREVIEW_CLOSE = "閉じる"
PREVIEW_LOADING = "読み込み中…"
PREVIEW_ERROR = "表示できません: {message}"
PREVIEW_KEYS = "← → 回転 ／ R 180° ／ ↑ ↓ ページ移動 ／ Esc 閉じる"

# --- ステータス ------------------------------------------------------------
STATUS_IDLE = "PDF を追加してください。"
STATUS_LOADING = "サムネイルを読み込み中… {done} / {total}"
STATUS_READY = "← → で回転 ／ R で 180° ／ ↑ ↓ でページ移動 ／ ダブルクリックで拡大"
STATUS_STARTED = "書き出しを開始しています…"
STATUS_PROGRESS = "書き出し中 {done} / {total}  {name}"
STATUS_CANCELLING = "キャンセルしています…"
STATUS_DONE = "完了: PNG を {n} 枚書き出しました。"
STATUS_CANCELLED = "キャンセルしました（{n} 枚書き出し済み）。"
STATUS_ERROR = "エラーで中断しました。"
STATUS_CLOSING = "処理の停止を待っています…"

# --- ダイアログ ------------------------------------------------------------
DLG_PICK_PDF = "PDF を選択"
DLG_PDF_FILTER = "PDF ファイル (*.pdf)"
DLG_PICK_OUTPUT = "出力先フォルダを選択"

WARN_NO_PDF = "PDF ファイルが見つかりませんでした。"
WARN_DUPLICATE = "{n} 件は読み込み済みのためスキップしました。"
WARN_NO_PAGES = "書き出すページがありません。PDF を追加してください。"
WARN_NO_OUTPUT = "出力先フォルダを選択してください。"
WARN_LOAD_FAILED = "次の PDF を読み込めませんでした。\n\n{items}"
CONFIRM_CLEAR = "読み込んだページと回転の設定をすべてクリアしますか？"
CONFIRM_EXIT = "書き出し中です。中断して終了しますか？"
ERROR_DIALOG = "書き出し中にエラーが発生しました。\n\n{message}"

SUMMARY_DONE = "PNG を {n} 枚書き出しました。"
SUMMARY_CANCELLED = "キャンセルしました。"
SUMMARY_DIRS = "保存先:"
SUMMARY_ERRORS = "エラー（{n} 件）:"
SUMMARY_MORE = "…ほか {n} 件"
