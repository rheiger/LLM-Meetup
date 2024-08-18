import argparse
import yaml
from typing import Dict, Any, List
import socket
from anthropic import Anthropic, HUMAN_PROMPT, AI_PROMPT
from dotenv import load_dotenv
import os
from typing import Tuple

def load_config(config_file: str) -> Dict[str, Any]:
    with open(config_file, 'r') as f:
        return yaml.safe_load(f)

def load_system_prompt(prompt_file: str) -> Tuple[str, str]:
    with open(prompt_file, 'r') as f:
        content = f.read()
        first_line = content.split('\n')[0]
        persona_name = first_line.split(':')[-1].strip()
        return content, persona_name

def handle_client(s: socket.socket, anthropic_client: Anthropic, config: Dict[str, Any], system_prompt: str, persona_name: str) -> None:
    # Send persona name to proxy
    s.sendall(f"/iam: {persona_name}\n".encode('utf-8'))

    while True:
        try:
            data = s.recv(8192).decode('utf-8').strip()
            print(f"Received: '{data}'")
            if not data or data.lower() in {"exit", "quit", "bye"}:
                break

            response = anthropic_client.messages.create(
                model=config['model'],
                system=system_prompt,
                messages=[
                    {"role": "user", "content": data}
                ],
                max_tokens=config.get('max_tokens', 1000),
                temperature=config.get('temperature', 0.7),
            )
            reply = response.content[0].text.encode('utf-8').strip() + b'\n'
            print(f"Reply with '{reply}'")
            s.sendall(reply)
        except Exception as e:
            print(f"Error: {e}")
            break

def main():
    parser = argparse.ArgumentParser(description="Anthropic Claude TCP Server")
    parser.add_argument("prompt_file", help="Markdown file containing the system prompt")
    parser.add_argument("-c", "--config", default="anthropic.yml", help="YAML configuration file")
    parser.add_argument("-H", "--host", default="127.0.0.1", help="TCP server host")
    parser.add_argument("-p", "--port", type=int, default=18888, help="TCP server port")
    args = parser.parse_args()

    config = load_config(args.config)
    system_prompt, persona_name = load_system_prompt(args.prompt_file)

    load_dotenv()  # This will load variables from a .env file if it exists
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not found in environment variables")

    anthropic_client = Anthropic(api_key=api_key)
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.connect((args.host, args.port))
            print(f"Connected to {args.host}:{args.port}")
            handle_client(s, anthropic_client, config, system_prompt, persona_name)
        except socket.error as e:
            print(f"Socket error: {e}")

if __name__ == "__main__":
    main()
