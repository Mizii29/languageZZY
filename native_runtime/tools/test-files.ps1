param([Parameter(Mandatory=$true)][string]$Executable,[string]$Output)
$ErrorActionPreference='Stop'
$exe=(Resolve-Path -LiteralPath $Executable).Path
if($Output -and (Test-Path -LiteralPath $Output)) {throw 'Preserve existing evidence; choose a new Output'}
$folder=Join-Path ([IO.Path]::GetTempPath()) ('ZZY N4-02 文件 '+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path (Join-Path $folder 'scripts') | Out-Null
$utf8=[Text.UTF8Encoding]::new($false,$true)
$records=[Collections.Generic.List[object]]::new()
$passed=$false
function Require([bool]$value,[string]$message) {if(-not $value) {throw $message}}
function Quote-Zzy([string]$value) {
    return '"'+$value.Replace('[OoO]','[OoO][OoO]').Replace('"','[OoO]q').Replace("`r",'[OoO]r').Replace("`n",'[OoO]n')+'"'
}
function Invoke-Case([string]$id,[string]$source,[string]$expected='',[hashtable]$limits=@{},[int]$exit=0,[string]$code='',[string]$mode='run') {
    $file=Join-Path $folder ('scripts/'+$id+'.zzy')
    [IO.File]::WriteAllText($file,$source,$utf8)
    $start=[Diagnostics.ProcessStartInfo]::new();$start.FileName=$exe
    $start.Arguments=$mode+' "'+$file+'" --diagnostic-format json'
    if($limits.Count) {
        $config=Join-Path $folder ($id+'.json')
        [IO.File]::WriteAllText($config,(@{policy_version=1;limits=$limits} | ConvertTo-Json -Compress),$utf8)
        $start.Arguments+=' --limits "'+$config+'"'
    }
    $start.WorkingDirectory=$folder;$start.UseShellExecute=$false;$start.CreateNoWindow=$true
    $start.RedirectStandardOutput=$true;$start.RedirectStandardError=$true;$start.RedirectStandardInput=$true
    $start.StandardOutputEncoding=$utf8;$start.StandardErrorEncoding=$utf8
    $start.EnvironmentVariables['PATH']='';$start.EnvironmentVariables['PYTHONPATH']='invalid-native-files'
    $process=[Diagnostics.Process]::new();$process.StartInfo=$start
    try {
        $null=$process.Start();$process.StandardInput.Close()
        $stdout=$process.StandardOutput.ReadToEndAsync();$stderr=$process.StandardError.ReadToEndAsync()
        $timeout=-not $process.WaitForExit(30000)
        if($timeout) {$process.Kill();$process.WaitForExit()}
        $record=[ordered]@{id=$id;command=$start.Arguments;exit_code=$process.ExitCode;stdout=$stdout.Result;stderr=$stderr.Result;timed_out=$timeout}
        $records.Add($record)
        Require (-not $timeout -and $record.exit_code -eq $exit -and $record.stdout -ceq $expected) ('File/JSON output mismatch: '+$id)
        if($code) {
            $diag=$record.stderr | ConvertFrom-Json
            Require ($diag.code -ceq $code -and $diag.schema_version -eq 1 -and $diag.kind -eq 'error') ('Wrong diagnostic: '+$id)
        } else {Require ($record.stderr -ceq '') ('Unexpected diagnostic: '+$id)}
    } finally {if($process.Id -and -not $process.HasExited) {$process.Kill();$process.WaitForExit()};$process.Dispose()}
    Require (@(Get-ChildItem -LiteralPath $folder -Filter '.zzy-*.tmp').Count -eq 0) ('Leaked temporary file: '+$id)
}
function Failure-Case([string]$id,[string]$call) {
    Invoke-Case $id ('(?_?)'+$call+'{(T_T)(m)=>{io.print("failed");}_=>{io.print("wrong");}}') "failed`n"
}
try {
    Invoke-Case 'roundtrip' ('io.print(io.write_text("a.txt","旧[OoO]n"));io.print(io.read_text("a.txt"));'+
        'io.print(io.write_atomic("a.txt","新😀"));io.print(io.write_text("b.txt","replacement"));'+
        'io.print(io.replace_file("b.txt","a.txt"));io.print(io.read_text("a.txt"));') `
        "(^_^)(null)`n(^_^)(旧`n)`n(^_^)(null)`n(^_^)(null)`n(^_^)(null)`n(^_^)(replacement)`n"
    Require ([IO.File]::ReadAllText((Join-Path $folder 'a.txt'),$utf8) -ceq 'replacement') 'Wrong replaced file'
    Require (-not (Test-Path -LiteralPath (Join-Path $folder 'b.txt'))) 'Replacement source survived'
    Require (-not (Test-Path -LiteralPath (Join-Path $folder 'scripts/a.txt'))) 'Paths were based on source directory'
    $text=[string][char]0xfeff+"中文😀`r`n尾`r"
    Invoke-Case 'unicode' ('io.print(io.write_atomic("保存 中文.json",'+(Quote-Zzy $text)+'));io.print(io.read_text("保存 中文.json"));') ("(^_^)(null)`n(^_^)("+$text+")`n")
    Require ([Convert]::ToBase64String([IO.File]::ReadAllBytes((Join-Path $folder '保存 中文.json'))) -ceq [Convert]::ToBase64String($utf8.GetBytes($text))) 'BOM/CRLF bytes changed'
    Invoke-Case 'empty' 'io.print(io.write_atomic("empty",""));io.print(io.read_text("empty"));' "(^_^)(null)`n(^_^)()`n"
    [IO.File]::WriteAllBytes((Join-Path $folder 'bad'),[byte[]]@(255))
    foreach($pair in @(@('bad-utf8','io.read_text("bad")'),@('missing','io.read_text("missing")'),
        @('no-parent','io.write_atomic("no-parent/a","x")'),@('replace-missing','io.replace_file("missing","a.txt")'),
        @('directory','io.read_text("scripts")'),@('empty-path','io.read_text("")'))) {Failure-Case $pair[0] $pair[1]}
    Invoke-Case 'outer-type' 'io.write_text("absent",1);' '' @{} 1 'E201'
    Invoke-Case 'arity' 'io.write_atomic("absent");' '' @{} 1 'E202'
    Require (-not (Test-Path -LiteralPath (Join-Path $folder 'absent'))) 'Invalid call created output'
    [IO.File]::WriteAllText((Join-Path $folder 'dep.zzy'),'io.input("no prompt");io.write_text("absent","bad");',$utf8)
    Invoke-Case 'check' '(use) "../dep.zzy" (as) m;(shape) X{x:=io.write_text("absent","default");}(zno)l:=(zzz)(io.write_text("absent","lazy"));io.write_atomic("a.txt","changed");' '' @{} 0 '' 'check'
    Require (-not (Test-Path -LiteralPath (Join-Path $folder 'absent'))) 'check executed user I/O/default/Lazy'
    Require ([IO.File]::ReadAllText((Join-Path $folder 'a.txt')) -ceq 'replacement') 'check modified target'
    [IO.File]::WriteAllText((Join-Path $folder 'x'),'中',$utf8)
    [IO.File]::WriteAllText((Join-Path $folder 'y'),'😀😀',$utf8)
    foreach($limit in @(2,3,4)) {
        [IO.File]::WriteAllText((Join-Path $folder 'target'),'old',$utf8)
        $exit=if($limit -eq 2){1}else{0};$code=if($exit){'E211'}else{''};$out=if($exit){''}else{"(^_^)(null)`n"}
        Invoke-Case ('atomic-'+$limit) 'io.print(io.write_atomic("target","中"));' $out @{io_payload_bytes=$limit} $exit $code
        Require ([IO.File]::ReadAllText((Join-Path $folder 'target')) -ceq $(if($exit){'old'}else{'中'})) 'Atomic limit modified old target'
        $out=if($exit){''}else{"(^_^)(中)`n"}
        Invoke-Case ('read-'+$limit) 'io.print(io.read_text("x"));' $out @{io_payload_bytes=$limit} $exit $code
    }
    foreach($limit in @(1,2,3)) {
        $exit=if($limit -eq 1){1}else{0};$code=if($exit){'E211'}else{''};$out=if($exit){''}else{"0`n"}
        Invoke-Case ('points-'+$limit) 'io.read_text("y");io.print(0);' $out @{text_codepoints=$limit} $exit $code
    }
    Invoke-Case 'json-tags' 'io.print(data.parse("[0,-0,1.0,-0.0,1e-9999,9007199254740993,true,null]"));' "(^_^)([0, 0, 1.0, -0.0, 0.0, 9007199254740993, true, null])`n"
    foreach($limit in @(2,3,4)) {
        $exit=if($limit -eq 2){1}else{0};$code=if($exit){'E211'}else{''};$out=if($exit){''}else{"(^_^)(123)`n"}
        Invoke-Case ('digits-'+$limit) 'io.print(data.parse(text.join(["1","2","3"],"")));' $out @{numeric_digits=$limit} $exit $code
    }
    Invoke-Case 'json-sharing' '(zno)a:=[1];io.print(data.stringify([a,a]));array.push(a,a);(?_?)data.stringify(a){(T_T)(m)=>{io.print("cycle");}_=>{io.print("wrong");}}' "(^_^)([[1],[1]])`ncycle`n"
    Failure-Case 'json-surrogate' ('data.parse('+(Quote-Zzy '"\ud800"')+')')
    Failure-Case 'json-duplicate' ('data.parse('+(Quote-Zzy '{"a":1,"\u0061":2}')+')')
    Failure-Case 'json-overflow' 'data.parse("1e9999")'
    Failure-Case 'json-trailing' 'data.parse("[1,]")'
    $deep=('['*1000)+'0'+(']'*1000)
    Invoke-Case 'json-deep' ('(?_?)data.parse('+(Quote-Zzy $deep)+'){(^_^)(v)=>{io.print(data.kind(v));}_=>{io.print("wrong");}}') "array`n" @{value_depth=1000}
    Invoke-Case 'json-too-deep' ('data.parse('+(Quote-Zzy $deep)+');') '' @{value_depth=999} 1 'E211'
    Invoke-Case 'recover' 'io.print(data.stringify([1,1.0,(true),(null)]));io.print(io.read_text("a.txt"));' "(^_^)([1,1.0,true,null])`n(^_^)(replacement)`n"
    Require ($records.Count -eq 33) 'File/JSON collection changed or became empty'
    $passed=$true
} finally {
    if($Output) {
        $out=[IO.Path]::GetFullPath($Output);$parent=Split-Path -Parent $out
        if($parent) {New-Item -ItemType Directory -Path $parent -Force | Out-Null}
        [IO.File]::WriteAllText($out,([ordered]@{schema_version=1;passed=$passed;executable=$exe;exe_sha256=(Get-FileHash -LiteralPath $exe).Hash.ToLowerInvariant();cwd=$folder;path_empty=$true;expected=33;records=@($records)} | ConvertTo-Json -Depth 20),$utf8)
    }
}
"File/JSON integration: $($records.Count)/33"
