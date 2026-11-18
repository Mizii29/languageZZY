param([Parameter(Mandatory=$true)][string]$Executable,[string]$Output)
$ErrorActionPreference='Stop'
$exe=(Resolve-Path -LiteralPath $Executable).Path
if($Output -and (Test-Path -LiteralPath $Output)) {throw 'Preserve existing evidence; choose a new Output'}
$folder=Join-Path ([IO.Path]::GetTempPath()) ('ZZY N4-03 SQLite 中文 '+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path (Join-Path $folder 'scripts') | Out-Null
$utf8=[Text.UTF8Encoding]::new($false,$true)
$records=[Collections.Generic.List[object]]::new();$passed=$false
function Require([bool]$value,[string]$message) {if(-not $value) {throw $message}}
function Invoke-Case([string]$id,[string]$source,[string]$expected='',[hashtable]$limits=@{},[int]$exit=0,[string]$code='',[string]$mode='run') {
    $file=Join-Path $folder ('scripts/'+$id+'.zzy');[IO.File]::WriteAllText($file,$source,$utf8)
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
    $start.EnvironmentVariables['PATH']='';$start.EnvironmentVariables['PYTHONPATH']='invalid-native-sqlite'
    $process=[Diagnostics.Process]::new();$process.StartInfo=$start
    try {
        $null=$process.Start();$process.StandardInput.Close()
        $stdout=$process.StandardOutput.ReadToEndAsync();$stderr=$process.StandardError.ReadToEndAsync()
        $timeout=-not $process.WaitForExit(10000)
        if($timeout) {$process.Kill();$process.WaitForExit()}
        $record=[ordered]@{id=$id;command=$start.Arguments;exit_code=$process.ExitCode;stdout=$stdout.Result;stderr=$stderr.Result;timed_out=$timeout}
        $records.Add($record)
        Require (-not $timeout -and $record.exit_code -eq $exit -and $record.stdout -ceq $expected) ('SQLite output mismatch: '+$id+'; '+($record | ConvertTo-Json -Compress))
        if($code) {
            $diag=$record.stderr | ConvertFrom-Json
            $location=if($id -eq 'post-commit-output') {$null -eq $diag.file -and $null -eq $diag.span -and $diag.message -match 'stdout_bytes'} else {$diag.file -eq ('scripts/'+$id+'.zzy') -and $diag.span.start.line -gt 0}
            Require ($diag.code -ceq $code -and $diag.schema_version -eq 1 -and $diag.kind -eq 'error' -and $location) ('Wrong SQLite diagnostic: '+$id)
            Require ($record.stderr -notmatch 'Traceback|sqlite3\.[A-Za-z]+Error|OperationalError|IntegrityError') ('Leaked backend exception: '+$id)
        } else {Require ($record.stderr -ceq '') ('Unexpected diagnostic: '+$id)}
    } finally {if($process.Id -and -not $process.HasExited) {$process.Kill();$process.WaitForExit()};$process.Dispose()}
    Require (-not (Test-Path -LiteralPath (Join-Path $folder 'state.sqlite3-journal'))) ('Leaked transaction journal: '+$id)
}
function Work([string]$body,[string]$path='state.sqlite3') {return '(addnew) work(){'+$body+'}io.print(db.transaction("'+$path+'",work));'}
function Query([string]$sql,[string]$params='[]') {return Work ('(return) (^_^)(db.query("'+$sql+'",'+$params+'));')}
try {
    Invoke-Case 'check' '(addnew) work(){io.print("bad");(return) (^_^)(0);}(shape) X{x:=db.transaction("check.sqlite3",work);}(zno) l:=(zzz)(db.transaction("check.sqlite3",work));db.transaction("check.sqlite3",work);' '' @{} 0 '' 'check'
    Require (-not (Test-Path -LiteralPath (Join-Path $folder 'check.sqlite3'))) 'check opened SQLite'
    Invoke-Case 'create' (Query 'CREATE TABLE t(id INTEGER PRIMARY KEY, title TEXT UNIQUE, n INTEGER)') "(^_^)([])`n"
    Require ((Test-Path -LiteralPath (Join-Path $folder 'state.sqlite3')) -and -not (Test-Path -LiteralPath (Join-Path $folder 'scripts/state.sqlite3'))) 'Database path is not relative to cwd'
    Invoke-Case 'insert' (Query 'INSERT INTO t(title,n) VALUES(?,?)' '["中文😀; literal[OoO]q",9223372036854775807]') "(^_^)([])`n"
    Invoke-Case 'restart' (Query 'SELECT id,title,n FROM t ORDER BY id') "(^_^)([[1, 中文😀; literal`", 9223372036854775807]])`n"
    Invoke-Case 'types' (Query 'SELECT ?,?,?,?,?' ("[-9223372036854775808,1.0,(null),`"中`0尾`",0]")) "(^_^)([[-9223372036854775808, 1.0, null, 中`0尾, 0]])`n"
    Invoke-Case 'rollback-result' (Work 'db.query("INSERT INTO t(title) VALUES(?)",["declined"]);(return) (T_T)("business");') "(T_T)(business)`n"
    Invoke-Case 'rollback-diagnostic' (Work 'db.query("INSERT INTO t(title) VALUES(?)",["error"]);1/0;(return) (^_^)(0);') '' @{} 1 'E205'
    Invoke-Case 'rollback-wrong-result' (Work 'db.query("INSERT INTO t(title) VALUES(?)",["wrong"]);(return) 0;') '' @{} 1 'E201'
    Invoke-Case 'rollback-constraint' (Work 'db.query("INSERT INTO t(title) VALUES(?)",["first"]);db.query("INSERT INTO t(title) VALUES(?)",["first"]);(return) (^_^)(0);') '' @{} 1 'E401'
    Invoke-Case 'after-errors' (Query 'SELECT count(*) FROM t') "(^_^)([[1]])`n"
    Invoke-Case 'outside' 'db.query("SELECT 1",[]);' '' @{} 1 'E401'
    Invoke-Case 'arity' 'db.transaction("absent");' '' @{} 1 'E202'
    Invoke-Case 'outer-type' 'db.transaction(1,io.print);' '' @{} 1 'E201'
    Invoke-Case 'callback-arity' '(addnew) work(x){(return) (^_^)(x);}db.transaction("absent",work);' '' @{} 1 'E201'
    Invoke-Case 'callback-native' 'db.transaction("absent",io.print);' '' @{} 1 'E201'
    Invoke-Case 'nested' (Work '(addnew) inner(){(return) (^_^)(0);}db.transaction("absent",inner);(return) (^_^)(0);') '' @{} 1 'E401'
    Require (-not (Test-Path -LiteralPath (Join-Path $folder 'absent'))) 'Invalid callback/nested call opened a connection'
    foreach($pair in @(@('bool','[(true)]','E201'),@('array','[[1]]','E201'),@('map','[data.map()]','E201'),
        @('big-positive','[9223372036854775808]','E208'),@('big-negative','[-9223372036854775809]','E208'))) {
        Invoke-Case ('parameter-'+$pair[0]) (Query 'SELECT ?' $pair[1]) '' @{} 1 $pair[2]
    }
    Invoke-Case 'parameter-count' (Query 'SELECT ?') '' @{} 1 'E401'
    Invoke-Case 'query-type' (Work 'db.query("SELECT 1",1);(return) (^_^)(0);') '' @{} 1 'E201'
    Invoke-Case 'query-arity' (Work 'db.query("SELECT 1");(return) (^_^)(0);') '' @{} 1 'E202'
    foreach($pair in @(@('begin','BEGIN'),@('commit','COMMIT'),@('rollback','ROLLBACK'),@('savepoint','SAVEPOINT x'),
        @('attach',"ATTACH DATABASE 'another.sqlite3' AS x"),@('pragma','PRAGMA user_version'),
        @('extension',"SELECT load_extension('none')"),@('multi','INSERT INTO t(title) VALUES(1); SELECT 2'),@('syntax','NOT SQL'))) {
        Invoke-Case ('sql-'+$pair[0]) (Query $pair[1]) '' @{} 1 'E401'
    }
    Require (-not (Test-Path -LiteralPath (Join-Path $folder 'another.sqlite3'))) 'ATTACH created a file'
    Invoke-Case 'comments' (Query 'SELECT 7; -- allowed trailing comment') "(^_^)([[7]])`n"
    Invoke-Case 'empty-statement' (Query '-- comment only') "(^_^)([])`n"
    Invoke-Case 'blob' (Query "SELECT X'0102'") '' @{} 1 'E201'
    Invoke-Case 'nonfinite' (Query 'SELECT 1e999') '' @{} 1 'E201'
    Invoke-Case 'invalid-text' (Query "SELECT CAST(X'ff' AS TEXT)") '' @{} 1 'E401'
    Invoke-Case 'missing-parent' (Work '(return) (^_^)(0);' 'missing/x.sqlite3') '' @{} 1 'E401'
    Invoke-Case 'nul-path' (Work '(return) (^_^)(0);' "bad`0path") '' @{} 1 'E401'
    Invoke-Case 'nul-sql' (Query "SELECT 1`0") '' @{} 1 'E401'
    foreach($limit in @(1,2,3)) {
        $exit=if($limit -eq 1){1}else{0};$code=if($exit){'E211'}else{''};$out=if($exit){''}else{"(^_^)([[1], [2]])`n"}
        Invoke-Case ('rows-'+$limit) (Query 'SELECT 1 UNION ALL SELECT 2') $out @{container_items=$limit} $exit $code
    }
    $sql='SELECT 1 /*'+('x'*64)+'*/';$length=$utf8.GetByteCount($sql)
    foreach($limit in @(($length-1),$length,($length+1))) {
        $exit=if($limit -lt $length){1}else{0};$code=if($exit){'E211'}else{''};$out=if($exit){''}else{"(^_^)([[1]])`n"}
        Invoke-Case ('payload-'+$limit) (Query $sql) $out @{io_payload_bytes=$limit} $exit $code
    }
    Invoke-Case 'deadline' (Query 'WITH RECURSIVE n(x) AS(VALUES(1) UNION ALL SELECT x+1 FROM n) SELECT sum(x) FROM n') '' @{} 1 'E401'
    Invoke-Case 'post-commit-output' (Query 'INSERT INTO t(title) VALUES(123)') '' @{stdout_bytes=1} 1 'E211'
    Invoke-Case 'final-persistent-recovery' (Query 'SELECT count(*) FROM t') "(^_^)([[2]])`n"
    Require ($records.Count -eq 50) 'SQLite collection changed or became empty'
    $passed=$true
} finally {
    if($Output) {
        $out=[IO.Path]::GetFullPath($Output);$parent=Split-Path -Parent $out
        if($parent) {New-Item -ItemType Directory -Path $parent -Force | Out-Null}
        $dll=Get-Item -LiteralPath (Join-Path $env:SystemRoot 'System32/winsqlite3.dll')
        [IO.File]::WriteAllText($out,([ordered]@{schema_version=1;passed=$passed;executable=$exe;exe_sha256=(Get-FileHash -LiteralPath $exe).Hash.ToLowerInvariant();cwd=$folder;path_empty=$true;expected=50;sqlite_dll=$dll.FullName;sqlite_dll_version=$dll.VersionInfo.FileVersion;sqlite_dll_sha256=(Get-FileHash -LiteralPath $dll.FullName).Hash.ToLowerInvariant();records=@($records)} | ConvertTo-Json -Depth 20),$utf8)
    }
}
"SQLite integration: $($records.Count)/50"
