param(
  [Parameter(Mandatory=$true)]
  [ValidateSet("codex", "workbuddy", "all")]
  [string]$Target,
  [switch]$Force,
  [switch]$Setup
)

$Arguments = @("$PSScriptRoot/install.py", $Target)
if ($Force) { $Arguments += "--force" }
if ($Setup) { $Arguments += "--setup" }

if (Get-Command py -ErrorAction SilentlyContinue) {
  & py -3 @Arguments
} elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
  & python3 @Arguments
} else {
  & python @Arguments
}
exit $LASTEXITCODE
