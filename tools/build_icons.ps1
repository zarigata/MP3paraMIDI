param(
    [string]$Src = "assets\master.svg",
    [string]$Out = "assets\icons"
)

# Fail loudly when a command errors so CI can detect issues.
$ErrorActionPreference = 'Stop'

# Ensure required tooling is available.
if (-not (Get-Command inkscape -ErrorAction SilentlyContinue)) {
    Write-Error "Inkscape is required but not found in PATH."
}

if (-not (Get-Command magick -ErrorAction SilentlyContinue)) {
    Write-Error "ImageMagick (magick) is required but not found in PATH."
}

$pngDir = Join-Path $Out 'png'
$icoDir = Join-Path $Out 'ico'

$pngSizes = 16,32,48,64,128,256,512,1024
$icoSizes = 16,24,32,48,64,128,256

# Prepare output directories and clear previously generated assets.
New-Item -ItemType Directory -Force -Path $pngDir | Out-Null
New-Item -ItemType Directory -Force -Path $icoDir | Out-Null

Get-ChildItem $pngDir -Filter '*.png' -ErrorAction SilentlyContinue | Remove-Item -Force
Get-ChildItem $icoDir -Filter '*.ico' -ErrorAction SilentlyContinue | Remove-Item -Force

# Export PNG renditions at all requested resolutions.
foreach ($size in $pngSizes) {
    $pngPath = Join-Path $pngDir "icon_$size.png"
    & inkscape $Src --export-type=png --export-filename=$pngPath -w $size -h $size
}

# Gather PNG paths for bundling into a single ICO.
$icoInputs = @()
foreach ($size in $icoSizes) {
    $pngPath = Join-Path $pngDir "icon_$size.png"
    if (Test-Path $pngPath) {
        $icoInputs += $pngPath
    }
}

if ($icoInputs.Count -eq 0) {
    Write-Error "No ICO source images were generated."
}

$icoOut = Join-Path $icoDir 'mp3paramidi.ico'
& magick convert @icoInputs -define icon:auto-resize -colors 256 $icoOut

Write-Output "Icons generated in $Out"
