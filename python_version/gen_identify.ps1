Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.SetOutputToWaveFile("c:\Users\R1 LAB\Desktop\Desktop-bk\driver\python_version\sound_engine\sounds\identify_done.wav")
$synth.Speak("Identify complete")
$synth.Dispose()
