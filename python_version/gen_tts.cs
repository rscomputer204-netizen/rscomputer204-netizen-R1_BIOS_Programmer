using System;
using System.Speech.Synthesis;

class Program
{
    static void Main()
    {
        string outDir = @"c:\Users\R1 LAB\Desktop\Desktop-bk\driver\python_version\sound_engine\sounds";
        System.IO.Directory.CreateDirectory(outDir);

        using (SpeechSynthesizer synth = new SpeechSynthesizer())
        {
            synth.SetOutputToWaveFile(System.IO.Path.Combine(outDir, "read_done.wav"));
            synth.Speak("Read complete");
            
            synth.SetOutputToWaveFile(System.IO.Path.Combine(outDir, "write_done.wav"));
            synth.Speak("Write complete");
            
            synth.SetOutputToWaveFile(System.IO.Path.Combine(outDir, "verify_done.wav"));
            synth.Speak("Verify complete");
            
            synth.SetOutputToWaveFile(System.IO.Path.Combine(outDir, "error.wav"));
            synth.Speak("System error");
            
            synth.SetOutputToWaveFile(System.IO.Path.Combine(outDir, "click.wav"));
            synth.Speak("Click");
        }
        Console.WriteLine("Done generating TTS files.");
    }
}
