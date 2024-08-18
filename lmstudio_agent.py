import argparse
import yaml
from typing import Dict, Any, List
import socket
from openai import OpenAI
from typing import Tuple

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

def handle_client(s: socket.socket, config: Dict[str, Any], system_prompt: str, persona_name: str) -> None:
    # Send persona name to proxy
    s.sendall(f"/iam: {persona_name} (LM Studio)\n".encode('utf-8'))
    
    client = OpenAI(base_url=config['lmstudio_api_base'], api_key="lm-studio")
    chat_history: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]

    while True:
        try:
            data = s.recv(8192).decode('utf-8').strip()
            print(f"Received: '{data}'")
            if not data:
                break
            if data.lower() in {"exit", "quit", "bye"}:
                return

            chat_history.append({"role": "user", "content": data})
            
            completion = client.chat.completions.create(
                model=config['model'],
                messages=chat_history,
                temperature=config.get('temperature', 0.7),
                max_tokens=config.get('max_tokens', 100),
            )
            
            reply = completion.choices[0].message.content.encode('utf-8').strip() + b'\n'
            chat_history.append({"role": "assistant", "content": completion.choices[0].message.content})
            print(f"Reply with '{reply}'\n"
                  f"Total tokens: {completion.usage.total_tokens}")
            s.sendall(reply)
        except Exception as e:
            print(f"Error: {e}")
            break

def main():
    parser = argparse.ArgumentParser(description="LM Studio LLM TCP Server")
    parser.add_argument("prompt_file", help="Markdown file containing the system prompt")
    parser.add_argument("-c", "--config", default="lmstudio.yml", help="YAML configuration file")
    parser.add_argument("-H", "--host", default="127.0.0.1", help="TCP server host")
    parser.add_argument("-p", "--port", type=int, default=18888, help="TCP server port")
    args = parser.parse_args()

    config = load_config(args.config)
    system_prompt, persona_name = load_system_prompt(args.prompt_file)
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.connect((args.host, args.port))
            print(f"Connected to {args.host}:{args.port}")
            handle_client(s, config, system_prompt, persona_name)
        except socket.error as e:
            print(f"Socket error: {e}")

if __name__ == "__main__":
    main()