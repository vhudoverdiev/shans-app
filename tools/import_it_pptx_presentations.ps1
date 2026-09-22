$ErrorActionPreference = "Stop"

$sourceRoot = (Get-ChildItem -Path (Join-Path $env:USERPROFILE 'Desktop') -Recurse -Filter 'Day01*.pptx' -File | Select-Object -First 1).Directory.FullName
$projectRoot = Split-Path -Parent $PSScriptRoot
$pdfRoot = Join-Path $projectRoot 'app\static\presentations\python-basics'
$slidesRoot = Join-Path $projectRoot 'app\static\presentation-slides\python-basics'
$startDay = if ($env:IT_START_DAY) { [int]$env:IT_START_DAY } else { 1 }

New-Item -ItemType Directory -Force -Path $pdfRoot, $slidesRoot | Out-Null
$powerPoint = New-Object -ComObject PowerPoint.Application

try {
    Get-ChildItem -LiteralPath $sourceRoot -Filter '*.pptx' -File | ForEach-Object {
        if ($_.Name -notmatch '^Day(\d{2})_') { return }
        $day = [int]$Matches[1]
        if ($day -lt $startDay) { return }
        $deck = $null
        try {
            $deck = $powerPoint.Presentations.Open($_.FullName, $true, $true, $false)
            $pdfPath = Join-Path $pdfRoot ("python_day{0:00}_simple_readable.pdf" -f $day)
            $slideDir = Join-Path $slidesRoot ("day-{0:00}" -f $day)
            if (Test-Path -LiteralPath $slideDir) { Remove-Item -LiteralPath $slideDir -Recurse -Force }
            New-Item -ItemType Directory -Force -Path $slideDir | Out-Null

            $deck.SaveAs($pdfPath, 32)
            $deck.Export($slideDir, 'PNG', 960, 540)
            Get-ChildItem -LiteralPath $slideDir -Filter '*.PNG' | Sort-Object Name | ForEach-Object {
                $number = [int][regex]::Replace($_.BaseName, '[^0-9]', '')
                Rename-Item -LiteralPath $_.FullName -NewName ("slide-{0:00}.png" -f $number)
            }
            Write-Output ("Day {0:00}: {1} slides" -f $day, $deck.Slides.Count)
        }
        finally {
            if ($null -ne $deck) { $deck.Close() }
        }
    }
}
finally {
    $powerPoint.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($powerPoint) | Out-Null
}
