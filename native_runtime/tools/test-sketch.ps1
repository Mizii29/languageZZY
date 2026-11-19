param([Parameter(Mandatory=$true)][string]$Executable,[string]$Output)
$ErrorActionPreference='Stop'
$exe=(Resolve-Path -LiteralPath $Executable).Path
$root=Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$fixture=Join-Path $root 'native_runtime/tests/sketch'
$records=[Collections.Generic.List[object]]::new()
$folder=Join-Path ([IO.Path]::GetTempPath()) ('ZZY Sketch '+[char]0x753b+' '+[Guid]::NewGuid().ToString('N'))
if($Output -and (Test-Path -LiteralPath $Output)) {throw 'Choose a new output file'}
New-Item -ItemType Directory -Path $folder | Out-Null
function Require([bool]$Condition,[string]$Message) {if(-not $Condition) {throw $Message}}
function Check-Case($CaseId,$Mode,$File,$ExitCode,$ExpectedOut,$Code,$Line,$Config) {
    $start=[Diagnostics.ProcessStartInfo]::new()
    $start.FileName=$exe;$start.Arguments="$Mode ""$File"" --diagnostic-format json"
    if($Config) {$start.Arguments+=" --limits ""$Config"""}
    $start.WorkingDirectory=$folder;$start.UseShellExecute=$false;$start.CreateNoWindow=$true
    $start.RedirectStandardOutput=$true;$start.RedirectStandardError=$true
    $start.StandardOutputEncoding=[Text.UTF8Encoding]::new($false,$true)
    $start.StandardErrorEncoding=[Text.UTF8Encoding]::new($false,$true)
    $start.EnvironmentVariables['PATH']=''
    $start.EnvironmentVariables['PYTHONPATH']='invalid-zzy-native'
    $p=[Diagnostics.Process]::new();$p.StartInfo=$start
    try {
        $null=$p.Start();$stdout=$p.StandardOutput.ReadToEndAsync();$stderr=$p.StandardError.ReadToEndAsync()
        $timeout=-not $p.WaitForExit(20000)
        if($timeout) {$p.Kill();$p.WaitForExit()}
        $record=[ordered]@{id=$CaseId;mode=$Mode;exit_code=$p.ExitCode;stdout=$stdout.Result;stderr=$stderr.Result;timeout=$timeout}
        $records.Add($record)
        Require (-not $timeout -and $record.exit_code -eq $ExitCode -and $record.stdout -ceq $ExpectedOut) (
            'Sketch mismatch: '+($record|ConvertTo-Json -Compress))
        if($Code) {
            $diagnostic=$record.stderr|ConvertFrom-Json
            Require ($diagnostic.schema_version -eq 1 -and $diagnostic.code -eq $Code -and
                ($null -eq $Line -or $diagnostic.span.start.line -eq $Line)) ('Sketch diagnostic mismatch: '+$record.stderr)
        } else {Require ($record.stderr -ceq '') ('Unexpected error: '+$record.stderr)}
    } finally {$p.Dispose()}
}
$ids=[ordered]@{
    e1=@('initial','movement','pen-up-jump','arc-closed','bezier','fill-cancel','color-identity','typed-function',
        'bool','rgb-bool','rgb-range','width-zero','radius-zero','derived-range','bad-point-late','fill-nested',
        'fill-two-points','fill-other-pen','duplicate-name','canvas-zero','huge-int','snapshot-frozen','native-constructor',
        'native-method','native-call','svg-available','show-headless','undo-available')
    e2=@('layers','text','headless')
    e3=@('history','fill-history')
}
$passed=$false
try {
    foreach($suite in $ids.Keys) {
        $manifest=[IO.File]::ReadAllText((Join-Path $root "tests/$suite/cases.json")) | ConvertFrom-Json
        Require ($manifest.schema_version -eq 1) ('Wrong manifest schema: '+$suite)
        foreach($id in $ids[$suite]) {
            $chosen=@($manifest.cases | Where-Object id -ceq "$suite-$id")
            Require ($chosen.Count -eq 2 -and (($chosen.mode|Sort-Object) -join ',') -ceq 'check,run') "Missing check/run: $suite-$id"
            foreach($case in $chosen) {
                $line=if($case.diagnostic.span) {$case.diagnostic.span[0]} else {$null}
                Check-Case $case.id $case.mode (Join-Path $root $case.file) $case.exit_code $case.stdout $case.diagnostic.code $line
            }
        }
    }
    $program=Join-Path $fixture 'geometry.zzy'
    $svg=Join-Path $folder 'drawing.svg'
    Check-Case 'svg-no-effect' check $program 0 ''
    Require (-not (Test-Path -LiteralPath $svg)) 'check produced drawing'
    $positions=@('true','sketch.Position::{x: 0.0, y: 0.0}','true','sketch.Position::{x: 10.0, y: 10.0}','') -join [char]10
    Check-Case 'svg-publish' run $program 0 ($positions+'(^_^)(null)'+[char]10)
    $original=[IO.File]::ReadAllText($svg)
    [xml]$xml=$original
    $ns=[Xml.XmlNamespaceManager]::new($xml.NameTable)
    $ns.AddNamespace('s','http://www.w3.org/2000/svg')
    Require ($xml.DocumentElement.viewBox -ceq '0 0 201 101') 'SVG viewBox'
    Require ($xml.SelectSingleNode('/s:svg/s:title',$ns).InnerText -ceq '<&>') 'SVG title'
    Require ($xml.SelectSingleNode('//s:clipPath/s:rect',$ns).width -ceq '201') 'SVG clipping'
    $scene=$xml.SelectSingleNode('/s:svg/s:g/s:g',$ns)
    Require ($scene.transform -ceq 'translate(100.5 50.5)') 'SVG origin'
    $objects=@($scene.SelectNodes('s:g',$ns))
    Require (($objects.id -join ',') -ceq 'object-1,object-2') 'SVG ordered IDs'
    $paths=@($objects[0].SelectNodes('s:path',$ns))
    Require ($paths.Count -eq 3 -and $paths[0].d -ceq 'M0 0 L10.0 0 L10.0 -10.0 Z' -and
        $paths[0].GetAttribute('fill-rule') -ceq 'evenodd') 'SVG fill and orientation'
    Require ($paths[1].d -ceq 'M0 0 L10.0 0' -and $paths[2].d -ceq 'M10.0 0 L10.0 -10.0') 'SVG open strokes'
    foreach($path in $paths[1..2]) {
        Require ($path.stroke -ceq '#010203' -and $path.GetAttribute('stroke-width') -ceq '2.0') 'SVG stroke style'
    }
    $label=$objects[1].SelectSingleNode('s:text',$ns)
    $expectedLabel=[string][char]0x4e2d+[char]0x6587+'<&>'
    Require ($label.InnerText -ceq $expectedLabel -and $label.y -ceq '-10.0') 'SVG escaped UTF-8 and text coordinates'
    Check-Case 'locked-layer' run (Join-Path $fixture 'locked.zzy') 1 '' E203 6
    Check-Case 'foreign-layer' run (Join-Path $fixture 'foreign.zzy') 1 '' E203 5
    $limit=Join-Path $folder 'limits.json'
    [IO.File]::WriteAllText($limit,'{"policy_version":1,"limits":{"io_payload_bytes":360}}')
    Check-Case 'svg-budget' run $program 1 $positions E211 18 $limit
    Require ([IO.File]::ReadAllText($svg) -ceq $original) 'budget failure changed the previous SVG'
    Require (@(Get-ChildItem -LiteralPath $folder -Filter '.zzy-*.tmp' -Force).Count -eq 0) 'temporary file leaked'
    Require ($records.Count -eq (2*($ids.e1.Count+$ids.e2.Count+$ids.e3.Count)+5)) 'empty or incomplete fixed selection'
    $passed=$true
} finally {
    if($Output) {
        [IO.File]::WriteAllText([IO.Path]::GetFullPath($Output),(@{
            passed=$passed;exe=$exe;sha256=(Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash;records=$records
        }|ConvertTo-Json -Depth 12))
    }
    $resolved=(Resolve-Path -LiteralPath $folder).Path
    $temp=[IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')+'\'
    if($resolved -ne [IO.Path]::GetFullPath($folder) -or -not $resolved.StartsWith($temp,[StringComparison]::OrdinalIgnoreCase)) {
        throw 'Refusing to remove an unexpected test directory'
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force
}
Write-Output ("Sketch geometry fixed: {0}/{0}" -f $records.Count)
