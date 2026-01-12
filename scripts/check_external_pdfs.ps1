$ErrorActionPreference = 'Stop'

$paths = @(
    "c:\Users\issoufou abdou\Desktop\DOSSIERS CLIENTS\Dossiers presidence\garage  ex SNTN\HANGR69.pdf",
    "c:\Users\issoufou abdou\Desktop\DOSSIERS CLIENTS\Dossiers presidence\garage  ex SNTN\LOCAL ONDULAIRE.pdf",
    "c:\Users\issoufou abdou\Desktop\DOSSIERS CLIENTS\Dossiers presidence\garage  ex SNTN\plan de masse SNTN3.pdf",
    "c:\Users\issoufou abdou\Desktop\DOSSIERS CLIENTS\Dossiers presidence\garage  ex SNTN\plan de masse.pdf",
    "c:\Users\issoufou abdou\Desktop\DOSSIERS CLIENTS\Dossiers presidence\garage  ex SNTN\TRANDFO1.pdf",
    "c:\Users\issoufou abdou\Desktop\DOSSIERS CLIENTS\Dossiers presidence\garage  ex SNTN\grand hangar1.pdf",
    "c:\Users\issoufou abdou\Desktop\DOSSIERS CLIENTS\Dossiers presidence\garage  ex SNTN\grand hangar2.pdf",
    "c:\Users\issoufou abdou\Desktop\DOSSIERS CLIENTS\Dossiers presidence\garage  ex SNTN\grand hangar6.pdf",
    "c:\Users\issoufou abdou\Desktop\DOSSIERS CLIENTS\Dossiers presidence\garage  ex SNTN\grand hangar7.pdf",
    "c:\Users\issoufou abdou\Desktop\DOSSIERS CLIENTS\Dossiers presidence\garage  ex SNTN\grand hangar26.pdf",
    "c:\Users\issoufou abdou\Desktop\DOSSIERS CLIENTS\Dossiers presidence\garage  ex SNTN\grand hangar-VUES.pdf",
    "c:\Users\issoufou abdou\Desktop\DOSSIERS CLIENTS\Dossiers presidence\garage  ex SNTN\hangar 4.pdf",
    "c:\Users\issoufou abdou\Desktop\DOSSIERS CLIENTS\Dossiers presidence\garage  ex SNTN\hangar de lavage6.pdf",
    "c:\Users\issoufou abdou\Desktop\DOSSIERS CLIENTS\Dossiers presidence\garage  ex SNTN\hangar1.pdf",
    "c:\Users\issoufou abdou\Desktop\DOSSIERS CLIENTS\Dossiers presidence\garage  ex SNTN\hangar2.pdf",
    "c:\Users\issoufou abdou\Desktop\DOSSIERS CLIENTS\Dossiers presidence\garage  ex SNTN\hangar3.pdf",
    "c:\Users\issoufou abdou\Desktop\DOSSIERS CLIENTS\Dossiers presidence\garage  ex SNTN\hangar15.pdf",
    "c:\Users\issoufou abdou\Desktop\DOSSIERS CLIENTS\Dossiers presidence\garage  ex SNTN\hangar16.pdf",
    "c:\Users\issoufou abdou\Desktop\DOSSIERS CLIENTS\Dossiers presidence\garage  ex SNTN\hangar89.pdf"
)

$items = foreach ($p in $paths) {
    if (Test-Path -LiteralPath $p) {
        $i = Get-Item -LiteralPath $p
        [pscustomobject]@{
            Exists   = $true
            Name     = $i.Name
            SizeMB   = [math]::Round($i.Length / 1MB, 2)
            FullName = $i.FullName
        }
    }
    else {
        [pscustomobject]@{
            Exists   = $false
            Name     = [IO.Path]::GetFileName($p)
            SizeMB   = $null
            FullName = $p
        }
    }
}

$missing = $items | Where-Object { -not $_.Exists }
$present = $items | Where-Object { $_.Exists }
$totalBytes = ($present | ForEach-Object { (Get-Item -LiteralPath $_.FullName).Length } | Measure-Object -Sum).Sum
$totalMB = if ($totalBytes) { [math]::Round($totalBytes / 1MB, 2) } else { 0 }

$sorted = $items | Sort-Object -Property @{ Expression = { $_.Exists }; Descending = $true }, @{ Expression = { $_.Name }; Descending = $false }

$reportPath = Join-Path $PSScriptRoot 'external_pdfs_report.txt'
$lines = New-Object System.Collections.Generic.List[string]

$lines.Add(("Found: {0} / {1} PDFs" -f $present.Count, $items.Count))
$lines.Add(("Missing: {0}" -f $missing.Count))
$lines.Add(("Total size: {0} MB" -f $totalMB))
$lines.Add('')

$lines.Add("Exists\tSizeMB\tName\tFullName")
foreach ($row in $sorted) {
    $size = if ($null -eq $row.SizeMB) { "" } else { $row.SizeMB }
    $lines.Add(("{0}\t{1}\t{2}\t{3}" -f $row.Exists, $size, $row.Name, $row.FullName))
}

if ($missing.Count -gt 0) {
    $lines.Add('')
    $lines.Add('Missing files (full paths):')
    foreach ($m in $missing) {
        $lines.Add($m.FullName)
    }
}

$lines | Set-Content -LiteralPath $reportPath -Encoding UTF8

Write-Output ("Wrote report: {0}" -f $reportPath)
