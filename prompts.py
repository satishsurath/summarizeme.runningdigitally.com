"""Centralized prompt templates and system instructions for SummarizeMe.

Provides system personas, RAG prompt builders, and structured summarization templates.
"""

SYSTEM_PROMPT_RAG = """
You are SummarizeMe AI, an expert technical research assistant for YouTube video transcripts.

Core Rules & Guardrails:
1. Grounding: Answer strictly using only information in <context> tags. Do not rely on unverified external facts.
2. Fallback: If context lacks info, state: "I could not find information addressing your question in the video(s)."
3. Formatting: Present response in clean Markdown with clear headings, bullet points, and code blocks as appropriate.
4. Citations: When referencing specific details, cite the relevant video title or section context.
""".strip()

SYSTEM_PROMPT_SUMMARIZER = """
You are an expert technical writer and analyst specializing in video content summarization.
Your objective is to extract high-value insights and accurate technical details without fluff.
Always format your output in polished, professional Markdown with clear visual hierarchy.
""".strip()


def build_chat_prompt(context: str, user_query: str) -> str:
    """Build XML-formatted user prompt for RAG chat queries."""
    return f"""
<context>
{context}
</context>

<user_query>
{user_query}
</user_query>

Please provide a comprehensive, well-structured answer in Markdown based strictly on the context above.
""".strip()


def build_prompts_for_chunk(chunk_text: str) -> dict[str, str]:
    """Return a dict of four structured summarization prompts:

    - "concise": executive summary (100-150 words)
    - "key_topics": main themes with bold subheadings and bullet points
    - "takeaways": actionable takeaways and key lessons
    - "comprehensive": detailed study notes with technical specifics and quotes
    """
    return {
        "concise": f"""
<instructions>
Provide an executive summary (100-150 words) of the following transcript text.
Cover the primary thesis, key discussion points, and main conclusion.
</instructions>

<transcript_text>
{chunk_text}
</transcript_text>
""".strip(),
        "key_topics": f"""
<instructions>
Extract the main themes and sub-topics from the following transcript text.
Organize your output with bold thematic subheadings and bullet points explaining each topic's significance.
</instructions>

<transcript_text>
{chunk_text}
</transcript_text>
""".strip(),
        "takeaways": f"""
<instructions>
Extract practical takeaways, key lessons, actionable advice, and memorable insights from the transcript text.
Format as a clean bulleted list, highlighting actionable steps in bold.
</instructions>

<transcript_text>
{chunk_text}
</transcript_text>
""".strip(),
        "comprehensive": f"""
<instructions>
Produce comprehensive, detailed study notes for the following transcript text.
Include major arguments, technical terms, step-by-step concepts, quotes, and specific references.
Use Markdown headers, bullet lists, and bold emphasis for maximum readability.
</instructions>

<transcript_text>
{chunk_text}
</transcript_text>
""".strip(),
    }
