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
$records=[Collections.Generic.List[object]]::new();$passed=$false
try {
    foreach($command in @('info','source-info','lex','check','run','test')) {
        $start=[Diagnostics.ProcessStartInfo]::new();$start.FileName=$exe
        $start.Arguments=if($command -eq 'info') {'info'} else {$command+' 中文.zzy --diagnostic-format json'}
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
        if($command -in @('check','run','test')) {
            if($record.exit_code -ne 2 -or $record.stdout -ne '' -or ($record.stderr | ConvertFrom-Json).code -ne 'E402') {throw 'Unsupported capability smoke failed'}
        } else {
            if($record.exit_code -ne 0 -or $record.stderr -ne '') {throw 'Smoke command failed'}
            if($command -eq 'info' -and ($record.stdout | ConvertFrom-Json).stage -ne 'N1') {throw 'Wrong installed stage'}
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
    $passed=$true
} finally {
    $report=[ordered]@{schema_version=1;passed=$passed;scope='source-external executable smoke; installation provenance is provided by caller';executable=$exe;exe_sha256=(Get-FileHash -LiteralPath $exe).Hash.ToLowerInvariant();cwd=$folder;path_empty=$true;records=@($records.ToArray())}
    [IO.File]::WriteAllText($out,($report | ConvertTo-Json -Depth 20),[Text.UTF8Encoding]::new($false))
}
Write-Output ('Source-external smoke: '+$records.Count+' passed')
