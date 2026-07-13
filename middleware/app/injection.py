"""Core business logic: system-prompt injection into an OpenAI messages array.

Kept as a pure function with no I/O so it is trivial to unit-test (SRP).
"""

from typing import Any

Message = dict[str, Any]


def prepend_system_prompt(messages: list[Message], prompt: str) -> list[Message]:
    """Return a NEW messages list with our system prompt as the first message.

    - Does not mutate the input list (pure function).
    - If the request already contains system messages (Open WebUI may send one),
      ours still goes first — the assignment requires *prepending*.
    """
    system_message: Message = {"role": "system", "content": prompt}
    return [system_message, *messages]
