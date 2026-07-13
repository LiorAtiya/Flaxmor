"""Tests for the core business logic: prepend_system_prompt (pure function)."""

from app.injection import Message, prepend_system_prompt

PROMPT: str = "You are a structured data extractor."


def test_prompt_is_prepended_first() -> None:
    messages: list[Message] = [{"role": "user", "content": "hello"}]
    result: list[Message] = prepend_system_prompt(messages, PROMPT)

    assert result[0] == {"role": "system", "content": PROMPT}
    assert result[1] == {"role": "user", "content": "hello"}
    assert len(result) == 2


def test_original_order_is_preserved() -> None:
    messages: list[Message] = [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "reply"},
        {"role": "user", "content": "second"},
    ]
    result: list[Message] = prepend_system_prompt(messages, PROMPT)

    assert [m["content"] for m in result] == [PROMPT, "first", "reply", "second"]


def test_existing_system_message_stays_after_ours() -> None:
    """Open WebUI may send its own system message — ours must still come first."""
    messages: list[Message] = [
        {"role": "system", "content": "webui system prompt"},
        {"role": "user", "content": "hi"},
    ]
    result: list[Message] = prepend_system_prompt(messages, PROMPT)

    assert result[0]["content"] == PROMPT
    assert result[1] == {"role": "system", "content": "webui system prompt"}


def test_empty_messages_list() -> None:
    result: list[Message] = prepend_system_prompt([], PROMPT)

    assert result == [{"role": "system", "content": PROMPT}]


def test_input_list_is_not_mutated() -> None:
    """Pure function contract: the caller's list must stay untouched."""
    messages: list[Message] = [{"role": "user", "content": "hi"}]
    original_snapshot: list[Message] = [dict(m) for m in messages]

    prepend_system_prompt(messages, PROMPT)

    assert messages == original_snapshot
    assert len(messages) == 1
