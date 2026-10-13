<#
.SYNOPSIS
    重建 quant 项目的虚拟环境并安装依赖（Python 3.11）。

.DESCRIPTION
    步骤：
      1. 定位 Python 3.11（优先 .python/python/python.exe，其次 PATH）
      2. 创建 .venv
      3. 确保 venv 内可用 pip / setuptools / wheel
      4. 安装 tools/sandbox/sitecustomize.py（沙箱兼容补丁）
      5. 安装 requirements.txt
      6. 以可编辑模式安装本项目，提供 quant 命令

    兼容 Windows PowerShell 5.1 与 PowerShell 7+。

.NOTES
    为什么关闭构建隔离（--no-build-isolation）：
        pip 的构建隔离会在临时目录里再建一个虚拟环境，在受限环境下会卡住；
        这里先保证 venv 内有 setuptools + wheel，然后关闭构建隔离。
    为什么强制重装 setuptools：
        ensurepip 失败时需要从基础解释器复制 pip/setuptools，
        复制出来的包可能缺少 _distutils_hack 等顶层模块，导致构建后端不可用。

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1
    scripts\bootstrap.bat
#>
[CmdletBinding()]
param(
    [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Get-PythonTag {
    param([string]$Exe)
    try {
        $out = & $Exe -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -eq 0 -and $out) { return ($out | Select-Object -First 1).Trim() }
    } catch { }
    return $null
}

function Resolve-Python {
    param([string]$Explicit)
    $candidates = @()
    if ($Explicit) { $candidates += $Explicit }
    $candidates += (Join-Path $root ".python/python/python.exe")
    $candidates += (Join-Path $root ".python/python.exe")
    $candidates += "python"
    $candidates += "py"

    foreach ($candidate in $candidates) {
        if ($candidate -match "[\\/]") {
            if (-not (Test-Path $candidate)) { continue }
        } else {
            if (-not (Get-Command $candidate -ErrorAction SilentlyContinue)) { continue }
        }
        $tag = Get-PythonTag -Exe $candidate
        if ($tag -eq "3.11") {
            Write-Host "使用 Python: $candidate ($tag)"
            return $candidate
        } elseif ($tag) {
            Write-Host "跳过 $candidate (版本 $tag，需要 3.11)"
        }
    }
    throw "未找到 Python 3.11。请安装后通过 -PythonExe 指定，例如： powershell -File scripts\bootstrap.ps1 -PythonExe C:\Python311\python.exe"
}

$python = Resolve-Python -Explicit $PythonExe

if (-not (Test-Path ".venv")) {
    Write-Host "创建虚拟环境 .venv ..."
    & $python -m venv .venv
}

$venvPython = Join-Path $root ".venv/Scripts/python.exe"
$venvSite = Join-Path $root ".venv/Lib/site-packages"

# venv 内没有 pip 时（受限环境下 ensurepip 可能失败），从基础解释器复制
& $venvPython -m pip --version *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "venv 缺少 pip，从基础解释器复制 ..."
    $baseSite = & $python -c "import sysconfig; print(sysconfig.get_paths()['purelib'])"
    $baseSite = ($baseSite | Select-Object -First 1).Trim()
    New-Item -ItemType Directory -Force $venvSite | Out-Null
    Get-ChildItem $baseSite | Where-Object { $_.Name -match "^(pip|setuptools)" } | ForEach-Object {
        Copy-Item -Recurse -Force $_.FullName $venvSite
    }
}

Write-Host "安装 pip / setuptools / wheel ..."
& $venvPython -m pip install --no-cache-dir --upgrade pip wheel
& $venvPython -m pip install --no-cache-dir --force-reinstall --no-deps setuptools

$patch = Join-Path $root "tools/sandbox/sitecustomize.py"
if (Test-Path $patch) {
    Copy-Item -Force $patch (Join-Path $venvSite "sitecustomize.py")
    Write-Host "已应用沙箱兼容补丁 sitecustomize.py"
}

Write-Host "安装依赖（可能需要几分钟）..."
& $venvPython -m pip install --no-cache-dir --no-build-isolation -r requirements.txt

Write-Host "以可编辑模式安装本项目 ..."
& $venvPython -m pip install --no-cache-dir --no-deps --no-build-isolation -e .

Write-Host ""
Write-Host "完成。验证："
Write-Host "  .venv\Scripts\python.exe -m quant info"
Write-Host "  .venv\Scripts\python.exe -m pytest"
