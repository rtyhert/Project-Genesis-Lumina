#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Lumina — PowerShell Launcher
.DESCRIPTION
    Build, test, and run Lumina from PowerShell (Windows).
    Equivalent to start.py commands for Windows-native workflows.
.EXAMPLE
    .\start.ps1 run --mock
    .\start.ps1 test
    .\start.ps1 proto
    .\start.ps1 check
#>

param(
    [ValidateSet('run','test','lint','proto','install','check','cpp-minimal','clean')]
    [string]$Command = 'run',

    [switch]$Mock,
    [switch]$NoMock,
    [switch]$OpenBrowser,
    [string]$Config
)

$ProjectRoot = Split-Path -Parent $PSScriptRoot
if (-not $ProjectRoot) { $ProjectRoot = $PSScriptRoot }
$LuminaPy = Join-Path $ProjectRoot "lumina-py"

function Get-Python {
    foreach ($c in @('python', 'python3', 'py')) {
        $exe = Get-Command $c -ErrorAction SilentlyContinue
        if ($exe) { return $exe.Source }
    }
    throw "Python not found"
}

function Run-Start {
    $python = Get-Python
    $env:PYTHONPATH = $LuminaPy
    if ($Mock) { $env:LUMINA_MOCK = '1' }
    elseif ($NoMock) { $env:LUMINA_MOCK = '0' }

    Push-Location $LuminaPy
    try {
        $proc = Start-Process -NoNewWindow -PassThru -FilePath $python -ArgumentList @('-m', 'src.main')
        if ($OpenBrowser -and -not $Mock) {
            Start-Sleep -Seconds 3
            Start-Process "http://localhost:8000/"
        } elseif ($OpenBrowser -and $Mock) {
            Write-Host "[start] --open-browser skipped in mock mode (no UI server)"
        }
        $proc.WaitForExit()
    } finally {
        Pop-Location
    }
}

function Run-Test {
    $python = Get-Python
    $env:LUMINA_MOCK = '1'
    Push-Location $LuminaPy
    try {
        & $python -m pytest tests/ -v --tb=short
    } finally {
        Pop-Location
    }
}

function Run-Lint {
    $python = Get-Python
    Push-Location $LuminaPy
    try {
        pip install ruff -q
        & $python -m ruff check src/ tests/
    } finally {
        Pop-Location
    }
}

function Run-Proto {
    $protoBat = Join-Path $ProjectRoot "lumina-proto" "build_proto.bat"
    if (Test-Path $protoBat) {
        Push-Location (Split-Path -Parent $protoBat)
        try {
            & $protoBat
        } finally {
            Pop-Location
        }
    } else {
        Write-Error "build_proto.bat not found"
    }
}

function Run-Install {
    $python = Get-Python
    $req = Join-Path $LuminaPy "requirements.txt"
    & $python -m pip install -r $req
}

function Run-Check {
    Write-Host "Lumina Environment Check" -ForegroundColor Cyan
    $checks = @(
        @{Name="Python"; Test={Get-Python}}
        @{Name="FastAPI"; Test={python -c "import fastapi" 2>$null}}
        @{Name="gRPC"; Test={python -c "import grpc" 2>$null}}
        @{Name="Proto stubs"; Test={Test-Path (Join-Path $ProjectRoot "lumina-proto/build/lumina_pb2.py")}}
    )
    foreach ($c in $checks) {
        $ok = & $c.Test
        $s = if ($ok) { "OK" } else { "MISSING" }
        Write-Host "  [$s] $($c.Name)"
    }
}

function Run-CppMinimal {
    $protoBuild = Join-Path $ProjectRoot "lumina-proto" "build"
    if (-not (Test-Path $protoBuild)) {
        Run-Proto
    }
    $cppDir = Join-Path $ProjectRoot "lumina-cpp"
    Push-Location $cppDir
    try {
        cmake -B build -DCMAKE_BUILD_TYPE=Debug -DLUMINA_BUILD_GRPC_ONLY=ON
        cmake --build build --parallel
        if (Test-Path "build/lumina_grpc_check.exe") {
            Write-Host "BUILD OK" -ForegroundColor Green
        }
    } finally {
        Pop-Location
    }
}

function Run-Clean {
    $dirs = @(
        Join-Path $LuminaPy "cache"
        Join-Path $ProjectRoot "lumina-cpp" "build"
        Join-Path $ProjectRoot "lumina-proto" "build"
    )
    foreach ($d in $dirs) {
        if (Test-Path $d) { Remove-Item -Recurse -Force $d }
    }
    Get-ChildItem -Recurse -Filter "__pycache__" -Directory $ProjectRoot -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force
}

switch ($Command) {
    "run"         { Run-Start }
    "test"        { Run-Test }
    "lint"        { Run-Lint }
    "proto"       { Run-Proto }
    "install"     { Run-Install }
    "check"       { Run-Check }
    "cpp-minimal" { Run-CppMinimal }
    "clean"       { Run-Clean }
}
