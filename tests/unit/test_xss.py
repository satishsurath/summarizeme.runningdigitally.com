"""Tests for XSS prevention in md_safe."""

import os

os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/test_xss.db")


class TestMdSafe:
    """Tests for the md_safe markdown-to-HTML helper."""

    def test_script_tag_escaped(self):
        """<script> tags in input must not appear in rendered output."""
        from app import md_safe

        result = md_safe("<script>alert(1)</script>")
        assert "<script>" not in result
        assert "alert(1)" in result  # text still visible, just escaped

    def test_img_onerror_escaped(self):
        """Inline event handlers must be neutralised (img tag must be escaped)."""
        from app import md_safe

        result = md_safe('<img src=x onerror="alert(1)">')
        # The entire <img tag must be escaped — no live element can execute onerror
        assert "<img" not in result

    def test_normal_markdown_still_renders(self):
        """Regular markdown (bold, italic, links) must still work."""
        from app import md_safe

        result = md_safe("**bold** and _italic_")
        assert "<strong>bold</strong>" in result
        assert "<em>italic</em>" in result

    def test_empty_string_returns_empty(self):
        """Empty input returns empty string."""
        from app import md_safe

        assert md_safe("") == ""
        assert md_safe(None) == ""  # type: ignore[arg-type]
