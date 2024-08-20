import argparse
import yaml
from typing import Dict, Any, List
import socket
import ollama
from typing import Tuple
import logging
import json 
import random

def load_config(config_file: str) -> Dict[str, Any]:
    """Load configuration from a YAML file."""
    with open(config_file, 'r') as f:
        return yaml.safe_load(f)


def load_system_prompt(prompt_file: str) -> Tuple[str, str]:
    """Load system prompt from a file and extract persona name."""
    with open(prompt_file, 'r') as f:
        content = f.read()
        first_line = content.split('\n')[0]
        persona_name = first_line.split(':')[-1].strip()
        return content, persona_name

def get_byte_size(chat_history):
    # Get the length of the byte data
    byte_size = len(json.dumps(chat_history).encode('utf-8'))    
    return byte_size

def truncate_middle(chat_history: List[Dict[str,str]]):
    """Truncate 10% from random place around the middle of a chat history."""
    logging.debug(f"chat_history has {len(chat_history)} messages")
    logging.debug(f"chat_history has {get_byte_size(chat_history)} bytes")
    logging.debug(f"chat_history[0] is {chat_history[0]}")
    logging.debug(f"chat_history[1] is {chat_history[1]}")
    if len(chat_history) > 2:
        logging.debug(f"chat_history[2] is {chat_history[2]}")
    if len(chat_history) > 4:
        logging.debug(f"chat_history[-1] is {chat_history[-1]}")
    num_messages = len(chat_history)
    to_remove = round(num_messages * 0.2)
    if to_remove % 2 != 0:
        to_remove += 1
    logging.debug(f"Truncating {to_remove} messages from a random place in chat history, ensuring the last element is preserved")
    if to_remove > 0:
        start_index = max(2, random.randrange(2, len(chat_history) - to_remove - 1, 2))
        chat_history = chat_history[:start_index] + chat_history[start_index + to_remove:]
        logging.warning(f"Truncated chat history to {len(chat_history)} messages starting at {start_index} removing {to_remove} messages")

    return chat_history

def handle_client(s: socket.socket, ollama_client: ollama.Client, config: Dict[str, Any], system_prompt: str, persona_name: str) -> None:
    """Handle client connections and process requests."""
    # Send persona name to proxy
    s.sendall(f"/iam: {persona_name}.{config['model']}\n".encode('utf-8'))
    chat_history: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
    max_bytes = config['max_tokens'] * 30 + 1024 if 'max_tokens' in config else 32768 # Estimate 6 bytes per character (safe for UTF-8)
    while True:
        try:
            data = s.recv(max_bytes).decode('utf-8').strip()
            logging.info(f"Received: '{data}'")
            if not data:
                break
            if data.lower() == "/end":
                if s.fileno() != -1:
                    s.sendall("/end".encode('utf-8'))
                break
            if any(data.lower().startswith(cmd) for cmd in {"/stop", "/quit", "/exit"}):
                break
            chat_history.append({"role": "user", "content": data})

            byte_size = get_byte_size(chat_history)
            if byte_size > max_bytes - 1024:
                logging.warning(f"Chat history is too long {len(chat_history)} ({byte_size} bytes), truncating")
                truncate_middle(chat_history)
            response = ollama_client.chat(
                model=config['model'],
                messages=chat_history,
                stream=False,
                options={
                    "temperature": config.get('temperature', 0.7),
                    "top_p": config.get('top_p', 0.9),
                    "top_k": config.get('top_k', 40),
                }
            )
            reply = response['message']['content'].encode('utf-8').strip() + b'\n'
            context = json.dumps(response, indent=2)
            logging.debug(f"Context: {context}")
            chat_history.append({"role": "assistant", "content": response['message']['content']})
            logging.info(f"Reply with '{reply}'\n"
                  f"{response['prompt_eval_count']} input tokens evaluated in {round(response['prompt_eval_duration']/1e9, 3)} seconds, "
                  f"{response['eval_count']} output tokens evaluated in {round(response['total_duration']/1e9, 3)} seconds {round(1e9 * float(response['eval_count']) / response['total_duration'], 3)} tokens/sec")
            s.sendall(reply)
        except (socket.error, ollama.ResponseError) as e:
            logging.exception(f"Error: {e}")
            break

def main():
    parser = argparse.ArgumentParser(description="Ollama LLM TCP Server")
    parser.add_argument("prompt_file", help="Markdown file containing the system prompt")
    parser.add_argument("-c", "--config", default="config/ollama.yml", help="YAML configuration file")
    parser.add_argument("-H", "--host", default="127.0.0.1", help="TCP server host")
    parser.add_argument("-p", "--port", type=int, default=18888, help="TCP server port")
    parser.add_argument("-l","--logfile", help="Log file path")
    parser.add_argument("-v","--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("-q","--quiet", action="store_true", help="Enable quiet mode with minimal logging")
    args = parser.parse_args()

    if args.quiet:
        log_level = logging.WARNING
    elif args.verbose:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    logging.basicConfig(filename=args.logfile, level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')

    config = load_config(args.config)

    system_prompt, persona_name = load_system_prompt(args.prompt_file)

    ollama_client = ollama.Client(host=config.get('host', 'http://localhost:11434'))
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.connect((args.host, args.port))
            logging.info(f"Connected to {args.host}:{args.port}")
            handle_client(s, ollama_client, config, system_prompt, persona_name)
        except socket.error as e:
            logging.exception(f"Socket error: {e}")

if __name__ == "__main__":
    main()