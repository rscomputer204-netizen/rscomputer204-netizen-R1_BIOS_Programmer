Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer

$outDir = "c:\Users\R1 LAB\Desktop\Desktop-bk\driver\python_version\sound_engine\sounds"
if (-not (Test-Path $outDir)) {
    New-Item -ItemType Directory -Force -Path $outDir | Out-Null
}

$sounds = @{
    "read_done.wav" = "Read complete"
    "write_done.wav" = "Write complete"
    "verify_done.wav" = "Verify complete"
    "erase_done.wav" = "Erase complete"
    "error.wav" = "System error"
    "click.wav" = "Click"
    "auto_done.wav" = "Auto sequence complete"
}

foreach ($key in $sounds.Keys) {
    $path = Join-Path $outDir $key
    $text = $sounds[$key]
    
    $synth.SetOutputToWaveFile($path)
    $synth.Speak($text)
}

$synth.Dispose()
Write-Host "Audio generation complete."
