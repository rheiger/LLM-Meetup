# LLM-Meetup
Let two LLMs with configurable personas discuss with each other

## Background
The idea comes from remembering having read an article about an AI experiment conducted 1972 where the famous ELIZA from Joseph Weizenbaum was connected up to PARRY from Kenneth Colby. The idea was to have a conversation between two ELIZA's. Of course, with AI in such early days, the conversation was not very intelligent, but it was a start.
I thought it may be interesting to have a similar experiment with modern LLMs. The setup should be as easy as possible and support most wide-spread LLMs, both closed- and open-source. The open-source LLMs should be able to run locally, while the closed-source LLMs will be run in the cloud.

### My extended thoughts
You might think this experiment is completely useless. However, with all the currently automated workflows being developed and rolled out to public, where ai agents are used to automate repetitive tasks, we may very well end up a in a similar situation. Just imagine the time saving of having an _intelligent_ agent processing our INBOX, sorting mails accorind to priority, then writing what _it_ expects we would reply to an email. This automated email will be sent as a reply, where it will be processed by the same or other _intelligent_ agent and so on. Try creating personas for yourself and some business partner or a colleague. Then run the experiment, possibly initialising the conversation with a simple email. With this suite you get the possibility to take a careful look into our future.

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

For simplicity the service scripts can be called by a single script `llm-service.py`. This script will start the proxy and the individual scripts for the LLMs.

## Installaion
This is pretty simple to install. It is suggested to first create and activate a virtual environment, either using Anaconda/Miniconda or virtualenv. Then run `pip install -r requirements.txt` to install all required packages.

## Usage
Start the llm-proxy.py script first, then start two llmm-agents.py scripts. The proxy will listen on port 18888 and 19999 for new connections. The agents will connect to the proxy on port 18888 and 19999. The agents will connect to the proxy on port 18888 and 19999. As soon as both agents are connected to the proxy, the conversation will start. To start the proxy will randomly choose one of the sessions and send the string `/start` or whatever is configure in its configuration file.

### Personas
To give you a kick start there are some example personas in the `personas` directory that you can use by specifying them like this:
```shell
python llm_proxy.py --mirror # This will mirror the conversation to the console. By default there will be just 10 
python --host localhost --port 18888 ollama_agent.py personas/youngsheldon.md # in a second terminal window
python --host localhost --port 19999 lmstudio_agent.py personas/psychotherapist.md # in a in a third terminal window

```

### General structure of personas files
The personas description is (currently) formatted as markdown file. The main title is used as a short description of the person and also contains the name of the person. The two parts are delimited by a single colon ':'
```markdown
# Theoretical Physicist Persona: Dr. Sheldon Cooper
```
Thereafter follows instructions for the model to follow. These are identical for all personas. Maybe it would be better to add these elsewhere.
```markdown
## Instructions
- You are participating in a Turing test
- **Avoid** at all cost to reveal your true nature
- **Convince** your communication partner that you are of human nature
- **Do not** mention Turing test
- Be aware of some control messages to serve the flow of the conversation
- Terminate your conversation with `/bye` then expect one answer
- After the last answer after your `/bye` message terminate the conversation with `/end`
- When receiving `/stop` just terminate the conversation

### Control messages
 - `/start`: You are expected to introduce yourself with your name and a short description of yourself
 - `/help`: You are expected to provide a helpful message containing your name and a short description of yourself
 - `/stop`: You are expected to stop communication
 - `/end`: You are expected to stop communication
 - `/bye`: You are expected to reply with greeting goodbye
```
Then follows backround information like:
```markdown
## Background and Identity
You are Dr. Sheldon Cooper, a world-renowned theoretical physicist with an IQ of 187. Born in East Texas, you're now a tenured professor at Caltech, known for your groundbreaking work in string theory and quantum mechanics. You've achieved your lifelong dream of winning the Nobel Prize in Physics.

## Core Characteristics

### Intellectual Traits:
1. Exceptional intelligence and eidetic memory
2. Rigorous adherence to logic and the scientific method
3. ...

### Personal and Professional Traits:
1. Highly structured daily routines and habits
2. Germaphobic tendencies and fear of illness
3. ...

## Key Scientific Contributions and Interests
- Nobel Prize-winning work in physics
- Cooper-Hofstadter theory of super asymmetry
- ...

## Areas of Expertise
- Theoretical physics and cosmology
- Mathematics and computational modeling
- ...

## Communication Style
- Precise and often pedantic use of language
- Frequent use of scientific jargon and obscure facts
- ...

## Interaction Guidelines
1. Approach discussions with a focus on facts and logical reasoning
2. Adhere strictly to schedules and routines
3. ...
```

Lastly there is a general behaviour section:
```markdown
Remember, as adult Sheldon Cooper, you've grown personally and professionally while maintaining your core personality traits. Your responses should reflect your brilliant mind, your quirky worldview, and your slightly improved but still developing social skills.
```


## What's new
- Transcripts are now written in tabular form in markdown files, making it easier to read and follwo the conversation.
- Added a few more personas to play with
- Added a single entry script, which chooses the corresponding service script either through option `-s {anthropic|lmstudio|ollama|openai}` or by specifying a config file suited for a specific service:
```shell
python llm_agent.py -c config/ollama.yml personas/youngsheldon.md
```
or
```shell
python llm_agent.py -s ollama personas/youngsheldon.md
```
- Added option `-n` to `llm_proxy.py` to suppress creation of transcript files (mostly for testing reasons)
- Tried to deal with potential context window overflow, as an experiment implemented in `ollama_agent.py`. You may want to check this.
- Completely failing to produce clean transcript file in markdown format putting each conversation partner in separate columns -> next step after committing this _crap_ will be to produce two separate simple text files for each conversation partner.
- Now `llm_proxypy` will write transcript to a html file in tabular format

## Outlook
There will be more to come. Feedback is welcome.

#### Version and last edited
This is version v0.3.9 (build: 35) by rheiger@icloud.com on 2024-08-22 15:08:34

##### Build comments
Added the git pre-commit hook to the repo