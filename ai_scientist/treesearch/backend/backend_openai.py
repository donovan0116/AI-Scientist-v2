import json
import logging
import os
import time

from .utils import FunctionSpec, OutputType, opt_messages_to_list, backoff_create
from funcy import notnone, once, select_values
import openai
from rich import print

logger = logging.getLogger("ai-scientist")


OPENAI_TIMEOUT_EXCEPTIONS = (
    openai.RateLimitError,
    openai.APIConnectionError,
    openai.APITimeoutError,
    openai.InternalServerError,
)


def _openrouter_http_client():
    """Build an optional HTTP client that uses proxy for OpenRouter (to avoid 403 region blocks).
    Uses a long timeout so OpenRouter (often slow from some regions) does not hit httpx's default 5s.
    """
    proxy = (
        os.environ.get("OPENROUTER_HTTPS_PROXY")
        or os.environ.get("HTTPS_PROXY")
        or os.environ.get("http_proxy")
        or os.environ.get("HTTP_PROXY")
    )
    if not proxy:
        return None
    try:
        import httpx
        # httpx default is 5s; OpenRouter can be slow → use 10min read, 60s connect (why curl works but code timed out)
        timeout = httpx.Timeout(600.0, connect=60.0)
        return httpx.Client(proxy=proxy, timeout=timeout)
    except Exception as e:
        logger.warning("Could not create proxy client for OpenRouter: %s", e)
        return None


def get_ai_client(model: str, max_retries=2) -> openai.OpenAI:
    if model.startswith("openrouter/"):
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENROUTER_API_KEY environment variable is required when using openrouter/ models. "
                "Set it with: export OPENROUTER_API_KEY='your-key'"
            )
        kwargs = dict(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            max_retries=max_retries,
        )
        http_client = _openrouter_http_client()
        if http_client is not None:
            kwargs["http_client"] = http_client
            proxy = os.environ.get("OPENROUTER_HTTPS_PROXY") or os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
            logger.debug("Using proxy for OpenRouter: %s", proxy)
        return openai.OpenAI(**kwargs)
    if model.startswith("ollama/"):
        client = openai.OpenAI(
            base_url="http://localhost:11434/v1",
            max_retries=max_retries
        )
    else:
        client = openai.OpenAI(max_retries=max_retries)
    return client


def query(
    system_message: str | None,
    user_message: str | None,
    func_spec: FunctionSpec | None = None,
    **model_kwargs,
) -> tuple[OutputType, float, int, int, dict]:
    raw_model = model_kwargs.get("model")
    client = get_ai_client(raw_model, max_retries=0)
    filtered_kwargs: dict = select_values(notnone, model_kwargs)  # type: ignore

    messages = opt_messages_to_list(system_message, user_message)

    if func_spec is not None:
        filtered_kwargs["tools"] = [func_spec.as_openai_tool_dict]
        # force the model to use the function
        filtered_kwargs["tool_choice"] = func_spec.openai_tool_choice_dict

    # OpenRouter and Ollama use full model id in config; strip prefix for API
    if filtered_kwargs.get("model", "").startswith("openrouter/"):
        filtered_kwargs["model"] = filtered_kwargs["model"].replace("openrouter/", "", 1)
        # Together and other OpenRouter providers often require max_tokens and reject large values
        if not filtered_kwargs.get("max_tokens"):
            filtered_kwargs["max_tokens"] = 4096
        elif filtered_kwargs["max_tokens"] > 4096:
            filtered_kwargs["max_tokens"] = 4096
        # Only send params most providers support; drop any extras to avoid "Input validation error"
        allowed = {"model", "messages", "max_tokens", "temperature", "tools", "tool_choice"}
        filtered_kwargs = {k: v for k, v in filtered_kwargs.items() if k in allowed}
    elif filtered_kwargs.get("model", "").startswith("ollama/"):
        filtered_kwargs["model"] = filtered_kwargs["model"].replace("ollama/", "", 1)

    t0 = time.time()
    try:
        completion = backoff_create(
            client.chat.completions.create,
            OPENAI_TIMEOUT_EXCEPTIONS,
            messages=messages,
            **filtered_kwargs,
        )
    except (openai.BadRequestError, openai.APIStatusError, openai.APIError) as e:
        # Re-raise as a simple exception so multiprocessing can pickle it (OpenAI errors are not picklable)
        raise RuntimeError(f"API error: {e!s}") from None
    req_time = time.time() - t0

    # Diagnose why API sometimes returns None (see docs/API_NONE_DEBUG.md)
    if completion is None:
        logger.error(
            "API returned no completion (None). model=%s messages_count=%s",
            raw_model,
            len(messages),
        )
        raise RuntimeError(
            "API returned no completion (None). Possible timeout, rate limit, or provider error."
        )
    if not getattr(completion, "choices", None) or len(completion.choices) == 0:
        logger.error(
            "API returned empty choices. model=%s completion_id=%s",
            raw_model,
            getattr(completion, "id", None),
        )
        raise RuntimeError("API returned empty choices.")

    choice = completion.choices[0]

    if func_spec is None:
        output = choice.message.content
        if output is None:
            logger.warning(
                "API returned message.content=None (empty content). model=%s choice=%s",
                raw_model,
                choice,
            )
    else:
        assert (
            choice.message.tool_calls
        ), f"function_call is empty, it is not a function call: {choice.message}"
        assert (
            choice.message.tool_calls[0].function.name == func_spec.name
        ), "Function name mismatch"
        try:
            print(f"[cyan]Raw func call response: {choice}[/cyan]")
            output = json.loads(choice.message.tool_calls[0].function.arguments)
        except json.JSONDecodeError as e:
            logger.error(
                f"Error decoding the function arguments: {choice.message.tool_calls[0].function.arguments}"
            )
            raise e

    in_tokens = completion.usage.prompt_tokens
    out_tokens = completion.usage.completion_tokens

    info = {
        "system_fingerprint": completion.system_fingerprint,
        "model": completion.model,
        "created": completion.created,
    }

    return output, req_time, in_tokens, out_tokens, info
