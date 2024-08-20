import re
from datetime import datetime

def extract_name(filename):
    match = re.search(r'_([^_]+)\.txt', filename)
    return match.group(1) if match else "Unknown"

def parse_message(lines):
    header = lines[0]
    match = re.match(r'### (\d+) ### ([\d.]+) ###: (.+)', header)
    if match:
        count = int(match.group(1))
        delta = float(match.group(2))
        content = match.group(3) + '\n' + '\n'.join(lines[1:])
        return count, delta, content
    return None

def read_transcript(filename):
    with open(filename, 'r') as file:
        lines = file.readlines()
        messages = []
        current_message = []
        for line in lines:
            if line.startswith('### '):
                if current_message:
                    messages.append(parse_message(current_message))
                current_message = [line.strip()]
            else:
                current_message.append(line.strip())
        if current_message:
            messages.append(parse_message(current_message))
        return [msg for msg in messages if msg]

def combine_transcripts(file1, file2):
    name1 = extract_name(file1)
    name2 = extract_name(file2)
    
    transcript1 = read_transcript(file1)
    transcript2 = read_transcript(file2)
    
    combined = []
    i, j = 0, 0
    while i < len(transcript1) or j < len(transcript2):
        if i < len(transcript1) and (j == len(transcript2) or transcript1[i][0] <= transcript2[j][0]):
            combined.append((transcript1[i], None))
            i += 1
        else:
            combined.append((None, transcript2[j]))
            j += 1
    
    return name1, name2, combined

def format_message(message, debug=False):
    if debug and message:
        print(f"message='{message}'")
        print(f"message[2]='{message[2]}'")
    if message:
        content = message[2]
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

def write_combined_html(output_file, name1, name2, combined):
    with open(output_file, 'w') as file:
        file.write('<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="UTF-8">\n<meta name="viewport" content="width=device-width, initial-scale=1.0">\n<title>Transcript</title>\n<style>\n')
        file.write('table { border-collapse: collapse; width: 100%; }\n')
        file.write('th, td { border: 1px solid black; padding: 8px; text-align: left; }\n')
        file.write('th { background-color: #f2f2f2; }\n')
        file.write('</style>\n</head>\n<body>\n')
        file.write('<table>\n')
        file.write(f'<tr><th>Count</th><th>Delta</th><th>{name1}</th><th>{name2}</th></tr>\n')
        
        for msg1, msg2 in combined:
            count = msg1[0] if msg1 else msg2[0]
            delta = msg1[1] if msg1 else msg2[1]
            debug = count == 27
            content1 = format_message(msg1,debug)
            content2 = format_message(msg2,debug)
            
            file.write(f'<tr><td>{count}</td><td>{delta:.2f}</td><td>{content1}</td><td>{content2}</td></tr>\n')
        
        file.write('</table>\n</body>\n</html>')

import argparse
import glob
import os
import re
from datetime import datetime

def find_matching_transcripts(spec=None):
    all_transcripts = glob.glob("transcript_*.txt")
    matching_pairs = []

    for transcript in all_transcripts:
        match = re.search(r'transcript_(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}).*_(.+)\.txt', transcript)
        if match:
            timestamp, participant = match.groups()
            if not spec or spec.lower() in timestamp.lower() or spec.lower() in participant.lower():
                matching_pairs.append((timestamp, participant, transcript))

    matching_pairs.sort(key=lambda x: x[0], reverse=True)
    grouped_pairs = {}
    for timestamp, participant, transcript in matching_pairs:
        if timestamp not in grouped_pairs:
            grouped_pairs[timestamp] = []
        grouped_pairs[timestamp].append((participant, transcript))

    for timestamp, transcripts in grouped_pairs.items():
        if len(transcripts) == 2:
            return timestamp, transcripts[0][0], transcripts[1][0], transcripts[0][1], transcripts[1][1]

    return None

def main():
    parser = argparse.ArgumentParser(description="Combine LLM conversation transcripts")
    parser.add_argument("spec", nargs='?', help="Specify transcript files by time or name (e.g., 22:11:14 or tesla)")
    args = parser.parse_args()

    result = find_matching_transcripts(args.spec)
    if not result:
        print("No matching transcript files found.")
        return

    timestamp, name1, name2, file1, file2 = result
    output_file = f"combined_transcript_{timestamp}_{name1}---{name2}.html"

    name1, name2, combined = combine_transcripts(file1, file2)
    write_combined_html(output_file, name1, name2, combined)
    print(f"Combined transcript written to {output_file}")

if __name__ == "__main__":
    main()