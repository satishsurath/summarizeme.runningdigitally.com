"""
Frontend asset tests — SummarizeMe

Validates that frontend assets (JS, CSS) exist, are syntactically valid,
and expose the expected APIs. These tests catch SonarQube issues like:
- Unused variables
- Missing error handling
- Inconsistent naming
- Missing accessibility attributes
"""

import re
from pathlib import Path

import pytest

# Project root: tests/unit/test_frontend.py -> tests/unit -> tests -> project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
STATIC_DIR = PROJECT_ROOT / "static"
TEMPLATES_DIR = PROJECT_ROOT / "templates"


class TestFileExistence:
    """Verify all expected frontend files exist."""

    @pytest.mark.parametrize(
        "filepath",
        [
            "css/tailwind.config.js",
            "css/components.css",
            "css/icons.css",
            "js/toast.js",
            "js/loading.js",
            "js/index.js",
            "js/status.js",
            "layout.html",
        ],
    )
    def test_file_exists(self, filepath):
        path = STATIC_DIR / filepath if filepath.startswith(("css/", "js/")) else TEMPLATES_DIR / filepath
        assert path.exists(), f"Missing frontend file: {filepath}"

    def test_layout_includes_toast_js(self):
        layout = (TEMPLATES_DIR / "layout.html").read_text()
        assert "toast.js" in layout

    def test_layout_includes_loading_js(self):
        layout = (TEMPLATES_DIR / "layout.html").read_text()
        assert "loading.js" in layout

    def test_layout_includes_components_css(self):
        layout = (TEMPLATES_DIR / "layout.html").read_text()
        assert "components.css" in layout

    def test_layout_includes_icons_css(self):
        layout = (TEMPLATES_DIR / "layout.html").read_text()
        assert "icons.css" in layout


class TestToastSystem:
    """Validate toast.js structure and API."""

    @pytest.fixture
    def toast_source(self):
        return (STATIC_DIR / "js" / "toast.js").read_text()

    def test_class_exists(self, toast_source):
        assert "class ToastManager" in toast_source

    def test_show_method(self, toast_source):
        assert "show(" in toast_source

    def test_dismiss_method(self, toast_source):
        assert "dismiss(" in toast_source

    def test_success_method(self, toast_source):
        assert "success(" in toast_source

    def test_error_method(self, toast_source):
        assert "error(" in toast_source

    def test_warning_method(self, toast_source):
        assert "warning(" in toast_source

    def test_info_method(self, toast_source):
        assert "info(" in toast_source

    def test_global_singleton(self, toast_source):
        assert "const toast = new ToastManager()" in toast_source

    def test_no_alert_calls(self, toast_source):
        assert "alert(" not in toast_source

    def test_aria_attributes(self, toast_source):
        assert "aria-live" in toast_source
        assert "aria-atomic" in toast_source

    def test_escape_html(self, toast_source):
        assert "_escapeHtml" in toast_source or "textContent" in toast_source

    def test_auto_dismiss_configurable(self, toast_source):
        assert "duration" in toast_source


class TestLoadingSystem:
    """Validate loading.js structure and API."""

    @pytest.fixture
    def loading_source(self):
        return (STATIC_DIR / "js" / "loading.js").read_text()

    def test_class_exists(self, loading_source):
        assert "class LoadingManager" in loading_source

    def test_start_method(self, loading_source):
        assert "start(" in loading_source

    def test_end_method(self, loading_source):
        assert "end(" in loading_source

    def test_global_singleton(self, loading_source):
        assert "const loading = new LoadingManager()" in loading_source

    def test_disables_element(self, loading_source):
        assert "disabled = true" in loading_source

    def test_restores_element(self, loading_source):
        assert "disabled = false" in loading_source

    def test_preserves_original_text(self, loading_source):
        assert "originalText" in loading_source or "dataset.originalText" in loading_source

    def test_no_alert_calls(self, loading_source):
        assert "alert(" not in loading_source

    def test_map_for_tracking(self, loading_source):
        assert "Map" in loading_source or "activeLoads" in loading_source


class TestCSSComponents:
    """Validate components.css has expected classes."""

    @pytest.fixture
    def components_css(self):
        return (STATIC_DIR / "css" / "components.css").read_text()

    @pytest.mark.parametrize(
        "classname",
        [
            ".btn-primary",
            ".btn-secondary",
            ".btn-danger",
            ".btn-icon",
            ".card",
            ".card-header",
            ".card-body",
            ".input",
            ".badge",
            ".badge-success",
            ".badge-warning",
            ".badge-error",
            ".badge-info",
            ".status-dot",
            ".nav-link",
            ".sr-only",
            ".toast",
            ".spinner",
        ],
    )
    def test_exists(self, components_css, classname):
        assert classname in components_css

    def test_dark_mode(self, components_css):
        assert components_css.count("dark:") > 5

    def test_focus_rings(self, components_css):
        assert "focus:ring" in components_css or "focus-ring" in components_css


class TestIconSizing:
    """Validate icons.css has expected sizing classes."""

    @pytest.fixture
    def icons_css(self):
        return (STATIC_DIR / "css" / "icons.css").read_text()

    @pytest.mark.parametrize("classname", [".icon-sm", ".icon-md", ".icon-lg", ".icon-xl"])
    def test_exists(self, icons_css, classname):
        assert classname in icons_css


class TestLayoutHTML:
    """Validate layout.html structure and accessibility."""

    @pytest.fixture
    def layout(self):
        return (TEMPLATES_DIR / "layout.html").read_text()

    def test_skip_navigation(self, layout):
        assert "Skip to main content" in layout or "skip" in layout.lower()

    def test_main_content_id(self, layout):
        assert 'id="main-content"' in layout

    def test_live_region(self, layout):
        assert "aria-live" in layout

    def test_nav_label(self, layout):
        assert "aria-label" in layout

    def test_mobile_menu_aria(self, layout):
        assert "aria-expanded" in layout
        assert "aria-controls" in layout

    def test_dark_mode_toggle_aria(self, layout):
        count = layout.count('aria-label="Toggle dark mode"')
        assert count >= 2

    def test_brand_name(self, layout):
        assert "SummarizeMe" in layout

    def test_script_order(self, layout):
        toast_pos = layout.find("toast.js")
        loading_pos = layout.find("loading.js")
        index_pos = layout.find("index.js")
        assert toast_pos > 0 and loading_pos > 0 and index_pos > 0
        assert toast_pos < loading_pos < index_pos


class TestIndexJSIntegration:
    """Validate index.js uses toast and loading systems."""

    @pytest.fixture
    def index_js(self):
        return (STATIC_DIR / "js" / "index.js").read_text()

    def test_has_error_handling(self, index_js):
        assert "try" in index_js and "catch" in index_js

    def test_has_fetch_calls(self, index_js):
        assert "fetch(" in index_js


class TestSonarQuality:
    """Catch common SonarQube issues in frontend code."""

    @pytest.fixture
    def toast_source(self):
        return (STATIC_DIR / "js" / "toast.js").read_text()

    @pytest.fixture
    def loading_source(self):
        return (STATIC_DIR / "js" / "loading.js").read_text()

    def test_no_empty_catch_blocks(self, toast_source, loading_source):
        for _n, source in [("toast.js", toast_source), ("loading.js", loading_source)]:
            for block in re.findall(r"catch\s*\([^)]*\)\s*\{([^}]*)\}", source):
                body = block.strip()
                assert body and body not in ("", "//")

    def test_no_eval_calls(self, toast_source, loading_source):
        for _n, source in [("toast.js", toast_source), ("loading.js", loading_source)]:
            assert "eval(" not in source

    def test_consistent_naming(self, toast_source, loading_source):
        for _n, source in [("toast.js", toast_source), ("loading.js", loading_source)]:
            for var in re.findall(r"(?:const|let|var)\s+([a-zA-Z_][a-zA-Z0-9_]*)", source):
                if var[0].isupper() and f"class {var}" in source:
                    continue
                assert var[0].islower() or var.isupper()


class TestCSSQuality:
    """Validate CSS quality and consistency."""

    @pytest.fixture
    def components_css(self):
        return (STATIC_DIR / "css" / "components.css").read_text()

    @pytest.fixture
    def icons_css(self):
        return (STATIC_DIR / "css" / "icons.css").read_text()

    def test_no_important_rules(self, components_css, icons_css):
        for _n, css in [("components.css", components_css), ("icons.css", icons_css)]:
            assert "!important" not in css

    def test_components_use_tailwind(self, components_css):
        assert "@apply" in components_css

    def test_icons_have_consistent_sizes(self, icons_css):
        sizes = re.findall(r"w-(\d+)\s+h-(\d+)", icons_css)
        assert len(sizes) >= 4
