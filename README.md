# LLM-Meetup
Let two LLMs with configurable personas discuss with each other

## Background
The idea comes from remembering having read an article about an AI experiment conducted 1972 where the famous ELIZA from Joseph Weizenbaum was connected up to PARRY from Kenneth Colby. The idea was to have a conversation between two ELIZA's. Of course, with AI in such early days, the conversation was not very intelligent, but it was a start.
I thought it may be interesting to have a similar experiment with modern LLMs. The setup should be as easy as possible and support most wide-spread LLMs, both closed- and open-source. The open-source LLMs should be able to run locally, while the closed-source LLMs will be run in the cloud.

## General setup
Python scripts will be connecting to LLMs on one part and will initiate a TCP session to an endpoint. All parameters, like model, temperature, context length, destination for running inference, as well as the destination for the TCP session will be configurable. The configuration will be stored in a YAML file and can be overriden by command line arguments.
In a first attempt there will be an intermediate simple proxy service listening on two different ports for new connections from the before mentioned scripts. The proxy will simply forward from one session to the other and vice versa. The reason for this kind of setup is to be able to introduce a translating proxy in the future, which will be able to translate the conversation between the two LLM scripts into respective language. Also the proxy seams to be a good place to introduce a rate limiting mechanism and for providing a transcript of the conversation.
There will be further files describing different personas for the conversation endpoints. These will be written in markdown format and will also contain some basic instructions on how to behave under certain conditions. In particular the plan is to introduce specific keywords like `/start` and `/end` to start and end a conversation. 

## Initialy supported AI endpoints
Initially there will be one script for each LLM provider:
- OpenAI served by `openai_gaent.py`
- Anthropic served by `anthropic_agent.py`
- Ollama served by `ollama_agent.py`
- LM Studio served by `lmstudio_agent.py`

The proxy script will be `llm-proxy.py`

## Installaion
This is pretty simple to install. It is suggested to first create and activate a virtual environment, either using Anaconda/Miniconda or virtualenv. Then run `pip install -r requirements.txt` to install all required packages.

## Usage
Start the llm-proxy.py script first, then start two llmm-agents.py scripts. The proxy will listen on port 18888 and 19999 for new connections. The agents will connect to the proxy on port 18888 and 19999. The agents will connect to the proxy on port 18888 and 19999. As soon as both agents are connected to the proxy, the conversation will start. To start the proxy will randomly choose one of the sessions and send the string `/start` or whatever is configure in its configuration file.

### Personas
To give you a kick start there are some example personas in the `personas` directory that you can use by specifying them like this:
```
python llm_proxy.py --mirror # This will mirror the conversation to the console. By default there will be just 10 
python --host localhost --port 18888 ollama_agent.py personas/youngsheldon.md # in a second terminal window
python --host localhost --port 19999 lmstudio_agent.py personas/psychotherapist.md # in a in a third terminal window

```
## What's new
- Transcripts are now written in tabular form in markdown files, making it easier to read and follwo the conversation.
- Added a few more personas to play with
- Added a single entry script, which chooses the corresponding service script either through option `-s {anthropic|lmstudio|ollama|openai}` or by specifying a config file suited for a specific service:
```
python llm_agent.py -c config/ollama.yml personas/youngsheldon.md
```
or
```
python llm_agent.py -s ollama personas/youngsheldon.md
```


## Outlook
There will be more to come. But for now I will concentrate on the initial setup.

#### Version and last edited
This is version v0.2.1 (build: 2) by rheiger@icloud.com on 2024-08-19 16:49:59