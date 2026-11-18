param([Parameter(Mandatory=$true)][string]$Executable,[string]$Output,[switch]$FileJson)
$ErrorActionPreference='Stop'
$exe=(Resolve-Path -LiteralPath $Executable).Path
$root=Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$selection=Get-Content -LiteralPath (Join-Path $root 'native_runtime/tests/library/selection.json') -Raw | ConvertFrom-Json
$manifest=Get-Content -LiteralPath (Join-Path $root 'tests/p05/cases.json') -Raw | ConvertFrom-Json
if($selection.count -ne 126 -or @($selection.ids).Count -ne 126 -or @($selection.ids | Select-Object -Unique).Count -ne 126){throw 'Invalid fixed library selection'}
$ids=@($selection.ids)
$expectedCount=126
if($FileJson) {
    $ids=@($manifest.cases | Where-Object {$_.mode -eq 'run' -and $_.id -notin $selection.ids} | ForEach-Object {$_.id})
    $expectedCount=58
    if($ids.Count -ne $expectedCount -or @($ids | Select-Object -Unique).Count -ne $expectedCount) {throw 'Invalid fixed file/JSON selection'}
}
if($Output -and (Test-Path -LiteralPath $Output)){throw 'Evidence already exists'}
$records=[Collections.Generic.List[object]]::new()
$temporary=Join-Path ([IO.Path]::GetTempPath()) ('ZZY N4 library '+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $temporary | Out-Null
$passed=$false
try {
    foreach($id in $ids) {
        $cases=@($manifest.cases | Where-Object {$_.id -eq $id -and $_.mode -eq 'run'})
        if($cases.Count -ne 1){throw ('Missing or duplicate library case: '+$id)}
        $case=$cases[0]
        $start=[Diagnostics.ProcessStartInfo]::new();$start.FileName=$exe
        $start.Arguments='run "'+(Join-Path $root $case.file)+'" --diagnostic-format json'
        $start.WorkingDirectory=Join-Path $root $case.cwd
        if($case.limits) {
            $config=Join-Path $temporary 'limits.json'
            [IO.File]::WriteAllText($config,(@{policy_version=1;limits=$case.limits} | ConvertTo-Json -Depth 8),[Text.UTF8Encoding]::new($false))
            $start.Arguments+=' --limits "'+$config+'"'
        }
        $start.UseShellExecute=$false;$start.CreateNoWindow=$true
        $start.RedirectStandardOutput=$true;$start.RedirectStandardError=$true;$start.RedirectStandardInput=$true
        $start.StandardOutputEncoding=[Text.UTF8Encoding]::new($false,$true);$start.StandardErrorEncoding=[Text.UTF8Encoding]::new($false,$true)
        $start.EnvironmentVariables['PATH']='';$start.EnvironmentVariables['PYTHONPATH']='invalid-native-library'
        $p=[Diagnostics.Process]::new();$p.StartInfo=$start;$null=$p.Start()
        $bytes=[Text.Encoding]::UTF8.GetBytes($case.stdin)
        $p.StandardInput.BaseStream.Write($bytes,0,$bytes.Length);$p.StandardInput.Close()
        $out=$p.StandardOutput.ReadToEndAsync();$err=$p.StandardError.ReadToEndAsync()
        $timeout=-not $p.WaitForExit($case.timeout_seconds*1000);if($timeout){$p.Kill();$p.WaitForExit()}
        $r=[ordered]@{id=$id;exit_code=$p.ExitCode;stdout=$out.Result;stderr=$err.Result;timeout=$timeout}
        $records.Add($r);$p.Dispose()
        if($timeout -or $r.exit_code -ne $case.exit_code -or $r.stdout -cne $case.stdout){throw ('Library output mismatch: '+$id)}
        if($case.diagnostic) {
            $d=$r.stderr | ConvertFrom-Json;$expected=$case.diagnostic
            if($d.schema_version -ne 1 -or $d.kind -ne 'error' -or $d.code -ne $expected.code -or @($d.PSObject.Properties).Count -ne 7){throw ('Library diagnostic mismatch: '+$id)}
            $span=if($d.span){@($d.span.start.line,$d.span.start.column,$d.span.end.line,$d.span.end.column)}else{@()}
            if(($span -join ',') -ne (@($expected.span) -join ',')){throw ('Library span mismatch: '+$id)}
            if($expected.PSObject.Properties.Name -contains 'file' -and $d.file -cne $expected.file){throw ('Library file mismatch: '+$id)}
            if($expected.message_contains -and -not $d.message.Contains($expected.message_contains)){throw ('Library message mismatch: '+$id)}
            if($expected.PSObject.Properties.Name -contains 'notes' -and (@($d.notes) -join "`n") -cne (@($expected.notes) -join "`n")){throw ('Library notes mismatch: '+$id)}
        } elseif($r.stderr -ne ''){throw ('Unexpected library stderr: '+$id)}
    }
    $passed=$true
} finally {
    if([IO.Path]::GetFullPath($temporary).StartsWith([IO.Path]::GetTempPath(),[StringComparison]::OrdinalIgnoreCase)){Remove-Item -LiteralPath $temporary -Force -Recurse}
    if($Output) {
        $parent=Split-Path -Parent $Output;if($parent){New-Item -ItemType Directory -Path $parent -Force | Out-Null}
        [IO.File]::WriteAllText([IO.Path]::GetFullPath($Output),(@{schema_version=1;passed=$passed;exe=$exe;exe_sha256=(Get-FileHash -LiteralPath $exe).Hash.ToLowerInvariant();expected=$expectedCount;records=@($records)} | ConvertTo-Json -Depth 18),[Text.UTF8Encoding]::new($false))
    }
}
"Library fixed: $($records.Count)/$expectedCount"
