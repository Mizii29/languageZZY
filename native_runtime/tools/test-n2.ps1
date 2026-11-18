param([Parameter(Mandatory=$true)][string]$BuildDirectory,[Parameter(Mandatory=$true)][string]$Output)
$ErrorActionPreference='Stop'
$build=(Resolve-Path -LiteralPath $BuildDirectory).Path
if(Test-Path -LiteralPath $Output) {throw 'Choose a new evidence directory'}
New-Item -ItemType Directory -Path $Output | Out-Null
$log=Join-Path $Output 'native-tests.txt'
foreach($name in @('native-protocol-tests','native-frontend-tests','native-heap-tests','native-program-tests')) {
    $text=& (Join-Path $build ($name+'.exe')) 2>&1
    $code=$LASTEXITCODE
    $text | Tee-Object -FilePath $log -Append
    if($code -ne 0) {throw ('Native test failed: '+$name)}
}
$text=& (Join-Path $build 'native-program-tests.exe') unknown 2>&1
$code=$LASTEXITCODE
$text | Tee-Object -FilePath $log -Append
if($code -ne 1 -or ($text -join "`n") -notmatch 'no Program cases selected') {throw 'Empty Program collection must fail'}
& (Join-Path $PSScriptRoot 'test-fixed.ps1') -Executable (Join-Path $build 'zzy-native.exe') -Output (Join-Path $Output 'lexer.json')
& (Join-Path $PSScriptRoot 'test-check.ps1') -Executable (Join-Path $build 'zzy-native.exe') -Output (Join-Path $Output 'check.json')
Write-Output 'N2 native unit/fixed acceptance passed; CMake/CTest/install are separate gates.'
exit 0
