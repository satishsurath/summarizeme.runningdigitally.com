"""Unit tests for prompts.py and system prompt integration."""

from unittest.mock import MagicMock

from prompts import (
    SYSTEM_PROMPT_RAG,
    SYSTEM_PROMPT_SUMMARIZER,
    build_chat_prompt,
    build_prompts_for_chunk,
)
from summarizer_v2 import vllm_generate_chunk, vllm_generate_stream


class TestPromptsModule:
    """Test suite for centralized prompts.py module."""

    def test_system_prompts_not_empty(self):
        assert bool(SYSTEM_PROMPT_RAG)
        assert bool(SYSTEM_PROMPT_SUMMARIZER)
        assert "SummarizeMe AI" in SYSTEM_PROMPT_RAG
        assert "<context>" in SYSTEM_PROMPT_RAG

    def test_build_chat_prompt(self):
        context = "Video Transcript Chunk 1"
        user_query = "What is the main topic?"
        prompt = build_chat_prompt(context, user_query)

        assert "<context>" in prompt
        assert "<user_query>" in prompt
        assert context in prompt
        assert user_query in prompt

    def test_build_prompts_for_chunk(self):
        chunk_text = "This is a test transcript chunk for summarization."
        prompts = build_prompts_for_chunk(chunk_text)

        assert set(prompts.keys()) == {"concise", "key_topics", "takeaways", "comprehensive"}
        for _key, p in prompts.items():
            assert "<instructions>" in p
            assert "<transcript_text>" in p
            assert chunk_text in p


class TestSystemPromptIntegration:
    """Test suite for system_prompt parameters in generation functions."""

    def test_vllm_generate_chunk_includes_system_message(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "Generated Answer"
        mock_response.choices = [MagicMock(message=mock_message)]
        mock_client.chat.completions.create.return_value = mock_response

        res = vllm_generate_chunk(
            "test-model",
            "test prompt",
            client=mock_client,
            system_prompt="Test System Prompt",
        )

        assert res == "Generated Answer"
        mock_client.chat.completions.create.assert_called_once()
        kwargs = mock_client.chat.completions.create.call_args.kwargs
        messages = kwargs.get("messages", [])
        assert len(messages) == 2
        assert messages[0] == {"role": "system", "content": "Test System Prompt"}
        assert messages[1] == {"role": "user", "content": "test prompt"}

    def test_vllm_generate_chunk_without_system_prompt(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "Generated Answer"
        mock_response.choices = [MagicMock(message=mock_message)]
        mock_client.chat.completions.create.return_value = mock_response

        res = vllm_generate_chunk("test-model", "test prompt", client=mock_client)

        assert res == "Generated Answer"
        kwargs = mock_client.chat.completions.create.call_args.kwargs
        messages = kwargs.get("messages", [])
        assert len(messages) == 1
        assert messages[0] == {"role": "user", "content": "test prompt"}

    def test_vllm_generate_stream_yields_results(self, monkeypatch):
        mock_stream = [
            MagicMock(choices=[MagicMock(delta=MagicMock(content="Hello "))]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content="World!"))]),
        ]

        class MockChatClient:
            class chat:
                class completions:
                    @staticmethod
                    def create(**kwargs):
                        messages = kwargs.get("messages", [])
                        assert messages[0] == {"role": "system", "content": "Stream System"}
                        return mock_stream

        monkeypatch.setattr("summarizer_v2._OpenAI", lambda **kwargs: MockChatClient())
        monkeypatch.setattr("summarizer_v2._HAS_OPENAI", True)

        chunks = list(vllm_generate_stream("test-model", "user prompt", system_prompt="Stream System"))
        texts = [c[0] for c in chunks if c[0]]
        assert "".join(texts) == "Hello World!"
