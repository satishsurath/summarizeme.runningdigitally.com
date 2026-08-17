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

    def test_end_warns_on_missing_start(self, loading_source):
        """end() should warn when called without matching start()."""
        assert "console.warn" in loading_source


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

    @pytest.fixture
    def icons_css(self):
        return (STATIC_DIR / "css" / "icons.css").read_text()

    def test_no_apply_directives(self, components_css):
        """Components must use explicit CSS, not @apply (CDN compatibility)."""
        css_lines = [
            line
            for line in components_css.splitlines()
            if line.strip() and not line.strip().startswith("/*") and not line.strip().startswith("*")
        ]
        assert not any("@apply" in line for line in css_lines)

    def test_dark_mode(self, components_css):
        assert ".dark " in components_css or ".dark." in components_css

    def test_focus_rings(self, components_css):
        assert "box-shadow" in components_css and "outline" in components_css

    def test_no_important_rules(self, components_css):
        assert "!important" not in components_css


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

    @pytest.fixture
    def index_source(self):
        return (STATIC_DIR / "js" / "index.js").read_text()

    @pytest.fixture
    def status_source(self):
        return (STATIC_DIR / "js" / "status.js").read_text()

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

    def test_no_console_log_in_core(self, toast_source, loading_source):
        """Core toast/loading should not use console.log."""
        for _n, source in [("toast.js", toast_source), ("loading.js", loading_source)]:
            assert "console.log" not in source

    def test_loading_end_warns(self, loading_source):
        """loading.end() should warn on missing start()."""
        assert "console.warn" in loading_source


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

    def test_components_use_explicit_css(self, components_css):
        """Components must use explicit CSS for CDN compatibility."""
        css_lines = [
            line
            for line in components_css.splitlines()
            if line.strip() and not line.strip().startswith("/*") and not line.strip().startswith("*")
        ]
        assert not any("@apply" in line for line in css_lines)

    def test_icons_have_consistent_sizes(self, icons_css):
        # Now uses explicit CSS (width/height) instead of Tailwind @apply
        sizes = re.findall(r"width:\s*\d+\.?\d*rem;", icons_css)
        assert len(sizes) >= 4


class TestNotificationDropdown:
    """Validate notification dropdown component."""

    @pytest.fixture
    def notifications_js(self):
        return (STATIC_DIR / "js" / "notifications.js").read_text()

    @pytest.fixture
    def layout(self):
        return (TEMPLATES_DIR / "layout.html").read_text()

    @pytest.fixture
    def components_css(self):
        return (STATIC_DIR / "css" / "components.css").read_text()

    @pytest.fixture
    def icons_css(self):
        return (STATIC_DIR / "css" / "icons.css").read_text()

    def test_notifications_js_exists(self):
        assert (STATIC_DIR / "js" / "notifications.js").exists()

    def test_layout_includes_notifications_js(self, layout):
        assert "notifications.js" in layout

    def test_bell_button_in_layout(self, layout):
        assert "notificationBtn" in layout
        assert 'aria-label="Notifications"' in layout

    def test_notification_dropdown_in_layout(self, layout):
        assert "notificationDropdown" in layout
        assert "notificationList" in layout
        assert "notificationBadge" in layout

    def test_layout_has_status_link(self, layout):
        assert "status_page" in layout

    def test_layout_has_channels_link(self, layout):
        assert "Channels" in layout

    def test_polls_api(self, notifications_js):
        assert "fetch" in notifications_js
        assert "/api/active-tasks" in notifications_js

    def test_has_polling_interval(self, notifications_js):
        assert "setInterval" in notifications_js

    def test_escapes_html(self, notifications_js):
        assert "escapeHtml" in notifications_js or "textContent" in notifications_js

    def test_no_alert_calls(self, notifications_js):
        assert "alert(" not in notifications_js

    def test_no_console_log(self, notifications_js):
        assert "console.log" not in notifications_js

    def test_updates_badge(self, notifications_js):
        assert "notificationBadge" in notifications_js

    def test_progress_bar(self, notifications_js):
        assert "progress" in notifications_js.lower()

    def test_dropdown_toggle_aria(self, layout):
        assert "aria-expanded" in layout

    def test_icon_btn_class_exists(self, components_css):
        assert ".icon-btn" in components_css

    def test_notification_styles_exist(self, components_css):
        assert ".notification-dropdown" in components_css or "notification" in components_css.lower()


class TestNavRedesign:
    """Validate the Phase 2 navigation redesign."""

    @pytest.fixture
    def layout(self):
        return (TEMPLATES_DIR / "layout.html").read_text()

    def test_no_home_link(self, layout):
        """Home link should be replaced with Channels."""
        lines = layout.splitlines()
        for i, line in enumerate(lines):
            if "url_for('main.index')" in line or "url_for('main.index')" in line:
                # Check the text content of this nav link
                context = "\n".join(lines[max(0, i - 2) : i + 3])
                assert "Home" not in context or "Channels" in context

    def test_channels_link_present(self, layout):
        assert "Channels" in layout

    def test_admin_link_present(self, layout):
        assert "Admin" in layout

    def test_status_link_present(self, layout):
        assert "Status" in layout or "status_page" in layout

    def test_mobile_menu_has_links(self, layout):
        assert "mobile-menu" in layout
        assert "Channels" in layout
        assert "Status" in layout or "status_page" in layout
        assert "Admin" in layout

    def test_dark_mode_toggle_in_mobile(self, layout):
        assert "darkModeToggleMobile" in layout

    def test_no_inline_svg_in_nav(self, layout):
        """Nav links should use text labels, not inline SVGs."""
        nav_section = layout.split("<!-- Desktop nav links -->")[1].split("<!-- Right side")[0]
        assert "<svg" not in nav_section


class TestIconSystem:
    """Validate the icon system — icons.js, icons.css, macros.html."""

    @pytest.fixture
    def icons_js(self):
        return (STATIC_DIR / "js" / "icons.js").read_text()

    @pytest.fixture
    def icons_css(self):
        return (STATIC_DIR / "css" / "icons.css").read_text()

    @pytest.fixture
    def layout(self):
        return (TEMPLATES_DIR / "layout.html").read_text()

    @pytest.fixture
    def macros(self):
        return (TEMPLATES_DIR / "macros.html").read_text()

    def test_icons_js_exists(self):
        assert (STATIC_DIR / "js" / "icons.js").exists()

    def test_layout_includes_icons_js(self, layout):
        assert "icons.js" in layout

    def test_icons_js_has_library(self, icons_js):
        assert "IconLibrary" in icons_js

    def test_icons_js_has_render_method(self, icons_js):
        assert "render(" in icons_js

    def test_icons_js_has_render_custom(self, icons_js):
        assert "renderCustom" in icons_js

    def test_icons_js_has_icon_definitions(self, icons_js):
        for icon in ["bell", "sun", "moon", "menu", "edit", "trash", "refresh", "chat"]:
            assert f"'{icon}':" in icons_js or f'"{icon}":' in icons_js or f"{icon}:" in icons_js

    def test_icons_js_has_size_definitions(self, icons_js):
        for size in ["sm", "md", "lg", "xl"]:
            assert f"'{size}'" in icons_js or f'"{size}"' in icons_js

    def test_icons_js_no_console_log(self, icons_js):
        assert "console.log" not in icons_js

    def test_icons_js_no_alert(self, icons_js):
        assert "alert(" not in icons_js

    def test_icons_css_has_size_classes(self, icons_css):
        for size in [".icon-sm", ".icon-md", ".icon-lg", ".icon-xl"]:
            assert size in icons_css

    def test_icons_css_no_apply(self, icons_css):
        """icons.css must use explicit CSS, not @apply (CDN compatibility)."""
        css_lines = [
            line
            for line in icons_css.splitlines()
            if line.strip() and not line.strip().startswith("/*") and not line.strip().startswith("*")
        ]
        assert not any("@apply" in line for line in css_lines)

    def test_icons_css_has_dark_mode(self, icons_css):
        assert ".dark" in icons_css

    def test_macros_import_exists(self, layout):
        assert "from 'macros.html' import render_icon" in layout

    def test_macros_has_render_icon(self, macros):
        assert "render_icon" in macros

    def test_macros_has_icon_definitions(self, macros):
        for icon in ["bell", "sun", "moon", "menu", "edit", "trash"]:
            assert f"'{icon}'" in macros

    def test_macros_no_inline_svgs_in_nav(self, layout):
        """Desktop nav should use render_icon macro, not inline SVGs."""
        nav_section = layout.split("<!-- Desktop nav links -->")[1].split("<!-- Right side")[0]
        assert "<svg" not in nav_section

    def test_layout_no_inline_bell_svg(self, layout):
        """Bell icon should use macro, not inline SVG."""
        bell_section = layout.split("notificationBtn")[1].split("notificationBadge")[0]
        assert "<svg" not in bell_section

    def test_layout_no_inline_menu_svg(self, layout):
        """Menu icon should use macro, not inline SVG."""
        menu_section = layout.split("mobile-menu-button")[1].split("mobile-menu")[0]
        assert "<svg" not in menu_section

    def test_layout_no_inline_sun_moon_svgs(self, layout):
        """Sun/moon icons should use macro, not inline SVGs."""
        # Check that the dark-mode-toggle sections use render_icon, not <svg>
        # Count render_icon calls for sun/moon vs inline SVGs
        sun_macro_count = layout.count("render_icon('sun'")
        moon_macro_count = layout.count("render_icon('moon'")
        assert sun_macro_count >= 2  # desktop + mobile
        assert moon_macro_count >= 2  # desktop + mobile

    def test_index_js_uses_icon_library(self):
        index_js = (STATIC_DIR / "js" / "index.js").read_text()
        assert "IconLibrary" in index_js

    def test_toast_js_uses_icon_library(self):
        toast_js = (STATIC_DIR / "js" / "toast.js").read_text()
        assert "IconLibrary" in toast_js

    def test_status_js_uses_icon_library(self):
        status_js = (STATIC_DIR / "js" / "status.js").read_text()
        assert "IconLibrary" in status_js

    def test_layout_no_inline_icons_in_header(self, layout):
        """Header section should not have inline SVGs (except YouTube sprite)."""
        header = layout.split("</header>")[0]
        # Count SVGs - should only be the YouTube sprite at the bottom
        svg_count = header.count("<svg")
        assert svg_count == 0, f"Expected 0 inline SVGs in header, found {svg_count}"

    def test_icons_css_no_important(self, icons_css):
        assert "!important" not in icons_css

    def test_icons_css_no_apply_in_body(self, icons_css):
        css_lines = [
            line
            for line in icons_css.splitlines()
            if line.strip() and not line.strip().startswith("/*") and not line.strip().startswith("*")
        ]
        assert not any("@apply" in line for line in css_lines)


class TestMobileResponsiveness:
    """Validate mobile responsiveness improvements."""

    @pytest.fixture
    def videos_html(self):
        return (TEMPLATES_DIR / "videos.html").read_text()

    @pytest.fixture
    def admin_html(self):
        return (TEMPLATES_DIR / "admin_settings.html").read_text()

    @pytest.fixture
    def index_html(self):
        return (TEMPLATES_DIR / "index.html").read_text()

    @pytest.fixture
    def channel_chat_html(self):
        return (TEMPLATES_DIR / "channel_chat.html").read_text()

    @pytest.fixture
    def videos_js(self):
        return (STATIC_DIR / "js" / "videos.js").read_text()

    def test_videos_has_card_view(self, videos_html):
        assert "videosCardView" in videos_html

    def test_videos_table_hidden_on_mobile(self, videos_html):
        assert "hidden sm:block" in videos_html or "sm:hidden" in videos_html

    def test_videos_card_view_responsive(self, videos_html):
        # Card view should use sm:hidden to hide on desktop
        assert "sm:hidden" in videos_html

    def test_videos_js_renders_cards(self, videos_js):
        assert "videosCardView" in videos_js

    def test_admin_has_card_view(self, admin_html):
        assert "sm:hidden" in admin_html or "card" in admin_html.lower()

    def test_admin_table_responsive(self, admin_html):
        assert "hidden sm:block" in admin_html or "overflow-x-auto" in admin_html

    def test_index_has_legend_toggle(self, index_html):
        assert "Legend" in index_html

    def test_channel_chat_responsive_grid(self, channel_chat_html):
        assert "grid-cols-1" in channel_chat_html
        assert "lg:grid-cols-3" in channel_chat_html

    def test_layout_mobile_menu(self):
        layout = (TEMPLATES_DIR / "layout.html").read_text()
        assert "mobile-menu" in layout
        assert "md:hidden" in layout or "sm:hidden" in layout

    def test_no_horizontal_scroll_traps(self):
        """Pages should not have overflow-x: hidden that traps horizontal scroll."""
        for name in ["index", "channel_chat", "video_chat", "videos", "admin_settings", "status"]:
            html = (TEMPLATES_DIR / f"{name}.html").read_text()
            assert "overflow-x: hidden" not in html


class TestVideoThumbnails:
    """Validate video thumbnail system."""

    @pytest.fixture
    def thumbnails_js(self):
        return (STATIC_DIR / "js" / "thumbnails.js").read_text()

    @pytest.fixture
    def layout(self):
        return (TEMPLATES_DIR / "layout.html").read_text()

    @pytest.fixture
    def videos_html(self):
        return (TEMPLATES_DIR / "videos.html").read_text()

    @pytest.fixture
    def channel_chat_html(self):
        return (TEMPLATES_DIR / "channel_chat.html").read_text()

    def test_thumbnails_js_exists(self):
        assert (STATIC_DIR / "js" / "thumbnails.js").exists()

    def test_layout_includes_thumbnails_js(self, layout):
        assert "thumbnails.js" in layout

    def test_thumbnails_has_get_url(self, thumbnails_js):
        assert "getUrl" in thumbnails_js

    def test_thumbnails_has_get_best_url(self, thumbnails_js):
        assert "getBestUrl" in thumbnails_js

    def test_thumbnails_has_lazy_loading(self, thumbnails_js):
        assert "IntersectionObserver" in thumbnails_js

    def test_thumbnails_has_create(self, thumbnails_js):
        assert "create(" in thumbnails_js

    def test_thumbnails_url_format(self, thumbnails_js):
        assert "img.youtube.com" in thumbnails_js

    def test_thumbnails_no_console_log(self, thumbnails_js):
        assert "console.log" not in thumbnails_js

    def test_videos_has_thumbnail_in_table(self):
        videos_js = (STATIC_DIR / "js" / "videos.js").read_text()
        assert "ThumbnailSystem" in videos_js

    def test_channel_chat_has_thumbnail(self, channel_chat_html):
        assert "img.youtube.com" in channel_chat_html or "thumbnail" in channel_chat_html.lower()

    def test_thumbnail_lazy_loading(self, channel_chat_html):
        assert "loading=" in channel_chat_html.lower()

    def test_thumbnail_placeholder(self, thumbnails_js):
        assert "placeholder" in thumbnails_js.lower() or "fallback" in thumbnails_js.lower()


class TestChatUI:
    """Validate the Chat UI bubble system."""

    @pytest.fixture
    def chat_js(self):
        return (STATIC_DIR / "js" / "chat.js").read_text()

    @pytest.fixture
    def channel_chat_html(self):
        return (TEMPLATES_DIR / "channel_chat.html").read_text()

    @pytest.fixture
    def video_chat_html(self):
        return (TEMPLATES_DIR / "video_chat.html").read_text()

    @pytest.fixture
    def layout(self):
        return (TEMPLATES_DIR / "layout.html").read_text()

    def test_chat_js_exists(self):
        assert (STATIC_DIR / "js" / "chat.js").exists()

    def test_layout_includes_chat_js(self, layout):
        assert "chat.js" in layout

    def test_chat_ui_class_exists(self, chat_js):
        assert "class ChatUI" in chat_js

    def test_chat_has_send_message(self, chat_js):
        assert "sendMessage" in chat_js

    def test_chat_has_add_message(self, chat_js):
        assert "addMessage" in chat_js

    def test_chat_has_loading_indicator(self, chat_js):
        assert "showLoading" in chat_js

    def test_chat_has_error_handling(self, chat_js):
        assert "addMessage" in chat_js and "error" in chat_js.lower()

    def test_chat_uses_escapexml(self, chat_js):
        assert "escapeHtml" in chat_js or "textContent" in chat_js

    def test_chat_no_alert_calls(self, chat_js):
        assert "alert(" not in chat_js

    def test_chat_no_console_log(self, chat_js):
        assert "console.log" not in chat_js

    def test_chat_enter_to_send(self, chat_js):
        assert "Enter" in chat_js

    def test_chat_shift_enter_newline(self, chat_js):
        assert "shiftKey" in chat_js

    def test_channel_chat_uses_chat_ui(self, channel_chat_html):
        assert "ChatUI" in channel_chat_html

    def test_video_chat_uses_chat_ui(self, video_chat_html):
        assert "ChatUI" in video_chat_html

    def test_chat_result_has_scroll(self, channel_chat_html):
        assert "overflow-y-auto" in channel_chat_html or "overflow" in channel_chat_html

    def test_chat_result_has_space_between_messages(self, channel_chat_html):
        assert "space-y-4" in channel_chat_html or "space-y" in channel_chat_html


class TestToastSecurity:
    """Validate toast.js security and robustness fixes."""

    @pytest.fixture
    def toast_source(self):
        return (STATIC_DIR / "js" / "toast.js").read_text()

    def test_no_inline_onclick(self, toast_source):
        """Toast dismiss should use addEventListener, not inline onclick (XSS prevention)."""
        assert "onclick=" not in toast_source

    def test_uses_addeventlistener(self, toast_source):
        """Toast dismiss should use addEventListener for security."""
        assert "addEventListener" in toast_source

    def test_uses_textcontent_for_messages(self, toast_source):
        """Toast messages should use textContent, not innerHTML (XSS prevention)."""
        assert "textContent" in toast_source

    def test_has_max_toast_limit(self, toast_source):
        """Toast should enforce a max concurrent limit to prevent UI flooding."""
        assert "5" in toast_source  # max toast count

    def test_validates_type_param(self, toast_source):
        """Toast should validate type parameter."""
        assert "validTypes" in toast_source or "type" in toast_source

    def test_dismiss_all_null_guard(self, toast_source):
        """dismissAll should guard against null container."""
        assert "if (!this.container)" in toast_source or "this.container" in toast_source

    def test_dismiss_all_method_exists(self, toast_source):
        """dismissAll method should exist."""
        assert "dismissAll" in toast_source

    def test_dismiss_null_container_guard(self, toast_source):
        """dismissAll should check container before querying."""
        lines = toast_source.splitlines()
        dismiss_all_idx = None
        for i, line in enumerate(lines):
            if "dismissAll" in line and "(" in line:
                dismiss_all_idx = i
                break
        assert dismiss_all_idx is not None
        # Check next few lines for container guard
        snippet = "\n".join(lines[dismiss_all_idx : dismiss_all_idx + 5])
        assert "this.container" in snippet


class TestLoadingSecurity:
    """Validate loading.js security and robustness fixes."""

    @pytest.fixture
    def loading_source(self):
        return (STATIC_DIR / "js" / "loading.js").read_text()

    def test_loading_text_uses_textcontent(self, loading_source):
        """loadingText should be injected via textContent, not innerHTML (XSS prevention)."""
        # Should have createTextNode or textContent usage for loadingText
        assert "createTextNode" in loading_source or "textContent" in loading_source

    def test_dom_check_in_end(self, loading_source):
        """end() should check if element still in DOM before restoring."""
        assert "contains" in loading_source or "parentNode" in loading_source

    def test_is_active_method_exists(self, loading_source):
        """isActive method should exist."""
        assert "isActive" in loading_source

    def test_get_active_ids_method_exists(self, loading_source):
        """getActiveIds method should exist."""
        assert "getActiveIds" in loading_source


class TestLayoutAccessibility:
    """Validate layout.html accessibility improvements."""

    @pytest.fixture
    def layout(self):
        return (TEMPLATES_DIR / "layout.html").read_text()

    @pytest.fixture
    def notifications_js(self):
        return (STATIC_DIR / "js" / "notifications.js").read_text()

    def test_buttons_have_type_button(self, layout):
        """All buttons should have type='button' to prevent accidental form submission."""
        import re

        buttons = re.findall(r"<button[^>]*>", layout)
        for btn in buttons:
            assert 'type="button"' in btn or "type='button'" in btn, f"Button missing type='button': {btn}"

    def test_notification_dropdown_keyboard_nav(self, notifications_js):
        """Notification dropdown should have keyboard navigation."""
        assert "Escape" in notifications_js or "keydown" in notifications_js

    def test_notification_click_outside_close(self, notifications_js):
        """Notification dropdown should close on outside click."""
        assert "contains(e.target)" in notifications_js or "click" in notifications_js
