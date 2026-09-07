param(
    [string]$Python = ".\.venv\Scripts\python.exe"
)

$ErrorActionPreference = "Stop"
$projectDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonPath = if ([System.IO.Path]::IsPathRooted($Python)) {
    $Python
} else {
    Join-Path $projectDirectory $Python
}

if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw "找不到打包用 Python：$pythonPath"
}

Push-Location $projectDirectory
try {
    & $pythonPath -m PyInstaller --noconfirm --clean "mole_game.spec"
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller 打包失败，退出代码：$LASTEXITCODE"
    }

    $outputPath = Join-Path $projectDirectory "dist\药材打地鼠.exe"
    if (-not (Test-Path -LiteralPath $outputPath -PathType Leaf)) {
        throw "打包结束，但没有找到输出文件：$outputPath"
    }

    $outputFile = Get-Item -LiteralPath $outputPath
    $hash = Get-FileHash -LiteralPath $outputPath -Algorithm SHA256
    Write-Output "打包完成：$outputPath"
    Write-Output ("文件大小：{0:N2} MiB" -f ($outputFile.Length / 1MB))
    Write-Output "SHA256：$($hash.Hash)"
} finally {
    Pop-Location
}

