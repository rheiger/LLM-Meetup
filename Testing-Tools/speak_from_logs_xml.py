import sys
import pyttsx3
import re

engine = pyttsx3.init()

def speak(voice_id: str, text: str):
    engine.setProperty('voice', voice_id)
    engine.say(text)
    engine.runAndWait()

def find_voice_id_in(text: str) -> str:
    # From text extract voice properties in substring `<voice gender='m' xml:lang='sv' name='Oskar (Enhanced)'>`
    # and return the voice id
    # if no voice id is found, return empty string
    # if multiple voice ids are found, return the first one

    
    voices = engine.getProperty('voices')
    match = re.search(r"<voice.*?name='(.*?)'", text)
    if match:
        voice_name = match.group(1)
        for voice in voices:
            if voice_name.lower() in voice.name.lower():
                return voice.id
    return ""

def main():
    # open file(s) provided on command line in a loop
    for filename in sys.argv[1:]:
        with open(filename, 'r') as f:
            message = f.read()
            voice_id = find_voice_id_in(message)
            speak(voice_id, message)

if __name__ == "__main__":
    main()