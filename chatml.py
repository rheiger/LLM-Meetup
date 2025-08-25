import re
from typing import List, Dict

START_TOKEN = "<|im_start|>"
END_TOKEN = "<|im_end|>"


def encode(role: str, content: str) -> str:
    """Return a ChatML-formatted string for a single message."""
    content = content.strip()
    return f"{START_TOKEN}{role}\n{content}\n{END_TOKEN}\n"


def decode(stream: str) -> List[Dict[str, str]]:
    """Parse a ChatML-formatted string into a list of messages."""
    pattern = re.compile(r"<\|im_start\|>(\w+)\n(.*?)<\|im_end\|>", re.DOTALL)
    messages = []
    for match in pattern.finditer(stream):
        role, content = match.groups()
        messages.append({"role": role, "content": content.strip()})
    return messages
