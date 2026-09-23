# ============================================================================
#  Render the demo pages used by the built-in sample under demo/.
#
#  Why this exists
#      The repository ships no textbook content, so a fresh clone has nothing to
#      display.  This renders a few synthetic "textbook" pages whose text is
#      either public domain (the opening of Don Quijote) or written for this
#      project, so that anyone can clone the repo, run `python serve.py` and
#      immediately see the reader working - and so that the pipeline can be
#      shown running on a book it has never seen.
#
#  Input format
#      demo/source/demo_content.txt - plain pipe-separated lines, NOT JSON.
#      ConvertFrom-Json PSCustomObjects behave unpredictably under Windows
#      PowerShell 5.1 when accessed from command/argument positions: the value
#      silently comes back empty and a whole column of text vanishes without an
#      error.  Plain string arrays from -split have no such surprises.
#      See the header of that file for the field layout.
#
#  All text lives in the .txt file rather than here because Windows PowerShell
#  5.1 reads .ps1 files using the console code page and would mangle non-ASCII.
#
#  Usage:  powershell -ExecutionPolicy Bypass -File tools/make_demo_pages.ps1
# ============================================================================
param(
    [string]$Content = "",
    [string]$OutDir = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
if (-not $Content) { $Content = Join-Path $root "demo\source\demo_content.txt" }
if (-not $OutDir) { $OutDir = Join-Path $root "demo\pages" }

Add-Type -AssemblyName PresentationCore
Add-Type -AssemblyName PresentationFramework
Add-Type -AssemblyName WindowsBase

$PAGE_W = 1600
$PAGE_H = 2263
$MARGIN = 120
$SCALE = 1.30          # sizes in the content file are for a 1240px-wide design

$typeface = New-Object System.Windows.Media.Typeface("Microsoft YaHei")
$black = [System.Windows.Media.Brushes]::Black
$grey = New-Object System.Windows.Media.SolidColorBrush([System.Windows.Media.Color]::FromRgb(90, 90, 90))
$culture = [System.Globalization.CultureInfo]::GetCultureInfo('es-ES')

# Build a FormattedText from an already-resolved string.
# Every caller must pass a plain [string] variable, never a property expression.
function New-FT {
    param([string]$T, [double]$EmSize, $Brush, [double]$MaxW)
    $f = New-Object System.Windows.Media.FormattedText(
        $T, $culture,
        [System.Windows.FlowDirection]::LeftToRight,
        $typeface, ($EmSize * $SCALE), $Brush, 1.0)
    if ($MaxW -gt 0) { $f.MaxTextWidth = $MaxW }
    return $f
}

$lines = [System.IO.File]::ReadAllLines($Content, [System.Text.Encoding]::UTF8)
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Force -Path $OutDir | Out-Null }

$pages = @()
$cur = $null
foreach ($raw in $lines) {
    $line = $raw.Trim()
    if ($line.Length -eq 0) { continue }
    if ($line.StartsWith("#")) { continue }
    $f = $line -split '\|'
    $kind = $f[0]
    if ($kind -eq "PAGE") {
        $title = ""
        if ($f.Length -gt 1) { $title = $f[1] }
        $cur = @{ title = $title; blocks = @() }
        $pages += $cur
        continue
    }
    if ($null -eq $cur) { continue }
    $cur.blocks += , $f
}

$pageNo = 0
foreach ($page in $pages) {
    $pageNo++
    $dv = New-Object System.Windows.Media.DrawingVisual
    $dc = $dv.RenderOpen()

    $bg = New-Object System.Windows.Rect(0, 0, $PAGE_W, $PAGE_H)
    $dc.DrawRectangle([System.Windows.Media.Brushes]::White, $null, $bg)

    $y = [double]$MARGIN
    $contentW = $PAGE_W - 2 * $MARGIN

    foreach ($blk in $page.blocks) {
        $kind = [string]$blk[0]
        $sz = 25.0
        # 只有这些块的第三个字段是字号；V 行的第三个字段是词性（m. / adj. …），
        # 对它做 [double] 转换会直接抛异常。
        if (($kind -eq "H" -or $kind -eq "S" -or $kind -eq "P" -or
             $kind -eq "Z" -or $kind -eq "I") -and $blk.Length -gt 2 -and $blk[2]) {
            $sz = [double]$blk[2]
        }
        $txt = ""
        if ($blk.Length -gt 1) { $txt = [string]$blk[1] }

        switch ($kind) {
            "H" {
                $ft = New-FT $txt $sz $black $contentW
                $dc.DrawText($ft, (New-Object System.Windows.Point($MARGIN, $y)))
                $y += $ft.Height + 18
            }
            "S" {
                $ft = New-FT $txt $sz $grey $contentW
                $dc.DrawText($ft, (New-Object System.Windows.Point($MARGIN, $y)))
                $y += $ft.Height + 14
            }
            "R" {
                $y += 8
                $p1 = New-Object System.Windows.Point($MARGIN, $y)
                $p2 = New-Object System.Windows.Point(($PAGE_W - $MARGIN), $y)
                $dc.DrawLine((New-Object System.Windows.Media.Pen($grey, 2)), $p1, $p2)
                $y += 18
            }
            "P" {
                $ft = New-FT $txt $sz $black $contentW
                $dc.DrawText($ft, (New-Object System.Windows.Point($MARGIN, $y)))
                $y += $ft.Height + 20
            }
            "Z" {
                $ft = New-FT $txt $sz $black $contentW
                $dc.DrawText($ft, (New-Object System.Windows.Point($MARGIN, $y)))
                $y += $ft.Height + 14
            }
            "I" {
                $ft = New-FT $txt $sz $black $contentW
                $dc.DrawText($ft, (New-Object System.Windows.Point($MARGIN, $y)))
                $y += $ft.Height + 12
            }
            "SP" { $y += 24 }
            "V" {
                # three columns, like a real vocabulary table:
                #   word            pos.      meaning
                # All three must sit on the SAME side of the page midline: the
                # extractor separates side-by-side tables by that midline, so a
                # column straddling it gets cut in half and loses its meanings.
                $esT = ""
                $posT = ""
                $zhT = ""
                if ($blk.Length -gt 1) { $esT = [string]$blk[1] }
                if ($blk.Length -gt 2) { $posT = [string]$blk[2] }
                if ($blk.Length -gt 3) { $zhT = [string]$blk[3] }
                $fEs = New-FT $esT 25 $black 420
                $fPos = New-FT $posT 25 $grey 120
                $fZh = New-FT $zhT 25 $black 300
                $dc.DrawText($fEs, (New-Object System.Windows.Point($MARGIN, $y)))
                $dc.DrawText($fPos, (New-Object System.Windows.Point(560, $y)))
                $dc.DrawText($fZh, (New-Object System.Windows.Point(700, $y)))
                $h = [Math]::Max($fEs.Height, [Math]::Max($fPos.Height, $fZh.Height))
                $y += $h + 10
            }
            default { }
        }
    }

    $ftn = New-FT ([string]$pageNo) 20 $grey 0
    $px = ($PAGE_W - $ftn.Width) / 2
    $dc.DrawText($ftn, (New-Object System.Windows.Point($px, ($PAGE_H - 90))))

    $dc.Close()

    $rtb = New-Object System.Windows.Media.Imaging.RenderTargetBitmap(
        $PAGE_W, $PAGE_H, 96, 96, [System.Windows.Media.PixelFormats]::Pbgra32)
    $rtb.Render($dv)

    $enc = New-Object System.Windows.Media.Imaging.JpegBitmapEncoder
    $enc.QualityLevel = 88
    $enc.Frames.Add([System.Windows.Media.Imaging.BitmapFrame]::Create($rtb))

    $out = Join-Path $OutDir ("page_{0:d4}.jpg" -f $pageNo)
    $fs = [System.IO.File]::Create($out)
    try { $enc.Save($fs) } finally { $fs.Close() }

    $kb = [math]::Round((Get-Item $out).Length / 1KB, 1)
    Write-Output ("  page {0}  {1}x{2}  {3} KB  [{4}]" -f $pageNo, $PAGE_W, $PAGE_H, $kb, $page.title)
}

Write-Output ("wrote {0} demo pages to {1}" -f $pageNo, $OutDir)
