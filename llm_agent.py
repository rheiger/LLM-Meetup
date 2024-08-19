import argparse
import yaml
import importlib
import sys

def load_config(config_file):
    with open(config_file, 'r') as file:
        config = yaml.safe_load(file)
    return config

def main():
    parser = argparse.ArgumentParser(description="LLM Agent Selector")
    parser.add_argument("prompt_file", help="Markdown file containing the system prompt")
    parser.add_argument("-c", "--config", default="config/agent.yml", help="YAML configuration file")
    parser.add_argument("-s", "--service", choices=["lmstudio", "openai", "ollama", "anthropic"], help="Select the service to use")
    parser.add_argument("-H", "--host", default="127.0.0.1", help="TCP server host")
    parser.add_argument("-p", "--port", type=int, default=18888, help="TCP server port")
    
    # Parse known args to handle service-specific arguments
    args, unknown = parser.parse_known_args()

    config = load_config(args.config)

    if args.service and args.config == "config/agent.yml":
        args.config = (f"config/{args.service}.yml")

    if not args.service:
        args.service = config.get('Agent', {}).get('service')
    
    if not args.service:
        parser.error("Service must be specified either in the config file or as a command-line argument")

    # Import the appropriate agent module
    agent_module = importlib.import_module(f"{args.service}_agent")

    # Prepare arguments for the agent
    agent_args = [args.prompt_file, "-c", args.config, "-H", args.host, "-p", str(args.port)] + unknown
    # Run the agent's main function
    sys.argv = [sys.argv[0]] + agent_args
    agent_module.main()

if __name__ == "__main__":
    main()