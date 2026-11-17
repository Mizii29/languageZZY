param(
    [Parameter(Mandatory=$true)][string]$Executable,
    [string]$Output
)
$ErrorActionPreference='Stop'
$repoRoot=Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$exe=(Resolve-Path -LiteralPath $Executable).Path
if($Output -and (Test-Path -LiteralPath $Output)) {throw 'Evidence already exists'}
$folder=Join-Path ([IO.Path]::GetTempPath()) ('ZZY N1 fixed 中文 '+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $folder | Out-Null
$records=[Collections.Generic.List[object]]::new()
$passed=$false
function Require([bool]$Condition,[string]$Message) {if(-not $Condition) {throw $Message}}
function Display([string]$Path,[string]$Cwd) {
    $absolute=[IO.Path]::GetFullPath($Path)
    $base=[IO.Path]::GetFullPath($Cwd).TrimEnd('\')+'\'
    if([IO.Path]::GetPathRoot($absolute) -ine [IO.Path]::GetPathRoot($base)) {return $absolute.Replace('\','/')}
    return ([Uri]::UnescapeDataString(([Uri]$base).MakeRelativeUri([Uri]$absolute).ToString()))
}
try {
    $cases=@()
    foreach($name in @('tests/lex/cases.json','native_runtime/tests/frontend/cases.json')) {
        $manifest=[IO.File]::ReadAllText((Join-Path $repoRoot $name)) | ConvertFrom-Json
        Require ($manifest.schema_version -eq 1 -and @($manifest.cases).Count -gt 0) 'Empty or invalid fixed manifest'
        $cases+=@($manifest.cases)
    }
    Require ($cases.Count -gt 0) 'No fixed cases collected'
    Require (@($cases.id | Select-Object -Unique).Count -eq $cases.Count) 'Duplicate fixed case IDs'
    foreach($case in $cases) {
        $cwd=if($case.cwd) {Join-Path $repoRoot $case.cwd} else {$repoRoot}
        if($null -ne $case.input_hex) {
            $file=Join-Path $folder ($case.id+'.zzy')
            $bytes=[byte[]]::new($case.input_hex.Length/2)
            for($i=0;$i -lt $bytes.Length;$i++) {$bytes[$i]=[Convert]::ToByte($case.input_hex.Substring($i*2,2),16)}
            [IO.File]::WriteAllBytes($file,$bytes)
        } else {$file=Join-Path $repoRoot $case.file}
        $arguments=@($case.mode,$file,'--diagnostic-format','json')
        if($null -ne $case.limits) {
            $config=Join-Path $folder 'limits.json'
            [IO.File]::WriteAllText($config,(@{policy_version=1;limits=$case.limits} | ConvertTo-Json -Depth 10),[Text.UTF8Encoding]::new($false))
            $arguments+=@('--limits',$config)
        }
        $start=[Diagnostics.ProcessStartInfo]::new()
        $start.FileName=$exe
        $start.Arguments=($arguments | ForEach-Object {'"'+$_+'"'}) -join ' '
        $start.WorkingDirectory=$cwd
        $start.UseShellExecute=$false
        $start.CreateNoWindow=$true
        $start.RedirectStandardOutput=$true
        $start.RedirectStandardError=$true
        $start.StandardOutputEncoding=[Text.UTF8Encoding]::new($false,$true)
        $start.StandardErrorEncoding=[Text.UTF8Encoding]::new($false,$true)
        $start.EnvironmentVariables['PATH']=''
        $start.EnvironmentVariables['PYTHONPATH']='unusable-native-fixed'
        $process=[Diagnostics.Process]::new();$process.StartInfo=$start
        $null=$process.Start()
        $stdout=$process.StandardOutput.ReadToEndAsync();$stderr=$process.StandardError.ReadToEndAsync()
        $timedOut=-not $process.WaitForExit(15000)
        if($timedOut) {$process.Kill();$process.WaitForExit()}
        $record=[ordered]@{id=$case.id;arguments=$arguments;exit_code=$process.ExitCode;stdout=$stdout.Result;stderr=$stderr.Result;timed_out=$timedOut}
        $records.Add($record);$process.Dispose()
        Require (-not $timedOut) ('Timeout: '+$case.id)
        Require ($record.exit_code -eq $case.exit_code) ('Exit differs: '+$case.id)
        if($null -ne $case.tokens) {
            $tokens=@($record.stdout.TrimEnd().Split("`n") | ForEach-Object {$_ | ConvertFrom-Json})
            Require ($tokens.Count -eq $case.tokens.Count) ('Token count: '+$case.id)
            for($i=0;$i -lt $tokens.Count;$i++) {
                $actual=$tokens[$i];$expected=$case.tokens[$i]
                Require ($actual.schema_version -eq 1 -and @($actual.PSObject.Properties).Count -eq 6 -and $actual.raw -is [bool]) ('Token schema: '+$case.id)
                Require ($actual.kind -ceq $expected[0] -and $actual.lexeme -ceq $expected[1] -and $actual.value -ceq $expected[2] -and $actual.raw -eq $expected[3]) ('Token value: '+$case.id+' '+$i)
                $coordinates=@($actual.span.start.line,$actual.span.start.column,$actual.span.end.line,$actual.span.end.column)
                Require (($coordinates -join ',') -ceq ($expected[4] -join ',')) ('Token span: '+$case.id+' '+$i)
            }
        } elseif($null -ne $case.info) {
            $actual=$record.stdout | ConvertFrom-Json
            Require (@($actual.PSObject.Properties).Count -eq 7) ('source-info schema: '+$case.id)
            Require ($actual.file -ceq (Display $file $cwd)) ('source-info file: '+$case.id)
            foreach($property in $case.info.PSObject.Properties) {Require ($actual.($property.Name) -ceq $property.Value) ('source-info '+$property.Name+': '+$case.id)}
        } else {Require ($record.stdout -ceq $case.stdout) ('stdout differs: '+$case.id)}
        if($case.exit_code -eq 0) {Require ($record.stderr -eq '') ('unexpected stderr: '+$case.id)}
        else {
            $actual=$record.stderr | ConvertFrom-Json
            Require ($actual.schema_version -eq 1 -and $actual.kind -eq 'error' -and $actual.code -eq $case.diagnostic.code -and @($actual.PSObject.Properties).Count -eq 7) ('diagnostic schema/code: '+$case.id)
            if($null -eq $case.diagnostic.span) {Require ($null -eq $actual.span) ('diagnostic null span: '+$case.id)}
            else {
                $coordinates=@($actual.span.start.line,$actual.span.start.column,$actual.span.end.line,$actual.span.end.column)
                Require (($coordinates -join ',') -ceq ($case.diagnostic.span -join ',')) ('diagnostic span: '+$case.id)
            }
            $expectedFile=if($case.diagnostic.PSObject.Properties.Name -contains 'file') {$case.diagnostic.file} else {Display $file $cwd}
            Require ($actual.file -ceq $expectedFile) ('diagnostic file: '+$case.id)
            if($case.diagnostic.message_contains) {Require ($actual.message.Contains($case.diagnostic.message_contains)) ('resource key: '+$case.id)}
            Require ([Text.Encoding]::UTF8.GetByteCount($record.stderr) -le 4096) ('diagnostic reserve: '+$case.id)
        }
    }
    $passed=$true
} finally {
    if($Output) {
        $report=[ordered]@{schema_version=1;passed=$passed;count=$records.Count;scope='PowerShell fixed N1 manifests, no Python coordinator';exe=$exe;exe_sha256=(Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant();records=@($records.ToArray())}
        [IO.File]::WriteAllText([IO.Path]::GetFullPath($Output),($report | ConvertTo-Json -Depth 30),[Text.UTF8Encoding]::new($false))
    }
    # Only this newly created, known temporary folder is removed.
    $resolved=[IO.Path]::GetFullPath($folder)
    if(-not $resolved.StartsWith([IO.Path]::GetTempPath(),[StringComparison]::OrdinalIgnoreCase)) {throw 'Unexpected temporary target'}
    Remove-Item -LiteralPath $resolved -Recurse -Force
}
Write-Output ('Native fixed expectations: '+$records.Count+' passed')
