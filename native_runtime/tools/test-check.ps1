param([Parameter(Mandatory=$true)][string]$Executable,[string]$Output)
$ErrorActionPreference='Stop'
& (Join-Path $PSScriptRoot 'test-fixed.ps1') -Executable $Executable -Output $Output -Suite Check
