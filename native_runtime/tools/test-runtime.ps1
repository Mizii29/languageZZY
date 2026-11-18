param([Parameter(Mandatory=$true)][string]$Executable,[string]$Output)
$ErrorActionPreference='Stop'
$exe=(Resolve-Path -LiteralPath $Executable).Path
$suite=Join-Path (Split-Path -Parent $PSScriptRoot) 'tests/runtime'
$manifest=[IO.File]::ReadAllText((Join-Path $suite 'cases.json')) | ConvertFrom-Json
if($manifest.schema_version -ne 1 -or @($manifest.cases).Count -eq 0) {throw 'No runtime cases collected'}
if(@($manifest.cases.id | Select-Object -Unique).Count -ne @($manifest.cases).Count) {throw 'Duplicate runtime IDs'}
if($Output -and (Test-Path -LiteralPath $Output)) {throw 'Evidence already exists'}
$records=[Collections.Generic.List[object]]::new()
$temporary=Join-Path ([IO.Path]::GetTempPath()) ('ZZY N3 '+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $temporary | Out-Null
try {
    foreach($case in $manifest.cases) {
        $start=[Diagnostics.ProcessStartInfo]::new();$start.FileName=$exe
        $start.Arguments='run "'+(Join-Path $suite $case.file)+'" --diagnostic-format json'
        if($case.limits) {
            $config=Join-Path $temporary 'limits.json'
            [IO.File]::WriteAllText($config,(@{policy_version=1;limits=$case.limits} | ConvertTo-Json -Depth 10),[Text.UTF8Encoding]::new($false))
            $start.Arguments+=' --limits "'+$config+'"'
        }
        $start.UseShellExecute=$false;$start.CreateNoWindow=$true
        $start.RedirectStandardOutput=$true;$start.RedirectStandardError=$true
        $start.StandardOutputEncoding=[Text.UTF8Encoding]::new($false,$true);$start.StandardErrorEncoding=[Text.UTF8Encoding]::new($false,$true)
        $start.EnvironmentVariables['PATH']='';$start.EnvironmentVariables['PYTHONPATH']='unusable-native-runtime'
        $p=[Diagnostics.Process]::new();$p.StartInfo=$start;$null=$p.Start()
        $stdout=$p.StandardOutput.ReadToEndAsync();$stderr=$p.StandardError.ReadToEndAsync()
        $timeout=-not $p.WaitForExit(15000);if($timeout) {$p.Kill();$p.WaitForExit()}
        $r=[ordered]@{id=$case.id;exit_code=$p.ExitCode;stdout=$stdout.Result;stderr=$stderr.Result;timeout=$timeout};$records.Add($r);$p.Dispose()
        if($timeout -or $r.exit_code -ne $case.exit_code -or $r.stdout.Replace("`r`n","`n") -cne $case.stdout) {throw ('Runtime mismatch: '+$case.id+' '+($r | ConvertTo-Json -Compress))}
        if($case.code) {
            $diagnostic=$r.stderr | ConvertFrom-Json
            if($diagnostic.schema_version -ne 1 -or $diagnostic.kind -ne 'error' -or $diagnostic.code -ne $case.code -or @($diagnostic.PSObject.Properties).Count -ne 7 -or -not $diagnostic.file -or -not $diagnostic.span) {throw ('Runtime diagnostic mismatch: '+$case.id)}
        } elseif($r.stderr -ne '') {throw ('Unexpected stderr: '+$case.id)}
    }
} finally {
    Remove-Item -LiteralPath $temporary -Recurse -Force
    if($Output) {
        $parent=Split-Path -Parent $Output;if($parent) {New-Item -ItemType Directory -Force -Path $parent | Out-Null}
        [IO.File]::WriteAllText($Output,(@{schema_version=1;exe=$exe;exe_sha256=(Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLower();expected=@($manifest.cases).Count;records=@($records)} | ConvertTo-Json -Depth 20),[Text.UTF8Encoding]::new($false))
    }
}
Write-Output ('Runtime fixed: '+$records.Count+'/'+@($manifest.cases).Count)
