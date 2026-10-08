# Inno Setup 6 をプロジェクトフォルダ内（.tools\innosetup）にポータブル展開する。
#
# Inno Setup 自身のセットアップのポータブルモード（/PORTABLE=1）を使うので、
# スタートメニュー・アンインストール情報・レジストリには登録しない。
# 不要になったら .tools\innosetup を削除すれば元通り。
#
# 使い方:  powershell -ExecutionPolicy Bypass -File tools\setup-inno.ps1

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\env.ps1"

$InnoVersion = "6.7.3"
$InnoDir = Join-Path $ToolsDir "innosetup"
$Iscc = Join-Path $InnoDir "ISCC.exe"

if (Test-Path $Iscc) {
    Write-Host "Inno Setup は準備済みです: $Iscc"
    return
}

New-Item -ItemType Directory -Force $ToolsDir | Out-Null
$tag = "is-" + ($InnoVersion -replace '\.', '_')
$url = "https://github.com/jrsoftware/issrc/releases/download/$tag/innosetup-$InnoVersion.exe"
$exe = Join-Path $ToolsDir "innosetup-$InnoVersion.exe"
Write-Host "Inno Setup $InnoVersion をダウンロード中..."
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Invoke-WebRequest -Uri $url -OutFile $exe -UseBasicParsing

$innoArgs = @(
    "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-",
    "/CURRENTUSER", "/PORTABLE=1", "/NOICONS", "/TASKS=",
    "/DIR=`"$InnoDir`""
)
$p = Start-Process -FilePath $exe -ArgumentList $innoArgs -Wait -PassThru
Remove-Item $exe
if ($p.ExitCode -ne 0 -or -not (Test-Path $Iscc)) {
    throw "Inno Setup の展開に失敗しました（終了コード $($p.ExitCode)）。"
}
Write-Host "準備完了: $Iscc" -ForegroundColor Green
