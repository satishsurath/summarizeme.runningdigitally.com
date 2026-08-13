import os
import re

from dotenv import load_dotenv

try:
    from openai import OpenAI as _OpenAI

    _HAS_OPENAI = True
except ImportError:
    _HAS_OPENAI = False

try:
    from ollama import Client as _OllamaClient

    _HAS_OLLAMA = True
except ImportError:
    _HAS_OLLAMA = False


load_dotenv()
# vLLM (OpenAI-compatible) or Ollama (backend-agnostic)
_VLLM_GEN_HOST = os.getenv("VLLM_GEN_HOST", "localhost")
_VLLM_GEN_PORT = os.getenv("VLLM_GEN_PORT", "8000")
_OLLAMA_HOST = os.getenv("REMOTE_OLLAMA_HOST", "localhost")
_USE_VLLM = os.getenv("VLLM_GEN_HOST") is not None

# Build URLs
VLLM_GEN_URL = f"http://{_VLLM_GEN_HOST}:{_VLLM_GEN_PORT}"
OLLAMA_URL = f"http://{_OLLAMA_HOST}:11434"
LLM_BASE_URL = VLLM_GEN_URL if _USE_VLLM else OLLAMA_URL


# Get the correct base URL
def _get_llm_url():
    return VLLM_GEN_URL if _USE_VLLM else OLLAMA_URL


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


def build_prompts_for_chunk(chunk_text):
    """
    Return a dict of four prompts:
    - "concise": a short summary
    - "key_topics": high-level topics
    - "takeaways": key insights, lessons
    - "comprehensive": thorough notes capturing examples, references, quotes, etc.

    We add a bit more "context" or "instruction" for each prompt.
    """
    return {
        "concise": f"""
You are an expert summarizer. Read the following text and produce a concise summary
(no more than 150 words) covering the main idea only:

TEXT:
{chunk_text}
""".strip(),
        "key_topics": f"""
You are an expert note-taker. From the following text, list the main topics or themes
(with short bullet points), focusing on clarity and coverage:

TEXT:
{chunk_text}
""".strip(),
        "takeaways": f"""
You are a teaching assistant. From the text below, list the key takeaways or lessons
the reader should remember. Focus on clarity and practical insights, in short bullet points:

TEXT:
{chunk_text}
""".strip(),
        "comprehensive": f"""
You are a meticulous researcher. Provide a comprehensive set of notes about
the following text, capturing major points, examples, references, or quotes.
Organize your notes with headings or bullet points. Aim for thoroughness:

TEXT:
{chunk_text}
""".strip(),
    }


def ollama_generate_chunk(model_name, prompt, client=None):
    """
    Generate text via LLM backend (vLLM or Ollama).
    Args:
        model_name: Model identifier
        prompt: Prompt text
        client: Optional OpenAI client for dependency injection (testing)
    """
    llm_url = _get_llm_url()

    if _USE_VLLM:
        if not _HAS_OPENAI:
            print("[ERROR] openai SDK not installed")
            return ""
        chat_client = client or _OpenAI(base_url=llm_url, api_key="not-needed")
        response = chat_client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096,
        )
        data = response.choices[0].message.content if response.choices else ""
    else:
        if not _HAS_OLLAMA:
            print("[ERROR] ollama SDK not installed")
            return ""
        chat_client = client or _OllamaClient(host=llm_url)
        response = chat_client.chat(model=model_name, messages=[{"role": "user", "content": prompt}])
        data = response.message.content or ""

    return data.strip() if data else ""
