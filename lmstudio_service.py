import argparse
import yaml
from typing import Dict, Any, List
import socket
from openai import OpenAI
from typing import Tuple
import sys
import logging

__version__ = "This is version v0.4.12 (build: 50) by rheiger@icloud.com on 2024-08-25 22:29:59"

def load_config(config_file: str) -> Dict[str, Any]:
    """Load configuration from a YAML file."""
    with open(config_file, 'r') as f:
        return yaml.safe_load(f)

def load_system_prompt(prompt_file: str) -> Tuple[str, str]:
    with open(prompt_file, 'r') as f:
        content = f.read()
        first_line = content.split('\n')[0]
        persona_name = first_line.split(':')[-1].strip()
        return content, persona_name

def handle_client(s: socket.socket, config: Dict[str, Any], system_prompt: str, persona_name: str, quiet: bool) -> None:
    # Send persona name to proxy
    logging.debug(f"Sending persona name to proxy: {persona_name}.{config['model']}")
    s.sendall(f"/iam: {persona_name}.LMStudio\n".encode('utf-8'))
    
    client = OpenAI(base_url=config['lmstudio_api_base'], api_key="lm-studio")
    chat_history: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]

    msg_count = 0
    max_bytes = config['max_tokens'] * 6 if 'max_tokens' in config else 32768 # Estimate 6 bytes per character (safe for UTF-8)
    keep_looping = True
    while keep_looping:
        try:
            data = s.recv(max_bytes).decode('utf-8').strip()
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
                keep_looping = False
            data = data.replace("/start","Hello") if msg_count == 0 else data.replace("/start",".") # remove the start sequence from the prompt

            chat_history.append({"role": "user", "content": data})
            
            completion = client.chat.completions.create(
                model=config['model'],
                messages=chat_history,
                temperature=config.get('temperature', 0.7),
                max_tokens=config.get('max_tokens', 100),
            )
            
            reply = completion.choices[0].message.content.strip() + '\n'
            chat_history.append({"role": "assistant", "content": completion.choices[0].message.content})
            if not quiet:
                print(f"Inferred: {reply}\n================\n")
            logging.debug(f"Reply with '{reply}'")
            if not keep_looping:
                reply += "/end\n"
            s.sendall(reply.encode('utf-8'))
            msg_count += 1
        except Exception as e:
            logging.exception(f"Error: {e}")
            break
    if not keep_looping:
        logging.info(f"Terminating conversation after receiving /bye, closing connection ({s})")
        if s.fileno() != -1:
            s.sendall("/end".encode('utf-8'))
        else:
            logging.warning("Socket is already closed, could not send /end")

def main():
    parser = argparse.ArgumentParser(description="LM Studio LLM TCP Server")
    parser.add_argument("prompt_file", nargs='?', help="Markdown file containing the system prompt")
    parser.add_argument("-c", "--config", default="config/lmstudio.yml", help="YAML configuration file")
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
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.connect((args.host, args.port))
            logging.info(f"Connected to {args.host}:{args.port}")
            handle_client(s, config, system_prompt, persona_name,args.quiet)
        except socket.error as e:
            logging.exception(f"Socket error: {e}")

if __name__ == "__main__":
    main()