param([ValidateSet('Debug','Release')][string]$Configuration='Debug')
$ErrorActionPreference='Stop'
$repo=Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$native=Join-Path $repo 'native_runtime'
$build=Join-Path $repo ('build/native-n2-msvc-direct-'+$Configuration.ToLowerInvariant())
$tool='C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC\14.40.33807'
$sdk='C:\Program Files (x86)\Windows Kits\10'
$sdkVersion='10.0.22000.0'
$compiler=Join-Path $tool 'bin/Hostx64/x64/cl.exe'
if(-not (Test-Path -LiteralPath $compiler)) {throw 'Expected existing MSVC compiler is unavailable; no installation attempted'}
New-Item -ItemType Directory -Force -Path $build | Out-Null
# Session only. Same frozen toolset, SDK and CRT as N1. This is direct MSVC
# evidence, explicitly NOT a replacement for CMake configure/build/CTest.
$env:Path=(Join-Path $tool 'bin/Hostx64/x64')+';'+$env:Path
$env:INCLUDE=(Join-Path $tool 'include')+';'+(Join-Path $sdk "Include/$sdkVersion/ucrt")+';'+(Join-Path $sdk "Include/$sdkVersion/um")+';'+(Join-Path $sdk "Include/$sdkVersion/shared")
$env:LIB=(Join-Path $tool 'lib/x64')+';'+(Join-Path $sdk "Lib/$sdkVersion/ucrt/x64")+';'+(Join-Path $sdk "Lib/$sdkVersion/um/x64")
$options=@('/nologo','/std:c++17','/W4','/WX','/utf-8','/EHsc','/permissive-','/D_WIN32_WINNT=0x0A00','/DWINVER=0x0A00',('/I'+(Join-Path $native 'include')))
if($Configuration -eq 'Debug') {$options+=@('/Od','/Zi','/MDd')} else {$options+=@('/O2','/DNDEBUG','/MD')}
$targets=@(@('src/main.cpp','zzy-native'),@('tests/native/protocol.cpp','native-protocol-tests'),@('tests/native/heap.cpp','native-heap-tests'),@('tests/native/lifecycle.cpp','native-lifecycle-probe'),@('tests/native/frontend.cpp','native-frontend-tests'),@('tests/native/program.cpp','native-program-tests'))
foreach($target in $targets) {
    & $compiler @options ('/Fo'+(Join-Path $build ($target[1]+'.obj'))) ('/Fd'+(Join-Path $build ($target[1]+'.pdb'))) ('/Fe'+(Join-Path $build ($target[1]+'.exe'))) (Join-Path $native $target[0]) /link /INCREMENTAL:NO /STACK:8388608
    if($LASTEXITCODE -ne 0) {throw ('Direct MSVC compilation failed: '+$target[0])}
}
Write-Output ('Direct MSVC '+$Configuration+' built: '+$build+'; CMake/CTest not implied.')
