#
# Echter Schreibtest für Claudus, nur für Windows-Testrechner (GitHub Actions).
# Braucht Administratorrechte. Legt eine virtuelle Platte (VHD) an, hängt sie
# ein und schreibt darauf, genau wie auf einen USB-Stick:
#   1. Die Sicherheitsprüfung sperrt die VHD (kein USB) und die Windows-Platte.
#   2. Kleines Testabbild (nicht auf 4096 ausgerichtet) schreiben + zurücklesen.
#   3. Ein manipuliertes Byte wird beim Zurücklesen erkannt.
#   4. Die echte Kairo-ISO laden, Prüfsumme prüfen, schreiben, zurücklesen,
#      Windows erkennt danach die Partitionen der ISO.
#   5. Rufus (Plan B) laden und Signatur prüfen.
#
# NICHT auf deinem PC ausführen, das ist nur für die CI gedacht.

param(
    [Parameter(Mandatory = $true)][string]$WorkDir,
    [switch]$SkipRealIso
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
. (Join-Path $root 'ClaudusLib.ps1')

$script:pass = 0
$script:fail = 0
function Assert-True {
    param([bool]$Condition, [string]$Name)
    if ($Condition) { $script:pass++; Write-Host "ok   $Name" }
    else { $script:fail++; Write-Host "FAIL $Name" -ForegroundColor Red }
}

if (-not $env:GITHUB_ACTIONS) { throw 'Dieser Test läuft nur in GitHub Actions.' }
if (-not (Test-ClaudusAdmin)) { throw 'Braucht Administratorrechte.' }
Write-Host ('PowerShell ' + $PSVersionTable.PSVersion)

New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null
$vhd = Join-Path $WorkDir 'claudus-test.vhd'
if (Test-Path -LiteralPath $vhd) { Remove-Item -LiteralPath $vhd -Force }

function Invoke-DiskPart([string]$Text) {
    $f = Join-Path $WorkDir ('dp-{0}.txt' -f [guid]::NewGuid())
    [IO.File]::WriteAllText($f, $Text, [Text.Encoding]::ASCII)
    $out = & diskpart.exe /s $f 2>&1
    Remove-Item -LiteralPath $f -Force
    if ($LASTEXITCODE -ne 0) { throw ("diskpart: " + ($out -join "`n")) }
}

Invoke-DiskPart ("create vdisk file=`"$vhd`" maximum=2048 type=expandable`r`nselect vdisk file=`"$vhd`"`r`nattach vdisk`r`nexit`r`n")
try {
    Start-Sleep -Seconds 2
    $disk = Get-DiskImage -ImagePath $vhd | Get-Disk
    $n = [int]$disk.Number
    Write-Host ("VHD ist Platte $n, BusType " + (ConvertTo-ClaudusBusType $disk.BusType))
    $dev = Get-ClaudusDevicePath -DiskNumber $n

    # 1. Sicherheitsprüfung
    $info = @(Get-ClaudusDiskInfo -MinBytes 1GB)
    $vInfo = @($info | Where-Object { $_.Number -eq $n })
    Assert-True ($vInfo.Count -eq 1 -and -not $vInfo[0].Ok) 'Sicherheitsprüfung sperrt die VHD (kein USB)'
    $sysNum = (Get-Partition -DriveLetter $env:SystemDrive.Substring(0, 1)).DiskNumber
    Assert-True (-not (@($info | Where-Object { $_.Number -eq $sysNum })[0].Ok)) 'Sicherheitsprüfung sperrt die Windows-Platte'
    Assert-True (@($info | Where-Object { $_.Ok }).Count -eq 0) 'Auf dem Testrechner ist keine Platte freigegeben'

    # 2. Kleines Testabbild, Länge absichtlich nicht durch 4096 teilbar
    $img = Join-Path $WorkDir 'test.img'
    $bytes = New-Object byte[] (9MB + 1536)
    (New-Object Random 42).NextBytes($bytes)
    [IO.File]::WriteAllBytes($img, $bytes)
    $fake = [pscustomobject]@{ Path = $img; Size = [int64]$bytes.Length; Hash = (Get-ClaudusFileSha256 -Path $img) }
    $res = Invoke-ClaudusWriteCore -Iso $fake -DiskNumber $n
    Assert-True $res.Ok 'Testabbild geschrieben und identisch zurückgelesen'

    # 3. Ein Byte auf der Platte ändern, Zurücklesen muss es merken
    Initialize-ClaudusNative
    $fs = [ClaudusNative]::Open($dev, $true)
    try {
        $blk = New-Object byte[] 4096
        [void]$fs.Seek(5MB, 'Begin')
        [void]$fs.Read($blk, 0, 4096)
        $blk[100] = $blk[100] -bxor 0xFF
        [void]$fs.Seek(5MB, 'Begin')
        $fs.Write($blk, 0, 4096)
        $fs.Flush($true)
    } finally { $fs.Dispose() }
    $bad = Get-ClaudusDeviceSha256 -DevicePath $dev -Length $fake.Size
    Assert-True ($bad -ne $fake.Hash) 'Manipuliertes Byte wird beim Zurücklesen erkannt'

    # 4. Echte Kairo-ISO
    if (-not $SkipRealIso) {
        $iso = Get-ClaudusIso -WorkDir $WorkDir
        Assert-True ($iso.Size -gt 1GB) ("Kairo-ISO geladen und Prüfsumme passt: " + $iso.Name)
        $again = Find-ClaudusLocalIso -WorkDir $WorkDir
        Assert-True ($again -and $again.Hash -eq $iso.Hash) 'Geladene ISO wird ohne Internet wiedergefunden'
        $sw = [Diagnostics.Stopwatch]::StartNew()
        $res = Invoke-ClaudusWriteCore -Iso $iso -DiskNumber $n
        Write-Host ('Schreiben + Zurücklesen: {0:N0} s' -f $sw.Elapsed.TotalSeconds)
        Assert-True $res.Ok 'Kairo-ISO geschrieben und Bit für Bit identisch zurückgelesen'
        Update-HostStorageCache
        Start-Sleep -Seconds 2
        $parts = @(Get-Partition -DiskNumber $n -ErrorAction SilentlyContinue)
        $parts | Format-Table PartitionNumber, Offset, Size, Type, GptType -AutoSize | Out-String | Write-Host
        Assert-True ($parts.Count -ge 1) ('Windows erkennt die Partitionen der ISO (' + $parts.Count + ')')

        # Nochmal: Ein zweites Schreiben auf denselben, jetzt eingehängten Stick
        # muss auch klappen (Stick, auf dem schon Kairo ist).
        $res2 = Invoke-ClaudusWriteCore -Iso $fake -DiskNumber $n
        Assert-True $res2.Ok 'Erneutes Schreiben auf einen Stick mit eingehängter ISO klappt'
    }

    # 5. Rufus
    $rufus = Get-ClaudusRufus -WorkDir $WorkDir
    $sig = Get-AuthenticodeSignature -FilePath $rufus
    Assert-True ($sig.Status -eq 'Valid') ("Rufus geladen, Signatur gültig: " + $sig.SignerCertificate.Subject)
} finally {
    try { Invoke-DiskPart ("select vdisk file=`"$vhd`"`r`ndetach vdisk`r`nexit`r`n") } catch { Write-Warning $_ }
}

Write-Host ''
Write-Host ("{0} bestanden, {1} fehlgeschlagen" -f $script:pass, $script:fail)
if ($script:fail -gt 0) { exit 1 }
exit 0
