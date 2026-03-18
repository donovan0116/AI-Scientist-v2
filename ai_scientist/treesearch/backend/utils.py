from dataclasses import dataclass

import jsonschema
from dataclasses_json import DataClassJsonMixin

PromptType = str | dict | list
FunctionCallType = dict
OutputType = str | FunctionCallType


import backoff
import logging
from typing import Callable

logger = logging.getLogger("ai-scientist")

# Store last exception reason for on_backoff callback (backoff retries on falsy return)
_last_backoff_reason: list[str] = [""]


def _log_backoff_reason(details: dict) -> None:
    """Log the actual error that caused this backoff (so it appears next to 'Backing off ...')."""
    reason = _last_backoff_reason[0]
    if reason:
        logger.warning(
            "Backing off backoff_create(...) — connection/API error reason: %s",
            reason,
        )


@backoff.on_predicate(
    wait_gen=backoff.expo,
    max_value=60,
    factor=1.5,
    on_backoff=_log_backoff_reason,
)
def backoff_create(
    create_fn: Callable, retry_exceptions: list[Exception], *args, **kwargs
):
    _last_backoff_reason[0] = ""
    try:
        return create_fn(*args, **kwargs)
    except retry_exceptions as e:
        # Build a clear reason string (include status code for API errors if available)
        reason_parts = [f"{type(e).__name__}: {e!s}"]
        if getattr(e, "status_code", None) is not None:
            reason_parts.append(f"HTTP status={e.status_code}")
        if getattr(e, "response", None) is not None:
            body = getattr(e.response, "text", None) or getattr(e.response, "body", None)
            if body and len(str(body)) < 500:
                reason_parts.append(f"response={body!s}")
        _last_backoff_reason[0] = " ".join(reason_parts)
        logger.info("Backoff exception: %s", e)
        return False


def opt_messages_to_list(
    system_message: str | None, user_message: str | None
) -> list[dict[str, str]]:
    messages = []
    if system_message:
        messages.append({"role": "system", "content": system_message})
    if user_message:
        messages.append({"role": "user", "content": user_message})
    return messages


def compile_prompt_to_md(prompt: PromptType, _header_depth: int = 1) -> str:
    """Convert a prompt into markdown format"""
    try:
        logger.debug(f"compile_prompt_to_md input: type={type(prompt)}")
        if isinstance(prompt, (list, dict)):
            logger.debug(f"prompt content: {prompt}")

        if prompt is None:
            return ""

        if isinstance(prompt, str):
            return prompt.strip() + "\n"

        if isinstance(prompt, list):
            # Handle empty list case
            if not prompt:
                return ""
            # Special handling for multi-modal messages
            if all(isinstance(item, dict) and "type" in item for item in prompt):
                # For multi-modal messages, just pass through without modification
                return prompt

            try:
                result = "\n".join([f"- {s.strip()}" for s in prompt] + ["\n"])
                return result
            except Exception as e:
                logger.error(f"Error processing list items: {e}")
                logger.error("List contents:")
                for i, item in enumerate(prompt):
                    logger.error(f"  Item {i}: type={type(item)}, value={item}")
                raise

        if isinstance(prompt, dict):
            # Check if this is a single multi-modal message
            if "type" in prompt:
                return prompt

            # Regular dict processing
            try:
                out = []
                header_prefix = "#" * _header_depth
                for k, v in prompt.items():
                    logger.debug(f"Processing dict key: {k}")
                    out.append(f"{header_prefix} {k}\n")
                    out.append(compile_prompt_to_md(v, _header_depth=_header_depth + 1))
                return "\n".join(out)
            except Exception as e:
                logger.error(f"Error processing dict: {e}")
                logger.error(f"Dict contents: {prompt}")
                raise

        raise ValueError(f"Unsupported prompt type: {type(prompt)}")

    except Exception as e:
        logger.error("Error in compile_prompt_to_md:")
        logger.error(f"Input type: {type(prompt)}")
        logger.error(f"Input content: {prompt}")
        logger.error(f"Error: {str(e)}")
        raise


@dataclass
class FunctionSpec(DataClassJsonMixin):
    name: str
    json_schema: dict  # JSON schema
    description: str

    def __post_init__(self):
        # validate the schema
        jsonschema.Draft7Validator.check_schema(self.json_schema)

    @property
    def as_openai_tool_dict(self):
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.json_schema,
            },
        }

    @property
    def openai_tool_choice_dict(self):
        return {
            "type": "function",
            "function": {"name": self.name},
        }
