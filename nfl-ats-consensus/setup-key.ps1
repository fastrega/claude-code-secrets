# Save an OpenRouter API key on THIS Windows machine, safely.
#
#   powershell -ExecutionPolicy Bypass -File .\setup-key.ps1
#
# The key is read as a SecureString so it is never echoed to the console and
# never becomes a command argument, which keeps it out of your terminal
# scrollback and out of PowerShell history. It is written to
# %USERPROFILE%\.config\atsc\env with the ACL reset so only you can read it,
# outside the git tree entirely, so it cannot be committed by accident.

$ErrorActionPreference = 'Stop'

$ConfigDir  = Join-Path $env:USERPROFILE '.config\atsc'
$ConfigFile = Join-Path $ConfigDir 'env'

Write-Host 'OpenRouter key setup'
Write-Host "  destination: $ConfigFile"
Write-Host '  get a key at https://openrouter.ai/keys'
Write-Host ''

if ((Test-Path $ConfigFile) -and (Select-String -Path $ConfigFile -Pattern '^OPENROUTER_API_KEY=' -Quiet)) {
    $reply = Read-Host 'A key is already saved there. Replace it? [y/N]'
    if ($reply -notmatch '^[yY]') {
        Write-Host 'Left unchanged.'
        exit 0
    }
}

# -AsSecureString suppresses echo. The plaintext exists only inside this
# process, for as long as it takes to write the file.
$Secure = Read-Host 'Paste your key (it will not be shown), then press Enter' -AsSecureString

$Bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secure)
try {
    $Key = [System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($Bstr)
} finally {
    # Zero the unmanaged copy rather than leaving it in memory to be swapped out.
    [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Bstr)
}

if ([string]::IsNullOrWhiteSpace($Key)) {
    # Write-Error under ErrorActionPreference='Stop' throws a stack trace at the
    # user for what is just an empty input, so report it plainly instead.
    Write-Host 'Nothing entered. Aborted.'
    exit 1
}

$Key = $Key.Trim()
if (-not $Key.StartsWith('sk-or-')) {
    Write-Host 'Warning: OpenRouter keys normally start with "sk-or-". Saving anyway.'
}

New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null

# UTF8 without BOM: a BOM would become part of the first variable name and the
# key would silently fail to load.
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($ConfigFile, "OPENROUTER_API_KEY=$Key`n", $Utf8NoBom)

# Windows has no chmod. Break inheritance from the parent directory and grant
# read access to this user only, which is the NTFS equivalent of 0600.
try {
    icacls $ConfigFile /inheritance:r /grant:r "$($env:USERNAME):(R,W)" | Out-Null
    Write-Host ''
    Write-Host "Saved to $ConfigFile (readable only by $env:USERNAME)."
} catch {
    Write-Host ''
    Write-Host "Saved to $ConfigFile."
    Write-Host 'Could not tighten the file permissions automatically; the file is still saved.'
}

$Key = $null
[System.GC]::Collect()

Write-Host 'The key is outside the git tree, so it cannot be committed.'
Write-Host ''
Write-Host 'Verifying — this prints a fingerprint, never the key itself:'
Write-Host ''

$Python = $null
foreach ($candidate in @('python', 'py', 'python3')) {
    if (Get-Command $candidate -ErrorAction SilentlyContinue) { $Python = $candidate; break }
}

if ($Python) {
    & $Python -m atsc.cli doctor
    if ($LASTEXITCODE -ne 0) {
        Write-Host ''
        Write-Host '  Could not run the check — the key is still saved.'
        Write-Host '  Most likely the dependencies are missing. From this directory:'
        Write-Host ''
        Write-Host "      $Python -m pip install -r requirements.txt"
        Write-Host "      $Python -m atsc.cli doctor"
    }
} else {
    Write-Host '  Python was not found on PATH — the key is still saved.'
    Write-Host '  Install Python 3.11+ from https://python.org (tick "Add python.exe to PATH"),'
    Write-Host '  then run:  python -m pip install -r requirements.txt'
}
