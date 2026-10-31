# Сборка YouMusicDownloader.exe (PowerShell)
# Запуск:  powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
#          powershell -ExecutionPolicy Bypass -File .\build_exe.ps1 -Mode onedir   # папка, мгновенный старт
#          powershell -ExecutionPolicy Bypass -File .\build_exe.ps1 -Console        # с консолью, для отладки
#
# Требуется один раз:
#   pip install -U pyinstaller yt-dlp pillow imageio-ffmpeg
# (imageio-ffmpeg нужен только чтобы получить бинарник ffmpeg для вшивания в exe)
# Повторная сборка нужна после обновления yt-dlp: он упаковывается внутрь .exe.

param(
    [switch]$Console,
    [ValidateSet("onefile", "onedir")]
    [string]$Mode = "onefile"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# 1. Иконка (если есть Pillow и файла ещё нет)
if (-not (Test-Path "app_icon.ico")) {
    python make_icon.py
}

# 2. FFmpeg для вшивания внутрь exe
python prepare_ffmpeg.py
if ($LASTEXITCODE -ne 0) {
    throw "Не удалось подготовить vendor\ffmpeg.exe (pip install imageio-ffmpeg)"
}

# 3. Аргументы PyInstaller
$pyiArgs = @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--name", "YouMusicDownloader",
    "--collect-all", "yt_dlp"
)

if ($Mode -eq "onedir") {
    # Папка с exe и DLL — стартует почти мгновенно (нет распаковки при запуске)
    $pyiArgs += "--onedir"
    $distPath = "dist_onedir"
} else {
    $pyiArgs += "--onefile"
    $distPath = "dist"
}

$pyiArgs += @("--distpath", $distPath)

if ($Console) {
    $pyiArgs += "--console"
} else {
    $pyiArgs += "--windowed"
}

if (Test-Path "app_icon.ico") {
    $pyiArgs += @("--icon", "app_icon.ico")
}

# ffmpeg кладётся в корень распаковки сборки (_MEIPASS)
$pyiArgs += @("--add-binary", "vendor\ffmpeg.exe;.")

$pyiArgs += "music_downloader.py"

# 4. Сборка
python @pyiArgs

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller завершился с кодом $LASTEXITCODE"
}

$exe = if ($Mode -eq "onedir") {
    Join-Path $PSScriptRoot "dist_onedir\YouMusicDownloader\YouMusicDownloader.exe"
} else {
    Join-Path $PSScriptRoot "dist\YouMusicDownloader.exe"
}
if (-not (Test-Path $exe)) {
    throw "Не найден результат сборки: $exe"
}

$sizeMb = [math]::Round((Get-Item $exe).Length / 1MB, 1)
$folderMb = [math]::Round(((Get-ChildItem (Split-Path $exe) -Recurse -File | Measure-Object Length -Sum).Sum) / 1MB, 1)
Write-Host ""
Write-Host "Готово: $exe"
Write-Host "Режим: $Mode | exe: $sizeMb МБ | папка целиком: $folderMb МБ"
Write-Host "Проверка: пуск: `"$exe` --selftest`"   (отчёт в selftest.txt рядом с exe)"
