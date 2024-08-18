import argparse
import yaml
from typing import Dict, Any, List
import socket
import ollama
from typing import Tuple

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

def handle_client(s: socket.socket, ollama_client: ollama.Client, config: Dict[str, Any], system_prompt: str, persona_name: str) -> None:
    """Handle client connections and process requests."""
    # Send persona name to proxy
    s.sendall(f"/iam: {persona_name} (Ollama)\n".encode('utf-8'))
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
            response = ollama_client.chat(
                model=config['model'],
                messages=chat_history,
                stream=False,
                options={
                    "temperature": config.get('temperature', 0.7),
                    "top_p": config.get('top_p', 1.0),
                    "top_k": config.get('top_k', 40),
                }
            )
            reply = response['message']['content'].encode('utf-8').strip() + b'\n'
            chat_history.append({"role": "assistant", "content": response['message']['content']})
            print(f"Reply with '{reply}'\n"
                  f"{response['prompt_eval_count']} tokens in {round(response['prompt_eval_duration']/1e9, 2)} seconds, "
                  f"{response['eval_count']} tokens out, total duration= {round(response['total_duration']/1e9, 2)} seconds")
            s.sendall(reply)
        except (socket.error, ollama.ResponseError) as e:
            print(f"Error: {e}")
            break

def main():
    parser = argparse.ArgumentParser(description="Ollama LLM TCP Server")
    parser.add_argument("prompt_file", help="Markdown file containing the system prompt")
    parser.add_argument("-c", "--config", default="ollama.yml", help="YAML configuration file")
    parser.add_argument("-H", "--host", default="127.0.0.1", help="TCP server host")
    parser.add_argument("-p", "--port", type=int, default=18888, help="TCP server port")
    args = parser.parse_args()

    config = load_config(args.config)
    system_prompt, persona_name = load_system_prompt(args.prompt_file)

    ollama_client = ollama.Client(host=config.get('host', 'http://localhost:11434'))
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.connect((args.host, args.port))
            print(f"Connected to {args.host}:{args.port}")
            handle_client(s, ollama_client, config, system_prompt, persona_name)
        except socket.error as e:
            print(f"Socket error: {e}")

if __name__ == "__main__":
    main()