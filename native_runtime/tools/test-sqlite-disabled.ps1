param([Parameter(Mandatory=$true)][string]$Executable)
$ErrorActionPreference='Stop'
$exe=(Resolve-Path -LiteralPath $Executable).Path
$folder=Join-Path ([IO.Path]::GetTempPath()) ('ZZY SQLite disabled '+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $folder | Out-Null
$file=Join-Path $folder 'disabled.zzy';$database=Join-Path $folder 'not-created.sqlite3'
[IO.File]::WriteAllText($file,('(addnew) work(){(return) (^_^)(0);}db.transaction("'+$database+'",work);'),[Text.UTF8Encoding]::new($false))
$info=& $exe info | ConvertFrom-Json
if($LASTEXITCODE -or $info.sqlite_enabled -ne $false) {throw 'SQLite OFF info mismatch'}
$out=& $exe check $file 2>&1
if($LASTEXITCODE -or $out) {throw 'Disabled SQLite static check failed'}
$p=[Diagnostics.ProcessStartInfo]::new($exe,('run "'+$file+'" --diagnostic-format json'))
$p.UseShellExecute=$false;$p.CreateNoWindow=$true;$p.RedirectStandardOutput=$true;$p.RedirectStandardError=$true
$p.EnvironmentVariables['PATH']='';$p.EnvironmentVariables['PYTHONPATH']='invalid-sqlite-disabled'
$process=[Diagnostics.Process]::Start($p)
try {
    $stdout=$process.StandardOutput.ReadToEnd();$stderr=$process.StandardError.ReadToEnd();$process.WaitForExit()
    if($process.ExitCode -ne 1 -or $stdout -or ($stderr | ConvertFrom-Json).code -ne 'E402' -or (Test-Path -LiteralPath $database)) {throw 'Disabled SQLite run rejection failed'}
} finally {$process.Dispose()}
'SQLite disabled: 3/3 (info/check/run)'
