param(
    [Parameter(Mandatory=$true)][string]$BuildDirectory,
    [Parameter(Mandatory=$true)][string]$Output
)
$ErrorActionPreference='Stop'
$repoRoot=Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$build=(Resolve-Path -LiteralPath $BuildDirectory).Path
$out=[IO.Path]::GetFullPath((Join-Path $repoRoot $Output))
if(Test-Path -LiteralPath $out) {throw 'Choose a new evidence directory; existing evidence is preserved.'}
New-Item -ItemType Directory -Path $out | Out-Null
$stage=Join-Path ([IO.Path]::GetTempPath()) ('ZZY N0 '+[Guid]::NewGuid().ToString('N')+'/中文 路径/bin')
if([IO.Path]::GetFullPath($stage).StartsWith($repoRoot,[StringComparison]::OrdinalIgnoreCase)) {
    throw 'The source-external stage must be outside the repository.'
}
New-Item -ItemType Directory -Path $stage -Force | Out-Null
$names=@('zzy-native.exe','native-protocol-tests.exe','native-heap-tests.exe','native-lifecycle-probe.exe')
foreach($name in $names) {Copy-Item -LiteralPath (Join-Path $build $name) -Destination $stage}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot '../tests/golden/no-execute.zzy') -Destination (Join-Path $stage 'no-execute.zzy')
$records=New-Object System.Collections.Generic.List[object]
function Invoke-Native([string]$Name,[string]$Arguments,[int]$Expected=0) {
    $start=New-Object Diagnostics.ProcessStartInfo
    $start.FileName=Join-Path $stage $Name
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
    if(-not $process.WaitForExit(10000)) {$process.Kill();$process.WaitForExit();throw 'Native test timed out; not passed.'}
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
    Require ($value.stage -eq 'N0' -and $value.pointer_bits -eq 64 -and $value.cxx_standard -eq 17) 'incorrect info'
    Require ($value.python_fallback -eq $false -and @($value.supported_commands).Count -eq 1 -and $value.supported_commands[0] -eq 'info') 'incorrect capabilities'
    Require ($value.resource_policy.host_decimal_digits -eq 0 -and $value.resource_policy.effective_decimal_digits -eq 4096) 'incorrect decimal policy'
    # Fixed independently from default-v1 contract and documented native host bound.
    Require ($value.resource_fingerprint -eq 'c9a540b6ea917d42f3d6c915801dce802ee771a18b1ab6139eab2ebc8161b14d') 'incorrect policy fingerprint'
    $null=Invoke-Native 'zzy-native.exe' '--help'
    $null=Invoke-Native 'zzy-native.exe' '--version'
    foreach($command in @('source-info','lex','check','run','test')) {
        $result=Invoke-Native 'zzy-native.exe' ($command+' no-execute.zzy --diagnostic-format json') 2
        $errorRecord=$result.stderr | ConvertFrom-Json
        Require ($result.stdout -eq '' -and $errorRecord.schema_version -eq 1 -and $errorRecord.code -eq 'E402' -and $errorRecord.kind -eq 'error') 'unsupported protocol mismatch'
        Require ($null -eq $errorRecord.file -and $null -eq $errorRecord.span -and $errorRecord.notes[0] -eq ('capability='+$command)) 'unsupported location/capability mismatch'
    }
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
    $imports=[ordered]@{}
    $objdump=(Get-Command objdump.exe -ErrorAction Stop).Source
    foreach($name in $names) {
        $lines=& $objdump -p (Join-Path $stage $name)
        if($LASTEXITCODE -ne 0) {throw 'PE import check failed'}
        $dlls=@($lines | Select-String 'DLL Name:' | ForEach-Object {$_.ToString().Split(':')[-1].Trim()})
        Require ($dlls.Count -gt 0) 'empty PE imports'
        Require (@($dlls | Where-Object {$_ -notmatch '^(KERNEL32|msvcrt|USER32)\.dll$'}).Count -eq 0) 'unreviewed direct DLL dependency'
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
    $report=[ordered]@{schema_version=1;passed=$passed;scope='N0 direct MinGW prototype; NOT CMake/CTest acceptance';os=[Environment]::OSVersion.VersionString;process_bits=([IntPtr]::Size*8);cwd=$stage;path_empty=$true;pythonpath='unusable-python-path';cmake_available=([bool](Get-Command cmake -ErrorAction SilentlyContinue));ctest_available=([bool](Get-Command ctest -ErrorAction SilentlyContinue));records=@($records.ToArray());imports=$imports;artifacts=$artifacts;sources=$sources;manual_ctrl_c='not run';cmake_install='not run';sanitizer='not run'}
    [IO.File]::WriteAllText((Join-Path $out 'report.json'),($report | ConvertTo-Json -Depth 30),[Text.UTF8Encoding]::new($false))
}
Write-Output ('N0 prototype: '+$records.Count+' process cases passed; evidence='+$out)
