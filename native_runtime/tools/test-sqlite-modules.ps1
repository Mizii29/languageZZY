param([Parameter(Mandatory=$true)][string]$Executable,[Parameter(Mandatory=$true)][string]$Output)
$ErrorActionPreference='Stop';$exe=(Resolve-Path -LiteralPath $Executable).Path
if(Test-Path -LiteralPath $Output) {throw 'Preserve module evidence; choose new output'}
$folder=Join-Path ([IO.Path]::GetTempPath()) ('ZZY SQLite modules 中文 '+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $folder | Out-Null
$utf8=[Text.UTF8Encoding]::new($false,$true)
[IO.File]::WriteAllText((Join-Path $folder 'probe.zzy'),('(addnew) work(){db.query("CREATE TABLE t(v INTEGER)",[]);'+
    'db.query("INSERT INTO t VALUES(42)",[]);(for) i (in) 0..<15000 {io.print(0);}(return) (^_^)(0);}io.print(db.transaction("probe.sqlite3",work));'),$utf8)
$start=[Diagnostics.ProcessStartInfo]::new();$start.FileName=$exe;$start.Arguments='run probe.zzy --diagnostic-format json'
$start.WorkingDirectory=$folder;$start.UseShellExecute=$false;$start.CreateNoWindow=$true
$start.RedirectStandardOutput=$true;$start.RedirectStandardError=$true
$start.StandardOutputEncoding=$utf8;$start.StandardErrorEncoding=$utf8
$start.EnvironmentVariables['PATH']='';$start.EnvironmentVariables['PYTHONPATH']='invalid-sqlite-module-probe'
$process=[Diagnostics.Process]::new();$process.StartInfo=$start;$passed=$false;$modules=@();$children=@()
try {
    $null=$process.Start();$first=$process.StandardOutput.ReadLineAsync()
    if(-not $first.Wait(10000) -or $first.Result -cne '0') {throw 'SQLite CLI did not reach observable transaction'}
    $modules=@($process.Modules | ForEach-Object {$file=Get-Item -LiteralPath $_.FileName
        [ordered]@{name=$_.ModuleName;path=$_.FileName;version=$file.VersionInfo.FileVersion;company=$file.VersionInfo.CompanyName;sha256=(Get-FileHash -LiteralPath $_.FileName).Hash.ToLowerInvariant()}})
    $sqlite=@($modules | Where-Object {$_.name -ieq 'winsqlite3.dll'})
    $expected=Join-Path $env:SystemRoot 'System32/winsqlite3.dll'
    if($sqlite.Count -ne 1 -or $sqlite[0].path -ine $expected) {throw 'SQLite did not load the fixed system component'}
    $signature=Get-AuthenticodeSignature -LiteralPath $expected
    if($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Microsoft Windows') {throw 'Unreviewed SQLite component signer'}
    if(@($modules | Where-Object {$_.name -match '^(python|_tkinter|tcl|tk\d)'}).Count) {throw 'SQLite CLI loaded Python/GUI'}
    $children=@(Get-CimInstance Win32_Process -Filter ('ParentProcessId='+$process.Id) | Select-Object -ExpandProperty Name)
    if(@($children | Where-Object {$_ -notmatch '^conhost\.exe$'}).Count) {throw 'SQLite CLI created a child process'}
    $tail=$process.StandardOutput.ReadToEndAsync();$errors=$process.StandardError.ReadToEndAsync()
    if(-not $process.WaitForExit(30000)) {throw 'SQLite module probe timeout'}
    if($process.ExitCode -ne 0 -or $errors.Result -cne '' -or ($first.Result+"`n"+$tail.Result) -cne (('0'+"`n")*15000+"(^_^)(0)`n")) {throw 'SQLite module probe result mismatch'}
    $passed=$true
} finally {
    if($process.Id -and -not $process.HasExited) {$process.Kill();$process.WaitForExit()}
    $record=[ordered]@{schema_version=1;passed=$passed;executable=$exe;exe_sha256=(Get-FileHash -LiteralPath $exe).Hash.ToLowerInvariant();cwd=$folder;path_empty=$true;pythonpath='invalid-sqlite-module-probe';sqlite_signer=$(if($signature){$signature.SignerCertificate.Subject});modules=$modules;children=$children;exit_code=$(if($process.HasExited){$process.ExitCode})}
    $process.Dispose();[IO.File]::WriteAllText([IO.Path]::GetFullPath($Output),($record | ConvertTo-Json -Depth 15),$utf8)
}
'SQLite actual CLI modules: PASS'
