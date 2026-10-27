param(
    [Parameter(Mandatory = $true)][string]$Destination,
    [string]$DownloadPython = 'python',
    [string]$Archive = ''
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$RuntimeLock = Get-Content -LiteralPath "$PSScriptRoot/runtime.json" -Raw | ConvertFrom-Json
if (Test-Path -LiteralPath $Destination) { throw "Runtime destination already exists: $Destination" }
$RuntimeDirectory = New-Item -ItemType Directory -Path $Destination
$ArchivePath = Join-Path $RuntimeDirectory.FullName 'python.tar.gz'
if ($Archive) {
    Copy-Item -LiteralPath $Archive -Destination $ArchivePath
} else {
    # The runner's existing Python downloads bytes only. Tests use the verified runtime below.
    & $DownloadPython -I -c 'import sys,urllib.request; urllib.request.urlretrieve(sys.argv[1],sys.argv[2])' $RuntimeLock.url $ArchivePath
    if ($LASTEXITCODE -ne 0) { throw 'Python archive download failed' }
}
$ActualHash = (Get-FileHash -LiteralPath $ArchivePath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($ActualHash -ne $RuntimeLock.sha256) { throw 'Python archive SHA-256 mismatch; archive will not be executed' }
& tar -xzf $ArchivePath -C $RuntimeDirectory.FullName
if ($LASTEXITCODE -ne 0) { throw 'Python archive extraction failed' }
$RuntimePython = Join-Path $RuntimeDirectory.FullName 'python/python.exe'
& $RuntimePython -I -X utf8 -c 'import platform,sys; assert platform.python_implementation()=="CPython"; assert sys.version_info[:3]==(3,12,14); print(sys.version)'
if ($LASTEXITCODE -ne 0) { throw 'Python runtime version verification failed' }
if ($env:GITHUB_PATH) {
    Split-Path -Parent $RuntimePython | Out-File -FilePath $env:GITHUB_PATH -Encoding utf8 -Append
    Join-Path (Split-Path -Parent $RuntimePython) 'Scripts' | Out-File -FilePath $env:GITHUB_PATH -Encoding utf8 -Append
}
Write-Output "Verified Python: $RuntimePython"
