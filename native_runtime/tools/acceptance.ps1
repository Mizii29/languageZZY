param(
    [Parameter(Mandatory=$true)][string]$BuildDirectory,
    [Parameter(Mandatory=$true)][string]$Output,
    [ValidateSet('DirectGCC','CMakeMSVC','DirectMSVC')][string]$BuildOrigin='DirectGCC',
    [ValidateSet('Debug','Release')][string]$Configuration='Debug',
    [string]$CMakeBuildDirectory,
    [string]$Dumpbin,
    [string]$InstalledExecutable
)
$ErrorActionPreference='Stop'
$repoRoot=Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$build=(Resolve-Path -LiteralPath $BuildDirectory).Path
$provenance=[ordered]@{origin=$BuildOrigin;configuration=$Configuration;build_directory=$build}
if($BuildOrigin -eq 'CMakeMSVC') {
    if(-not $CMakeBuildDirectory -or -not $Dumpbin) {throw 'CMakeMSVC requires CMakeBuildDirectory and the reviewed VS dumpbin path'}
    $cache=(Resolve-Path -LiteralPath (Join-Path $CMakeBuildDirectory 'CMakeCache.txt')).Path
    $cacheText=[IO.File]::ReadAllText($cache)
    if($cacheText -notmatch '(?m)^BUILD_TESTING:BOOL=ON\r?$' -or $cacheText -notmatch '(?m)^CMAKE_GENERATOR:INTERNAL=Visual Studio 17 2022\r?$') {throw 'CMake cache must enable tests and use VS2022'}
    if($build -ne (Join-Path (Split-Path -Parent $cache) $Configuration)) {throw 'BuildDirectory must be the selected CMake configuration'}
    $Dumpbin=(Resolve-Path -LiteralPath $Dumpbin).Path
    $provenance.cache=$cache;$provenance.cache_sha256=(Get-FileHash -LiteralPath $cache).Hash.ToLowerInvariant()
    $provenance.dumpbin=$Dumpbin;$provenance.dumpbin_version=(Get-Item -LiteralPath $Dumpbin).VersionInfo.FileVersion
}
if($BuildOrigin -eq 'DirectMSVC') {
    if(-not $Dumpbin) {throw 'DirectMSVC requires reviewed dumpbin path'}
    $Dumpbin=(Resolve-Path -LiteralPath $Dumpbin).Path
    $provenance.dumpbin=$Dumpbin
    $provenance.dumpbin_version=(Get-Item -LiteralPath $Dumpbin).VersionInfo.FileVersion
    $provenance.cmake='not run; direct MSVC only'
}
if($InstalledExecutable) {
    if($BuildOrigin -ne 'CMakeMSVC' -or $Configuration -ne 'Release') {throw 'Only CMake MSVC Release can be the installed package'}
    $InstalledExecutable=(Resolve-Path -LiteralPath $InstalledExecutable).Path
    if($InstalledExecutable.StartsWith($repoRoot,[StringComparison]::OrdinalIgnoreCase)) {throw 'Published executable must be outside the source repository'}
    if((Get-FileHash -LiteralPath $InstalledExecutable).Hash -ne (Get-FileHash -LiteralPath (Join-Path $build 'zzy-native.exe')).Hash) {throw 'Published executable differs from the tested Release build'}
    $provenance.published_executable=$InstalledExecutable
}
$out=[IO.Path]::GetFullPath((Join-Path $repoRoot $Output))
if(Test-Path -LiteralPath $out) {throw 'Choose a new evidence directory; existing evidence is preserved.'}
New-Item -ItemType Directory -Path $out | Out-Null
$stage=Join-Path ([IO.Path]::GetTempPath()) ('ZZY N1 '+[Guid]::NewGuid().ToString('N')+'/中文 路径/bin')
if([IO.Path]::GetFullPath($stage).StartsWith($repoRoot,[StringComparison]::OrdinalIgnoreCase)) {
    throw 'The source-external stage must be outside the repository.'
}
New-Item -ItemType Directory -Path $stage -Force | Out-Null
$names=@('zzy-native.exe','native-protocol-tests.exe','native-heap-tests.exe','native-lifecycle-probe.exe','native-frontend-tests.exe','native-program-tests.exe','native-runtime-values-tests.exe','native-execution-tests.exe')
foreach($name in $names) {Copy-Item -LiteralPath (Join-Path $build $name) -Destination $stage}
$cliExecutable=if($InstalledExecutable) {$InstalledExecutable} else {Join-Path $stage 'zzy-native.exe'}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot '../tests/golden/no-execute.zzy') -Destination (Join-Path $stage 'no-execute.zzy')
$records=New-Object System.Collections.Generic.List[object]
function Invoke-Native([string]$Name,[string]$Arguments,[int]$Expected=0,[int]$TimeoutMilliseconds=60000) {
    $start=New-Object Diagnostics.ProcessStartInfo
    $start.FileName=if($Name -eq 'zzy-native.exe') {$cliExecutable} else {Join-Path $stage $Name}
    $start.Arguments=$Arguments
    $start.WorkingDirectory=$stage
    $start.UseShellExecute=$false
    $start.CreateNoWindow=$true
    $start.RedirectStandardOutput=$true
    $start.RedirectStandardError=$true
    $start.StandardOutputEncoding=New-Object Text.UTF8Encoding($false,$true)
    $start.StandardErrorEncoding=New-Object Text.UTF8Encoding($false,$true)
    $start.EnvironmentVariables['PATH']=''
    $start.EnvironmentVariables['PYTHONPATH']='unusable-python-path'
    $process=New-Object Diagnostics.Process
    $process.StartInfo=$start
    $null=$process.Start()
    $stdout=$process.StandardOutput.ReadToEndAsync()
    $stderr=$process.StandardError.ReadToEndAsync()
    if(-not $process.WaitForExit($TimeoutMilliseconds)) {$process.Kill();$process.WaitForExit();throw 'Native test timed out; not passed.'}
    $record=[ordered]@{exe=$Name;arguments=$Arguments;exit_code=$process.ExitCode;stdout=$stdout.Result;stderr=$stderr.Result;timed_out=$false}
    $records.Add($record)
    $process.Dispose()
    if($record.exit_code -ne $Expected) {throw ('Unexpected exit for '+$Name+' '+$Arguments+': '+$record.exit_code+' '+$record.stderr)}
    return $record
}
function Require([bool]$Condition,[string]$Message) {if(-not $Condition){throw $Message}}

$passed=$false
try {
    $info=Invoke-Native 'zzy-native.exe' 'info'
    Require ($info.stderr -eq '') 'info emitted stderr'
    $value=$info.stdout | ConvertFrom-Json
    $provenance.info=$value
    if($BuildOrigin -ne 'DirectGCC') {
        Require ($value.compiler -eq 'MSVC') 'CMake MSVC provenance disagrees with the executable'
        $expectedCrt=if($Configuration -eq 'Debug') {'MSVC /MDd (debug runtime, not redistributable)'} else {'MSVC /MD (VC Redistributable required)'}
        Require ($value.crt -eq $expectedCrt) 'selected configuration CRT mismatch'
    }
    Require ($value.stage -eq 'N3-dev' -and $value.pointer_bits -eq 64 -and $value.cxx_standard -eq 17) 'incorrect info'
    Require ($value.python_fallback -eq $false -and @($value.supported_commands).Count -eq 6 -and $value.supported_commands[0] -eq 'info' -and 'run' -in $value.supported_commands) 'incorrect capabilities'
    Require ($value.resource_policy.host_decimal_digits -eq 0 -and $value.resource_policy.effective_decimal_digits -eq 4096) 'incorrect decimal policy'
    # Fixed independently from default-v1 contract and documented native host bound.
    Require ($value.resource_fingerprint -eq 'c9a540b6ea917d42f3d6c915801dce802ee771a18b1ab6139eab2ebc8161b14d') 'incorrect policy fingerprint'
    $null=Invoke-Native 'zzy-native.exe' '--help'
    $null=Invoke-Native 'zzy-native.exe' '--version'
    $result=Invoke-Native 'zzy-native.exe' 'check no-execute.zzy --diagnostic-format json'
    Require ($result.stdout -eq '' -and $result.stderr -eq '') 'check must prepare without side effects'
    $result=Invoke-Native 'zzy-native.exe' 'test no-execute.zzy --diagnostic-format json' 2
    $errorRecord=$result.stderr | ConvertFrom-Json
    Require ($result.stdout -eq '' -and $errorRecord.schema_version -eq 1 -and $errorRecord.code -eq 'E402' -and $errorRecord.kind -eq 'error') 'unsupported protocol mismatch'
    Require ($null -eq $errorRecord.file -and $null -eq $errorRecord.span -and $errorRecord.notes[0] -eq 'capability=test') 'unsupported location/capability mismatch'
    $result=Invoke-Native 'zzy-native.exe' 'run no-execute.zzy --diagnostic-format json' 1
    $errorRecord=$result.stderr | ConvertFrom-Json
    Require ($result.stdout -eq '' -and $errorRecord.schema_version -eq 1 -and $errorRecord.code -eq 'E402' -and $errorRecord.kind -eq 'error' -and $errorRecord.span.start.line -eq 1) 'unported host must fail at the call without side effects'
    [IO.File]::WriteAllText((Join-Path $stage 'core.zzy'),'io.print(18446744073709551616+1);',[Text.UTF8Encoding]::new($false))
    $result=Invoke-Native 'zzy-native.exe' 'run core.zzy'
    Require ($result.stdout -ceq "18446744073709551617`n" -and $result.stderr -eq '') 'source-external core runtime failed'
    foreach($case in @('integers','floating','cycles','budgets','ownership','opaque')) {
        $result=Invoke-Native 'native-runtime-values-tests.exe' $case
        Require ($result.stdout.Replace("`r`n","`n") -ceq ($case+": PASS`n") -and $result.stderr -eq '') ('runtime value case missing: '+$case)
    }
    foreach($case in @('recovery','lazy','cycles','input','resources')) {
        $result=Invoke-Native 'native-execution-tests.exe' $case
        Require ($result.stdout.Replace("`r`n","`n") -ceq ($case+": PASS`n") -and $result.stderr -eq '') ('runtime execution case missing: '+$case)
    }
    $sample='(zno) 名 := "😀";'
    [IO.File]::WriteAllText((Join-Path $stage '中文 source.zzy'),$sample,[Text.UTF8Encoding]::new($false))
    $result=Invoke-Native 'zzy-native.exe' 'source-info "中文 source.zzy"'
    $source=$result.stdout | ConvertFrom-Json
    Require ($source.bytes -eq 20 -and $source.codepoints -eq 15 -and $source.lines -eq 1 -and $source.syntax_checked -eq $false) 'source-info codepoint snapshot mismatch'
    $result=Invoke-Native 'zzy-native.exe' 'lex "中文 source.zzy" --diagnostic-format=json'
    $tokens=@($result.stdout.TrimEnd().Split("`n") | ForEach-Object {$_ | ConvertFrom-Json})
    Require ($tokens.Count -eq 6 -and $tokens[1].kind -eq 'IDENT' -and $tokens[1].lexeme -ceq '名' -and $tokens[3].value -ceq '😀') 'source-external Unicode lex failed'
    Require ($tokens[3].span.start.column -eq 12 -and $tokens[3].span.end.column -eq 15 -and $tokens[5].span.start.column -eq 16) 'supplementary character coordinates mismatch'
    $null=Invoke-Native 'zzy-native.exe' 'lex no-execute.zzy --diagnostic-format json'
    Require (-not (Test-Path -LiteralPath (Join-Path $stage 'native-side-effect.txt'))) 'unsupported command executed source'
    foreach($arguments in @('unknown --diagnostic-format json','info --limits missing.json --diagnostic-format json')) {
        $result=Invoke-Native 'zzy-native.exe' $arguments 2
        Require (($result.stderr | ConvertFrom-Json).code -eq 'E401') 'bad arguments accepted'
    }
    $result=Invoke-Native 'native-protocol-tests.exe' ''
    Require ($result.stdout.Trim() -eq 'protocol: 3 checks passed') 'protocol test count mismatch'
    $heapCases=@('array-cycle','map-cycle','closure-cycle','reachable-alias','quota-gc-retry','atomic-limits','allocation-rollback','ownership','cancellation','unwind-roots','iterative-graph','repeated-collection')
    foreach($case in $heapCases) {
        $result=Invoke-Native 'native-heap-tests.exe' $case
        Require ($result.stdout.Trim() -eq ($case+": passed`nheap: 1 cases passed")) ('heap case missing: '+$case)
    }
    $result=Invoke-Native 'native-heap-tests.exe' 'not-a-case' 1
    Require ($result.stderr.Trim() -eq 'no cases collected') 'empty test selection was not rejected'
    foreach($case in @('ast','captures','scopes','purity','literals','budgets','graph','readonly','metadata','cancellation')) {
        $result=Invoke-Native 'native-program-tests.exe' $case
        Require ($result.stdout.Trim() -eq ($case+": passed`nprogram: 1 cases passed")) ('Program case missing: '+$case)
    }
    $result=Invoke-Native 'native-program-tests.exe' 'unknown' 1
    Require ($result.stderr.Contains('no Program cases selected')) 'empty Program collection succeeded'
    foreach($case in @('sha256','utf8','positions','source-loader','policy','diagnostics','lexer-boundaries','default-boundaries','source-defaults','cancel-during-scan','output','cancellation-points')) {
        $timeout=if($case -eq 'default-boundaries') {180000} else {60000}
        $result=Invoke-Native 'native-frontend-tests.exe' $case 0 $timeout
        Require ($result.stdout.Trim() -eq ($case+": passed`nfrontend: 1 cases passed")) ('frontend case missing: '+$case)
    }
    $result=Invoke-Native 'native-frontend-tests.exe' 'not-a-case' 1
    Require ($result.stderr.Contains('no frontend cases selected')) 'empty frontend selection accepted'
    foreach($mode in @('success','resource','cancel','error','success')) {
        $expected=if($mode -eq 'success'){0}elseif($mode -eq 'cancel'){130}else{1}
        $result=Invoke-Native 'native-lifecycle-probe.exe' $mode $expected
        $counts=$result.stdout | ConvertFrom-Json
        Require ($counts.objects -eq 0 -and $counts.slots -eq 0 -and $counts.payload -eq 0) 'cleanup did not refund quotas'
        if($mode -eq 'success') {Require ($result.stderr -eq '') 'recovery failed'}
        else {
            $diag=$result.stderr | ConvertFrom-Json
            Require ($diag.schema_version -eq 1 -and $null -eq $diag.file -and $null -eq $diag.span) 'lifecycle diagnostic schema mismatch'
            if($mode -eq 'resource') {Require ($diag.code -eq 'E211' -and $diag.notes[0] -eq 'limit=runtime_objects') 'resource protocol mismatch'}
            elseif($mode -eq 'cancel') {Require ($diag.kind -eq 'cancelled' -and $null -eq $diag.code) 'cancel protocol mismatch'}
            else {Require ($diag.kind -eq 'internal_error' -and $null -eq $diag.code) 'internal error disguised'}
        }
    }
    # A real externally killed process. This proves OS process cleanup/recovery,
    # not RAII execution under a hard kill or a future interpreter worker tree.
    $start=New-Object Diagnostics.ProcessStartInfo
    $start.FileName=Join-Path $stage 'native-lifecycle-probe.exe'
    $start.Arguments='wait-timeout'
    $start.WorkingDirectory=$stage
    $start.UseShellExecute=$false
    $start.CreateNoWindow=$true
    $start.RedirectStandardOutput=$true
    $start.RedirectStandardError=$true
    $start.EnvironmentVariables['PATH']=''
    $start.EnvironmentVariables['PYTHONPATH']='unusable-python-path'
    $waiting=New-Object Diagnostics.Process
    $waiting.StartInfo=$start
    try {
        $null=$waiting.Start()
        $ready=$waiting.StandardOutput.ReadLineAsync()
        Require ($ready.Wait(5000) -and $ready.Result -eq 'READY') 'timeout probe never became ready'
        Require (-not $waiting.WaitForExit(200)) 'timeout probe exited before timeout'
        $waiting.Kill()
        Require ($waiting.WaitForExit(5000)) 'timeout process survived termination'
        $records.Add([ordered]@{exe='native-lifecycle-probe.exe';arguments='wait-timeout';exit_code=$waiting.ExitCode;stdout="READY`n";stderr=$waiting.StandardError.ReadToEnd();timed_out=$true;purpose='expected timeout cleanup probe';process_exited=$waiting.HasExited})
    } finally {
        if(-not $waiting.HasExited) {$waiting.Kill();$waiting.WaitForExit()}
        $waiting.Dispose()
    }
    $null=Invoke-Native 'native-lifecycle-probe.exe' 'success'
    $dependency=Invoke-Native 'native-lifecycle-probe.exe' 'dependencies'
    $loaded=$dependency.stdout | ConvertFrom-Json
    Require (@($loaded.modules).Count -gt 0) 'process dependency snapshot failed'
    Require (@($loaded.children | Where-Object {$_.name -notmatch '^conhost\.exe$'}).Count -eq 0) 'unexpected native child process'
    Require (@($loaded.children | Where-Object {$_.name -match '^(python|py)'}).Count -eq 0) 'Python child process loaded'
    Require (@($loaded.modules | Where-Object {$_ -match '^(python|_tkinter|tcl|tk\d)'}).Count -eq 0) 'Python/GUI runtime loaded'
    # Inspect the actual CLI while its lex output fills a pipe. No sleep-based
    # race or Python-assisted probe: a complete scan precedes output publication.
    [IO.File]::WriteAllText((Join-Path $stage 'modules.zzy'),('+'*5000),[Text.UTF8Encoding]::new($false))
    [IO.File]::WriteAllText((Join-Path $stage 'module-limits.json'),'{"policy_version":1,"limits":{"stdout_bytes":10000000}}',[Text.UTF8Encoding]::new($false))
    $start=[Diagnostics.ProcessStartInfo]::new()
    $start.FileName=$cliExecutable
    $start.Arguments='lex modules.zzy --limits module-limits.json --diagnostic-format json'
    $start.WorkingDirectory=$stage;$start.UseShellExecute=$false;$start.CreateNoWindow=$true
    $start.RedirectStandardOutput=$true;$start.RedirectStandardError=$true
    $start.StandardOutputEncoding=[Text.UTF8Encoding]::new($false,$true)
    $start.StandardErrorEncoding=[Text.UTF8Encoding]::new($false,$true)
    $start.EnvironmentVariables['PATH']='';$start.EnvironmentVariables['PYTHONPATH']='unusable-python-path'
    $running=[Diagnostics.Process]::new();$running.StartInfo=$start
    try {
        $null=$running.Start()
        $first=$running.StandardOutput.ReadLineAsync()
        Require ($first.Wait(10000) -and $first.Result.Contains('"kind":"PLUS"')) 'CLI never reached output safe point'
        $cliModules=@($running.Modules | ForEach-Object {$_.ModuleName})
        $moduleDetails=@($running.Modules | ForEach-Object {
            $file=Get-Item -LiteralPath $_.FileName
            [ordered]@{name=$_.ModuleName;path=$_.FileName;version=$file.VersionInfo.FileVersion;company=$file.VersionInfo.CompanyName;sha256=(Get-FileHash -LiteralPath $_.FileName).Hash.ToLowerInvariant()}
        })
        Require ($cliModules.Count -gt 0) 'actual CLI module snapshot empty'
        Require (@($cliModules | Where-Object {$_ -match '^(python|_tkinter|tcl|tk\d)'}).Count -eq 0) 'actual CLI loaded Python/GUI'
        # Preserve the independently observed module evidence even if the
        # separate system CIM process-tree permission is unavailable.
        [IO.File]::WriteAllText((Join-Path $out 'loaded-modules.json'),([ordered]@{
            executable=$cliExecutable;process_id=$running.Id;exe_sha256=(Get-FileHash -LiteralPath $cliExecutable).Hash.ToLowerInvariant();
            no_python_gui=$true;modules=$moduleDetails;process_tree='separate CIM check follows; not established by this record'
        } | ConvertTo-Json -Depth 15),[Text.UTF8Encoding]::new($false))
        $children=@(Get-CimInstance Win32_Process -Filter ('ParentProcessId='+$running.Id) | Select-Object -ExpandProperty Name)
        Require (@($children | Where-Object {$_ -notmatch '^conhost\.exe$'}).Count -eq 0) 'actual CLI created child process'
        $tail=$running.StandardOutput.ReadToEndAsync();$stderr=$running.StandardError.ReadToEndAsync()
        Require ($running.WaitForExit(10000)) 'inspected CLI failed to terminate'
        Require ($running.ExitCode -eq 0 -and $stderr.Result -eq '') 'inspected CLI failed'
        $records.Add([ordered]@{exe='zzy-native.exe';executable=$cliExecutable;arguments=$start.Arguments;exit_code=$running.ExitCode;stdout=($first.Result+"`n"+$tail.Result);stderr=$stderr.Result;timed_out=$false;modules=$cliModules;module_details=$moduleDetails;children=$children;purpose='actual CLI runtime inspection'})
    } finally {
        if(-not $running.HasExited) {$running.Kill();$running.WaitForExit()}
        $running.Dispose()
    }
    $imports=[ordered]@{}
    # Exact reviewed direct imports, not an arbitrary MSVC/API-set wildcard.
    $allowed=if($BuildOrigin -eq 'DirectGCC') {@('KERNEL32.dll','msvcrt.dll','USER32.dll')}
        elseif($Configuration -eq 'Debug') {@('KERNEL32.dll','MSVCP140D.dll','VCRUNTIME140D.dll','VCRUNTIME140_1D.dll','ucrtbased.dll')}
        else {@('KERNEL32.dll','MSVCP140.dll','VCRUNTIME140.dll','VCRUNTIME140_1.dll','api-ms-win-crt-runtime-l1-1-0.dll','api-ms-win-crt-stdio-l1-1-0.dll','api-ms-win-crt-heap-l1-1-0.dll','api-ms-win-crt-math-l1-1-0.dll','api-ms-win-crt-locale-l1-1-0.dll','api-ms-win-crt-convert-l1-1-0.dll')}
    if($BuildOrigin -eq 'DirectGCC') {$objdump=(Get-Command objdump.exe -ErrorAction Stop).Source}
    foreach($name in $names) {
        if($BuildOrigin -ne 'DirectGCC') {
            $lines=& $Dumpbin /dependents (Join-Path $stage $name)
            $dlls=@($lines | Where-Object {$_ -match '^\s+(\S+\.dll)\s*$'} | ForEach-Object {$_.Trim()})
        } else {
            $lines=& $objdump -p (Join-Path $stage $name)
            $dlls=@($lines | Select-String 'DLL Name:' | ForEach-Object {$_.ToString().Split(':')[-1].Trim()})
        }
        if($LASTEXITCODE -ne 0) {throw 'PE import check failed'}
        [IO.File]::WriteAllLines((Join-Path $out ($name+'.imports.txt')),[string[]]$lines,[Text.UTF8Encoding]::new($false))
        Require ($dlls.Count -gt 0) 'empty PE imports'
        Require (@($dlls | Where-Object {$_ -notin $allowed}).Count -eq 0) 'unreviewed direct DLL dependency'
        $imports[$name]=$dlls
    }
    $artifacts=[ordered]@{}
    foreach($name in $names) {$artifacts[$name]=(Get-FileHash -LiteralPath (Join-Path $stage $name) -Algorithm SHA256).Hash.ToLowerInvariant()}
    $sources=[ordered]@{}
    $nativeRoot=Split-Path -Parent $PSScriptRoot
    foreach($file in (Get-ChildItem -LiteralPath $nativeRoot -Recurse -File | Where-Object {$_.Extension -in @('.cpp','.hpp','.h','.cmake','.json','.zzy','.ps1','.py') -or $_.Name -eq 'CMakeLists.txt'} | Sort-Object FullName)) {
        $path=$file.FullName.Substring($nativeRoot.Length+1).Replace('\','/')
        $bytes=[Text.Encoding]::UTF8.GetBytes([IO.File]::ReadAllText($file.FullName).Replace("`r`n","`n"))
        $sha=[Security.Cryptography.SHA256]::Create()
        try {$sources[$path]=([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-','').ToLowerInvariant()} finally {$sha.Dispose()}
    }
    $passed=$true
} finally {
    $scope=if($BuildOrigin -eq 'CMakeMSVC') {'N3 CMake/MSVC '+$Configuration+' executable acceptance; CTest/install results are separate evidence'} elseif($BuildOrigin -eq 'DirectMSVC') {'N3 direct MSVC '+$Configuration+'; NOT CMake/CTest/install acceptance'} else {'N3 direct MinGW validation; NOT CMake/CTest/install acceptance'}
    $report=[ordered]@{schema_version=1;passed=$passed;scope=$scope;provenance=$provenance;os=[Environment]::OSVersion.VersionString;process_bits=([IntPtr]::Size*8);cwd=$stage;path_empty=$true;pythonpath='unusable-python-path';cmake_available=([bool](Get-Command cmake -ErrorAction SilentlyContinue));ctest_available=([bool](Get-Command ctest -ErrorAction SilentlyContinue));records=@($records.ToArray());imports=$imports;allowed_direct_imports=$allowed;artifacts=$artifacts;sources=$sources;manual_ctrl_c='not run';cmake_install=$(if($BuildOrigin -eq 'CMakeMSVC') {'see separate install log and published-copy smoke'} else {'not run'});sanitizer='not run'}
    [IO.File]::WriteAllText((Join-Path $out 'report.json'),($report | ConvertTo-Json -Depth 30),[Text.UTF8Encoding]::new($false))
}
Write-Output ('N3 native: '+$records.Count+' process cases passed; evidence='+$out)
