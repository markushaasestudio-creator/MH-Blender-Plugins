param(
    [string]$PythonVersion = "3.13",
    [switch]$InstallTesseract
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Venv = Join-Path $RepoRoot ".venv-analyzer"
$Requirements = Join-Path $RepoRoot "blender_extension\requirements-analyzer.txt"

if (-not (Test-Path (Join-Path $Venv "Scripts\python.exe"))) {
    Write-Host "Creating analyzer environment: $Venv"
    py "-$PythonVersion" -m venv $Venv
} else {
    Write-Host "Reusing analyzer environment: $Venv"
}

$Python = Join-Path $Venv "Scripts\python.exe"
& $Python -m pip install --upgrade pip
& $Python -m pip install -r $Requirements

if ($InstallTesseract) {
    $Tesseract = "C:\Program Files\Tesseract-OCR\tesseract.exe"
    if (-not (Test-Path $Tesseract)) {
        Write-Host "Installing Tesseract OCR with WinGet..."
        winget install --exact --id UB-Mannheim.TesseractOCR --accept-package-agreements --accept-source-agreements
    } else {
        Write-Host "Tesseract already present: $Tesseract"
    }
}

Write-Host ""
Write-Host "Analyzer Python ready:"
Write-Host $Python
Write-Host ""
Write-Host "v0.1.2 adds no mandatory Python packages beyond the v0.1.1 analyzer environment."
Write-Host "The local Ollama integration uses Ollama's REST API and Python's standard library."
