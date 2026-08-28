[CmdletBinding()]
param(
    [switch]$SkipInstall,
    [switch]$SkipTests,
    [switch]$RunVhdTests,
    [switch]$Clean
)

$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$venvPath = Join-Path $projectRoot '.venv-build'
$pythonPath = Join-Path $venvPath 'Scripts\python.exe'

function Assert-ProjectChild([string]$Path) {
    $root = [System.IO.Path]::GetFullPath($projectRoot).TrimEnd('\') + '\'
    $resolved = [System.IO.Path]::GetFullPath($Path)
    if (-not $resolved.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to modify a path outside the project: $resolved"
    }
}

if ($Clean) {
    foreach ($name in @('build', 'dist')) {
        $target = Join-Path $projectRoot $name
        Assert-ProjectChild $target
        if (Test-Path -LiteralPath $target) {
            Remove-Item -LiteralPath $target -Recurse -Force
        }
    }
}

if (-not (Test-Path -LiteralPath $pythonPath)) {
    py -3.13 -m venv $venvPath
}

$version = & $pythonPath -c "import platform, struct; print(platform.python_version()); print(struct.calcsize('P') * 8)"
if ($version[0] -ne '3.13.14' -or $version[1] -ne '64') {
    throw "The locked build requires CPython 3.13.14 x86-64; found $($version -join ' / ')."
}

if (-not $SkipInstall) {
    & $pythonPath -m pip install --disable-pip-version-check --requirement (Join-Path $projectRoot 'requirements-lock.txt')
}

$env:PYTHONPATH = Join-Path $projectRoot 'src'
if (-not $SkipTests) {
    if ($RunVhdTests) { $env:PS2RIPPER_RUN_VHD_TESTS = '1' }
    & $pythonPath -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed; executable was not built.' }
}

$originalPath = $env:PATH
$pythonBase = & $pythonPath -c "import sys; print(sys.base_prefix)"
$env:PATH = @(
    (Join-Path $venvPath 'Scripts'),
    $pythonBase,
    (Join-Path $env:SystemRoot 'System32'),
    $env:SystemRoot
) -join ';'
try {
    & $pythonPath -m PyInstaller --noconfirm --clean (Join-Path $projectRoot 'PS2Ripper.spec')
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed.' }
}
finally {
    $env:PATH = $originalPath
}

$executable = Join-Path $projectRoot 'dist\PS2OPLRipper.exe'
if (-not (Test-Path -LiteralPath $executable)) { throw 'Expected executable was not produced.' }
$hash = Get-FileHash -LiteralPath $executable -Algorithm SHA256
if (-not $env:CI) {
    $process = Start-Process -FilePath $executable -ArgumentList '--self-test' -WindowStyle Hidden -Wait -PassThru
    if ($process.ExitCode -ne 0) { throw "Packaged executable self-test failed with exit code $($process.ExitCode)." }
}
Write-Host "Built: $executable"
Write-Host "SHA-256: $($hash.Hash)"
