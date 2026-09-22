$ErrorActionPreference = "Stop"
try {
    [void][Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
    $langs = [Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages
    Write-Output "=== Windows.Media.Ocr available languages ==="
    if ($langs.Count -eq 0) { Write-Output "(none installed)" }
    foreach ($l in $langs) {
        Write-Output ("{0}  |  display={1}  |  native={2}" -f $l.LanguageTag, $l.DisplayName, $l.NativeName)
    }
    Write-Output ("MaxDimension: " + [Windows.Media.Ocr.OcrEngine]::MaxImageDimension)
} catch {
    Write-Output ("OCR ERROR: " + $_.Exception.Message)
}

Write-Output ""
Write-Output "=== OCR language packs in registry ==="
$paths = @(
  "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\OCR",
  "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\OCR"
)
foreach ($p in $paths) {
    if (Test-Path $p) {
        Get-ChildItem $p -Recurse -ErrorAction SilentlyContinue | ForEach-Object { Write-Output ("  " + $_.Name) }
    }
}

Write-Output ""
Write-Output "=== tesseract / other OCR binaries on disk ==="
$cands = @(
  "C:\Program Files\Tesseract-OCR\tesseract.exe",
  "C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
  "C:\Program Files\Microsoft Office\root\Office16\ONENOTE.EXE",
  "C:\Program Files (x86)\Microsoft Office\root\Office16\ONENOTE.EXE"
)
foreach ($c in $cands) { if (Test-Path $c) { Write-Output ("  FOUND: " + $c) } else { Write-Output ("  no: " + $c) } }
