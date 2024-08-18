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
- OpenAI served by `openai_gaent.py``
- Anthropic served by `anthropic_agent.py`
- Ollama served by `ollama_agent.py`
- LM Studio served by `lmstudio_agent.py`

The proxy script will be `llm-proxy.py`

## Outlook
There will be more to come. But for now I will concentrate on the initial setup.

#### Version and last edited
This is version v0.0.1 (build: 2) by rheiger@icloud.com on 2024-08-18 16:41:12