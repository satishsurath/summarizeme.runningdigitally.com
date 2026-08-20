# ADR 0003: System Personas, XML Tag Delimitation, and Centralized Prompting Architecture

## Status
Accepted

## Date
2026-08-18

## Context
Previous prompt construction in SummarizeMe embedded prompt text directly inside user message strings (`messages=[{"role": "user", "content": prompt}]`), omitting native LLM `system` role instructions (`{"role": "system", "content": SYSTEM_PROMPT}`). 

Additionally, RAG context and user queries were concatenated as unstructured plain text strings without explicit delimiters (`\nContext:\n...\n\nUser Query:\n...`). Summarization prompts were brief 2-line instructions without persona guardrails or structured output templates.

External prompt engineering research for open-weights LLMs (Qwen 3.6 35B) establishes that:
1. Native system role separation improves instruction compliance, grounding, and enables vLLM static KV-cache reuse.
2. Enclosing RAG inputs in explicit XML tags (`<context>`, `<user_query>`, `<instructions>`, `<transcript_text>`) prevents context-instruction conflation and prompt injection ambiguities.
3. Structured output templates significantly improve Markdown hierarchy and information extraction depth.

## Decision
1. **Centralized Prompt Repository (`prompts.py`):**
   - Create [`prompts.py`](../../prompts.py) containing system personas (`SYSTEM_PROMPT_RAG`, `SYSTEM_PROMPT_SUMMARIZER`), RAG prompt builder `build_chat_prompt()`, and structured summary builder `build_prompts_for_chunk()`.

2. **System Role Integration (`summarizer_v2.py`):**
   - Extend `vllm_generate_chunk` and `vllm_generate_stream` to accept an optional `system_prompt` parameter, constructing role-separated message lists (`[{"role": "system", ...}, {"role": "user", ...}]`).

3. **XML Tag Delimitation & Anti-Hallucination Guardrails:**
   - Enclose RAG retrieval contexts in `<context>` tags and user queries in `<user_query>` tags across all chat endpoints (`blueprints/chat.py`).
   - Enforce strict grounding guardrails (*"Answer strictly using only the provided information enclosed in <context> tags"*).

4. **Structured Summarization Prompts:**
   - Upgrade summarization prompts (`concise`, `key_topics`, `takeaways`, `comprehensive`) to extract high-value insights, actionable knowledge, and step-by-step concepts formatted in crisp Markdown.

## Consequences

### Positive
- **Higher Instruction & Grounding Compliance:** Native system prompts enforce strict reliance on retrieved context, reducing hallucinations.
- **vLLM KV-Cache Efficiency:** Static system prompts enable vLLM to reuse prefix KV caches across API requests.
- **Superior Summarization Quality:** End users receive well-structured Markdown notes with clear visual hierarchy, bold subheadings, and actionable takeaways.
- **Maintainability:** Prompts are centralized in [`prompts.py`](../../prompts.py) rather than scattered across blueprint modules.

### Negative / Trade-offs
- Slight increase in system prompt token overhead (~100 tokens per request), which is offset by vLLM KV caching.
