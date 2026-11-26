#
# Claudus: Wechsel-Kit für Kairo OS (Windows).
#
# Start: Doppelklick auf Claudus.cmd (fragt nach Administratorrechten).
# Oder in PowerShell als Administrator:
#   powershell -ExecutionPolicy Bypass -File .\Claudus.ps1 [-Action Check|Iso|Write|Verify|Sheet|Rufus|All]
#
# Claudus ändert nichts an Windows. Gelöscht und beschrieben wird nur der
# USB-Stick, den du auswählst und mit LÖSCHEN bestätigst.

[CmdletBinding()]
param(
    [ValidateSet('Menu', 'Check', 'Iso', 'Write', 'Verify', 'Sheet', 'Rufus', 'All')]
    [string]$Action = 'Menu',
    [string]$WorkDir = ''
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'ClaudusLib.ps1')
if (-not $WorkDir) { $WorkDir = Get-ClaudusDefaultWorkDir }
try { $Host.UI.RawUI.WindowTitle = 'Claudus ' + $script:ClaudusVersion } catch { }

function Show-Banner {
    Write-Host ''
    Write-Host '   ____ _                 _           ' -ForegroundColor Green
    Write-Host '  / ___| | __ _ _   _  __| |_   _ ___ ' -ForegroundColor Green
    Write-Host ' | |   | |/ _` | | | |/ _` | | | / __|' -ForegroundColor Green
    Write-Host ' | |___| | (_| | |_| | (_| | |_| \__ \' -ForegroundColor Green
    Write-Host '  \____|_|\__,_|\__,_|\__,_|\__,_|___/' -ForegroundColor Green
    Write-Host ('  Wechsel-Kit für Kairo OS, Version {0}' -f $script:ClaudusVersion)
    Write-Host ''
}

function Read-Answer([string]$Prompt) {
    Write-Host $Prompt -NoNewline -ForegroundColor White
    return ([string](Read-Host)).Trim()
}

function Get-Iso {
    # Geprüfte ISO besorgen: aus dem Internet, sonst eine schon geprüfte lokale.
    try {
        return Get-ClaudusIso -WorkDir $WorkDir
    } catch {
        Write-Host ('ISO holen ging nicht: ' + $_.Exception.Message) -ForegroundColor Red
        $local = Find-ClaudusLocalIso -WorkDir $WorkDir
        if ($local) {
            Write-Host 'Nehme die schon geladene ISO und prüfe sie erneut ...'
            if ((Get-ClaudusFileSha256 -Path $local.Path) -eq $local.Hash) { return $local }
            Write-Host 'Auch die lokale ISO passt nicht zur Prüfsumme.' -ForegroundColor Red
        }
        return $null
    }
}

function Invoke-Check {
    Write-Host '== Vorab-Check: Hardware ==' -ForegroundColor Cyan
    $hw = @(Get-ClaudusHardwareReport)
    Write-ClaudusLines $hw
    Write-Host ''
    Write-Host '== Vorab-Check: Sicherung (dauert je nach Dateien eine Minute) ==' -ForegroundColor Cyan
    $bk = @(Get-ClaudusBackupReport)
    Write-ClaudusLines $bk
    $report = Join-Path (Get-ClaudusDesktop) 'Claudus-Bericht.txt'
    $head = 'Claudus-Bericht vom ' + (Get-Date -Format 'dd.MM.yyyy HH:mm')
    [IO.File]::WriteAllText($report, ($head + "`r`n`r`n" + (ConvertTo-ClaudusLinesText ($hw + $bk))), (New-Object Text.UTF8Encoding($true)))
    Write-Host ''
    $warn = @(($hw + $bk) | Where-Object { $_.Level -eq 'WARNUNG' }).Count
    if ($warn -gt 0) {
        Write-Host "$warn WARNUNG(EN): erst erledigen, dann wechseln." -ForegroundColor Red
    } else {
        Write-Host 'Keine Warnungen. Gelbe Hinweise trotzdem lesen.' -ForegroundColor Green
    }
    Write-Host "Bericht gespeichert: $report"
}

function Invoke-Write {
    if (-not (Test-ClaudusAdmin)) {
        Write-Host 'Zum Schreiben braucht Claudus Administratorrechte. Starte Claudus.cmd per Doppelklick.' -ForegroundColor Red
        return
    }
    $iso = Get-Iso
    if (-not $iso) { return }
    Write-Host ('ISO geprüft: {0} (SHA256 passt)' -f $iso.Name) -ForegroundColor Green
    Write-Host ''
    Write-Host 'Steck jetzt den USB-Stick ein (alles darauf wird gelöscht). Andere USB-Sticks und externe Platten am besten abziehen.'
    [void](Read-Answer 'Enter drücken, wenn der Stick steckt ... ')

    $minBytes = Get-ClaudusAlignedLength -Length $iso.Size
    $disks = @(Get-ClaudusDiskInfo -MinBytes $minBytes)
    Write-Host ''
    Write-Host 'Gefundene Laufwerke:'
    foreach ($d in $disks) {
        $line = '  [{0}] {1}, {2}, {3}' -f $d.Number, $d.Model, (Format-ClaudusSize $d.Size), $d.BusType
        if ($d.Letters.Count -gt 0) { $line += ' (' + ($d.Letters -join ' ') + ')' }
        if ($d.Ok) {
            Write-Host ($line + '  <- möglich') -ForegroundColor Green
        } else {
            Write-Host ($line + '  gesperrt: ' + ($d.Reasons -join ', ')) -ForegroundColor DarkGray
        }
    }
    $ok = @($disks | Where-Object { $_.Ok })
    if ($ok.Count -eq 0) {
        Write-Host ''
        Write-Host 'Kein passender USB-Stick gefunden (mind. 2 GB, höchstens 256 GB, per USB). Stick neu einstecken und nochmal.' -ForegroundColor Yellow
        return
    }
    $answer = Read-Answer 'Nummer des Sticks eintippen (oder Enter zum Abbrechen): '
    if (-not $answer) { Write-Host 'Abgebrochen, nichts geändert.'; return }
    $pick = @($ok | Where-Object { [string]$_.Number -eq $answer }) | Select-Object -First 1
    if (-not $pick) { Write-Host 'Diese Nummer ist nicht freigegeben. Abgebrochen, nichts geändert.' -ForegroundColor Red; return }

    Write-Host ''
    Write-Host ('GELÖSCHT WIRD: {0}, {1}, Seriennummer {2}' -f $pick.Model, (Format-ClaudusSize $pick.Size), $pick.Serial) -ForegroundColor Red
    if ($pick.Letters.Count -gt 0) { Write-Host ('Das sind deine Laufwerke ' + ($pick.Letters -join ' ') + '. Alles darauf ist danach weg.') -ForegroundColor Red }
    $confirm = Read-Answer 'Zum Bestätigen LÖSCHEN eintippen: '
    if (@('LÖSCHEN', 'LOESCHEN') -notcontains $confirm.ToUpperInvariant()) { Write-Host 'Nicht bestätigt. Nichts geändert.'; return }

    # Direkt vorher nochmal lesen: steckt noch derselbe Stick?
    $now = @(Get-ClaudusDiskInfo -MinBytes $minBytes | Where-Object { $_.Number -eq $pick.Number }) | Select-Object -First 1
    if (-not $now -or -not $now.Ok -or -not (Test-ClaudusSameDisk -Before $pick -Now $now)) {
        Write-Host 'Der Stick hat sich seit der Auswahl verändert (abgezogen oder getauscht). Abbruch, nichts geschrieben.' -ForegroundColor Red
        return
    }

    try {
        $res = Invoke-ClaudusWriteCore -Iso $iso -DiskNumber $pick.Number
    } catch {
        Write-Host ('Schreiben fehlgeschlagen: ' + $_.Exception.Message) -ForegroundColor Red
        Write-Host 'Plan B: Im Menü [6] Rufus starten, Kairo-ISO wählen, beim Nachfragen "DD-Modus" nehmen.' -ForegroundColor Yellow
        return
    }
    if ($res.Ok) {
        Write-Host ''
        Write-Host 'FERTIG: Stick geschrieben und Bit für Bit zurückgelesen, Prüfsumme passt.' -ForegroundColor Green
        Write-Host 'Fragt Windows jetzt nach Formatieren: Abbrechen. Den Stick kannst du abziehen.'
        Write-Host 'Weiter mit dem Spickzettel (Menü [5]).'
    } else {
        Write-Host ''
        Write-Host 'FEHLER: Was auf dem Stick steht, passt nicht zur ISO.' -ForegroundColor Red
        Write-Host ('  erwartet {0}' -f $res.Expected)
        Write-Host ('  gelesen  {0}' -f $res.Actual)
        Write-Host 'Meist ist der Stick defekt oder gefälscht. Anderen Stick nehmen oder Plan B (Rufus).' -ForegroundColor Yellow
    }
}

function Invoke-Verify {
    if (-not (Test-ClaudusAdmin)) { Write-Host 'Braucht Administratorrechte (Claudus.cmd).' -ForegroundColor Red; return }
    $iso = Find-ClaudusLocalIso -WorkDir $WorkDir
    if (-not $iso) { Write-Host 'Keine geladene ISO gefunden. Erst [2] ausführen.' -ForegroundColor Yellow; return }
    $disks = @(Get-ClaudusDiskInfo -MinBytes $iso.Size | Where-Object { $_.Ok })
    if ($disks.Count -eq 0) { Write-Host 'Kein USB-Stick gefunden.' -ForegroundColor Yellow; return }
    foreach ($d in $disks) { Write-Host ('  [{0}] {1}, {2}' -f $d.Number, $d.Model, (Format-ClaudusSize $d.Size)) }
    $answer = Read-Answer 'Welcher Stick soll geprüft werden (nur lesen)? '
    $pick = @($disks | Where-Object { [string]$_.Number -eq $answer }) | Select-Object -First 1
    if (-not $pick) { Write-Host 'Abgebrochen.'; return }
    $hash = Get-ClaudusDeviceSha256 -DevicePath (Get-ClaudusDevicePath -DiskNumber $pick.Number) -Length $iso.Size
    if ($hash -eq $iso.Hash) {
        Write-Host ('Stick ist in Ordnung: identisch mit {0}.' -f $iso.Name) -ForegroundColor Green
    } else {
        Write-Host 'Stick passt NICHT zur ISO. Neu schreiben (Menü [3]).' -ForegroundColor Red
    }
}

function Invoke-Sheet {
    $vendor = ''
    try { $vendor = [string](Get-CimInstance Win32_BaseBoard -ErrorAction Stop | Select-Object -First 1).Manufacturer } catch { }
    $disks = @()
    try { $disks = @(Get-ClaudusDiskInfo) } catch { }
    $tag = ''
    $local = Find-ClaudusLocalIso -WorkDir $WorkDir
    if ($local) { $tag = $local.Tag }
    $text = New-ClaudusSpickzettel -BoardVendor $vendor -Disks $disks -IsoTag $tag
    $path = Join-Path (Get-ClaudusDesktop) 'Kairo-Spickzettel.txt'
    [IO.File]::WriteAllText($path, $text, (New-Object Text.UTF8Encoding($true)))
    Write-Host $text
    Write-Host ''
    Write-Host "Gespeichert: $path  (abfotografieren oder ausdrucken)" -ForegroundColor Green
    try { Start-Process notepad.exe -ArgumentList ('"' + $path + '"') } catch { }
}

function Invoke-Rufus {
    try {
        $rufus = Get-ClaudusRufus -WorkDir $WorkDir
    } catch {
        Write-Host $_.Exception.Message -ForegroundColor Red
        return
    }
    Write-Host 'Rufus ist da und echt signiert. So geht es dort:' -ForegroundColor Green
    Write-Host '  1. Laufwerk: deinen USB-Stick wählen (Name prüfen!)'
    Write-Host '  2. AUSWAHL: die Kairo-ISO aus ' $WorkDir
    Write-Host '  3. START. Fragt Rufus "ISOHybrid-Abbild erkannt": "Im DD-Abbild-Modus schreiben" wählen.'
    Write-Host '  4. Warnung "Alle Daten werden gelöscht": OK. Danach ist der Stick fertig.'
    Start-Process -FilePath $rufus
}

function Invoke-Menu {
    while ($true) {
        Show-Banner
        if (-not (Test-ClaudusAdmin)) {
            Write-Host '  (Ohne Administratorrechte gestartet: [3] und [4] gehen nur über Claudus.cmd)' -ForegroundColor Yellow
        }
        Write-Host '  [1] Vorab-Check: Hardware + Sicherung (ändert nichts)'
        Write-Host '  [2] Kairo-ISO laden und Prüfsumme checken'
        Write-Host '  [3] USB-Stick schreiben und zurücklesen (löscht den Stick)'
        Write-Host '  [4] Stick nachprüfen (nur lesen)'
        Write-Host '  [5] Spickzettel für den Wechsel (Tasten, Ablauf, Notfall)'
        Write-Host '  [6] Plan B: Rufus holen und starten'
        Write-Host '  [A] Alles der Reihe nach (1, 3, 5)'
        Write-Host '  [Q] Beenden'
        $c = (Read-Answer '  Auswahl: ').ToUpperInvariant()
        Write-Host ''
        try {
            switch ($c) {
                '1' { Invoke-Check }
                '2' { $i = Get-Iso; if ($i) { Write-Host ('OK: {0}, SHA256 {1}' -f $i.Path, $i.Hash) -ForegroundColor Green } }
                '3' { Invoke-Write }
                '4' { Invoke-Verify }
                '5' { Invoke-Sheet }
                '6' { Invoke-Rufus }
                'A' { Invoke-Check; Write-Host ''; Invoke-Write; Write-Host ''; Invoke-Sheet }
                'Q' { return }
                default { Write-Host 'Unbekannte Auswahl.' }
            }
        } catch {
            Write-Host ('Fehler: ' + $_.Exception.Message) -ForegroundColor Red
        }
        Write-Host ''
        [void](Read-Answer 'Enter für das Menü ... ')
    }
}

try {
    switch ($Action) {
        'Menu'   { Invoke-Menu }
        'Check'  { Invoke-Check }
        'Iso'    { $i = Get-Iso; if (-not $i) { exit 1 }; Write-Host $i.Path }
        'Write'  { Invoke-Write }
        'Verify' { Invoke-Verify }
        'Sheet'  { Invoke-Sheet }
        'Rufus'  { Invoke-Rufus }
        'All'    { Invoke-Check; Invoke-Write; Invoke-Sheet }
    }
} catch {
    Write-Host ('Claudus ist abgestürzt: ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host $_.ScriptStackTrace
    if ($Action -eq 'Menu') { [void](Read-Host 'Enter zum Schließen') }
    exit 1
}
