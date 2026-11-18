param([Parameter(Mandatory=$true)][string]$Executable,[Parameter(Mandatory=$true)][string]$Output)
$ErrorActionPreference='Stop'
$exe=(Resolve-Path -LiteralPath $Executable).Path
$out=[IO.Path]::GetFullPath($Output)
if(Test-Path -LiteralPath $out) {throw 'Do not overwrite smoke evidence'}
$repoRoot=Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$folder=Join-Path ([IO.Path]::GetTempPath()) ('ZZY native install 中文 '+[Guid]::NewGuid().ToString('N'))
if([IO.Path]::GetFullPath($folder).StartsWith($repoRoot,[StringComparison]::OrdinalIgnoreCase)) {throw 'Smoke must run outside source'}
New-Item -ItemType Directory -Path $folder | Out-Null
[IO.File]::WriteAllText((Join-Path $folder '中文.zzy'),'(zno) 名 := "😀";',[Text.UTF8Encoding]::new($false))
[IO.File]::WriteAllText((Join-Path $folder '运行 中文.zzy'),'io.print(18446744073709551616+1);',[Text.UTF8Encoding]::new($false))
Copy-Item -LiteralPath (Join-Path $PSScriptRoot '../tests/golden/no-execute.zzy') -Destination (Join-Path $folder 'no-execute.zzy')
$records=[Collections.Generic.List[object]]::new();$passed=$false
try {
    foreach($command in @('info','source-info','lex','check','run','test')) {
        $start=[Diagnostics.ProcessStartInfo]::new();$start.FileName=$exe
        $start.Arguments=if($command -eq 'info') {'info'} elseif($command -eq 'run') {'run "运行 中文.zzy" --diagnostic-format json'} else {$command+' 中文.zzy --diagnostic-format json'}
        $start.WorkingDirectory=$folder;$start.UseShellExecute=$false;$start.CreateNoWindow=$true
        $start.RedirectStandardOutput=$true;$start.RedirectStandardError=$true
        $start.StandardOutputEncoding=[Text.UTF8Encoding]::new($false,$true);$start.StandardErrorEncoding=[Text.UTF8Encoding]::new($false,$true)
        $start.EnvironmentVariables['PATH']='';$start.EnvironmentVariables['PYTHONPATH']='unusable-smoke'
        $process=[Diagnostics.Process]::new();$process.StartInfo=$start;$null=$process.Start()
        $stdout=$process.StandardOutput.ReadToEndAsync();$stderr=$process.StandardError.ReadToEndAsync()
        $timedOut=-not $process.WaitForExit(15000)
        if($timedOut) {$process.Kill();$process.WaitForExit()}
        $record=[ordered]@{command=$start.Arguments;exit_code=$process.ExitCode;stdout=$stdout.Result;stderr=$stderr.Result;timed_out=$timedOut}
        $records.Add($record);$process.Dispose()
        if($timedOut) {throw 'Smoke timeout'}
        if($command -eq 'test') {
            if($record.exit_code -ne 2 -or $record.stdout -ne '' -or ($record.stderr | ConvertFrom-Json).code -ne 'E402') {throw 'Unsupported capability smoke failed'}
        } else {
            if($record.exit_code -ne 0 -or $record.stderr -ne '') {throw 'Smoke command failed'}
            if($command -eq 'info' -and ($record.stdout | ConvertFrom-Json).stage -ne 'N3-dev') {throw 'Wrong installed stage'}
            if($command -eq 'run' -and $record.stdout -cne "18446744073709551617`n") {throw 'Installed arbitrary integer run mismatch'}
            if($command -eq 'check' -and $record.stdout -ne '') {throw 'check unexpectedly printed'}
            if($command -eq 'source-info') {
                $source=$record.stdout | ConvertFrom-Json
                if($source.bytes -ne 20 -or $source.codepoints -ne 15 -or $source.syntax_checked -ne $false) {throw 'Installed source-info mismatch'}
            }
            if($command -eq 'lex') {
                $tokens=@($record.stdout.TrimEnd().Split("`n") | ForEach-Object {$_ | ConvertFrom-Json})
                if($tokens.Count -ne 6 -or $tokens[1].lexeme -cne '名' -or $tokens[3].value -cne '😀' -or $tokens[5].kind -ne 'EOF') {throw 'Installed lex mismatch'}
            }
        }
    }
    foreach($command in @('check','run','test')) {
        $start=[Diagnostics.ProcessStartInfo]::new();$start.FileName=$exe
        $start.Arguments=$command+' no-execute.zzy --diagnostic-format json'
        $start.WorkingDirectory=$folder;$start.UseShellExecute=$false;$start.CreateNoWindow=$true
        $start.RedirectStandardOutput=$true;$start.RedirectStandardError=$true
        $start.StandardOutputEncoding=[Text.UTF8Encoding]::new($false,$true);$start.StandardErrorEncoding=[Text.UTF8Encoding]::new($false,$true)
        $start.EnvironmentVariables['PATH']='';$start.EnvironmentVariables['PYTHONPATH']='unusable-smoke'
        $process=[Diagnostics.Process]::new();$process.StartInfo=$start;$null=$process.Start()
        $stdout=$process.StandardOutput.ReadToEndAsync();$stderr=$process.StandardError.ReadToEndAsync()
        if(-not $process.WaitForExit(15000)) {$process.Kill();$process.WaitForExit();throw 'No-execute smoke timeout'}
        $record=[ordered]@{command=$start.Arguments;exit_code=$process.ExitCode;stdout=$stdout.Result;stderr=$stderr.Result;timed_out=$false}
        $records.Add($record);$process.Dispose()
        if($command -eq 'check') {
            if($record.exit_code -ne 0 -or $record.stdout -ne '' -or $record.stderr -ne '') {throw 'check did not prepare the fixed side-effect fixture'}
        } else {
            $expected=if($command -eq 'run') {1} else {2}
            if($record.exit_code -ne $expected -or $record.stdout -ne '' -or ($record.stderr | ConvertFrom-Json).code -ne 'E402') {throw 'Unsupported capability did not reject the fixed side-effect fixture'}
        }
        if(Test-Path -LiteralPath (Join-Path $folder 'native-side-effect.txt')) {throw 'check/run/test executed user code'}
    }
    $passed=$true
} finally {
    $report=[ordered]@{schema_version=1;passed=$passed;scope='source-external executable smoke; installation provenance is provided by caller';executable=$exe;exe_sha256=(Get-FileHash -LiteralPath $exe).Hash.ToLowerInvariant();cwd=$folder;path_empty=$true;pythonpath='unusable-smoke';side_effect_absent=(-not (Test-Path -LiteralPath (Join-Path $folder 'native-side-effect.txt')));records=@($records.ToArray())}
    [IO.File]::WriteAllText($out,($report | ConvertTo-Json -Depth 20),[Text.UTF8Encoding]::new($false))
}
if(-not $passed) {throw 'Source-external smoke failed; report preserves the observed records.'}
Write-Output ('Source-external smoke: '+$records.Count+' passed')
