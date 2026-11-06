# sync_results.ps1 : copy finished Colab results from Google Drive (G:\My Drive\nizam-ocr\out, synced by Drive for
# desktop) into E:\nizam-data\ocr\colab\output, then import them as Surya page candidates (tools/colab/import_returned.sh,
# idempotent). Prints the documents that gained candidates.
$src = "G:\My Drive\nizam-ocr\out"
$dst = "E:\nizam-data\ocr\colab\output"
if (-not (Test-Path $src)) { "no results folder on Drive yet"; exit 0 }
New-Item -ItemType Directory -Force $dst | Out-Null
$n = 0
Get-ChildItem $src -Directory | ForEach-Object {
    $f = Join-Path $_.FullName "results.json"
    $t = Join-Path (Join-Path $dst $_.Name) "results.json"
    if ((Test-Path $f) -and -not (Test-Path $t)) {
        New-Item -ItemType Directory -Force (Split-Path $t) | Out-Null
        Copy-Item $f "$t.tmp"; Move-Item -Force "$t.tmp" $t; $n++
    }
}
"copied $n new result(s) from Drive"
wsl -- bash /mnt/e/Nizam_e_Qanoon/tools/colab/import_returned.sh
