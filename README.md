# LLM-Meetup
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![CI](https://github.com/LLM-Meetup/LLM-Meetup/actions/workflows/ci.yml/badge.svg)](https://github.com/LLM-Meetup/LLM-Meetup/actions/workflows/ci.yml)

LLM-Meetup lets two LLMs with configurable personas converse through a simple proxy, making it easy to experiment with automated conversations.

## Features
- Connects two LLMs through a proxy to explore automated dialogues
- Supports OpenAI, Anthropic, Ollama, and LM Studio
- Personas defined in Markdown files
- Transcripts written in Markdown and HTML with optional speech output
- Optional translation of conversations
- Docker deployment via `docker-compose`

## Quick Start

### Local
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# start proxy
python llm_proxy.py --mirror

# run two services in separate terminals
python openai_service.py personas/youngsheldon.md --host localhost --port 18888
python anthropic_service.py personas/psychotherapist.md --host localhost --port 19999
```

### Docker
`docker-compose` reads settings from a `.env` file. Copy `env.example` to `.env` and customize the values, then start the stack:

```bash
docker-compose up --build -d

# in separate terminals run services inside the container
docker-compose exec llm_meetup python openai_service.py personas/einstein_en.md --host llm_meetup --port ${LLM_PROXY_PORT}
docker-compose exec llm_meetup python anthropic_service.py personas/psychotherapist.md --host llm_meetup --port ${LLM_PROXY_PORT}
```

## Configuration
Services read default configuration from environment variables before parsing command line options. Create a `.env` file (see `env.example`) to set values:

| Variable | Purpose |
| --- | --- |
| `LLM_PROXY_HOST` | Host where the proxy listens and where services connect |
| `LLM_PROXY_PORT` | Port used by the proxy and the default for services |
| `OPENAI_API_KEY` | API key for OpenAI and translation |
| `OPENAI_MODEL` | Default model for the OpenAI service |
| `OPENAI_API_BASE` | Optional base URL for the OpenAI API |
| `ANTHROPIC_API_KEY` | API key for the Anthropic service |
| `ANTHROPIC_MODEL` | Default model for the Anthropic service |
| `OLLAMA_MODEL` | Default model for the Ollama service |
| `OLLAMA_API_HOST` | URL of the Ollama API server |
| `LMSTUDIO_MODEL` | Default model for the LM Studio service |
| `LMSTUDIO_API_BASE` | Base URL for the LM Studio server |
| `TRAFFIC_DOMAIN` | Domain used for Traefik routing with docker-compose |

## Personas
Example personas live in the `personas` directory. Use them like:

```bash
python llm_proxy.py --mirror
python ollama_service.py personas/youngsheldon.md --host localhost --port 18888
python lmstudio_service.py personas/psychotherapist.md --host localhost --port 19999
```

### General structure of persona files
Persona descriptions are Markdown files. The main title is a short description and the name, separated by a colon:

```markdown
# Theoretical Physicist Persona: Dr. Sheldon Cooper
```

Then follow instructions and background information along with interaction guidelines and control messages (`/start`, `/help`, `/stop`, `/bye`, `/end`). Finish with a behavior note.

## Development
Contributions are welcome. See the [contribution guidelines](.github/CONTRIBUTING.md) for details.

## What's new
- Transcripts are written in tabular Markdown files, making it easier to follow the conversation.
- Added a few more personas.
- Added a single entry script that chooses the service script through option `-s {anthropic|lmstudio|ollama|openai}` or by specifying a config file:
  ```bash
  python llm_service_caller.py -c config/ollama.yml personas/youngsheldon.md
  ```
  or
  ```bash
  python llm_service_caller.py -s ollama personas/youngsheldon.md
  ```
- Added option `-n` to `llm_proxy.py` to suppress creation of transcript files (useful for testing).
- Experimented with context window overflow handling in `ollama_agent.py`.
- `llm_proxy` writes transcripts to an HTML file in tabular format.
- `llm_proxy` can optionally speak the conversation aloud.

### Notes for the speech feature
This has only been tested on a Mac. It uses voices provided by macOS. You need to install voices for the languages and gender you intend to use. Be aware that adding speech slows down the conversation.

## Outlook
There will be more to come. Feedback is welcome.

### Roadmap
- Expand the web UI so conversations can be configured and controlled when running in containers.

#### Version and last edited
This is version: v0.5.1 (build: 61) by rheiger@icloud.com on 2024-08-29 13:58:46

##### Build comments
Added translation to conversation
Implemented translation into `llm_proxy`, fixed to using OpenAI API, which is also accessible for LM Studio and probably Ollama

