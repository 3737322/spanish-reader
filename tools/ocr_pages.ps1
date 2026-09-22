# Windows.Media.Ocr batch OCR -> JSON (word-level bounding boxes).
# Must run under Windows PowerShell 5.1 (WinRT projection is unavailable in PS7).
# Usage: powershell -File ocr_pages.ps1 -InDir <dir> -OutFile <json> -Langs "en-GB,zh-Hans-CN" [-Limit N]
param(
    [Parameter(Mandatory = $true)][string]$InDir,
    [Parameter(Mandatory = $true)][string]$OutFile,
    [string]$Langs = "en-GB",
    [int]$Limit = 0,
    [int]$Start = 0
)
$ErrorActionPreference = "Stop"

[void][Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
[void][Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType = WindowsRuntime]
[void][Windows.Graphics.Imaging.SoftwareBitmap, Windows.Foundation, ContentType = WindowsRuntime]
[void][Windows.Storage.StorageFile, Windows.Foundation, ContentType = WindowsRuntime]
[void][Windows.Globalization.Language, Windows.Foundation, ContentType = WindowsRuntime]
Add-Type -AssemblyName System.Runtime.WindowsRuntime

$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
        $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    })[0]

function Await($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    [void]$netTask.Wait(-1)
    $netTask.Result
}

# ---- build one engine per requested language ----
$engines = @()
foreach ($tag in ($Langs -split ',')) {
    $tag = $tag.Trim()
    if (-not $tag) { continue }
    $lang = $null
    foreach ($l in [Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages) {
        if ($l.LanguageTag -eq $tag) { $lang = $l; break }
    }
    if ($null -eq $lang) {
        Write-Output ("WARN: OCR language not installed: " + $tag)
        continue
    }
    $e = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang)
    if ($null -eq $e) { Write-Output ("WARN: cannot create engine for " + $tag); continue }
    $engines += [pscustomobject]@{ tag = $tag; engine = $e }
}
if ($engines.Count -eq 0) { throw "no usable OCR engine" }
Write-Output ("engines: " + (($engines | ForEach-Object { $_.tag }) -join ", "))

$files = Get-ChildItem -Path $InDir -Filter *.jpg | Sort-Object Name
if ($Start -gt 0) { $files = $files | Select-Object -Skip $Start }
if ($Limit -gt 0) { $files = $files | Select-Object -First $Limit }
Write-Output ("pages to OCR: " + $files.Count)

$sw = [System.Diagnostics.Stopwatch]::StartNew()
$records = New-Object System.Collections.ArrayList
$n = 0

foreach ($f in $files) {
    $sf = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($f.FullName)) ([Windows.Storage.StorageFile])
    $stream = Await ($sf.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
    try {
        $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
        $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
        $pw = $bitmap.PixelWidth; $ph = $bitmap.PixelHeight

        $perLang = @{}
        foreach ($pair in $engines) {
            $res = Await ($pair.engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
            $lines = New-Object System.Collections.ArrayList
            foreach ($line in $res.Lines) {
                $words = New-Object System.Collections.ArrayList
                foreach ($w in $line.Words) {
                    $r = $w.BoundingRect
                    [void]$words.Add([pscustomobject]@{
                            t = $w.Text
                            x = [Math]::Round($r.X, 1); y = [Math]::Round($r.Y, 1)
                            w = [Math]::Round($r.Width, 1); h = [Math]::Round($r.Height, 1)
                        })
                }
                [void]$lines.Add([pscustomobject]@{ text = $line.Text; words = $words })
            }
            $perLang[$pair.tag] = $lines
        }
        $bitmap.Dispose()

        [void]$records.Add([pscustomobject]@{
                file = $f.Name; w = $pw; h = $ph; ocr = $perLang
            })
    } finally { $stream.Dispose() }

    $n++
    if ($n % 10 -eq 0) { Write-Output ("  {0}/{1}  {2:N1}s" -f $n, $files.Count, $sw.Elapsed.TotalSeconds) }
}

$dir = Split-Path $OutFile
if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
$json = $records | ConvertTo-Json -Depth 6 -Compress
[System.IO.File]::WriteAllText($OutFile, $json, (New-Object System.Text.UTF8Encoding($false)))
Write-Output ("wrote {0} page records -> {1}  ({2:N1}s, {3:N0} KB)" -f $records.Count, $OutFile, $sw.Elapsed.TotalSeconds, ((Get-Item $OutFile).Length / 1KB))
