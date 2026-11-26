#
# Unit-Tests für Claudus. Läuft unter Windows PowerShell 5.1 und PowerShell 7.
# Schreibt nichts auf Platten. Aufruf:
#   powershell -ExecutionPolicy Bypass -File windows\claudus\tests\Test-Claudus.ps1
#
# Exit-Code 0 = alles bestanden.

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$script:pass = 0
$script:fail = 0

function Assert-True {
    param([bool]$Condition, [string]$Name)
    if ($Condition) {
        $script:pass++
        Write-Host "ok   $Name"
    } else {
        $script:fail++
        Write-Host "FAIL $Name" -ForegroundColor Red
    }
}

function Assert-Throws {
    param([scriptblock]$Block, [string]$Name)
    $threw = $false
    try { & $Block | Out-Null } catch { $threw = $true }
    Assert-True $threw $Name
}

Write-Host ('PowerShell ' + $PSVersionTable.PSVersion)

# --- Syntax aller Skripte ---------------------------------------------------
foreach ($f in (Get-ChildItem -LiteralPath $root -Recurse -Filter '*.ps1')) {
    $tokens = $null
    $errors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile($f.FullName, [ref]$tokens, [ref]$errors)
    Assert-True ($errors.Count -eq 0) ("Syntax ok: " + $f.Name + (($errors | ForEach-Object { ' | ' + $_.Message + ' Zeile ' + $_.Extent.StartLineNumber }) -join ''))
}

. (Join-Path $root 'ClaudusLib.ps1')

# --- Sicherheitsprüfung der Zielplatte --------------------------------------
function New-MockDisk {
    param([int]$Number = 5, $Bus = 'USB', [int64]$Size = 32GB, [switch]$Boot, [switch]$System,
          [switch]$ReadOnly, [switch]$Offline, [string]$Serial = 'ABC123', [string]$UniqueId = 'UID-1')
    [pscustomobject]@{
        Number = $Number; BusType = $Bus; Size = $Size; IsBoot = [bool]$Boot; IsSystem = [bool]$System
        IsReadOnly = [bool]$ReadOnly; IsOffline = [bool]$Offline; Serial = $Serial; UniqueId = $UniqueId
    }
}
$iso = [int64]1717075968

Assert-True (Test-ClaudusTargetDisk -Disk (New-MockDisk) -MinBytes $iso).Ok 'USB-Stick 32 GB ist erlaubt'
Assert-True (Test-ClaudusTargetDisk -Disk (New-MockDisk -Bus 7) -MinBytes $iso).Ok 'BusType als Zahl 7 = USB wird erkannt'
Assert-True (Test-ClaudusTargetDisk -Disk (New-MockDisk -Bus 'SD') -MinBytes $iso).Ok 'SD-Karte ist erlaubt'
Assert-True (-not (Test-ClaudusTargetDisk -Disk (New-MockDisk -Bus 'NVMe') -MinBytes $iso).Ok) 'NVMe-SSD ist gesperrt'
Assert-True (-not (Test-ClaudusTargetDisk -Disk (New-MockDisk -Bus 'SATA') -MinBytes $iso).Ok) 'SATA-Platte ist gesperrt'
Assert-True (-not (Test-ClaudusTargetDisk -Disk (New-MockDisk -Bus 'File Backed Virtual') -MinBytes $iso).Ok) 'virtuelle Platte ist gesperrt'
Assert-True (-not (Test-ClaudusTargetDisk -Disk (New-MockDisk -Boot) -MinBytes $iso).Ok) 'USB mit IsBoot ist gesperrt'
Assert-True (-not (Test-ClaudusTargetDisk -Disk (New-MockDisk -System) -MinBytes $iso).Ok) 'USB mit IsSystem ist gesperrt'
Assert-True (-not (Test-ClaudusTargetDisk -Disk (New-MockDisk -Number 2) -MinBytes $iso -SystemDiskNumbers @(0, 2)).Ok) 'USB mit Windows/Auslagerungsdatei ist gesperrt'
Assert-True (-not (Test-ClaudusTargetDisk -Disk (New-MockDisk -Size 1TB) -MinBytes $iso).Ok) 'USB-Platte 1 TB ist gesperrt'
Assert-True (Test-ClaudusTargetDisk -Disk (New-MockDisk -Size 256GB) -MinBytes $iso).Ok '256 GB ist gerade noch erlaubt'
Assert-True (-not (Test-ClaudusTargetDisk -Disk (New-MockDisk -Size 1GB) -MinBytes $iso).Ok) 'zu kleiner Stick ist gesperrt'
Assert-True (-not (Test-ClaudusTargetDisk -Disk (New-MockDisk -Size 0) -MinBytes $iso).Ok) 'leerer Kartenleser ist gesperrt'
Assert-True (-not (Test-ClaudusTargetDisk -Disk (New-MockDisk -ReadOnly) -MinBytes $iso).Ok) 'schreibgeschützt ist gesperrt'
Assert-True (-not (Test-ClaudusTargetDisk -Disk (New-MockDisk -Offline) -MinBytes $iso).Ok) 'offline ist gesperrt'
$r = Test-ClaudusTargetDisk -Disk (New-MockDisk -Bus 'NVMe' -Boot) -MinBytes $iso
Assert-True ($r.Reasons.Count -ge 2) 'mehrere Sperrgründe werden alle genannt'

# --- Gleiche Platte? ----------------------------------------------------------
$a = New-MockDisk
Assert-True (Test-ClaudusSameDisk -Before $a -Now (New-MockDisk)) 'gleiche Platte wird erkannt'
Assert-True (-not (Test-ClaudusSameDisk -Before $a -Now (New-MockDisk -Serial 'XYZ'))) 'anderer Stick (Seriennummer) wird erkannt'
Assert-True (-not (Test-ClaudusSameDisk -Before $a -Now (New-MockDisk -Size 64GB))) 'anderer Stick (Größe) wird erkannt'
Assert-True (-not (Test-ClaudusSameDisk -Before $a -Now (New-MockDisk -UniqueId 'UID-2'))) 'anderer Stick (ID) wird erkannt'
Assert-True (-not (Test-ClaudusSameDisk -Before $a -Now (New-MockDisk -Number 6))) 'andere Nummer wird erkannt'

# --- SHA256SUMS -----------------------------------------------------------------
$h = 'ABCDEF0123456789abcdef0123456789abcdef0123456789abcdef0123456789'
$sums = "$h  kairo-1.0.1-2026.11.25-x86_64.iso`n"
Assert-True ((Get-ClaudusExpectedHash -SumsText $sums -FileName 'kairo-1.0.1-2026.11.25-x86_64.iso') -eq $h.ToLowerInvariant()) 'SHA256SUMS wird gelesen'
$sums2 = "1111111111111111111111111111111111111111111111111111111111111111 *andere.iso`r`n$h *out/kairo-1.0.2-2026.12.01-x86_64.iso`r`n"
Assert-True ((Get-ClaudusExpectedHash -SumsText $sums2 -FileName 'kairo-1.0.2-2026.12.01-x86_64.iso') -eq $h.ToLowerInvariant()) 'SHA256SUMS mit * und Pfad'
Assert-Throws { Get-ClaudusExpectedHash -SumsText $sums -FileName 'gibtsnicht.iso' } 'fehlender Eintrag wirft'
Assert-Throws { Get-ClaudusExpectedHash -SumsText 'kaputt  kairo.iso' -FileName 'kairo.iso' } 'kaputte Zeile wird nicht akzeptiert'

# --- Ausrichtung ----------------------------------------------------------------
Assert-True ((Get-ClaudusAlignedLength -Length 4096) -eq 4096) 'ausgerichtet bleibt gleich'
Assert-True ((Get-ClaudusAlignedLength -Length 4097) -eq 8192) 'wird auf 4096 aufgerundet'
Assert-True ((Get-ClaudusAlignedLength -Length $iso) -eq $iso) 'Kairo-1.0.1-ISO ist schon ausgerichtet'

# --- Tasten und WLAN-Einschätzung --------------------------------------------
Assert-True ((Get-ClaudusBoardKeys 'ASUSTeK COMPUTER INC.').Boot -eq 'F8') 'ASUS: F8'
Assert-True ((Get-ClaudusBoardKeys 'Micro-Star International Co., Ltd.').Boot -eq 'F11') 'MSI: F11'
Assert-True ((Get-ClaudusBoardKeys 'Gigabyte Technology Co., Ltd.').Boot -eq 'F12') 'Gigabyte: F12'
Assert-True ((Get-ClaudusBoardKeys 'ASRock').Boot -eq 'F11') 'ASRock: F11'
Assert-True ((Get-ClaudusBoardKeys 'Irgendwer GmbH').Name -eq 'unbekannt') 'unbekannter Hersteller'
Assert-True ((Get-ClaudusWifiVerdict 'PCI\VEN_8086&DEV_2723' 'Intel Wi-Fi 6 AX200')[0] -eq 'OK') 'Intel-WLAN ok'
Assert-True ((Get-ClaudusWifiVerdict 'PCI\VEN_14C3&DEV_7902' 'MediaTek')[0] -eq 'HINWEIS') 'MT7902 bekommt Hinweis'
Assert-True ((Get-ClaudusWifiVerdict 'PCI\VEN_14C3&DEV_0616' 'MediaTek MT7922')[0] -eq 'OK') 'MT7922 ok'
Assert-True ((Get-ClaudusWifiVerdict 'USB\VID_0BDA&PID_C811' 'Realtek 8811CU')[0] -eq 'HINWEIS') 'Realtek-USB bekommt Hinweis'
Assert-True ((Get-ClaudusWifiVerdict 'PCI\VEN_14E4&DEV_43A0' 'Broadcom')[0] -eq 'HINWEIS') 'Broadcom bekommt Hinweis'

# --- Spickzettel ----------------------------------------------------------------
$disks = @(
    [pscustomobject]@{ Number = 0; Model = 'Samsung 970'; Serial = 'S1'; Size = 500GB; BusType = 'NVMe'; Partitions = 4; PartStyle = 'GPT'; HasWindows = $true },
    [pscustomobject]@{ Number = 1; Model = 'Crucial P3'; Serial = 'C2'; Size = 1TB; BusType = 'NVMe'; Partitions = 0; PartStyle = 'RAW'; HasWindows = $false },
    [pscustomobject]@{ Number = 2; Model = 'SanDisk'; Serial = 'U3'; Size = 32GB; BusType = 'USB'; Partitions = 0; PartStyle = 'RAW'; HasWindows = $false }
)
$sheet = New-ClaudusSpickzettel -BoardVendor 'Micro-Star International Co., Ltd.' -Disks $disks -IsoTag 'v1.0.1'
Assert-True ($sheet -match 'Boot-Menü: F11') 'Spickzettel nennt die Boot-Taste'
Assert-True ($sheet -match 'WINDOWS.*Samsung 970.*S1') 'Spickzettel nennt die Windows-Platte'
Assert-True ($sheet -match 'KAIRO-ZIEL.*Crucial P3.*C2') 'Spickzettel nennt die leere Ziel-SSD'
Assert-True (-not ($sheet -match 'KAIRO-ZIEL.*SanDisk')) 'USB-Stick wird nicht als Ziel-SSD vorgeschlagen'
Assert-True ($sheet -match 'nomodeset') 'Spickzettel hat den Notfall für schwarzen Bildschirm'
Assert-True ($sheet -match 'kairo-rollback') 'Spickzettel nennt kairo-rollback'

# --- Auf echtem Windows: Berichte laufen durch, Systemplatte ist gesperrt -----
$onWindows = ($PSVersionTable.PSVersion.Major -le 5) -or $IsWindows
if ($onWindows) {
    $info = @(Get-ClaudusDiskInfo -MinBytes $iso)
    Assert-True ($info.Count -ge 1) 'Get-ClaudusDiskInfo findet Platten'
    $sysNum = (Get-Partition -DriveLetter $env:SystemDrive.Substring(0, 1)).DiskNumber
    $sysInfo = @($info | Where-Object { $_.Number -eq $sysNum })
    Assert-True ($sysInfo.Count -eq 1 -and -not $sysInfo[0].Ok) 'Windows-Platte ist gesperrt'
    Assert-True ($sysInfo.Count -eq 1 -and $sysInfo[0].HasWindows) 'Windows-Platte ist als solche erkannt'
    $hw = @(Get-ClaudusHardwareReport)
    Assert-True ($hw.Count -ge 3) ('Hardware-Bericht hat Zeilen (' + $hw.Count + ')')
    Write-ClaudusLines $hw
    $bk = @(Get-ClaudusBackupReport)
    Assert-True ($bk.Count -ge 2) ('Sicherungs-Bericht hat Zeilen (' + $bk.Count + ')')
    Write-ClaudusLines $bk
    $text = ConvertTo-ClaudusLinesText ($hw + $bk)
    Assert-True ($text.Length -gt 50) 'Bericht als Text'
}

Write-Host ''
Write-Host ("{0} bestanden, {1} fehlgeschlagen" -f $script:pass, $script:fail)
if ($script:fail -gt 0) { exit 1 }
exit 0
