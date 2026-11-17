param([ValidateSet('Debug','Release')][string]$Configuration='Debug')
$ErrorActionPreference='Stop'
$nativeRoot=Split-Path -Parent $PSScriptRoot
$repoRoot=Split-Path -Parent $nativeRoot
$nativeBuild=Join-Path $repoRoot ('build/native-direct-'+$Configuration.ToLowerInvariant())
$compiler=(Get-Command g++.exe -ErrorAction Stop).Source
New-Item -ItemType Directory -Force -Path $nativeBuild | Out-Null
$options=@('-std=c++17','-Wall','-Wextra','-Wpedantic','-Werror','-static-libgcc','-static-libstdc++','-D_WIN32_WINNT=0x0A00','-DWINVER=0x0A00','-I',(Join-Path $nativeRoot 'include'))
if($Configuration -eq 'Debug') {$options+=@('-O0','-g')} else {$options+=@('-O2','-DNDEBUG')}
$targets=@(@('src/main.cpp','zzy-native.exe'),@('tests/native/protocol.cpp','native-protocol-tests.exe'),@('tests/native/heap.cpp','native-heap-tests.exe'),@('tests/native/lifecycle.cpp','native-lifecycle-probe.exe'),@('tests/native/frontend.cpp','native-frontend-tests.exe'))
foreach($target in $targets) {
    & $compiler @options (Join-Path $nativeRoot $target[0]) '-o' (Join-Path $nativeBuild $target[1])
    if($LASTEXITCODE -ne 0) {throw ('Compilation failed: '+$target[0])}
}
Write-Output ('Direct compiler prototype built in '+$nativeBuild+'; this is NOT CMake/CTest acceptance.')
