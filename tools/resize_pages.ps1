# Windows Imaging Component (WIC / WPF) JPEG resizer - no external tools needed.
# Usage: powershell -File resize_pages.ps1 -InDir <dir> -OutDir <dir> -MaxWidth 1400 -Quality 78
param(
    [Parameter(Mandatory = $true)][string]$InDir,
    [Parameter(Mandatory = $true)][string]$OutDir,
    [int]$MaxWidth = 1400,
    [int]$Quality = 78,
    [int]$Limit = 0
)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName PresentationCore

if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Force -Path $OutDir | Out-Null }

$files = Get-ChildItem -Path $InDir -Filter *.jpg | Sort-Object Name
if ($Limit -gt 0) { $files = $files | Select-Object -First $Limit }
Write-Output ("resizing {0} images -> {1}px wide, q{2}" -f $files.Count, $MaxWidth, $Quality)

$sw = [System.Diagnostics.Stopwatch]::StartNew()
$n = 0
$info = @()
foreach ($f in $files) {
    $fs = [System.IO.File]::Open($f.FullName, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
    try {
        $dec = New-Object System.Windows.Media.Imaging.JpegBitmapDecoder($fs,
            [System.Windows.Media.Imaging.BitmapCreateOptions]::PreservePixelFormat,
            [System.Windows.Media.Imaging.BitmapCacheOption]::OnLoad)
        $frame = $dec.Frames[0]
        $ow = $frame.PixelWidth; $oh = $frame.PixelHeight
        $scale = [Math]::Min(1.0, [double]$MaxWidth / [double]$ow)
        $tw = [int][Math]::Round($ow * $scale); $th = [int][Math]::Round($oh * $scale)

        if ($scale -lt 1.0) {
            $st = New-Object System.Windows.Media.ScaleTransform($scale, $scale)
            $tb = New-Object System.Windows.Media.Imaging.TransformedBitmap($frame, $st)
            $src2 = $tb
        } else {
            $src2 = $frame
        }

        $enc = New-Object System.Windows.Media.Imaging.JpegBitmapEncoder
        $enc.QualityLevel = $Quality
        $enc.Frames.Add([System.Windows.Media.Imaging.BitmapFrame]::Create($src2))
        $outPath = Join-Path $OutDir $f.Name
        $os = [System.IO.File]::Create($outPath)
        try { $enc.Save($os) } finally { $os.Close() }
        $info += [pscustomobject]@{ file = $f.Name; ow = $ow; oh = $oh; w = $tw; h = $th }
    } finally { $fs.Close() }

    $n++
    if ($n % 25 -eq 0) { Write-Output ("  {0}/{1}  {2:N1}s" -f $n, $files.Count, $sw.Elapsed.TotalSeconds) }
}
$info | ConvertTo-Json -Depth 3 | Set-Content -Path (Join-Path $OutDir "_sizes.json") -Encoding UTF8
Write-Output ("done {0} images in {1:N1}s" -f $n, $sw.Elapsed.TotalSeconds)
