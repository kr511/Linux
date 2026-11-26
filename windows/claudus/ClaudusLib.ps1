#
# ClaudusLib.ps1: alle Funktionen von Claudus. Claudus.ps1 ist nur das Menü.
#
# Läuft in Windows PowerShell 5.1 (in Windows 10/11 eingebaut) und in
# PowerShell 7. Die Datei muss UTF-8 MIT BOM bleiben, sonst zeigt
# PowerShell 5.1 die Umlaute falsch an.
#
# Sicherheitsregeln (werden in tests/Test-Claudus.ps1 geprüft):
#   - Geschrieben wird nur auf eine Platte, die Test-ClaudusTargetDisk
#     freigibt: USB/SD, nicht Start- oder Systemplatte, kein Windows,
#     keine Auslagerungsdatei, höchstens 256 GB.
#   - Direkt vor dem Löschen wird die Platte erneut gelesen und mit der
#     Auswahl verglichen (Nummer, Seriennummer/ID, Größe). Wurde der Stick
#     getauscht, bricht Claudus ab.
#   - Geschrieben wird nur eine ISO, deren SHA256 zu SHA256SUMS passt.
#   - Nach dem Schreiben wird der Stick zurückgelesen und die Prüfsumme
#     verglichen.

$script:ClaudusVersion   = '1.0'
$script:ClaudusRepo      = 'kr511/Linux'
$script:MaxStickBytes    = [int64]256GB
$script:AllowedBusTypes  = @('USB', 'SD', 'MMC')
$script:ChunkBytes       = 4MB
$script:HeaderBytes      = 1MB
$script:AlignBytes       = 4096

# ---------------------------------------------------------------------------
# Kleinkram
# ---------------------------------------------------------------------------

function Test-ClaudusAdmin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $p  = New-Object Security.Principal.WindowsPrincipal($id)
    return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Format-ClaudusSize {
    param([int64]$Bytes)
    if ($Bytes -ge 1TB) { return ('{0:N1} TB' -f ($Bytes / 1TB)) }
    if ($Bytes -ge 1GB) { return ('{0:N1} GB' -f ($Bytes / 1GB)) }
    if ($Bytes -ge 1MB) { return ('{0:N0} MB' -f ($Bytes / 1MB)) }
    return ('{0:N0} Bytes' -f $Bytes)
}

function New-ClaudusLine {
    # Eine Zeile im Bericht. Level: OK, HINWEIS, WARNUNG, INFO
    param([string]$Level, [string]$Area, [string]$Text)
    [pscustomobject]@{ Level = $Level; Area = $Area; Text = $Text }
}

function Write-ClaudusLines {
    param([object[]]$Lines)
    foreach ($l in $Lines) {
        $color = 'Gray'
        switch ($l.Level) {
            'OK'      { $color = 'Green' }
            'HINWEIS' { $color = 'Yellow' }
            'WARNUNG' { $color = 'Red' }
            'INFO'    { $color = 'Cyan' }
        }
        Write-Host ('[{0,-7}] ' -f $l.Level) -ForegroundColor $color -NoNewline
        Write-Host ('{0}: {1}' -f $l.Area, $l.Text)
    }
}

function ConvertTo-ClaudusLinesText {
    param([object[]]$Lines)
    ($Lines | ForEach-Object { '[{0,-7}] {1}: {2}' -f $_.Level, $_.Area, $_.Text }) -join "`r`n"
}

function Get-ClaudusDesktop {
    $d = [Environment]::GetFolderPath('Desktop')
    if (-not $d) { $d = Join-Path $env:USERPROFILE 'Desktop' }
    if (-not (Test-Path -LiteralPath $d)) { New-Item -ItemType Directory -Force -Path $d | Out-Null }
    return $d
}

function Get-ClaudusDefaultWorkDir {
    return (Join-Path $env:USERPROFILE 'Downloads\Kairo')
}

# ---------------------------------------------------------------------------
# Datenträger: Auswahl und Sicherheitsprüfung
# ---------------------------------------------------------------------------

function ConvertTo-ClaudusBusType {
    # Get-Disk liefert BusType meist als Text ("USB"), manche Systeme als Zahl.
    param($Value)
    if ($null -eq $Value) { return 'Unbekannt' }
    $s = [string]$Value
    $map = @{ '1' = 'SCSI'; '3' = 'ATA'; '7' = 'USB'; '8' = 'RAID'; '10' = 'SAS';
              '11' = 'SATA'; '12' = 'SD'; '13' = 'MMC'; '15' = 'File Backed Virtual';
              '16' = 'Storage Spaces'; '17' = 'NVMe' }
    if ($map.ContainsKey($s)) { return $map[$s] }
    return $s
}

function Get-ClaudusSystemDiskNumbers {
    # Platten, auf denen Windows, die Startpartition oder eine
    # Auslagerungsdatei liegt. Auf diese schreibt Claudus nie.
    $nums = New-Object System.Collections.Generic.List[int]
    $letters = New-Object System.Collections.Generic.List[string]
    if ($env:SystemDrive) { $letters.Add($env:SystemDrive.Substring(0, 1)) }
    try {
        Get-CimInstance -ClassName Win32_PageFileUsage -ErrorAction Stop | ForEach-Object {
            if ($_.Name -and $_.Name.Length -ge 1) { $letters.Add($_.Name.Substring(0, 1)) }
        }
    } catch { }
    foreach ($l in ($letters | Select-Object -Unique)) {
        try {
            $p = Get-Partition -DriveLetter $l -ErrorAction Stop
            foreach ($x in @($p)) { $nums.Add([int]$x.DiskNumber) }
        } catch { }
    }
    try {
        Get-Disk -ErrorAction Stop | Where-Object { $_.IsBoot -or $_.IsSystem } |
            ForEach-Object { $nums.Add([int]$_.Number) }
    } catch { }
    return @($nums | Select-Object -Unique)
}

function Test-ClaudusTargetDisk {
    # Reine Prüffunktion (kein Zugriff auf echte Platten, darum testbar).
    # Gibt Ok und die Gründe zurück, warum eine Platte gesperrt ist.
    param(
        [Parameter(Mandatory = $true)] $Disk,
        [int64]$MinBytes = 0,
        [int[]]$SystemDiskNumbers = @()
    )
    $reasons = New-Object System.Collections.Generic.List[string]
    $bus = ConvertTo-ClaudusBusType $Disk.BusType

    if ($Disk.IsBoot)   { $reasons.Add('Windows startet von dieser Platte') }
    if ($Disk.IsSystem) { $reasons.Add('Systemplatte (Startpartition)') }
    if ($SystemDiskNumbers -contains [int]$Disk.Number) {
        $reasons.Add('Windows oder die Auslagerungsdatei liegt darauf')
    }
    if ($script:AllowedBusTypes -notcontains $bus) {
        $reasons.Add("kein USB-Stick (Anschluss: $bus)")
    }
    if ([int64]$Disk.Size -le 0) {
        $reasons.Add('kein Medium eingelegt')
    } elseif ($MinBytes -gt 0 -and [int64]$Disk.Size -lt $MinBytes) {
        $reasons.Add('zu klein (braucht ' + (Format-ClaudusSize $MinBytes) + ')')
    }
    if ([int64]$Disk.Size -gt $script:MaxStickBytes) {
        $reasons.Add('größer als 256 GB, eher eine Festplatte als ein Stick')
    }
    if ($Disk.IsReadOnly) { $reasons.Add('schreibgeschützt') }
    if ($Disk.IsOffline)  { $reasons.Add('offline') }

    [pscustomobject]@{
        Ok      = ($reasons.Count -eq 0)
        Reasons = @($reasons)
    }
}

function Get-ClaudusDiskInfo {
    # Alle Platten mit Prüfergebnis, für Liste und Bericht.
    param([int64]$MinBytes = 0)
    $sys = Get-ClaudusSystemDiskNumbers
    $disks = @(Get-Disk -ErrorAction Stop | Sort-Object Number)
    foreach ($d in $disks) {
        $letters = @()
        try {
            $letters = @(Get-Partition -DiskNumber $d.Number -ErrorAction Stop |
                Where-Object { $_.DriveLetter -and [string]$_.DriveLetter -ne [string][char]0 } |
                ForEach-Object { [string]$_.DriveLetter + ':' })
        } catch { }
        $partCount = 0
        try { $partCount = @(Get-Partition -DiskNumber $d.Number -ErrorAction Stop).Count } catch { }
        $check = Test-ClaudusTargetDisk -Disk $d -MinBytes $MinBytes -SystemDiskNumbers $sys
        $serial = ''
        if ($d.SerialNumber) { $serial = ([string]$d.SerialNumber).Trim() }
        [pscustomobject]@{
            Number      = [int]$d.Number
            Model       = ([string]$d.FriendlyName).Trim()
            Serial      = $serial
            UniqueId    = [string]$d.UniqueId
            Size        = [int64]$d.Size
            BusType     = (ConvertTo-ClaudusBusType $d.BusType)
            Partitions  = $partCount
            PartStyle   = [string]$d.PartitionStyle
            Letters     = $letters
            HasWindows  = ($sys -contains [int]$d.Number)
            Ok          = $check.Ok
            Reasons     = $check.Reasons
            Raw         = $d
        }
    }
}

function Test-ClaudusSameDisk {
    # Ist das noch dieselbe Platte wie bei der Auswahl?
    param([Parameter(Mandatory = $true)] $Before, [Parameter(Mandatory = $true)] $Now)
    if ([int]$Before.Number -ne [int]$Now.Number) { return $false }
    if ([int64]$Before.Size -ne [int64]$Now.Size) { return $false }
    if ([string]$Before.UniqueId -ne [string]$Now.UniqueId) { return $false }
    if ([string]$Before.Serial -ne [string]$Now.Serial) { return $false }
    return $true
}

# ---------------------------------------------------------------------------
# ISO holen und prüfen
# ---------------------------------------------------------------------------

function Enable-ClaudusTls {
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    } catch { }
}

function Get-ClaudusRelease {
    param([string]$Repo = $script:ClaudusRepo)
    Enable-ClaudusTls
    $headers = @{ 'User-Agent' = 'Claudus'; 'Accept' = 'application/vnd.github+json' }
    $rel = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/latest" -Headers $headers -UseBasicParsing -ErrorAction Stop
    $iso  = @($rel.assets | Where-Object { $_.name -like 'kairo-*-x86_64.iso' }) | Select-Object -First 1
    $sums = @($rel.assets | Where-Object { $_.name -eq 'SHA256SUMS' }) | Select-Object -First 1
    if (-not $iso -or -not $sums) {
        throw "Im neuesten Release ($($rel.tag_name)) fehlen ISO oder SHA256SUMS."
    }
    [pscustomobject]@{
        Tag     = [string]$rel.tag_name
        IsoName = [string]$iso.name
        IsoUrl  = [string]$iso.browser_download_url
        IsoSize = [int64]$iso.size
        SumsUrl = [string]$sums.browser_download_url
    }
}

function Get-ClaudusExpectedHash {
    # Liest den Hash für FileName aus dem Text einer SHA256SUMS-Datei
    # (Format von sha256sum: "<64 hex>  <name>" oder "<64 hex> *<name>").
    param([Parameter(Mandatory = $true)][string]$SumsText, [Parameter(Mandatory = $true)][string]$FileName)
    foreach ($line in ($SumsText -split "`r?`n")) {
        if ($line -match '^\s*([0-9a-fA-F]{64})\s+\*?(.+?)\s*$') {
            $name = Split-Path -Leaf $Matches[2]
            if ($name -eq $FileName) { return $Matches[1].ToLowerInvariant() }
        }
    }
    throw "In SHA256SUMS steht kein Eintrag für $FileName."
}

function Save-ClaudusFile {
    # Lädt eine Datei. Bevorzugt curl.exe (in Windows 10/11 eingebaut, kann
    # abgebrochene Downloads fortsetzen), sonst BITS, sonst Invoke-WebRequest.
    param([Parameter(Mandatory = $true)][string]$Url, [Parameter(Mandatory = $true)][string]$Path)
    $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
    if ($curl) {
        & $curl.Source -L --fail --retry 3 --retry-delay 3 -C - -o $Path $Url
        if ($LASTEXITCODE -eq 0) { return }
        Write-Warning "curl.exe meldet Fehler $LASTEXITCODE, versuche es anders."
    }
    try {
        Import-Module BitsTransfer -ErrorAction Stop
        Start-BitsTransfer -Source $Url -Destination $Path -ErrorAction Stop
        return
    } catch {
        Write-Warning "BITS ging nicht: $($_.Exception.Message)"
    }
    Enable-ClaudusTls
    $old = $ProgressPreference
    $ProgressPreference = 'SilentlyContinue'   # sonst ist IWR in PS 5.1 extrem langsam
    try {
        Invoke-WebRequest -Uri $Url -OutFile $Path -UseBasicParsing -ErrorAction Stop
    } finally {
        $ProgressPreference = $old
    }
}

function Get-ClaudusFileSha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
}

function Get-ClaudusIso {
    # Holt die neueste Kairo-ISO nach WorkDir (oder nimmt die vorhandene)
    # und prüft sie gegen SHA256SUMS. Wirft, wenn die Prüfsumme nicht passt.
    param([string]$WorkDir = (Get-ClaudusDefaultWorkDir), $Release = $null)
    if (-not $Release) { $Release = Get-ClaudusRelease }
    New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null

    $sumsPath = Join-Path $WorkDir 'SHA256SUMS'
    if (Test-Path -LiteralPath $sumsPath) { Remove-Item -LiteralPath $sumsPath -Force }
    Save-ClaudusFile -Url $Release.SumsUrl -Path $sumsPath
    $expected = Get-ClaudusExpectedHash -SumsText ([IO.File]::ReadAllText($sumsPath)) -FileName $Release.IsoName

    $isoPath = Join-Path $WorkDir $Release.IsoName
    if (Test-Path -LiteralPath $isoPath) {
        $have = (Get-Item -LiteralPath $isoPath).Length
        if ($have -gt $Release.IsoSize) { Remove-Item -LiteralPath $isoPath -Force }
    }
    $needDownload = $true
    if (Test-Path -LiteralPath $isoPath) {
        if ((Get-Item -LiteralPath $isoPath).Length -eq $Release.IsoSize) { $needDownload = $false }
    }
    if ($needDownload) {
        $drive = [IO.Path]::GetPathRoot((Resolve-Path -LiteralPath $WorkDir).ProviderPath)
        try {
            $free = (New-Object IO.DriveInfo($drive)).AvailableFreeSpace
            if ($free -lt ($Release.IsoSize + 200MB)) {
                throw ('Zu wenig Platz auf ' + $drive + ': frei ' + (Format-ClaudusSize $free) + ', nötig ' + (Format-ClaudusSize $Release.IsoSize))
            }
        } catch [System.ArgumentException] { }
        Write-Host ('Lade ' + $Release.IsoName + ' (' + (Format-ClaudusSize $Release.IsoSize) + ') ...')
        Save-ClaudusFile -Url $Release.IsoUrl -Path $isoPath
    } else {
        Write-Host 'ISO ist schon da, prüfe nur die Prüfsumme.'
    }

    Write-Host 'Prüfe SHA256 (dauert ein paar Sekunden) ...'
    $actual = Get-ClaudusFileSha256 -Path $isoPath
    if ($actual -ne $expected) {
        $bad = $isoPath + '.kaputt'
        Move-Item -LiteralPath $isoPath -Destination $bad -Force
        throw ("Prüfsumme passt NICHT. Erwartet $expected, bekommen $actual. " +
               "Die Datei wurde nach $bad verschoben. Einfach nochmal laden.")
    }
    [pscustomobject]@{
        Path = $isoPath
        Name = $Release.IsoName
        Tag  = $Release.Tag
        Size = [int64](Get-Item -LiteralPath $isoPath).Length
        Hash = $expected
    }
}

function Find-ClaudusLocalIso {
    # Schon geladene, geprüfte ISO wiederfinden (für "Stick schreiben" ohne Internet).
    param([string]$WorkDir = (Get-ClaudusDefaultWorkDir))
    $sumsPath = Join-Path $WorkDir 'SHA256SUMS'
    if (-not (Test-Path -LiteralPath $sumsPath)) { return $null }
    $text = [IO.File]::ReadAllText($sumsPath)
    $isos = @(Get-ChildItem -LiteralPath $WorkDir -Filter 'kairo-*-x86_64.iso' -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending)
    foreach ($f in $isos) {
        try { $expected = Get-ClaudusExpectedHash -SumsText $text -FileName $f.Name } catch { continue }
        $tag = ''
        if ($f.Name -match '^kairo-([0-9][^-]*)-') { $tag = 'v' + $Matches[1] }
        return [pscustomobject]@{ Path = $f.FullName; Name = $f.Name; Tag = $tag; Size = [int64]$f.Length; Hash = $expected }
    }
    return $null
}

# ---------------------------------------------------------------------------
# Rohes Schreiben und Zurücklesen
# ---------------------------------------------------------------------------

$script:ClaudusNativeSource = @'
using System;
using System.ComponentModel;
using System.IO;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;

public static class ClaudusNative
{
    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern SafeFileHandle CreateFileW(string name, uint access, uint share,
        IntPtr security, uint disposition, uint flags, IntPtr template);

    // PowerShell 5.1 läuft mit alter .NET-Pfadbehandlung, dort öffnet
    // FileStream keine Pfade wie \\.\PhysicalDrive1. Darum CreateFile direkt.
    public static FileStream Open(string path, bool write)
    {
        uint access = write ? 0xC0000000u : 0x80000000u;   // GENERIC_READ|WRITE
        uint flags  = write ? 0x80000000u : 0u;            // FILE_FLAG_WRITE_THROUGH
        SafeFileHandle h = CreateFileW(path, access, 3u, IntPtr.Zero, 3u, flags, IntPtr.Zero);
        if (h.IsInvalid)
        {
            int err = Marshal.GetLastWin32Error();
            throw new Win32Exception(err, "Kann " + path + " nicht öffnen (Windows-Fehler " + err + ")");
        }
        return new FileStream(h, write ? FileAccess.ReadWrite : FileAccess.Read, 4096, false);
    }
}
'@

function Initialize-ClaudusNative {
    if (-not ('ClaudusNative' -as [type])) {
        Add-Type -TypeDefinition $script:ClaudusNativeSource -Language CSharp
    }
}

function Get-ClaudusDevicePath {
    param([Parameter(Mandatory = $true)][int]$DiskNumber)
    return ('\\.\PhysicalDrive{0}' -f $DiskNumber)
}

function Get-ClaudusAlignedLength {
    param([int64]$Length, [int]$Align = $script:AlignBytes)
    $rest = $Length % $Align
    if ($rest -eq 0) { return $Length }
    return ($Length + ($Align - $rest))
}

function Clear-ClaudusDisk {
    # Entfernt alle Partitionen (diskpart "clean"), damit Windows keine
    # Laufwerke des Sticks mehr eingehängt hat und rohes Schreiben erlaubt.
    # NUR nach Test-ClaudusTargetDisk und Test-ClaudusSameDisk aufrufen.
    param([Parameter(Mandatory = $true)][int]$DiskNumber)
    $dpFile = Join-Path $env:TEMP ('claudus-diskpart-{0}.txt' -f [guid]::NewGuid())
    try {
        [IO.File]::WriteAllText($dpFile, "select disk $DiskNumber`r`nclean`r`nrescan`r`nexit`r`n", [Text.Encoding]::ASCII)
        $out = & diskpart.exe /s $dpFile 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw ("diskpart konnte den Stick nicht leeren (Code $LASTEXITCODE):`r`n" + ($out -join "`r`n"))
        }
    } finally {
        Remove-Item -LiteralPath $dpFile -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
}

function Write-ClaudusRaw {
    # Schreibt ImagePath 1:1 (wie Rufus im DD-Modus) nach DevicePath.
    # Die ersten 1 MiB (Partitionstabelle) kommen ZULETZT, damit Windows
    # nicht mitten im Schreiben Partitionen erkennt und einhängt.
    # Keine Sicherheitsprüfung hier: das macht Invoke-ClaudusWrite.
    param(
        [Parameter(Mandatory = $true)][string]$ImagePath,
        [Parameter(Mandatory = $true)][string]$DevicePath
    )
    Initialize-ClaudusNative
    $len = [int64](Get-Item -LiteralPath $ImagePath).Length
    $header = [int64][Math]::Min([int64]$script:HeaderBytes, $len)
    $chunk = [int]$script:ChunkBytes
    $buf = New-Object byte[] $chunk
    $src = [IO.File]::OpenRead($ImagePath)
    $dst = [ClaudusNative]::Open($DevicePath, $true)
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $lastUi = -1.0
    try {
        $plan = @(@{ From = $header; To = $len }, @{ From = [int64]0; To = $header })
        $done = [int64]0
        foreach ($part in $plan) {
            $pos = [int64]$part.From
            while ($pos -lt $part.To) {
                $want = [int][Math]::Min([int64]$chunk, $part.To - $pos)
                [void]$src.Seek($pos, 'Begin')
                $got = 0
                while ($got -lt $want) {
                    $n = $src.Read($buf, $got, $want - $got)
                    if ($n -le 0) { throw 'ISO-Datei endet unerwartet.' }
                    $got += $n
                }
                $writeLen = [int](Get-ClaudusAlignedLength -Length $want)
                if ($writeLen -gt $want) { [Array]::Clear($buf, $want, $writeLen - $want) }
                [void]$dst.Seek($pos, 'Begin')
                $dst.Write($buf, 0, $writeLen)
                $pos += $want
                $done += $want
                $t = $sw.Elapsed.TotalSeconds
                if ($t - $lastUi -ge 0.5 -or $done -eq $len) {
                    $lastUi = $t
                    $mbs = 0
                    if ($t -gt 0) { $mbs = [int](($done / 1MB) / $t) }
                    $pct = [int](100 * $done / $len)
                    Write-Progress -Activity 'Claudus schreibt den Stick' -Status ("{0}% ({1} MB/s)" -f $pct, $mbs) -PercentComplete $pct
                }
            }
        }
        $dst.Flush($true)
    } finally {
        Write-Progress -Activity 'Claudus schreibt den Stick' -Completed
        $dst.Dispose()
        $src.Dispose()
    }
    return $sw.Elapsed
}

function Get-ClaudusDeviceSha256 {
    # Liest die ersten Length Bytes von DevicePath und gibt ihren SHA256 zurück.
    param(
        [Parameter(Mandatory = $true)][string]$DevicePath,
        [Parameter(Mandatory = $true)][int64]$Length
    )
    Initialize-ClaudusNative
    $chunk = [int]$script:ChunkBytes
    $buf = New-Object byte[] $chunk
    $sha = [Security.Cryptography.SHA256]::Create()
    $dev = [ClaudusNative]::Open($DevicePath, $false)
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $lastUi = -1.0
    try {
        $pos = [int64]0
        while ($pos -lt $Length) {
            $use = [int][Math]::Min([int64]$chunk, $Length - $pos)
            $readLen = [int](Get-ClaudusAlignedLength -Length $use)
            $got = 0
            while ($got -lt $readLen) {
                $n = $dev.Read($buf, $got, $readLen - $got)
                if ($n -le 0) { throw 'Stick ist kürzer als die ISO.' }
                $got += $n
            }
            [void]$sha.TransformBlock($buf, 0, $use, $null, 0)
            $pos += $use
            $t = $sw.Elapsed.TotalSeconds
            if ($t - $lastUi -ge 0.5 -or $pos -eq $Length) {
                $lastUi = $t
                $pct = [int](100 * $pos / $Length)
                Write-Progress -Activity 'Claudus liest den Stick zurück' -Status "$pct%" -PercentComplete $pct
            }
        }
        [void]$sha.TransformFinalBlock((New-Object byte[] 0), 0, 0)
        return (([BitConverter]::ToString($sha.Hash)) -replace '-', '').ToLowerInvariant()
    } finally {
        Write-Progress -Activity 'Claudus liest den Stick zurück' -Completed
        $dev.Dispose()
        $sha.Dispose()
    }
}

function Invoke-ClaudusWriteCore {
    # Leeren, schreiben, zurücklesen. Die Platte muss vorher geprüft sein.
    param(
        [Parameter(Mandatory = $true)] $Iso,
        [Parameter(Mandatory = $true)][int]$DiskNumber
    )
    $dev = Get-ClaudusDevicePath -DiskNumber $DiskNumber
    Write-Host 'Leere den Stick ...'
    Clear-ClaudusDisk -DiskNumber $DiskNumber
    Write-Host 'Schreibe ...  (Fragt Windows gleich, ob der Stick formatiert werden soll: ABBRECHEN klicken!)' -ForegroundColor Yellow
    $took = Write-ClaudusRaw -ImagePath $Iso.Path -DevicePath $dev
    Write-Host ('Geschrieben in {0:mm\:ss}. Lese zum Vergleich zurück ...' -f $took)
    $hash = Get-ClaudusDeviceSha256 -DevicePath $dev -Length $Iso.Size
    try { Update-HostStorageCache -ErrorAction SilentlyContinue } catch { }
    [pscustomobject]@{
        Ok       = ($hash -eq $Iso.Hash)
        Expected = $Iso.Hash
        Actual   = $hash
    }
}

# ---------------------------------------------------------------------------
# Vorab-Check: Hardware
# ---------------------------------------------------------------------------

function Get-ClaudusBoardKeys {
    # Tasten fürs Boot-Menü und Setup je Hersteller (Desktop-Mainboards und
    # gängige Fertig-PCs). Kann je nach BIOS-Version abweichen.
    param([string]$Vendor)
    $v = ([string]$Vendor).ToLowerInvariant()
    if ($v -match 'asus')             { return @{ Name = 'ASUS';     Boot = 'F8';  Setup = 'Entf oder F2'; SecureBoot = 'F7 (Advanced Mode) > Boot > Secure Boot > OS Type: "Other OS"' } }
    if ($v -match 'micro-star|msi')   { return @{ Name = 'MSI';      Boot = 'F11'; Setup = 'Entf';        SecureBoot = 'F7 (Advanced) > Settings > Security > Secure Boot > Disabled' } }
    if ($v -match 'gigabyte|aorus')   { return @{ Name = 'Gigabyte'; Boot = 'F12'; Setup = 'Entf';        SecureBoot = 'Boot > Secure Boot > Disabled' } }
    if ($v -match 'asrock')           { return @{ Name = 'ASRock';   Boot = 'F11'; Setup = 'F2 oder Entf'; SecureBoot = 'Security > Secure Boot > Disabled' } }
    if ($v -match 'lenovo')           { return @{ Name = 'Lenovo';   Boot = 'F12'; Setup = 'F1 oder F2';   SecureBoot = 'Security > Secure Boot > Disabled' } }
    if ($v -match 'hewlett|hp')       { return @{ Name = 'HP';       Boot = 'F9';  Setup = 'F10';         SecureBoot = 'Advanced/Security > Secure Boot Configuration' } }
    if ($v -match 'dell')             { return @{ Name = 'Dell';     Boot = 'F12'; Setup = 'F2';          SecureBoot = 'Boot Configuration > Secure Boot' } }
    if ($v -match 'acer')             { return @{ Name = 'Acer';     Boot = 'F12'; Setup = 'F2';          SecureBoot = 'Boot > Secure Boot' } }
    return @{ Name = 'unbekannt'; Boot = 'F8, F11 oder F12'; Setup = 'Entf oder F2'; SecureBoot = 'meist unter Boot oder Security > Secure Boot' }
}

function Get-ClaudusWifiVerdict {
    # Grobe Einschätzung eines Netzwerkchips anhand der Hardware-ID.
    # Ehrlich: sicher ist es erst im Live-System (Test A4/A5).
    param([string]$PnpId, [string]$Description)
    $id = ([string]$PnpId).ToUpperInvariant()
    $d  = [string]$Description
    if ($id -match 'VEN_8086') { return @('OK', 'Intel, läuft unter Linux sehr zuverlässig') }
    if ($id -match 'VEN_14C3&DEV_7902') { return @('HINWEIS', 'MediaTek MT7902: Linux-Unterstützung ist sehr neu, LAN-Kabel oder Handy-USB-Tethering bereithalten') }
    if ($id -match 'VEN_14C3') { return @('OK', 'MediaTek, Treiber mt76 ist im Kernel') }
    if ($id -match 'VEN_14E4') { return @('HINWEIS', 'Broadcom: braucht oft einen Zusatztreiber, LAN-Kabel oder Handy-USB-Tethering bereithalten') }
    if ($id -match '^USB\\VID_0BDA') { return @('HINWEIS', 'USB-WLAN von Realtek: viele laufen (rtw88), manche nicht. LAN-Kabel oder Handy-USB-Tethering bereithalten') }
    if ($id -match 'VEN_10EC') { return @('OK', 'Realtek, Treiber ist im Kernel') }
    if ($id -match '^USB\\') { return @('HINWEIS', 'USB-Adapter: unter Linux nicht sicher, LAN-Kabel oder Handy-USB-Tethering bereithalten') }
    return @('HINWEIS', "unbekannter Chip ($d): erst im Live-System sicher")
}

function Get-ClaudusHardwareReport {
    $lines = New-Object System.Collections.Generic.List[object]

    # Start-Modus
    $fw = [string]$env:firmware_type
    if ($fw -eq 'UEFI') {
        $lines.Add((New-ClaudusLine 'OK' 'Start-Modus' 'Windows läuft im UEFI-Modus, passt'))
    } elseif ($fw) {
        $lines.Add((New-ClaudusLine 'HINWEIS' 'Start-Modus' "Windows läuft im Modus '$fw'. Kairo braucht UEFI: im Setup CSM/Legacy aus. Achtung: Ein Windows im Legacy-Modus startet danach evtl. nicht mehr, bis du CSM wieder einschaltest"))
    }

    # Secure Boot
    try {
        $sb = Confirm-SecureBootUEFI -ErrorAction Stop
        if ($sb) {
            $lines.Add((New-ClaudusLine 'HINWEIS' 'Secure Boot' 'ist AN. Vor dem Start vom Stick im Setup ausschalten (Kairo ist nicht für Secure Boot signiert)'))
        } else {
            $lines.Add((New-ClaudusLine 'OK' 'Secure Boot' 'ist aus, Stick kann starten'))
        }
    } catch {
        $lines.Add((New-ClaudusLine 'INFO' 'Secure Boot' 'konnte nicht gelesen werden (Claudus als Administrator starten). Im Zweifel im Setup ausschalten'))
    }

    # BitLocker / Geräteverschlüsselung
    try {
        $vols = @(Get-CimInstance -Namespace 'root/cimv2/Security/MicrosoftVolumeEncryption' -ClassName Win32_EncryptableVolume -ErrorAction Stop |
            Where-Object { $_.ProtectionStatus -eq 1 })
        if ($vols.Count -gt 0) {
            $letters = ($vols | ForEach-Object { $_.DriveLetter }) -join ', '
            $lines.Add((New-ClaudusLine 'WARNUNG' 'BitLocker' "ist AN ($letters). Wenn du Secure Boot ausschaltest, will Windows danach den Wiederherstellungsschlüssel. VORHER sichern: https://aka.ms/myrecoverykey (aufs Handy). Oder vor dem Neustart: Suspend-BitLocker -MountPoint C: -RebootCount 3"))
        } else {
            $lines.Add((New-ClaudusLine 'OK' 'BitLocker' 'keine aktive Verschlüsselung gefunden'))
        }
    } catch {
        $lines.Add((New-ClaudusLine 'INFO' 'BitLocker' 'Status unbekannt (nur als Administrator lesbar). Einstellungen > Datenschutz und Sicherheit > Geräteverschlüsselung ansehen'))
    }

    # CPU / RAM
    try {
        $cpu = (Get-CimInstance Win32_Processor -ErrorAction Stop | Select-Object -First 1).Name.Trim()
        $ram = [int64](Get-CimInstance Win32_ComputerSystem -ErrorAction Stop).TotalPhysicalMemory
        $lvl = 'OK'
        $txt = "$cpu, " + (Format-ClaudusSize $ram) + ' RAM'
        if ($ram -lt 7GB) { $lvl = 'HINWEIS'; $txt += ' (unter 8 GB wird GNOME mit Spielen knapp)' }
        $lines.Add((New-ClaudusLine $lvl 'Prozessor' $txt))
    } catch { }

    # Grafik
    try {
        $gpus = @(Get-CimInstance Win32_VideoController -ErrorAction Stop |
            Where-Object { $_.PNPDeviceID -match '^PCI\\' })
        foreach ($g in $gpus) {
            $n = [string]$g.Name
            if ($g.PNPDeviceID -match 'VEN_1002') {
                $t = "${n}: AMD, Treiber amdgpu + Mesa sind in Kairo"
                if ($n -match '6500 XT') { $t += ' (genau die Karte, für die Kairo eingestellt ist)' }
                $lines.Add((New-ClaudusLine 'OK' 'Grafik' $t))
            } elseif ($g.PNPDeviceID -match 'VEN_10DE') {
                $lines.Add((New-ClaudusLine 'HINWEIS' 'Grafik' "${n}: NVIDIA. Kairo ist auf AMD eingestellt, NVIDIA braucht danach den nvidia-Treiber"))
            } elseif ($g.PNPDeviceID -match 'VEN_8086') {
                $lines.Add((New-ClaudusLine 'OK' 'Grafik' "${n}: Intel, läuft"))
            } else {
                $lines.Add((New-ClaudusLine 'INFO' 'Grafik' $n))
            }
        }
        if ($gpus.Count -eq 0) { $lines.Add((New-ClaudusLine 'INFO' 'Grafik' 'keine Grafikkarte gefunden (VM?)')) }
    } catch { }

    # Netzwerk
    try {
        $nics = @(Get-NetAdapter -Physical -ErrorAction Stop | Where-Object { $_.InterfaceDescription -notmatch 'Bluetooth|Virtual|VPN' })
        $hasLan = $false
        foreach ($a in $nics) {
            $isWifi = ($a.NdisPhysicalMedium -eq 9) -or ($a.Name -match 'WLAN|Wi-?Fi') -or ($a.InterfaceDescription -match 'Wireless|Wi-?Fi|WLAN|802\.11')
            $verdict = Get-ClaudusWifiVerdict -PnpId $a.PnPDeviceID -Description $a.InterfaceDescription
            if ($isWifi) {
                $lines.Add((New-ClaudusLine $verdict[0] 'WLAN' ($a.InterfaceDescription + ': ' + $verdict[1])))
            } else {
                $hasLan = $true
                $state = 'kein Kabel'
                if ($a.Status -eq 'Up') { $state = 'Kabel steckt' }
                $lines.Add((New-ClaudusLine 'OK' 'LAN' ($a.InterfaceDescription + " ($state)")))
            }
        }
        if (-not $hasLan) {
            $lines.Add((New-ClaudusLine 'HINWEIS' 'Netzwerk' 'Kein LAN-Anschluss gefunden. Falls WLAN im Live-System nicht geht: Handy per USB anschließen und USB-Tethering einschalten'))
        }
    } catch {
        $lines.Add((New-ClaudusLine 'INFO' 'Netzwerk' 'Netzwerkkarten konnten nicht gelesen werden'))
    }

    # Platten
    try {
        $disks = @(Get-ClaudusDiskInfo)
        $internal = @($disks | Where-Object { @('USB', 'SD', 'MMC', 'File Backed Virtual') -notcontains $_.BusType })
        foreach ($d in $disks) {
            $desc = '{0} {1}, {2}, {3}, Seriennummer {4}' -f $d.Number, $d.Model, (Format-ClaudusSize $d.Size), $d.BusType, $d.Serial
            if ($d.Letters.Count -gt 0) { $desc += ', Laufwerke ' + ($d.Letters -join ' ') }
            $lines.Add((New-ClaudusLine 'INFO' 'Platte' $desc))
        }
        $win = @($internal | Where-Object { $_.HasWindows })
        $empty = @($internal | Where-Object { -not $_.HasWindows -and ($_.Partitions -eq 0 -or $_.PartStyle -eq 'RAW') })
        $other = @($internal | Where-Object { -not $_.HasWindows -and $_.Partitions -gt 0 -and $_.PartStyle -ne 'RAW' })
        foreach ($w in $win) {
            $t = "Windows liegt auf: $($w.Model) (Seriennummer $($w.Serial)). Diese Platte beim Installieren abstecken (PC vorher ganz aus, Netzteil-Schalter)."
            if ($w.BusType -eq 'NVMe') {
                $t += ' Sie steckt als M.2 auf dem Mainboard; abstecken heißt ausbauen. Ist dir das zu fummelig: drinlassen und im Installer streng nach Seriennummer wählen.'
            }
            $lines.Add((New-ClaudusLine 'INFO' 'Windows-Platte' $t))
        }
        if ($internal.Count -le 1) {
            $lines.Add((New-ClaudusLine 'WARNUNG' 'Kairo-SSD' 'Nur EINE interne Platte gefunden, und darauf ist Windows. Der Plan ist eine eigene SSD für Kairo. Installierst du trotzdem, ist Windows samt Dateien weg'))
        }
        foreach ($e in $empty) {
            $lines.Add((New-ClaudusLine 'OK' 'Kairo-SSD' ("Leer und bereit: {0}, {1}, Seriennummer {2}. Genau diese im Installer wählen (Schritt B2)" -f $e.Model, (Format-ClaudusSize $e.Size), $e.Serial)))
        }
        foreach ($o in $other) {
            $lines.Add((New-ClaudusLine 'HINWEIS' 'Kairo-SSD' ("{0} ({1}) hat Partitionen {2}. Der Installer löscht die gewählte Platte komplett, Daten darauf vorher sichern" -f $o.Model, $o.Serial, ($o.Letters -join ' '))))
        }
    } catch {
        $lines.Add((New-ClaudusLine 'INFO' 'Platten' ('konnten nicht gelesen werden: ' + $_.Exception.Message)))
    }

    # Mainboard und Tasten
    try {
        $bb = Get-CimInstance Win32_BaseBoard -ErrorAction Stop | Select-Object -First 1
        $k = Get-ClaudusBoardKeys -Vendor $bb.Manufacturer
        $lines.Add((New-ClaudusLine 'INFO' 'Mainboard' ("{0} {1}: Boot-Menü {2}, Setup {3}, Secure Boot: {4}" -f $bb.Manufacturer, $bb.Product, $k.Boot, $k.Setup, $k.SecureBoot)))
    } catch { }

    # Schnellstart
    try {
        $hb = (Get-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Power' -Name HiberbootEnabled -ErrorAction Stop).HiberbootEnabled
        if ($hb -eq 1) {
            $lines.Add((New-ClaudusLine 'HINWEIS' 'Schnellstart' 'Windows-Schnellstart ist an. Für den Umstieg egal, für späteres Dual-Boot besser aus (Admin-Terminal: powercfg /h off)'))
        }
    } catch { }

    # Laptop-Akku
    try {
        if (@(Get-CimInstance Win32_Battery -ErrorAction Stop).Count -gt 0) {
            $lines.Add((New-ClaudusLine 'HINWEIS' 'Strom' 'Laptop: beim Installieren ans Netzteil'))
        }
    } catch { }

    return $lines.ToArray()
}

# ---------------------------------------------------------------------------
# Vorab-Check: Sicherung
# ---------------------------------------------------------------------------

function Get-ClaudusFolderSize {
    param([string]$Path)
    $sum = [int64]0
    $count = 0
    Get-ChildItem -LiteralPath $Path -Recurse -File -Force -ErrorAction SilentlyContinue | ForEach-Object {
        $sum += $_.Length
        $count++
    }
    [pscustomobject]@{ Bytes = $sum; Files = $count }
}

function Get-ClaudusGitState {
    # Zustand eines Git-Repos: Remote? Ungespeicherte Änderungen? Nicht gepusht?
    param([Parameter(Mandatory = $true)][string]$Path, [Parameter(Mandatory = $true)][string]$Git)
    $common = @('-c', 'safe.directory=*', '-C', $Path)
    $remotes = @(& $Git @common remote 2>$null)
    $dirty = @(& $Git @common status --porcelain 2>$null | Where-Object { $_ })
    $ahead = $null
    $null = & $Git @common rev-parse --abbrev-ref '@{u}' 2>$null
    if ($LASTEXITCODE -eq 0) {
        $a = & $Git @common rev-list --count '@{u}..HEAD' 2>$null
        if ($LASTEXITCODE -eq 0) { $ahead = [int]$a }
    }
    [pscustomobject]@{
        Path      = $Path
        HasRemote = ($remotes.Count -gt 0)
        Dirty     = $dirty.Count
        Ahead     = $ahead
    }
}

function Get-ClaudusBackupReport {
    param([string[]]$ProjectRoots = $null)
    $lines = New-Object System.Collections.Generic.List[object]
    $lines.Add((New-ClaudusLine 'INFO' 'Sicherung' 'Nach Plan bleibt Windows auf seiner SSD und wird nicht gelöscht. Diese Liste ist die Versicherung für den Fall, dass beim Installieren die falsche Platte erwischt wird'))

    $oneDrive = [string]$env:OneDrive
    $folders = [ordered]@{
        'Desktop'   = [Environment]::GetFolderPath('Desktop')
        'Dokumente' = [Environment]::GetFolderPath('MyDocuments')
        'Bilder'    = [Environment]::GetFolderPath('MyPictures')
        'Videos'    = [Environment]::GetFolderPath('MyVideos')
        'Musik'     = [Environment]::GetFolderPath('MyMusic')
        'Downloads' = (Join-Path $env:USERPROFILE 'Downloads')
    }
    foreach ($k in $folders.Keys) {
        $p = $folders[$k]
        if (-not $p -or -not (Test-Path -LiteralPath $p)) { continue }
        $s = Get-ClaudusFolderSize -Path $p
        if ($s.Files -eq 0) { continue }
        $txt = '{0} Dateien, {1} ({2})' -f $s.Files, (Format-ClaudusSize $s.Bytes), $p
        if ($oneDrive -and $p.StartsWith($oneDrive, [StringComparison]::OrdinalIgnoreCase)) {
            $lines.Add((New-ClaudusLine 'OK' $k ($txt + ', liegt in OneDrive (gesichert, wenn der Sync grün ist)')))
        } elseif ($k -eq 'Downloads') {
            $lines.Add((New-ClaudusLine 'INFO' $k $txt))
        } else {
            $lines.Add((New-ClaudusLine 'HINWEIS' $k ($txt + ', nur auf diesem PC. Wichtiges auf Stick/externe Platte/Cloud kopieren')))
        }
    }

    # Git-Projekte
    $git = Get-Command git.exe -ErrorAction SilentlyContinue
    if (-not $ProjectRoots) {
        $ProjectRoots = @(
            [Environment]::GetFolderPath('MyDocuments'),
            [Environment]::GetFolderPath('Desktop'),
            (Join-Path $env:USERPROFILE 'source'),
            (Join-Path $env:USERPROFILE 'projects'),
            (Join-Path $env:USERPROFILE 'Projekte')
        )
    }
    $repos = New-Object System.Collections.Generic.List[string]
    foreach ($root in ($ProjectRoots | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -Unique)) {
        Get-ChildItem -LiteralPath $root -Directory -Recurse -Depth 4 -Force -Filter '.git' -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -notmatch '\\node_modules\\' } |
            ForEach-Object { $repos.Add($_.Parent.FullName) }
    }
    $repoList = @($repos | Select-Object -Unique)
    if ($repoList.Count -gt 0 -and -not $git) {
        $lines.Add((New-ClaudusLine 'HINWEIS' 'Projekte' ("{0} Git-Projekte gefunden, aber git.exe fehlt, darum nicht geprüft" -f $repoList.Count)))
    }
    if ($git) {
        foreach ($r in $repoList) {
            $st = Get-ClaudusGitState -Path $r -Git $git.Source
            if (-not $st.HasRemote) {
                $lines.Add((New-ClaudusLine 'WARNUNG' 'Projekt' "$r hat KEIN GitHub/Remote, existiert nur auf diesem PC"))
            } elseif ($st.Dirty -gt 0 -or ($st.Ahead -and $st.Ahead -gt 0)) {
                $t = $r + ':'
                if ($st.Dirty -gt 0) { $t += " $($st.Dirty) ungespeicherte Änderungen" }
                if ($st.Ahead -and $st.Ahead -gt 0) { $t += " $($st.Ahead) Commits nicht gepusht" }
                $lines.Add((New-ClaudusLine 'WARNUNG' 'Projekt' ($t + '. Committen und pushen')))
            } elseif ($null -eq $st.Ahead) {
                $lines.Add((New-ClaudusLine 'HINWEIS' 'Projekt' "$r hat Remote, aber der Zweig ist nicht verknüpft (git push -u)"))
            } else {
                $lines.Add((New-ClaudusLine 'OK' 'Projekt' "$r ist gepusht"))
            }
        }
    }

    # Spielstände
    $saves = @(
        (Join-Path $env:USERPROFILE 'Saved Games'),
        (Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'My Games'),
        (Join-Path $env:APPDATA '.minecraft\saves')
    )
    foreach ($s in $saves) {
        if (Test-Path -LiteralPath $s) {
            $z = Get-ClaudusFolderSize -Path $s
            if ($z.Files -gt 0) {
                $lines.Add((New-ClaudusLine 'HINWEIS' 'Spielstände' ("{0} ({1}). Viele Steam-Spiele haben Cloud-Speicher, der Rest nur hier" -f $s, (Format-ClaudusSize $z.Bytes))))
            }
        }
    }

    # Browser
    $browsers = @()
    if (Test-Path -LiteralPath (Join-Path $env:APPDATA 'Mozilla\Firefox\Profiles')) { $browsers += 'Firefox' }
    if (Test-Path -LiteralPath (Join-Path $env:LOCALAPPDATA 'Google\Chrome\User Data')) { $browsers += 'Chrome' }
    if (Test-Path -LiteralPath (Join-Path $env:LOCALAPPDATA 'Microsoft\Edge\User Data')) { $browsers += 'Edge' }
    if ($browsers.Count -gt 0) {
        $lines.Add((New-ClaudusLine 'HINWEIS' 'Browser' (($browsers -join ', ') + ': Sync mit Konto einschalten, dann sind Lesezeichen und Passwörter in Kairos Firefox wieder da (Firefox-Konto) bzw. exportieren')))
    }

    $lines.Add((New-ClaudusLine 'INFO' 'Zugänge' 'Passwörter für Discord, Steam, Spotify, Google/Microsoft, WLAN griffbereit haben (Handy). 2FA-App aufs Handy, nicht nur am PC'))
    return $lines.ToArray()
}

# ---------------------------------------------------------------------------
# Spickzettel
# ---------------------------------------------------------------------------

function New-ClaudusSpickzettel {
    param([string]$BoardVendor = '', [object[]]$Disks = @(), [string]$IsoTag = '')
    $k = Get-ClaudusBoardKeys -Vendor $BoardVendor
    $nl = "`r`n"
    $t = @()
    $t += 'KAIRO-SPICKZETTEL (von Claudus ' + $script:ClaudusVersion + ')'
    if ($IsoTag) { $t += 'Kairo ' + $IsoTag }
    $t += 'Abfotografieren oder aufs Handy schicken. Volle Anleitung: github.com/kr511/Linux/blob/main/docs/07-test-auf-deinem-pc.md'
    $t += ''
    $t += '== DEINE TASTEN (Mainboard: ' + $BoardVendor + ') =='
    $t += '  Boot-Menü: ' + $k.Boot + '    Setup/BIOS: ' + $k.Setup
    $t += '  Secure Boot aus: ' + $k.SecureBoot
    $t += '  (Taste direkt nach dem Einschalten mehrmals drücken.)'
    $t += ''
    $win = @($Disks | Where-Object { $_.HasWindows })
    $empty = @($Disks | Where-Object { -not $_.HasWindows -and @('USB', 'SD', 'MMC', 'File Backed Virtual') -notcontains $_.BusType -and ($_.Partitions -eq 0 -or $_.PartStyle -eq 'RAW') })
    if ($win.Count -gt 0 -or $empty.Count -gt 0) {
        $t += '== DEINE PLATTEN =='
        foreach ($w in $win)   { $t += '  WINDOWS (abstecken, NICHT wählen): ' + $w.Model + ', SN ' + $w.Serial }
        foreach ($e in $empty) { $t += '  KAIRO-ZIEL (im Installer wählen):  ' + $e.Model + ', SN ' + $e.Serial + ', ' + (Format-ClaudusSize $e.Size) }
        $t += ''
    }
    $t += '== ABLAUF =='
    $t += '  1. Windows herunterfahren (Shift gedrückt halten + Herunterfahren = wirklich aus).'
    $t += '  2. Netzteil-Schalter aus, Windows-SSD abstecken. Wieder an.'
    $t += '  3. Ins Setup (' + $k.Setup + '): Secure Boot aus, CSM/Legacy aus. Speichern (meist F10).'
    $t += '  4. Boot-Menü (' + $k.Boot + '): Eintrag "UEFI: <dein Stick>" wählen.'
    $t += '  5. Live-System: Willkommen > Hardware prüfen. Grafik, Internet, Ton grün? Sonst NICHT installieren.'
    $t += '  6. Installieren: Platte nach SERIENNUMMER wählen, Verschlüsselung an, Passwort AUFSCHREIBEN.'
    $t += '     Bestätigen mit LÖSCHEN. Warten bis "Kairo ist installiert".'
    $t += '  7. Herunterfahren, Stick ab, starten. Passwort: deutsche Tastatur (y/z vertauscht beachten).'
    $t += '  8. Erst wenn alles läuft: Windows-SSD wieder anstecken. Windows dann über ' + $k.Boot + ' starten.'
    $t += ''
    $t += '== NOTFALL =='
    $t += '  Stick startet nicht:     Secure Boot wirklich aus? Anderen USB-Port (hinten am Mainboard) nehmen.'
    $t += '  Schwarzer Bildschirm:    Im Kairo-Bootmenü Eintrag markieren, "e" drücken (altes BIOS-Menü: Tab),'
    $t += '                           am Zeilenende " nomodeset" anhängen, Enter. Danach melden, das ist ein Treiberproblem.'
    $t += '  Kein Internet:           LAN-Kabel, oder Handy per USB + "USB-Tethering" einschalten.'
    $t += '  Desktop hängt (Live):    Strg+Alt+F5 = Notfall-Konsole.'
    $t += '  Installation bricht ab:  Foto vom Fenster, dann: cat /tmp/kairo-install.log (abfotografieren).'
    $t += '  Kairo startet nach Update nicht: Bootmenü "Kairo OS (Notfall)" oder App "Kairo Wiederherstellen".'
    $t += '  Kairo startet gar nicht: Vom Stick starten, Terminal, sudo kairo-rollback, Snapshot wählen.'
    $t += '  Zurück zu Windows:       Windows-SSD anstecken, ' + $k.Boot + ', "Windows Boot Manager". Kairo ändert an Windows nichts.'
    $t += '  Windows will BitLocker-Schlüssel: https://aka.ms/myrecoverykey  (oder Secure Boot wieder an).'
    $t += '  Kairo-Passwort vergessen: keine Rettung, nur Neuinstallation. Darum aufschreiben.'
    return ($t -join $nl)
}

# ---------------------------------------------------------------------------
# Plan B: Rufus
# ---------------------------------------------------------------------------

function Get-ClaudusRufus {
    # Lädt die portable Rufus-Version vom offiziellen GitHub-Release und
    # prüft die digitale Signatur (Akeo Consulting).
    param([string]$WorkDir = (Get-ClaudusDefaultWorkDir))
    Enable-ClaudusTls
    New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null
    $rel = Invoke-RestMethod -Uri 'https://api.github.com/repos/pbatard/rufus/releases/latest' -Headers @{ 'User-Agent' = 'Claudus' } -UseBasicParsing -ErrorAction Stop
    $asset = @($rel.assets | Where-Object { $_.name -match '^rufus-[0-9.]+p\.exe$' }) | Select-Object -First 1
    if (-not $asset) { throw 'Keine portable Rufus-Datei im Release gefunden. Hol Rufus von https://rufus.ie' }
    $path = Join-Path $WorkDir $asset.name
    if (-not (Test-Path -LiteralPath $path)) { Save-ClaudusFile -Url $asset.browser_download_url -Path $path }
    $sig = Get-AuthenticodeSignature -FilePath $path
    if ($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notmatch 'Akeo') {
        Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
        throw "Rufus-Signatur stimmt nicht ($($sig.Status)). Datei gelöscht. Hol Rufus von https://rufus.ie"
    }
    return $path
}
