"""Tests for thinking process parser and HTML entity decoder."""

from app_config import md_safe
from blueprints.chat import separate_thinking_and_answer


def test_md_safe_preserves_xss_protection():
    """Verify md_safe preserves XSS protection by escaping raw HTML tags."""
    input_text = 'Here\'s a test with "quotes" and <script>alert(1)</script>.'
    html = md_safe(input_text)

    # Dangerous tags must remain escaped
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_separate_thinking_and_answer_with_prefix():
    """Verify separate_thinking_and_answer isolates thinking prefix from main answer."""
    raw_text = (
        "Here's a thinking process:\n"
        "Analyze User Input: Test query.\n"
        "Drafting answer...\n"
        "✅ Output matches. [Proceeds]\n"
        "This video explains how Nvidia's Switchyard works."
    )
    thinking, answer = separate_thinking_and_answer(raw_text)
    assert thinking is not None
    assert "Analyze User Input" in thinking
    assert answer == "This video explains how Nvidia's Switchyard works."


def test_separate_thinking_and_answer_with_output_generation_proceeds():
    """Verify separate_thinking_and_answer correctly finds final [Output Generation] -> Proceeds boundary."""
    raw_text = (
        "Here's a thinking process:\n"
        "1. Check against Context: Draft attempt...\n"
        "Final Output Generation: (matches refined version) ✅\n"
        "Self-Correction/Refinement:\n"
        "I'll make it direct...\n"
        "Proceeds.\n"
        "[Output Generation] -&gt; Proceeds\n\n"
        "The video argues against relying on expensive cloud AI."
    )
    thinking, answer = separate_thinking_and_answer(raw_text)
    assert thinking is not None
    assert "Self-Correction/Refinement" in thinking
    assert "Proceeds." in thinking
    assert answer == "The video argues against relying on expensive cloud AI."


def test_separate_thinking_and_answer_with_done_marker():
    """Verify separate_thinking_and_answer includes intermediate draft and (Done.) inside thinking."""
    raw_text = (
        "Here's a thinking process:\n"
        "Output Generation.\n\n"
        "The video critiques companies for wasting money...✅\n"
        "   (Done.)\n\n"
        "This video critiques companies for wasting money on expensive cloud AI."
    )
    thinking, answer = separate_thinking_and_answer(raw_text)
    assert thinking is not None
    assert "(Done.)" in thinking
    assert answer == "This video critiques companies for wasting money on expensive cloud AI."


def test_separate_thinking_and_answer_strips_stray_emoji_and_p_tags():
    """Verify separate_thinking_and_answer strips leading <p>✅</p> and stray checkmarks from answer."""
    raw_text = (
        "<think>1. Analyze User Input...\n[Proceeds]</think>\n\n"
        "<p>✅</p>\n"
        "<p>The video argues against relying on costly cloud AI services.</p>"
    )
    thinking, answer = separate_thinking_and_answer(raw_text)
    assert thinking == "1. Analyze User Input...\n[Proceeds]"
    assert answer == "<p>The video argues against relying on costly cloud AI services.</p>"


def test_separate_thinking_and_answer_with_xml_tags():
    """Verify separate_thinking_and_answer isolates <think> tags."""
    raw_text = "<think>Analyzing context...</think>\n\nThis is the answer."
    thinking, answer = separate_thinking_and_answer(raw_text)
    assert thinking == "Analyzing context..."
    assert answer == "This is the answer."


def test_separate_thinking_and_answer_no_thinking():
    """Verify separate_thinking_and_answer returns None thinking for normal output."""
    raw_text = "This is a direct answer without thinking thoughts."
    thinking, answer = separate_thinking_and_answer(raw_text)
    assert thinking is None
    assert answer == raw_text
