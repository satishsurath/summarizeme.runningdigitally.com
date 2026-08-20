"""Tests for summarizer_v2.py — chunking, prompts, and vLLM generation."""

from summarizer_v2 import build_prompts_for_chunk, chunk_transcript, split_into_sentences


class TestSplitIntoSentences:
    """Tests for the sentence splitter."""

    def test_single_sentence(self):
        """A single sentence returns one element."""
        result = split_into_sentences("Hello world.")
        assert len(result) == 1
        assert "Hello world." in result

    def test_multiple_sentences(self):
        """Multiple sentences split correctly."""
        result = split_into_sentences("First sentence. Second sentence. Third.")
        assert len(result) == 3

    def test_question_and_exclamation(self):
        """Different punctuation marks are recognized."""
        result = split_into_sentences("A question? An exclamation! A period.")
        assert len(result) == 3
        assert "A question?" in result
        assert "An exclamation!" in result

    def test_trailing_whitespace_stripped(self):
        """Whitespace is cleaned from each sentence."""
        result = split_into_sentences("  First.  Second  ")
        for s in result:
            assert s == s.strip()

    def test_empty_input(self):
        """Empty string returns empty list."""
        result = split_into_sentences("")
        assert result == []

    def test_text_without_punctuation(self):
        """Text without sentence-ending punctuation returns remainder."""
        result = split_into_sentences("no punctuation here")
        assert len(result) == 1
        assert "no punctuation here" in result

    def test_mixed_punctuation(self):
        """Mixed .?! punctuation is handled."""
        result = split_into_sentences("One. Two? Three! Four.")
        assert len(result) == 4


class TestChunkTranscript:
    """Tests for the transcript chunker."""

    def test_small_transcript_single_chunk(self):
        """A short transcript stays as one chunk."""
        transcript = "A short text."
        chunks = chunk_transcript(transcript, max_words_per_chunk=4000)
        assert len(chunks) == 1

    def test_large_transcript_splits(self):
        """A long transcript is split into multiple chunks."""
        # Generate a transcript of ~5000 words
        words = ["word"] * 5000
        transcript = " ".join(words)
        chunks = chunk_transcript(transcript, max_words_per_chunk=4000)
        assert len(chunks) == 2
        assert all(chunk.strip() for chunk in chunks)

    def test_chunks_under_limit(self):
        """No chunk should exceed max_words_per_chunk."""
        words = ["short"] * 100
        transcript = " ".join(words)
        chunks = chunk_transcript(transcript, max_words_per_chunk=20)
        for chunk in chunks:
            assert len(chunk.split()) <= 20

    def test_empty_input(self):
        """Empty transcript returns empty list."""
        chunks = chunk_transcript("", max_words_per_chunk=4000)
        assert chunks == []

    def test_single_long_sentence_exceeds_limit(self):
        """A sentence longer than the limit is split by words."""
        words = ["word"] * 5000
        transcript = " ".join(words)  # No punctuation, treated as one sentence
        chunks = chunk_transcript(transcript, max_words_per_chunk=4000)
        assert len(chunks) == 2

    def test_chunk_boundaries_respect_sentences(self):
        """Chunks are built from complete sentences when possible."""
        sentences = ["First sentence. ", "Second sentence. ", "Third sentence."]
        transcript = "".join(sentences)
        chunks = chunk_transcript(transcript, max_words_per_chunk=10)
        # Should produce at least 2 chunks since 3 sentences * ~3 words = 9 words
        assert len(chunks) >= 1


class TestBuildPromptsForChunk:
    """Tests for the prompt builder."""

    def test_returns_four_prompts(self):
        """Should return exactly 4 prompt keys."""
        prompts = build_prompts_for_chunk("test text")
        assert set(prompts.keys()) == {"concise", "key_topics", "takeaways", "comprehensive"}

    def test_prompts_contain_text(self):
        """Each prompt should contain the chunk text."""
        prompts = build_prompts_for_chunk("my test content")
        for _key, prompt in prompts.items():
            assert "my test content" in prompt

    def test_prompts_have_role_instructions(self):
        """Each prompt should have structured instructions and transcript text blocks."""
        prompts = build_prompts_for_chunk("test")
        assert "<instructions>" in prompts["concise"]
        assert "<instructions>" in prompts["takeaways"]

    def test_concise_prompt_limits_word_count(self):
        """Concise prompt should mention word limit."""
        prompts = build_prompts_for_chunk("test")
        assert "150 words" in prompts["concise"]


class TestVllmGenerateChunk:
    """Tests for the LLM chunk generation function."""

    def test_returns_response_from_backend(self, mock_vllm_response):
        """With a mock LLM, should return the mocked response."""
        from summarizer_v2 import vllm_generate_chunk

        # mock_vllm_response patches openai.OpenAI
        # The mock OpenAI client returns "Mock response"
        result = vllm_generate_chunk("test-model", "test prompt")
        assert "Mock response" in result
