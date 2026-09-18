param(
    [Parameter(Mandatory=$true)]
    [string]$BlenderExe
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$SourceDir = Join-Path $RepoRoot "blender_extension"
$DistDir = Join-Path $RepoRoot "dist"
New-Item -ItemType Directory -Force -Path $DistDir | Out-Null

& $BlenderExe --command extension validate $SourceDir
& $BlenderExe --command extension build --source-dir $SourceDir --output-dir $DistDir
