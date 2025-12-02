"""
Tests for PageManager class.
"""
import pytest
from unittest.mock import MagicMock, call, patch
from core.page_manager import PageManager


class TestPageManagerInitialization:
    """Tests for PageManager initialization and setup."""

    def test_init_stores_page_reference(self):
        """Test that PageManager stores the page reference."""
        mock_page = MagicMock()
        mock_page.add_init_script = MagicMock()

        page_mgr = PageManager(mock_page)

        assert page_mgr.page is mock_page

    def test_init_calls_setup_page(self):
        """Test that __init__ triggers page setup."""
        mock_page = MagicMock()
        mock_page.add_init_script = MagicMock()

        page_mgr = PageManager(mock_page)

        # Should have called add_init_script twice (click highlighter + ext animations)
        assert mock_page.add_init_script.call_count == 2

    def test_inject_click_highlighter_adds_script(self):
        """Test that click highlighter script is injected."""
        mock_page = MagicMock()
        mock_page.add_init_script = MagicMock()

        PageManager(mock_page)

        # Check that add_init_script was called
        calls = mock_page.add_init_script.call_args_list

        # First call should be the click highlighter
        click_script = calls[0][0][0]
        assert "document.addEventListener('click'" in click_script
        assert "dot.style.border = '3px solid red'" in click_script
        assert "dot.style.borderRadius = '50%'" in click_script

    def test_disable_ext_animations_adds_script(self):
        """Test that ExtJS animation disable script is injected."""
        mock_page = MagicMock()
        mock_page.add_init_script = MagicMock()

        PageManager(mock_page)

        # Check that add_init_script was called
        calls = mock_page.add_init_script.call_args_list

        # Second call should be the ExtJS animation disabler
        ext_script = calls[1][0][0]
        assert "Ext.enableFx = false" in ext_script
        assert "animation: none !important" in ext_script
        assert "transition: none !important" in ext_script
        assert "__ext_disable_animations" in ext_script


class TestGetRFIframe:
    """Tests for get_rf_iframe method."""

    def test_finds_uxiframe_with_rfmenu_url(self):
        """Test finding the preferred uxiframe with RFMenu in URL."""
        mock_page = MagicMock()
        mock_page.add_init_script = MagicMock()

        # Create mock frames
        mock_main_frame = MagicMock()
        mock_main_frame.name = "main"
        mock_main_frame.url = "https://example.com"
        mock_main_frame.is_detached.return_value = False

        mock_rf_frame = MagicMock()
        mock_rf_frame.name = "uxiframe_rf"
        mock_rf_frame.url = "https://example.com/RFMenu"
        mock_rf_frame.is_detached.return_value = False

        mock_page.frames = [mock_main_frame, mock_rf_frame]
        mock_page.main_frame = mock_main_frame

        page_mgr = PageManager(mock_page)
        result = page_mgr.get_rf_iframe()

        assert result is mock_rf_frame

    def test_finds_uxiframe_without_rfmenu_url(self):
        """Test finding uxiframe even without RFMenu in URL (fallback)."""
        mock_page = MagicMock()
        mock_page.add_init_script = MagicMock()

        # Create mock frames
        mock_main_frame = MagicMock()
        mock_main_frame.name = "main"
        mock_main_frame.url = "https://example.com"
        mock_main_frame.is_detached.return_value = False

        mock_ux_frame = MagicMock()
        mock_ux_frame.name = "uxiframe_other"
        mock_ux_frame.url = "https://example.com/other"
        mock_ux_frame.is_detached.return_value = False

        mock_page.frames = [mock_main_frame, mock_ux_frame]
        mock_page.main_frame = mock_main_frame

        page_mgr = PageManager(mock_page)
        result = page_mgr.get_rf_iframe()

        # Should find the uxiframe as fallback
        assert result is mock_ux_frame

    def test_returns_main_frame_when_no_uxiframe(self):
        """Test returning main frame when no uxiframe is found."""
        mock_page = MagicMock()
        mock_page.add_init_script = MagicMock()

        # Create mock frames - no uxiframe
        mock_main_frame = MagicMock()
        mock_main_frame.name = "main"
        mock_main_frame.url = "https://example.com"
        mock_main_frame.is_detached.return_value = False

        mock_other_frame = MagicMock()
        mock_other_frame.name = "other_frame"
        mock_other_frame.url = "https://example.com/other"
        mock_other_frame.is_detached.return_value = False

        mock_page.frames = [mock_main_frame, mock_other_frame]
        mock_page.main_frame = mock_main_frame

        page_mgr = PageManager(mock_page)
        result = page_mgr.get_rf_iframe()

        # Should return main frame as final fallback
        assert result is mock_main_frame

    def test_skips_detached_frames(self):
        """Test that detached frames are ignored."""
        mock_page = MagicMock()
        mock_page.add_init_script = MagicMock()

        # Create mock frames
        mock_main_frame = MagicMock()
        mock_main_frame.name = "main"
        mock_main_frame.url = "https://example.com"
        mock_main_frame.is_detached.return_value = False

        # Detached frame that should be ignored
        mock_detached_frame = MagicMock()
        mock_detached_frame.name = "uxiframe_rf"
        mock_detached_frame.url = "https://example.com/RFMenu"
        mock_detached_frame.is_detached.return_value = True

        # Live uxiframe
        mock_live_frame = MagicMock()
        mock_live_frame.name = "uxiframe_rf2"
        mock_live_frame.url = "https://example.com/RFMenu"
        mock_live_frame.is_detached.return_value = False

        mock_page.frames = [mock_main_frame, mock_detached_frame, mock_live_frame]
        mock_page.main_frame = mock_main_frame

        page_mgr = PageManager(mock_page)
        result = page_mgr.get_rf_iframe()

        # Should skip detached and find the live frame
        assert result is mock_live_frame

    def test_handles_frame_exception_gracefully(self):
        """Test that exceptions when checking frames are handled gracefully."""
        mock_page = MagicMock()
        mock_page.add_init_script = MagicMock()

        # Create mock frames
        mock_main_frame = MagicMock()
        mock_main_frame.name = "main"
        mock_main_frame.url = "https://example.com"
        mock_main_frame.is_detached.return_value = False

        # Frame that raises exception on is_detached
        mock_bad_frame = MagicMock()
        mock_bad_frame.is_detached.side_effect = Exception("Frame error")

        # Good uxiframe
        mock_good_frame = MagicMock()
        mock_good_frame.name = "uxiframe_rf"
        mock_good_frame.url = "https://example.com/RFMenu"
        mock_good_frame.is_detached.return_value = False

        mock_page.frames = [mock_main_frame, mock_bad_frame, mock_good_frame]
        mock_page.main_frame = mock_main_frame

        page_mgr = PageManager(mock_page)
        result = page_mgr.get_rf_iframe()

        # Should skip the bad frame and find the good one
        assert result is mock_good_frame

    def test_prefers_newest_frames_first(self):
        """Test that newer frames are preferred (reversed iteration)."""
        mock_page = MagicMock()
        mock_page.add_init_script = MagicMock()

        # Create mock frames
        mock_main_frame = MagicMock()
        mock_main_frame.name = "main"
        mock_main_frame.url = "https://example.com"
        mock_main_frame.is_detached.return_value = False

        # Older frame (first in list)
        mock_old_frame = MagicMock()
        mock_old_frame.name = "uxiframe_old"
        mock_old_frame.url = "https://example.com/RFMenu"
        mock_old_frame.is_detached.return_value = False

        # Newer frame (last in list, should be preferred)
        mock_new_frame = MagicMock()
        mock_new_frame.name = "uxiframe_new"
        mock_new_frame.url = "https://example.com/RFMenu"
        mock_new_frame.is_detached.return_value = False

        mock_page.frames = [mock_main_frame, mock_old_frame, mock_new_frame]
        mock_page.main_frame = mock_main_frame

        page_mgr = PageManager(mock_page)
        result = page_mgr.get_rf_iframe()

        # Should return the newer frame (last in list)
        assert result is mock_new_frame

    def test_handles_frame_name_exception(self):
        """Test handling exception when accessing frame.name."""
        mock_page = MagicMock()
        mock_page.add_init_script = MagicMock()

        # Create mock frames
        mock_main_frame = MagicMock()
        mock_main_frame.name = "main"
        mock_main_frame.url = "https://example.com"
        mock_main_frame.is_detached.return_value = False

        # Frame that raises exception on name access
        mock_bad_frame = MagicMock()
        mock_bad_frame.is_detached.return_value = False
        type(mock_bad_frame).name = MagicMock(side_effect=Exception("Name error"))

        # Good frame
        mock_good_frame = MagicMock()
        mock_good_frame.name = "uxiframe_rf"
        mock_good_frame.url = "https://example.com/RFMenu"
        mock_good_frame.is_detached.return_value = False

        mock_page.frames = [mock_main_frame, mock_bad_frame, mock_good_frame]
        mock_page.main_frame = mock_main_frame

        page_mgr = PageManager(mock_page)
        result = page_mgr.get_rf_iframe()

        # Should skip bad frame and find good one
        assert result is mock_good_frame

    def test_empty_frames_list(self):
        """Test behavior with empty frames list."""
        mock_page = MagicMock()
        mock_page.add_init_script = MagicMock()

        mock_main_frame = MagicMock()
        mock_main_frame.name = "main"
        mock_main_frame.is_detached.return_value = False

        mock_page.frames = []
        mock_page.main_frame = mock_main_frame

        page_mgr = PageManager(mock_page)
        result = page_mgr.get_rf_iframe()

        # Should return main frame as final fallback
        assert result is mock_main_frame

    def test_multiple_uxiframes_prefers_rfmenu_url(self):
        """Test that when multiple uxiframes exist, prefer one with RFMenu URL."""
        mock_page = MagicMock()
        mock_page.add_init_script = MagicMock()

        mock_main_frame = MagicMock()
        mock_main_frame.name = "main"
        mock_main_frame.url = "https://example.com"
        mock_main_frame.is_detached.return_value = False

        # uxiframe without RFMenu
        mock_ux_other = MagicMock()
        mock_ux_other.name = "uxiframe_other"
        mock_ux_other.url = "https://example.com/other"
        mock_ux_other.is_detached.return_value = False

        # uxiframe with RFMenu (should be preferred)
        mock_ux_rfmenu = MagicMock()
        mock_ux_rfmenu.name = "uxiframe_rf"
        mock_ux_rfmenu.url = "https://example.com/RFMenu"
        mock_ux_rfmenu.is_detached.return_value = False

        mock_page.frames = [mock_main_frame, mock_ux_other, mock_ux_rfmenu]
        mock_page.main_frame = mock_main_frame

        page_mgr = PageManager(mock_page)
        result = page_mgr.get_rf_iframe()

        # Should prefer the RFMenu frame
        assert result is mock_ux_rfmenu
