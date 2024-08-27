import socket
import threading
import sys
import datetime
import re
import argparse
import logging
import yaml
import time
import select
import pyttsx3
import langdetect
import random
import signal
from typing import Dict, Any, List, Tuple
import ollama

__version__ = "This is version v0.5.0 (build: 60) by rheiger@icloud.com on 2024-08-27 21:36:52"

terminate = False
in_accept = False
translate_client = None
translate_config = None

def load_config(config_file: str) -> Dict[str, Any]:
    """Load configuration from a YAML file."""
    with open(config_file, 'r') as f:
        return yaml.safe_load(f)

# Implement a signal handler for SIGINT (Ctrl+C)
def signal_handler(sig, frame):
    global terminate, in_accept
    logging.info("Received SIGINT (Ctrl+C), terminating... ASAP")
    terminate = True
    if in_accept:
        logging.info("Terminating accept loop")
        raise KeyboardInterrupt

def sanitize_filename(name):
    # Remove any characters that aren't alphanumeric, underscore, or hyphen
    sanitized = re.sub(r'[^\w\-.$@,]', lambda m: '~' if m.start() > 0 else m.group(), name)    
    # Limit to 24 characters
    return sanitized[:32]

def initialize_tts_engine(persona_name, persona_lang, persona_gender, other_voice, logger, debug=False):
    tts_engine = pyttsx3.init()
    selected_voice = None
    try:
        logger.debug(f"other_voice = {other_voice}")
        voices = tts_engine.getProperty('voices')
        matching_voices = []
    
        logger.debug(f"persona_lang = {persona_lang}")
        if persona_lang != "--":
            matching_voices = [v for v in voices if any(persona_lang.lower() in lang.lower() for lang in v.languages) and v.id not in [other_voice.id if other_voice else ""]]
    
        if not matching_voices:
            matching_voices = voices
    
        if persona_gender.lower() == 'f':
            gender_voices = [v for v in matching_voices if 'female' in str(v.gender).lower()]
        elif persona_gender.lower() == 'm':
            gender_voices = [v for v in matching_voices if 'male' in str(v.gender).lower() and 'female' not in str(v.gender).lower()]
        else:
            gender_voices = None

        if not gender_voices:
            gender_voices = [v for v in matching_voices if 'neuter' in str(v.gender).lower()]
            logger.warning(f"No gender-specific voices found. Selecting a random voice from the list: {gender_voices}")
            if len(gender_voices) == 0:
                gender_voices = matching_voices
                logger.warning(f"Absolutely no gender-specific voices found. Selecting a random voice from the list: {gender_voices}")

        if gender_voices:
            selected_voice = random.choice(gender_voices)
            logger.info(f"Assigned voice: {selected_voice.name} ({selected_voice.languages}) [{selected_voice.gender}] to {persona_name}")
        else:
            logger.warning("No matching voices available, using default voice")
    except Exception as e:
        logger.exception(f"Failed to set voice: {e}")

    return tts_engine, selected_voice

def handle_client(client_socket, partner_socket, hello_message=None, transcript_file=None, session_name=None, mirror_stdout=False, max_messages=0, logger=None, debug=False, tts=False, other_voice=None):
    persona_name = None
    persona_lang = None
    persona_model = None
    persona_gender = None
    tts_engine = None
    selected_voice = None

    # Wait for the /iam message
    while not persona_name:
        data = client_socket.recv(4096).decode('utf-8').strip()
        if data.startswith('/iam:'):
            logger.debug(f"Received /iam message: {data}")
            pattern = r"/iam:\s*(?:(?:Dr\.|Prof\.|Mr\.|Mrs\.|Ms\.)\s*)*(?P<persona_name>\w+\.?(?:\s+\w+)*)\s*(?:\((?P<persona_lang>[^)]+)\))?\s*(?:\[(?P<persona_gender>[^\]]+)\])?\s*(?:\.\s*(?P<persona_model>.*))?"
            match = re.match(pattern, data)

            if match:
                full_name = match.group(1)
                persona_name = match.group("persona_name").strip()
                persona_lang = match.group("persona_lang").strip() if match.group("persona_lang") else "--"
                persona_gender = match.group("persona_gender") if match.group("persona_gender") else "--"
                persona_model = match.group("persona_model") if match.group("persona_model") else "Unknown_model"
                logger.info(f"Received persona name: {persona_name}, language: {persona_lang}, gender: {persona_gender}")
            else:
                logger.warning(f"Invalid /iam message format: '{data}'")
                persona_name = "Unknown"
                persona_lang = "--"
                persona_gender = "--"
                persona_model = "Unknown_model"
            break
    

    if tts:
        tts_engine, selected_voice = initialize_tts_engine(persona_name, persona_lang, persona_gender, other_voice, logger, debug)

    if hello_message:
        client_socket.send(hello_message.encode() + b'\n')
        logger.info(f"Sent hello message: {hello_message} to {client_socket.getpeername()}")

    if debug:
        logger.debug(f"Determined for persona {persona_name} language={persona_lang} gender={persona_gender} using voice {selected_voice.name if selected_voice else 'None'}")
    
    return persona_name, persona_lang, persona_model, persona_gender, tts_engine, selected_voice

def filter_md(s: str) -> str:
    """Escape markdown instructions from a string."""
    # s = s.replace('*', r'\*')
    # s = s.replace('_', r'\_')
    s = s.replace('`', r'\`')
    s = s.replace('#', r'\#')
    # s = s.replace('-', r'\-')
    s = s.replace('>', r'\>')
    s = s.replace('+', r'\+')
    s = s.replace('=', r'\=')
    s = s.replace('|', r'\|')
    # s = s.replace('[', r'\[')
    # s = s.replace(']', r'\]')
    # s = s.replace('(', r'\(')
    # s = s.replace(')', r'\)')
    # s = s.replace('!', r'\!')
    s = s.replace('\n\n', '<br>')
    def process_item(item):
        item = item.strip().lstrip('0123456789.-*+[] ')
        if item.lower().startswith('[ ]'):
            return f'<li><input type="checkbox"> {item[3:].strip()}</li>'
        elif item.lower().startswith('[x]'):
            return f'<li><input type="checkbox" checked> {item[3:].strip()}</li>'
        else:
            return f'<li>{item}</li>'

    def convert_list(match):
        lines = match.group(0).split('\n')
        list_type = 'ol' if re.match(r'^\d+\.', lines[0]) else 'ul'
        items = [process_item(line) for line in lines if line.strip()]
        return f'<{list_type}>\n' + '\n'.join(items) + f'\n</{list_type}>'

    # More strict pattern to match lists
    list_pattern = re.compile(r'(?:(?:^\d+\.|\-|\*|\+)[ \t].+\n?)+(?:\n|$)', re.MULTILINE)

    # Replace lists in the text
    converted_text = list_pattern.sub(convert_list, s)

    return converted_text

def convert_markdown_to_speech(markdown_text, logger, debug=False):
    # Convert markdown to speech notation for ttysx3 engine
    
    emoji_pattern = re.compile(
    r'([\U0001F600-\U0001F64F]'  # Emoticons
    r'|[\U0001F300-\U0001F5FF]'  # Symbols & Pictographs
    r'|[\U0001F680-\U0001F6FF]'  # Transport & Map Symbols
    r'|[\U0001F700-\U0001F77F]'  # Alchemical Symbols
    r'|[\U0001F780-\U0001F7FF]'  # Geometric Shapes Extended
    r'|[\U0001F800-\U0001F8FF]'  # Supplemental Arrows-C
    r'|[\U0001F900-\U0001F9FF]'  # Supplemental Symbols and Pictographs
    r'|[\U0001FA00-\U0001FA6F]'  # Chess Symbols
    r'|[\U0001FA70-\U0001FAFF]'  # Symbols and Pictographs Extended-A
    r'|[\U00002600-\U000026FF]'  # Miscellaneous Symbols
    r'|[\U00002700-\U000027BF]'  # Dingbats
    r'|[\U0001F1E6-\U0001F1FF]'  # Flags (iOS)
    r'|[\U0001F900-\U0001F9FF]'  # Supplemental Symbols and Pictographs
    r'|[\U0001F300-\U0001F5FF]'  # Misc Symbols and Pictographs
    r'|[\U0001F680-\U0001F6FF]'  # Transport and Map
    r'|[\U0001F700-\U0001F77F]'  # Alchemical Symbols
    r'|[\U0001F780-\U0001F7FF]'  # Geometric Shapes Extended
    r'|[\U0001F800-\U0001F8FF]'  # Supplemental Arrows-C
    r'|[\U0001F1E6-\U0001F1FF]'  # Regional Indicator Symbols
    r'|[\U0001F201-\U0001F251]'  # Enclosed Ideographic Supplement
    r'|[\U00002500-\U00002BEF]'  # Chinese characters
    r'|[\U00002702-\U000027B0]'  # Dingbats
    r'|[\U000024C2-\U0001F251]'  # Enclosed Characters
    r'|[\U0001F600-\U0001F636]'  # Emoticons
    r'|[\U0001F681-\U0001F6C5]'  # Transport and Map
    r'|[\U0001F30D-\U0001F567]'  # Weather, clocks, etc.
    r'|\U0001F4AF|\U0001F4A2|\U0001F4A5|\U0001F4AB|\U0001F4A6|\U0001F4A8|'  # Special Cases for Popular Emojis
    r'[\U0001F1E0-\U0001F1FF])'  # Flags
)

    # Remove or replace common markdown elements
    logger.debug(f"Converting markdown to speech: {markdown_text}")
    speech_text = markdown_text

    # IMPORTANT: We really need to handle double quotes as first instance to make sure we don't mess up quotes within SSML tags
    # NOTE: Probably, using this extended regex would prevent the problem from happening. The regex is checking for double quotes at the beginning of a line or whitespace followed by a double quote and end of string or followed by whitespace.
    speech_text = re.sub(r'(?:(^")|(\s"))(.*?)(")(?=\s|\.|!|,|;|:|\?|$)', r'<emphasis level="moderate"><prosody rate="slow" pitch="low">\3</prosody></emphasis><break time="100ms"/>', speech_text)
    speech_text = re.sub(r'„(.*?)“', r'<emphasis level="moderate"><prosody rate="slow" pitch="low">\1</prosody></emphasis><break time="100ms"/>', speech_text)
    speech_text = re.sub(r'«(.*?)»', r'<emphasis level="moderate"><prosody rate="slow" pitch="low">\1</prosody></emphasis><break time="100ms"/>', speech_text)
    speech_text = re.sub(r"(?:(^')|(\s'))(.*?)(')(?=\s|\.|!|,|;|:|\?|$)", r'<emphasis level="moderate"><prosody rate="slow" pitch="low">\3</prosody></emphasis><break time="100ms"/>', speech_text)
    speech_text = re.sub(emoji_pattern, r'<emphasis level="moderate"><prosody rate="slow" pitch="low">\1</prosody></emphasis><break time="75ms"/>', speech_text)
    # Convert headers to emphasized text
    speech_text = re.sub(r'^#{1,6}\s*(.*?)$', r'<emphasis level="strong"><prosody rate="slow" pitch="default">\1</prosody></emphasis><break time="1000ms"/>', speech_text, flags=re.MULTILINE)

    # Convert bold and italic
    speech_text = re.sub(r'\*\*(.*?)\*\*', r'<emphasis level="strong">\1</emphasis><break time="200ms"/>', speech_text)
    speech_text = re.sub(r'\*(.*?)\*', r'<prosody volume="soft" pitch="default" rate="slow">\1</prosody><break time="250ms"/>', speech_text)
    speech_text = re.sub(r'__(.*?)__', r'<emphasis level="strong">\1</emphasis><break time="200ms"/>', speech_text)
    speech_text = re.sub(r'_(.*?)_', r'<prosody volume="soft" pitch="default" rate="slow">\1</prosody><break time="250ms"/>', speech_text)
    # speech_text = re.sub(r'\((.*?)\)', r'<prosody volume="soft" pitch="default" rate="slow">\1</prosody><break time="200ms"/>', speech_text) # Heavily depends on whether it is description of action or not in parens '()'

    # Handle titles like Prof. Dr. etc.
    speech_text = re.sub(r'\b(Dr|Mr|Mrs|Ms|Prof)\.', r'\1<dot>', speech_text)

    # Convert lists to simple text
    speech_text = re.sub(r'^\s*[-*+]\s*(.*?)$', r'\1. ', speech_text, flags=re.MULTILINE)
    speech_text = re.sub(r'^\s*(\d+\.)\s*(.*?)$', r'\1 \2. ', speech_text, flags=re.MULTILINE)
    # logger.debug(f"After list handling notation:\n{speech_text}")

    # Remove links, keeping only the text
    speech_text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', speech_text)
    # logger.debug(f"After links notation:\n{speech_text}")

    # Remove any remaining special characters
    # speech_text = re.sub(r'[#_*~`>|]', '', speech_text)
    # logger.debug(f"After remaining special characters notation:\n{speech_text}")

    # Add pauses for better speech flow
    speech_text = speech_text.replace('... ', '<break time="300ms"/>')
    speech_text = speech_text.replace('… ', '<break time="300ms"/>')
    speech_text = speech_text.replace('. ', '.<break time="300ms"/>')
    speech_text = speech_text.replace('.\n\n', '.<break time="700ms"/>')
    speech_text = speech_text.replace('! ', '!<break time="400ms"/>')
    speech_text = speech_text.replace('? ', '?<break time="300ms"/>')
    speech_text = speech_text.replace('; ', ';<break time="150ms"/>')
    speech_text = speech_text.replace(' - ', ';<break time="150ms"/>')
    speech_text = speech_text.replace(': ', ';<break time="200ms"/>')
    speech_text = speech_text.replace(', ', ',<break time="100ms"/>')
    speech_text = speech_text.replace('<dot>', '.') # Recreate the '.' after the title
    speech_text = speech_text.replace('/start', '<lang xml:lang="en-US"><prosody volume="soft" pitch="low" rate="slow">Start of conversation</prosody></lang><break time="600ms"/>')
    speech_text = speech_text.replace('/bye', '<lang xml:lang="en-US"><prosody volume="default" pitch="default" rate="slow">Good bye.</prosody></lang>')
    speech_text = speech_text.replace('/end', '<lang xml:lang="en-US"><prosody volume="soft" pitch="low" rate="slow">Termination of conversation</prosody></lang><break time="600ms"/>')
    speech_text = speech_text.replace('/stop', '<lang xml:lang="en-US"><prosody volume="soft" pitch="low" rate="slow">Request conversation termination</prosody></lang><break time="600ms"/>')
    speech_text = speech_text.replace('/help', '<lang xml:lang="en-US"><prosody volume="soft" pitch="low" rate="slow">Unimplemented request for help</prosody></lang><break time="600ms"/>')
    # logger.debug(f"Converted markdown to speech notation:\n{speech_text}")
    # Wrap the entire text in SSML tags
    speech_text = f'<speak>{speech_text}</speak>'

    logger.debug(f"Converted markdown to speech notation:\n{speech_text}")

    return speech_text

def html_save_format_message(message, debug=False):
    if debug and message:
        print(f"message='{message}'")

    if message:
        content = message
        # Convert markdown to HTML
        content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', content)  # Bold
        content = re.sub(r'\*(.*?)\*', r'<em>\1</em>', content)  # Italic
        content = re.sub(r'^((?:\d+\. .*?\n)+)', lambda m: '<ol>' + re.sub(r'(\d+\. )(.*?)(?:\n|$)', r'<li>\2</li>', m.group(1)) + '</ol>\n', content, flags=re.MULTILINE)  # Ordered list
        content = re.sub(r'^(- |\* )(.*?)(\n\n|$)', r'<ul><li>\2</li></ul>\n\n', content, flags=re.DOTALL|re.MULTILINE)  # Unordered list
        content = re.sub(r'\n(- |\* )', r'</li><li>', content)  # Unordered list items
        content = re.sub(r'^(\[ \] )(.*?)(\n\n|$)', r'<ul class="checklist"><li><input type="checkbox">\2</li></ul>\n\n', content, flags=re.DOTALL|re.MULTILINE)  # Checkbox list
        content = re.sub(r'^(\[x\] )(.*?)(\n\n|$)', r'<ul class="checklist"><li><input type="checkbox" checked>\2</li></ul>\n\n', content, flags=re.DOTALL|re.MULTILINE)  # Checked checkbox list
        content = re.sub(r'\n(\[ \] )', r'</li><li><input type="checkbox">', content)  # Checkbox list items
        content = re.sub(r'\n(\[x\] )', r'</li><li><input type="checkbox" checked>', content)  # Checked checkbox list items
        return content
    return ""

# translate_system_prompt = """You are a professional **simultaneous interpreter**, fluent in all relevant languages.
#                             You only strictly translate from the identified language to the target language.
#                             You don't add any additional information or commentary.
#                             You never ask whether you should translate something else or not.
#                             You flawlessly identify the language of the input text and translate it into {target_language}"""

def language_lookup(language_code, logger, debug=False):
    # Define a dictionary to map language codes to language names
    language_names = {
        "en": "English",
        "de": "German",
        "fr": "French",
        "es": "Spanish",
        "it": "Italian",
        "pt": "Portuguese",
        "nl": "Dutch",
        "sv": "Swedish",
        "da": "Danish",
        "fi": "Finnish",
        "no": "Norwegian",
        "is": "Icelandic",
        "lt": "Lithuanian",
        "lv": "Latvian",
        "et": "Estonian",
        "pl": "Polish",
        "cs": "Czech",
        "sk": "Slovak",
        "hu": "Hungarian",
        "ro": "Romanian",
        "bg": "Bulgarian",
        "ru": "Russian",
        "uk": "Ukrainian",
        "el": "Greek",
        "tr": "Turkish",
        "ar": "Arabic",
        "he": "Hebrew",
        "fa": "Persian",
        "ur": "Urdu",
        "hi": "Hindi",
        "bn": "Bengali",
        "mr": "Marathi",
        "ta": "Tamil",
        "te": "Telugu",
        "kn": "Kannada",
        "ml": "Malayalam",
        "si": "Sinhala",
        "th": "Thai",
        "lo": "Lao",
        "km": "Khmer",
        "my": "Burmese",
        "ne": "Nepali",
        "si": "Sinhala",
        "zh": "Chinese",
        "ja": "Japanese",
        "ko": "Korean",
        "vi": "Vietnamese",
        "id": "Indonesian",
        "ms": "Malay",
        "tl": "Tagalog",
        "ms": "Malay",
    }
    return language_names[language_code]

def translate(text, source_language, target_language, logger, debug=False):
    global translate_client, translate_config
    if not translate_client:
        logger.error("Translation client not initialized. Please call initialize_translation_client() first.")
        return None
    if not translate_config:
        logger.error("Translation configuration not loaded. Please call load_translation_config() first.")
        return None
    target = language_lookup(target_language, logger, debug)
    logger.debug(f"Translating '{text}' to {target}")
    response = translate_client.chat(
        model=translate_config['model'],
        messages=[
            {"role": "system", "content": f"""You are a professional **interpreter**, fluent in all relevant languages.
                            You only translate the message text from the user from {language_lookup(source_language,logger,debug)} to {language_lookup(target_language, logger, debug)}.
                            You don't add any additional information or commentary.
                            You never ask any questions.
                            If both languages are the same, you don't translate and just return the original message text."""},
            {"role": "user", "content": text}
        ],
        stream=False,
        options={
            'temperature': translate_config['temperature'],
            'max_tokens': translate_config['max_tokens'],
            'top_p': translate_config['top_p'],
            'frequency_penalty': 0,
        }
    )
    translated_text = response['message']['content'].strip()
    logger.debug(f"{response['prompt_eval_count']} input tokens evaluated in {round(response['prompt_eval_duration']/1e9, 3)} seconds {round(1e9 * float(response['prompt_eval_count']) / response['prompt_eval_duration'], 3)} tokens/sec, "
            f"{response['eval_count']} output tokens evaluated in {round(response['total_duration']/1e9, 3)} seconds {round(1e9 * float(response['eval_count']) / response['total_duration'], 3)} tokens/sec")
    logger.info(f"Translated text: {translated_text}")
    return translated_text

def start_proxy(config, mirror_stdout, max_messages, logger, no_transcript, debug = False, tts=False):
    global terminate, in_accept
    port = config['proxy']['port']
    host = config['proxy']['host']
    hello = config['proxy'].get('hello', '')

    while not terminate:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            server.bind((host, port))
        except socket.error as e:
            logger.error(f"Binding failed: {e}")
            sys.exit()

        server.listen(2)

        logger.info(f"Proxy listening on {host}:{port}")

        client1 = None
        client2 = None
        transcript_file = None
        persona1 = None
        persona2 = None
        lang1 = None
        lang2 = None
        model1 = None
        model2 = None
        tts_engine1 = None
        tts_engine2 = None
        gender1 = None
        gender2 = None
        ssml_file1 = None
        ssml_file2 = None
        transcript_file = None
        
        try:
            try:
                in_accept = True
                client1, addr1 = server.accept()
                logger.info(f"Connection from {addr1[0]}:{addr1[1]}")

                client2, addr2 = server.accept()
                logger.info(f"Connection from {addr2[0]}:{addr2[1]}")
                in_accept = False
            except KeyboardInterrupt:
                logger.info("Terminating accept loop")
                break

            iso_date = datetime.datetime.now().isoformat()
            
            translate_voice1 = None
            translate_voice2 = None
            translate_tts1 = None
            translate_tts2 = None

            send_hello_to_first = True # Alternatively use False or random.choice([True, False])
            persona1,lang1,model1, gender1, tts_engine1, voice1 = handle_client(client1, client2, hello if send_hello_to_first else None, None, None, mirror_stdout, max_messages, logger, debug, tts, None)
            persona2,lang2,model2, gender2, tts_engine2, voice2 = handle_client(client2, client1, hello if not send_hello_to_first else None, None, None, mirror_stdout, max_messages, logger, debug, tts, voice1)
            safe_persona1 = sanitize_filename(persona1)
            safe_persona2 = sanitize_filename(persona2)
            # get a voice for the translation
            
            if tts and lang1 != lang2:
                translate_tts1, translate_voice1 = initialize_tts_engine(persona1, lang2, gender1, None, logger, debug)
                translate_tts2, translate_voice2 = initialize_tts_engine(persona2, lang1, gender2, translate_voice1, logger, debug)

            if tts and debug:
                ssml_file1_name = f'logs/tts_{iso_date}_{safe_persona1}({lang1})_{sanitize_filename(model1)}.xml'
                ssml_file2_name = f'logs/tts_{iso_date}_{safe_persona2}({lang2})_{sanitize_filename(model2)}.xml'
                ssml_file1 = open(ssml_file1_name, 'w', encoding='utf-8')
                ssml_file2 = open(ssml_file2_name, 'w', encoding='utf-8')
                ssml_file1.write(f"<speak><voice gender='{gender1}' xml:lang='{lang1}' name='{voice1.name}'>\n")
                ssml_file2.write(f"<speak><voice gender='{gender2}' xml:lang='{lang2}' name='{voice2.name}'>\n")
                ssml_file1.flush()
                ssml_file2.flush()

            if not no_transcript:
                transcript_filename = f'transcripts/transcript_{iso_date}_{safe_persona1}({lang1})_{sanitize_filename(model1)}---{safe_persona2}({lang2})_{sanitize_filename(model2)}.html'
                
                transcript_file = open(transcript_filename, 'w', encoding='utf-8')
                transcript_file.write('<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="UTF-8">\n<meta name="viewport" content="width=device-width, initial-scale=1.0">\n<title>Transcript</title>\n<style>\n')
                transcript_file.write('table { border-collapse: collapse; width: 100%; }\n')
                transcript_file.write('th, td { border: 1px solid black; padding: 8px; text-align: left; }\n')
                transcript_file.write('th { background-color: #f2f2f2; }\n')
                transcript_file.write('</style>\n</head>\n<body>\n')
                transcript_file.write('<table>\n')
                transcript_file.write(f'<tr><th>Count</th><th>Delta</th><th>{persona1}[{gender1}] ({model1})</th><th>Translation</th><th>{persona2}[{gender2}] ({model2})</th></tr>\n')

            message_count = 0
            last_time = datetime.datetime.now()
            
            while True:
                ready_sockets, _, _ = select.select([client1, client2], [], [], 1.0)
                
                if not ready_sockets:
                    continue

                for ready_socket in ready_sockets:
                    try:
                        data = ready_socket.recv(65536)
                        if not data:
                            logger.warning(f"Client {ready_socket.getpeername()} disconnected")
                            raise Exception("Client disconnected")

                        current_time = datetime.datetime.now()
                        delta = int((current_time - last_time).total_seconds())
                        last_time = current_time

                        logger.debug(f"Received {len(data)} bytes from {ready_socket.getpeername()}: {data}")
                        message = data.decode('utf-8').strip()
                        # message = re.sub(r'\n+', ' ', message) # TODO Maybe remove this
                        logger.debug(f"Received message: {message}")
                        
                        content1 = ""
                        content2 = ""
                        html_content_translated = ""

                        #------------------ Receive from client 1 ------------------
                        # Here is where we prepare to write out the transcript for session 1
                        if ready_socket == client1:
                            if not no_transcript:
                                # Check if we have received the hint that context might have been truncated
                                if message.startswith('/truncated:'):
                                    lb_pos = message.find('<br>')
                                    #transcript_file.write(f"| {message_count} | {delta} | _{message[:lb_pos]}_<br>{filter_md(message[lb_pos+4:])} | |\n")
                                    logger.warning(f"Received on 1 /truncate message: {message}")
                                    message = f"<i>{message[:lb_pos]}</i><br>{message[lb_pos+4:]}"
                                    d = data.decode('utf-8')
                                    d = d[d.find('<br>')+4:]
                                    data = d.encode('utf-8')
                                    # continue
                                # else:
                                #     #transcript_file.write(f"| {message_count} | {delta} | {filter_md(message)} | |\n")
                                if tts_engine1:
                                    tts_engine1.setProperty('voice',voice1.id)
                                    speech_text = convert_markdown_to_speech(message,logger,debug=debug)
                                    tts_engine1.say(speech_text)
                                    if debug:
                                        ssml_file1.write(f"\n<!--\n{message}\n-->\n")
                                        ssml_file1.write(f"{speech_text}\n\n")
                                        ssml_file1.flush()
                                    tts_engine1.runAndWait()
                                content1 = html_save_format_message(message) # save this for the transcript at the end of the loop
                            if lang1 != lang2:
                                translation = translate(message, lang1, lang2, logger, debug)
                                html_content_translated = html_save_format_message(translation)
                                if translate_tts1:
                                    translate_tts1.setProperty('voice',translate_voice1.id) # NOTE: Since the languages differ, we need to switch the voice to the target language
                                    ssml_content_translated = convert_markdown_to_speech(translation,logger,debug=debug)
                                    translate_tts1.say(ssml_content_translated)
                                    if debug:
                                        ssml_file1.write(f"\n<!--\n{translation}\n-->\n")
                                        ssml_file1.write(f"{ssml_content_translated}\n\n")
                                        ssml_file1.flush()
                                    translate_tts1.runAndWait()
                            else:
                                translation = message
                            last_time = datetime.datetime.now()
                            client2.send(translation.encode('utf-8'))

                        #------------------ Receive from client 2 ------------------
                        # Here is where we prepare to write out the transcript for session 2
                        else:
                            if not no_transcript:
                                if message.startswith('/truncated:'):
                                    lb_pos = message.find('<br>')
                                    # transcript_file.write(f"| {message_count} | {delta} | | _{message[:lb_pos]}_<br>{filter_md(message[lb_pos+4:])} |\n")
                                    logger.warning(f"Received on 2 /truncate message: {message}")
                                    message = f"<i>{message[:lb_pos]}</i><br>{message[lb_pos+4:]}"
                                    d = data.decode('utf-8')
                                    d = d[d.find('<br>')+4:]
                                    data = d.encode('utf-8')
                                    # continue
                                # else:
                                #     # transcript_file.write(f"| {message_count} | {delta} | | {filter_md(message)} |\n")
                                if tts_engine2:
                                    tts_engine2.setProperty('voice',voice2.id)
                                    speech_text = convert_markdown_to_speech(message,logger,debug=debug)
                                    tts_engine2.say(speech_text)
                                    if debug:
                                        ssml_file2.write(f"\n<!--\n{message}\n-->\n")
                                        ssml_file2.write(f"{speech_text}\n\n")
                                        ssml_file2.flush()
                                    tts_engine2.runAndWait()
                                content2 = html_save_format_message(message) # save this for the transcript at the end of the loop
                            if lang1 != lang2:
                                translation = translate(message, lang2, lang1, logger, debug)
                                html_content_translated = html_save_format_message(translation)
                                if translate_tts2:
                                    translate_tts2.setProperty('voice',translate_voice2.id) # NOTE: Since the languages differ, we need to switch the voice to the target language
                                    ssml_content_translated = convert_markdown_to_speech(translation,logger,debug=debug)
                                    translate_tts2.say(ssml_content_translated)
                                    if debug:
                                        ssml_file2.write(f"\n<!--\n{html_content_translated}\n-->\n")
                                        ssml_file2.write(f"{ssml_content_translated}\n\n")
                                        ssml_file2.flush()
                                    translate_tts2.runAndWait()
                            else:
                                translation = message
                            last_time = datetime.datetime.now()
                            client1.send(translation.encode('utf-8'))

                        if not no_transcript:
                            # Do the actual write to the transcript file
                            logger.debug(f"Writing message to transcript file: {content1} or {content2}")
                            transcript_file.write(f'<tr><td>{message_count}</td><td>{delta:.2f}</td><td>{content1}</td><td>{html_content_translated}</td><td>{content2}</td></tr>\n')
                            transcript_file.flush()
                        if mirror_stdout:
                            print(f"({message_count}) Delta: {delta}s, {persona1 if ready_socket == client1 else persona2}: {message}")
                        
                        message_count += 1
                        if max_messages > 0 and message_count >= max_messages:
                            logger.info(f"Reached max messages: {max_messages}")
                            raise Exception("Max messages reached")
                        
                        if terminate:
                            logger.info("Terminate flag set, terminating...")
                            raise Exception("Terminate flag set")

                    except Exception as e:
                        if str(e) != "Max messages reached":
                            logger.debug(f"Error handling client: {e}")
                            raise
                        else:
                            raise Exception("Max messages reached")

        except Exception as e:
            logger.exception(f"Connection ended: {e}")

        finally:
            if client1:
                try:
                    client1.send(b'/stop\n')
                    logger.info(f"Client1 {addr1[0]}:{addr1[1]} sent: /stop")
                    client1.close()
                except Exception as e:
                    logger.info(f"Client1 already closed: {e}")
                client1 = None
            if client2:
                try:
                    client2.send(b'/stop\n')
                    logger.info(f"Client2 {addr2[0]}:{addr2[1]} sent: /stop")
                    client2.close()
                except Exception as e:
                    logger.info(f"Client2 already closed: {e}")
                client2 = None
            if transcript_file:
                transcript_file.write('</table>\n</body>\n</html>')
                transcript_file.close()
            if tts and ssml_file1:
                ssml_file1.write('\n</voice>\n</speak>\n')
                ssml_file1.close()
            if tts and ssml_file2:
                ssml_file2.write('\n</voice>\n</speak>\n')
                ssml_file2.close()
            server.close()
            
        if not no_transcript:
            logger.info(f"Conversation ended. Transcript saved to {transcript_filename}")
        else:
            logger.info("Conversation ended. No transcript saved.")
        time.sleep(1)

def main():
    global translate_client, translate_config
    # install signal handlers
    signal.signal(signal.SIGINT, signal_handler)

    parser = argparse.ArgumentParser(description='TCP Proxy with transcription')
    parser.add_argument('-m', '--mirror', action='store_true', help='Mirror transcript to stdout')
    parser.add_argument('-M', '--max-messages', type=int, default=10, help='Maximum number of messages to forward (0 for unlimited)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging')
    parser.add_argument('-d', '--debug', action='store_true', help='Enable debugging')
    parser.add_argument('-l', '--logfile', help='Specify a log file')
    parser.add_argument('-c', '--config', default='config/llm_proxy_config.yml', help='Specify a config file')
    parser.add_argument('-t', '--translate_config', default='config/ollama_interpreter.yml', help='Specify a config file')
    parser.add_argument('-H','--host', default='127.0.0.1', help='Specify the host')
    parser.add_argument('-p','--port', type=int, default=18888, help='Specify the port')
    parser.add_argument('-q','--quiet', action='store_true', help='Enable quiet mode with minimal logging')
    parser.add_argument('-n','--no-transcript', action='store_true', help='Omit writing a transcript file')
    parser.add_argument("-V","--version", action="store_true", help="print version information, then quit")
    parser.add_argument("-s","--tts", action="store_true", help="Enable text-to-speech output")
    args = parser.parse_args()

    if args.version:
        print(f"Ollama Agent ({sys.argv[0]}) {__version__}")
        exit(0)

    try:
        with open(args.config, 'r') as config_file:
            config = yaml.safe_load(config_file)
    except FileNotFoundError:
        config = {'proxy': {}}

    config['proxy']['mirror'] = args.mirror
    config['proxy']['max_messages'] = args.max_messages
    config['proxy']['verbose'] = args.verbose
    config['proxy']['logfile'] = args.logfile
    config['proxy']['host'] = args.host
    config['proxy']['port'] = args.port
    config['proxy']['no_transcript'] = args.no_transcript

    if args.quiet:
        log_level = logging.WARNING
    elif args.verbose:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    if config['proxy'].get('logfile'):
        logging.basicConfig(filename=config['proxy']['logfile'], level=log_level, format=log_format)
    else:
        logging.basicConfig(level=log_level, format=log_format)
    logger = logging.getLogger('tcp_proxy')

    translate_config = load_config(args.translate_config)

    translate_client = ollama.Client(host=translate_config.get('host', 'http://localhost:11434'))

    start_proxy(config, config['proxy'].get('mirror', False), config['proxy'].get('max_messages', 10), logger, config['proxy'].get('no_transcript', False), args.debug, args.tts)

if __name__ == "__main__":
    main()
