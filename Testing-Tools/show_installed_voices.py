"""
Collects and prints information about the available text-to-speech voices on the system.

This function initializes a pyttsx3 engine, retrieves the list of available voices, sorts them by language and gender, and prints the name, language, and gender of each voice.

The `if __name__ == "__main__":` block allows this script to be run directly to see the list of available voices.
"""
import pyttsx3

def collect_voices():
    engine = pyttsx3.init()
    voices = engine.getProperty('voices')
    # sort voices by language and gender
    voices.sort(key=lambda x: (x.languages, x.gender))
    for voice in voices:
        print(f"Voice: {voice.name}, Language: {voice.languages}, Gender: {voice.gender}")

if __name__ == "__main__":
    collect_voices()