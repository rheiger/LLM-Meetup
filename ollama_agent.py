import argparse
import yaml
from typing import Dict, Any, List
import socket
import ollama
from typing import Tuple
import logging
import json 
import random
import sys

__version__ = "This is version v0.4.3 (build: 41) by rheiger@icloud.com on 2024-08-23 03:27:52"

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
    to_remove = 0
    start_index = 0
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

    return chat_history, start_index, to_remove

def filter_md(s: str) -> str:
    """Escape markdown instructions from a string."""
    # s = s.replace('*', r'\*')
    # s = s.replace('_', r'\_')
    # s = s.replace('`', r'\`')
    # s = s.replace('#', r'\#')
    # s = s.replace('-', r'\-')
    # s = s.replace('>', r'\>')
    # s = s.replace('+', r'\+')
    # s = s.replace('=', r'\=')
    # s = s.replace('|', r'\|')
    # s = s.replace('[', r'\[')
    # s = s.replace(']', r'\]')
    # s = s.replace('(', r'\(')
    # s = s.replace(')', r'\)')
    # s = s.replace('!', r'\!')
    return s

def handle_client(s: socket.socket, ollama_client: ollama.Client, config: Dict[str, Any], system_prompt: str, persona_name: str, quiet: bool) -> None:
    """Handle client connections and process requests."""
    # Send persona name to proxy
    s.sendall(f"/iam: {persona_name}.{config['model']}\n".encode('utf-8'))

    chat_history: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
    max_bytes = config['max_tokens'] * 30 + 1024 if 'max_tokens' in config else 32768 # Estimate 6 bytes per character (safe for UTF-8)
    # max_bytes = 8192 # WARNING AND TODO: Tis is just for testing truncation of chat history without having to wait too long
    keep_looping = True
    while keep_looping:
        try:
            data = s.recv(max_bytes+2048).decode('utf-8').strip()
            logging.debug(f"Received: '{data}'")
            if not data:
                logging.warning("Received empty data, closing connection")
                break
            if not quiet:
                print(f"Received: '{data}'\n---")
            if data.lower().startswith("/end") or data.lower().endswith("/end"):
                logging.info(f"Received /end, closing connection ({data})")
                if s.fileno() != -1:
                    s.sendall("/end".encode('utf-8'))
                else:
                    logging.warning("Socket is already closed, could not send /end")
                break
            if data.lower().startswith("/help") or data.lower().endswith("/help"):
                logging.warning(f"Received /help, don't know what to do ({data})")
            if any(data.lower().startswith(cmd) for cmd in {"/stop", "/quit", "/exit"}) or any(data.lower().endswith(cmd) for cmd in {"/stop", "/quit", "/exit"}):
                logging.info(f"Received stop command ({data}), closing connection")
                break
            if data.lower().startswith("/bye") or data.lower().endswith("/bye"):
                logging.warning(f"Received /bye, Finishing the conversation ({data})")

            # Needed to keep context for ollama
            chat_history.append({"role": "user", "content": data})

            byte_size = get_byte_size(chat_history)
            if byte_size > max_bytes - 1024:
                logging.warning(f"Chat history is too long {len(chat_history)} ({byte_size} bytes), truncating")
                chat_history, start_index, to_remove = truncate_middle(chat_history)
                prefix = f"/truncated: {to_remove} messages starting at {start_index}<br>"
            else:
                logging.debug(f"Chat history is {len(chat_history)} messages ({byte_size} bytes of max {max_bytes} bytes)")
                prefix = ""

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
            reply = response['message']['content'].strip()
            if not quiet:
                print(f"Inferred: {reply}\n================\n")
            chat_history.append({"role": "assistant", "content": response['message']['content']})
            logging.debug(f"{response['prompt_eval_count']} input tokens evaluated in {round(response['prompt_eval_duration']/1e9, 3)} seconds {round(1e9 * float(response['prompt_eval_count']) / response['prompt_eval_duration'], 3)} tokens/sec, "
                  f"{response['eval_count']} output tokens evaluated in {round(response['total_duration']/1e9, 3)} seconds {round(1e9 * float(response['eval_count']) / response['total_duration'], 3)} tokens/sec")

            # Now send what the LLM created as reply
            msg = f"{prefix}{filter_md(response['message']['content'])}"
            s.sendall(msg.encode('utf-8'))
        except (socket.error, ollama.ResponseError) as e:
            logging.exception(f"Error: {e}")
            break
    if not keep_looping:
        logging.info(f"Terminating conversation after receiving /by, closing connection ({s})")
        if s.fileno() != -1:
            s.sendall("/end".encode('utf-8'))
        else:
            logging.warning("Socket is already closed, could not send /end")


def main():
    parser = argparse.ArgumentParser(description="Ollama LLM TCP Server")
    parser.add_argument("prompt_file", nargs='?', help="Markdown file containing the system prompt")
    parser.add_argument("-c", "--config", default="config/ollama.yml", help="YAML configuration file")
    parser.add_argument("-H", "--host", default="127.0.0.1", help="TCP server host")
    parser.add_argument("-p", "--port", type=int, default=18888, help="TCP server port")
    parser.add_argument("-l","--logfile", help="Log file path")
    parser.add_argument("-v","--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("-q","--quiet", action="store_true", help="Enable quiet mode with minimal logging")
    parser.add_argument("-V","--version", action="store_true", help="print version information, then quit")
    args = parser.parse_args()

    if args.version:
        print(f"Ollama Agent ({sys.argv[0]}) {__version__}")
        exit(0)

    if not args.prompt_file:
        parser.error("prompt_file is required unless --version is specified")
    
    if args.quiet:
        log_level = logging.WARNING
    elif args.verbose:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    logging.basicConfig(filename=args.logfile, level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')

    logging.getLogger("httpx").setLevel(logging.WARNING)

    config = load_config(args.config)

    system_prompt, persona_name = load_system_prompt(args.prompt_file)

    ollama_client = ollama.Client(host=config.get('host', 'http://localhost:11434'))
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.connect((args.host, args.port))
            logging.info(f"Connected to {args.host}:{args.port}")
            handle_client(s, ollama_client, config, system_prompt, persona_name, args.quiet)
        except socket.error as e:
            logging.exception(f"Socket error: {e}")

if __name__ == "__main__":
    main()