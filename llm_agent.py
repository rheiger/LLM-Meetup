import argparse
import yaml
import importlib
import sys

__version__ = "v0.0.2 (build: 33) by rheiger@icloud.com on 2024-08-22 15:17:17"

def load_config(config_file):
    with open(config_file, 'r') as file:
        config = yaml.safe_load(file)
    return config

def main():
    parser = argparse.ArgumentParser(description="LLM Agent Selector")
    parser.add_argument("prompt_file", nargs="?", help="Markdown file containing the system prompt")
    parser.add_argument("-c", "--config", default="config/agent.yml", help="YAML configuration file")
    parser.add_argument("-s", "--service", choices=["lmstudio", "openai", "ollama", "anthropic"], help="Select the service to use")
    parser.add_argument("-H", "--host", default="127.0.0.1", help="TCP server host")
    parser.add_argument("-p", "--port", type=int, default=18888, help="TCP server port")
    parser.add_argument("-l","--logfile", help="Log file path")
    parser.add_argument("-v","--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("-q","--quiet", action="store_true", help="Enable quiet mode with minimal logging")
    parser.add_argument("-V","--version", action="store_true", help="print version information, then quit")
    
    # Parse known args to handle service-specific arguments
    args, unknown = parser.parse_known_args()

    config = load_config(args.config)

    if args.version:
        print(f"Ollama Agent ({sys.argv[0]}) {__version__}")
        exit(0)

    if not args.prompt_file:
        parser.error("prompt_file is required unless --version is specified")

    if args.service and args.config == "config/agent.yml":
        args.config = (f"config/{args.service}.yml")

    if not args.service:
        args.service = config.get('Agent', {}).get('service')
    
    if not args.service:
        parser.error("Service must be specified either in the config file or as a command-line argument")

    # Import the appropriate agent module
    agent_module = importlib.import_module(f"{args.service}_agent")

    # Prepare arguments for the agent
    agent_args = [args.prompt_file, "-c", args.config, "-H", args.host, "-p", str(args.port)]
    if args.verbose:
        agent_args.append("-v")
    if args.quiet:
        agent_args.append("-q")
    if args.logfile:
        agent_args.extend(["-l", args.logfile])
    agent_args.extend(unknown)
    # Run the agent's main function
    sys.argv = [sys.argv[0]] + agent_args
    agent_module.main()

if __name__ == "__main__":
    main()