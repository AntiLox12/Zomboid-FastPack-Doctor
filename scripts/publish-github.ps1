$ErrorActionPreference = "Stop"

$repository = "AntiLox12/Zomboid-FastPack-Doctor"

$ghCommand = Get-Command gh -ErrorAction SilentlyContinue
if ($ghCommand) {
    $gh = $ghCommand.Source
} elseif (Test-Path -LiteralPath "C:\Program Files\GitHub CLI\gh.exe") {
    $gh = "C:\Program Files\GitHub CLI\gh.exe"
} else {
    throw "GitHub CLI is not installed. Install it with: winget install --id GitHub.cli -e"
}

& $gh auth status

$previousPreference = $ErrorActionPreference
$ErrorActionPreference = "SilentlyContinue"
& $gh repo view $repository --json nameWithOwner 2>$null | Out-Null
$repositoryExists = $LASTEXITCODE -eq 0
$ErrorActionPreference = $previousPreference

if (-not $repositoryExists) {
    & $gh repo create $repository `
        --public `
        --description "Diagnostics and cooperative lazy initialization for Project Zomboid Build 42 modpacks" `
        --disable-wiki
}

$previousPreference = $ErrorActionPreference
$ErrorActionPreference = "SilentlyContinue"
git remote get-url origin 2>$null | Out-Null
$originExists = $LASTEXITCODE -eq 0
$ErrorActionPreference = $previousPreference

if (-not $originExists) {
    git remote add origin "https://github.com/$repository.git"
}

git push --set-upstream origin main
git push origin v0.1.0

& $gh repo edit $repository `
    --add-topic project-zomboid `
    --add-topic build-42 `
    --add-topic modding `
    --add-topic modpack `
    --add-topic diagnostics

Write-Host "Published: https://github.com/$repository"
Write-Host "The v0.1.0 tag starts the GitHub Actions release build."
