import logging
import os
import re

import httpx
from dotenv import load_dotenv

from prompts import build_prompts_for_chunk  # re-exported for callers

__all__ = [
    "build_prompts_for_chunk",
    "chunk_transcript",
    "split_into_sentences",
    "vllm_embed_chunk",
    "vllm_generate_chunk",
    "vllm_generate_stream",
]

try:
    from openai import (
        APIConnectionError,
        APIError,
        APIStatusError,
    )
    from openai import (
        OpenAI as _OpenAI,
    )

    _HAS_OPENAI = True
except ImportError:
    _HAS_OPENAI = False


load_dotenv()
# vLLM (OpenAI-compatible) LLM backend
_VLLM_GEN_HOST = os.getenv("VLLM_GEN_HOST", "localhost")
_VLLM_EMBED_HOST = os.getenv("VLLM_EMBED_HOST", "localhost")
_VLLM_EMBED_PORT = os.getenv("VLLM_EMBED_PORT", "8001")
_VLLM_GEN_PORT = os.getenv("VLLM_GEN_PORT", "8000")
_VLLM_GEN_API_KEY = os.getenv("VLLM_GEN_API_KEY", "not-needed")
# Build URLs
VLLM_GEN_URL = f"http://{_VLLM_GEN_HOST}:{_VLLM_GEN_PORT}"
VLLM_EMBED_URL = f"http://{_VLLM_EMBED_HOST}:{_VLLM_EMBED_PORT}"

logger = logging.getLogger(__name__)


def split_into_sentences(text):
    """
    Split text into sentences by typical punctuation delimiters.
    We'll split on '.', '?', '!', and preserve those delimiters
    so we can re-attach them.
    Then we trim whitespace.
    """
    # A simple approach: use a regex that matches on (.?!),
    # capturing the punctuation to re-attach. This won't be perfect for
    # abbreviations, decimal points, etc., but it's a decent start.
    sentence_pattern = re.compile(r"([^.?!]+[.?!])")
    # This returns a list of "sentence-like" strings, each ending with punctuation
    parts = sentence_pattern.findall(text)
    # If there's leftover text without punctuation, we handle that as well
    remainder = sentence_pattern.sub("", text).strip()
    if remainder:
        parts.append(remainder)

    # Clean up extra whitespace
    sentences = [p.strip() for p in parts if p.strip()]
    return sentences


def chunk_transcript(transcript, max_words_per_chunk=4000):
    """
    Improved chunker:
    1) Split transcript into sentences.
    2) Combine sentences into chunks until we reach ~4k words.
    3) If a single sentence is >4k words, we split that sentence by words.

    Returns a list of chunk strings.
    """
    sentences = split_into_sentences(transcript)
    chunks = []
    current_words = []
    current_count = 0

    for sentence in sentences:
        # Word count for this sentence
        words_in_sentence = sentence.split()
        sentence_len = len(words_in_sentence)

        if sentence_len > max_words_per_chunk:
            # The sentence alone exceeds chunk size
            # -> break this sentence into sub-chunks by words
            start = 0
            while start < sentence_len:
                end = start + max_words_per_chunk
                sub_chunk_words = words_in_sentence[start:end]
                sub_chunk_str = " ".join(sub_chunk_words)
                chunks.append(sub_chunk_str)
                start = end
        else:
            # Check if adding this sentence to current chunk
            # would exceed max_words_per_chunk
            if current_count + sentence_len > max_words_per_chunk:
                # flush current chunk
                chunks.append(" ".join(current_words))
                current_words = []
                current_count = 0

            # Add this sentence
            current_words.extend(words_in_sentence)
            current_count += sentence_len

    # leftover
    if current_words:
        chunks.append(" ".join(current_words))

    return chunks


# ----------------------------
# 2) IMPROVED PROMPT ENGINEERING
# ----------------------------


def vllm_generate_chunk(model_name, prompt, client=None, system_prompt=None):
    """
    Generate text via vLLM backend.
    Args:
        model_name: Model identifier
        prompt: Prompt text
        client: Optional OpenAI client for dependency injection (testing)
        system_prompt: Optional system persona prompt
    """
    from app_config import shared_logger

    llm_url = VLLM_GEN_URL

    if not _HAS_OPENAI:
        shared_logger.error("openai SDK not installed")
        return ""

    messages_list = []
    if system_prompt:
        messages_list.append({"role": "system", "content": system_prompt})
    messages_list.append({"role": "user", "content": prompt})

    base_url = f"{llm_url.rstrip('/')}/v1" if not llm_url.endswith("/v1") else llm_url
    try:
        chat_client = client or _OpenAI(base_url=base_url, api_key=_VLLM_GEN_API_KEY)
        response = chat_client.chat.completions.create(
            model=model_name,
            messages=messages_list,
            max_tokens=4096,
        )
        msg = response.choices[0].message if response.choices else None
        data = msg.content if msg and msg.content else (getattr(msg, "reasoning", None) or "")
    except Exception:
        # Fallback to httpx for vLLM compatibility
        try:
            resp = httpx.post(
                f"{llm_url}/v1/chat/completions",
                json={
                    "model": model_name,
                    "messages": messages_list,
                    "max_tokens": 4096,
                },
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {_VLLM_GEN_API_KEY}",
                },
                timeout=120,
            )
            try:
                result = resp.json()
                msg = result.get("choices", [{}])[0].get("message", {})
                data = msg.get("content") or msg.get("reasoning") or ""
            except Exception:
                shared_logger.error("vLLM returned invalid JSON: %s", resp.text[:200])
                return ""
            if resp.status_code != 200:
                shared_logger.error(
                    "vLLM HTTP error: %s %s",
                    resp.status_code,
                    resp.text[:200],
                )
                return ""
        except httpx.HTTPError:
            shared_logger.exception("vLLM httpx fallback failed")
            return ""

    return data.strip() if data else ""


def vllm_generate_stream(model_name: str, prompt: str, system_prompt: str | None = None):
    """
    Generate text via vLLM backend with streaming (SSE) support.
    Yields (chunk_text: str, done: bool) tuples.
    chunk_text is the new text fragment; done is True on the final chunk.
    """
    from app_config import shared_logger

    llm_url = VLLM_GEN_URL

    if not _HAS_OPENAI:
        shared_logger.error("openai SDK not installed")
        yield "", True
        return

    messages_list = []
    if system_prompt:
        messages_list.append({"role": "system", "content": system_prompt})
    messages_list.append({"role": "user", "content": prompt})

    base_url = f"{llm_url.rstrip('/')}/v1" if not llm_url.endswith("/v1") else llm_url
    try:
        chat_client = _OpenAI(base_url=base_url, api_key=_VLLM_GEN_API_KEY)
        stream = chat_client.chat.completions.create(
            model=model_name,
            messages=messages_list,
            max_tokens=4096,
            stream=True,
        )
        full_text = ""
        for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            delta_content = (delta.content if delta and delta.content else "") or (
                getattr(delta, "reasoning", None) or "" if delta else ""
            )
            if delta_content:
                full_text += delta_content
                yield delta_content, False
        yield "", True
    except Exception:
        # Fallback to httpx streaming for vLLM compatibility
        try:
            import json

            import httpx

            payload = {
                "model": model_name,
                "messages": messages_list,
                "max_tokens": 4096,
                "stream": True,
            }
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {_VLLM_GEN_API_KEY}",
            }
            with httpx.stream(
                "POST",
                f"{llm_url}/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=120,
            ) as resp:
                if resp.status_code != 200:
                    shared_logger.error(
                        "vLLM streaming HTTP error: %s %s",
                        resp.status_code,
                        resp.text[:200],
                    )
                    yield "", True
                    return
                full_text = ""
                for line in resp.iter_lines():
                    text = line  # httpx iter_lines returns str, not bytes
                    if not text or text.startswith(":"):
                        continue
                    if text.startswith("data: "):
                        data_str = text[6:]
                        if data_str == "[DONE]":
                            yield "", True
                            return
                        try:
                            data = json.loads(data_str)
                            delta = data.get("choices", [{}])[0].get("delta", {})
                            delta_content = delta.get("content", "") or ""
                            full_text += delta_content
                            yield delta_content, False
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
                yield "", True
        except httpx.HTTPError:
            shared_logger.exception("vLLM streaming httpx fallback failed")
            yield "", True


def vllm_embed_chunk(text_input, client=None, model_name="nemo-nomic-embed-text-v1.5", is_query=False):
    """
    Generate embedding via vLLM backend.
    Args:
        text_input: Single string to embed
        client: Optional OpenAI client for dependency injection (testing)
        model_name: Embedding model identifier (default: nomic embed)
        is_query: If True, uses 'search_query: ' prefix; else 'search_document: ' for Nomic v1.5
    """
    from app_config import shared_logger

    if (
        text_input
        and isinstance(text_input, str)
        and not (text_input.startswith("search_query: ") or text_input.startswith("search_document: "))
    ):
        prefix = "search_query: " if is_query else "search_document: "
        text_input = f"{prefix}{text_input}"

    llm_url = VLLM_EMBED_URL
    if not _HAS_OPENAI:
        shared_logger.error("openai SDK not installed")
        return None
    base_url = f"{llm_url.rstrip('/')}/v1" if not llm_url.endswith("/v1") else llm_url
    try:
        embed_client = client or _OpenAI(base_url=base_url, api_key=_VLLM_GEN_API_KEY)
        response = embed_client.embeddings.create(
            model=model_name,
            input=[text_input],
        )
        data = response.data[0].embedding if response.data else None
    except (APIError, APIStatusError, APIConnectionError):
        # Fallback to httpx for vLLM compatibility
        try:
            resp = httpx.post(
                f"{llm_url}/v1/embeddings",
                json={
                    "model": model_name,
                    "input": [text_input],
                },
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {_VLLM_GEN_API_KEY}",
                },
                timeout=30,
            )
            if resp.status_code == 200:
                result = resp.json()
                data = result.get("data", [{}])[0].get("embedding")
            else:
                shared_logger.error(
                    "vLLM embed HTTP error: %s %s",
                    resp.status_code,
                    resp.text[:200],
                )
                return None
        except httpx.HTTPError:
            shared_logger.exception("vLLM embed httpx fallback failed")
            return None

    return data
