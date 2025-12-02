"""
Tests for ScreenshotManager class.
"""
import pytest
from unittest.mock import MagicMock, patch, call
from pathlib import Path
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from core.screenshot import ScreenshotManager
from utils.eval_utils import PageUnavailableError


class TestScreenshotManagerInitialization:
    """Tests for ScreenshotManager initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default values."""
        with patch('core.screenshot.Path') as mock_path_class:
            mock_path = MagicMock()
            mock_path_class.return_value = mock_path

            mgr = ScreenshotManager()

            assert mgr.image_format == "png"
            assert mgr.image_quality is None
            assert mgr.sequence == 0
            mock_path.mkdir.assert_called_once_with(exist_ok=True)

    def test_init_with_custom_output_dir(self):
        """Test initialization with custom output directory."""
        with patch('core.screenshot.Path') as mock_path_class:
            mock_path = MagicMock()
            mock_path_class.return_value = mock_path

            mgr = ScreenshotManager(output_dir="custom_screenshots")

            mock_path_class.assert_called_once_with("custom_screenshots")

    def test_init_with_jpeg_format(self):
        """Test initialization with JPEG format."""
        with patch('core.screenshot.Path'):
            mgr = ScreenshotManager(image_format="jpeg", image_quality=85)

            assert mgr.image_format == "jpeg"
            assert mgr.image_quality == 85

    def test_init_with_jpg_format_converts_to_jpeg(self):
        """Test that 'jpg' format is converted to 'jpeg'."""
        with patch('core.screenshot.Path'):
            mgr = ScreenshotManager(image_format="jpg", image_quality=90)

            assert mgr.image_format == "jpeg"
            assert mgr.image_quality == 90

    def test_init_with_png_ignores_quality(self):
        """Test that quality is ignored for PNG format."""
        with patch('core.screenshot.Path'):
            mgr = ScreenshotManager(image_format="png", image_quality=85)

            assert mgr.image_format == "png"
            assert mgr.image_quality is None

    def test_init_with_invalid_format_raises_error(self):
        """Test that invalid format raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported screenshot format"):
            ScreenshotManager(image_format="bmp")

    def test_init_sets_labels_to_none(self):
        """Test that scenario and stage labels are initially None."""
        with patch('core.screenshot.Path'):
            mgr = ScreenshotManager()

            assert mgr.current_scenario_label is None
            assert mgr.current_stage_label is None


class TestRegisterRFCaptureHooks:
    """Tests for register_rf_capture_hooks method."""

    def test_registers_pre_hook(self):
        """Test registering pre-capture hook."""
        with patch('core.screenshot.Path'):
            mgr = ScreenshotManager()
            pre_hook = MagicMock()

            mgr.register_rf_capture_hooks(pre_hook=pre_hook)

            assert mgr._rf_pre_capture_hook is pre_hook

    def test_registers_post_hook(self):
        """Test registering post-capture hook."""
        with patch('core.screenshot.Path'):
            mgr = ScreenshotManager()
            post_hook = MagicMock()

            mgr.register_rf_capture_hooks(post_hook=post_hook)

            assert mgr._rf_post_capture_hook is post_hook

    def test_registers_both_hooks(self):
        """Test registering both hooks."""
        with patch('core.screenshot.Path'):
            mgr = ScreenshotManager()
            pre_hook = MagicMock()
            post_hook = MagicMock()

            mgr.register_rf_capture_hooks(pre_hook=pre_hook, post_hook=post_hook)

            assert mgr._rf_pre_capture_hook is pre_hook
            assert mgr._rf_post_capture_hook is post_hook


class TestBuildFilename:
    """Tests for _build_filename method."""

    def test_builds_filename_with_png(self):
        """Test building filename with PNG format."""
        with patch('core.screenshot.Path') as mock_path_class:
            mock_path = MagicMock()
            mock_path.__truediv__ = MagicMock(return_value=Path("screenshots/001_test.png"))
            mock_path_class.return_value = mock_path

            mgr = ScreenshotManager()
            mgr.sequence = 1

            result = mgr._build_filename("test")

            assert "001_test.png" in str(result)

    def test_builds_filename_with_jpeg(self):
        """Test building filename with JPEG format."""
        with patch('core.screenshot.Path') as mock_path_class:
            mock_path = MagicMock()
            mock_path.__truediv__ = MagicMock(return_value=Path("screenshots/001_test.jpg"))
            mock_path_class.return_value = mock_path

            mgr = ScreenshotManager(image_format="jpeg")
            mgr.sequence = 1

            result = mgr._build_filename("test")

            assert "001_test.jpg" in str(result)

    def test_builds_filename_with_custom_sequence(self):
        """Test building filename with custom sequence number."""
        with patch('core.screenshot.Path') as mock_path_class:
            mock_path = MagicMock()
            mock_path.__truediv__ = MagicMock(return_value=Path("screenshots/042_test.png"))
            mock_path_class.return_value = mock_path

            mgr = ScreenshotManager()

            result = mgr._build_filename("test", sequence=42)

            assert "042_test.png" in str(result)


class TestScreenshotKwargs:
    """Tests for _screenshot_kwargs method."""

    def test_builds_kwargs_for_png(self):
        """Test building kwargs for PNG format."""
        with patch('core.screenshot.Path'):
            mgr = ScreenshotManager()
            filename = Path("test.png")

            kwargs = mgr._screenshot_kwargs(filename)

            assert kwargs["path"] == str(filename)
            assert kwargs["type"] == "png"
            assert kwargs["timeout"] == 15000
            assert "quality" not in kwargs

    def test_builds_kwargs_for_jpeg_with_quality(self):
        """Test building kwargs for JPEG with quality."""
        with patch('core.screenshot.Path'):
            mgr = ScreenshotManager(image_format="jpeg", image_quality=85)
            filename = Path("test.jpg")

            kwargs = mgr._screenshot_kwargs(filename)

            assert kwargs["path"] == str(filename)
            assert kwargs["type"] == "jpeg"
            assert kwargs["quality"] == 85
            assert kwargs["timeout"] == 15000


class TestSanitizeScenarioName:
    """Tests for _sanitize_scenario_name method."""

    def test_preserves_alphanumeric(self):
        """Test preserves alphanumeric characters."""
        with patch('core.screenshot.Path'):
            mgr = ScreenshotManager()

            result = mgr._sanitize_scenario_name("test123")

            assert result == "test123"

    def test_preserves_hyphens_and_underscores(self):
        """Test preserves hyphens and underscores."""
        with patch('core.screenshot.Path'):
            mgr = ScreenshotManager()

            result = mgr._sanitize_scenario_name("test-name_123")

            assert result == "test-name_123"

    def test_replaces_special_characters(self):
        """Test replaces special characters with underscores."""
        with patch('core.screenshot.Path'):
            mgr = ScreenshotManager()

            result = mgr._sanitize_scenario_name("test/name:123")

            assert result == "test_name_123"

    def test_handles_empty_string(self):
        """Test handles empty string."""
        with patch('core.screenshot.Path'):
            mgr = ScreenshotManager()

            result = mgr._sanitize_scenario_name("")

            assert result == "unnamed"

    def test_handles_whitespace_only(self):
        """Test handles whitespace-only string."""
        with patch('core.screenshot.Path'):
            mgr = ScreenshotManager()

            result = mgr._sanitize_scenario_name("   ")

            assert result == "unnamed"

    def test_strips_leading_trailing_underscores(self):
        """Test strips leading and trailing underscores."""
        with patch('core.screenshot.Path'):
            mgr = ScreenshotManager()

            result = mgr._sanitize_scenario_name("___test___")

            assert result == "test"


class TestDefaultOverlayText:
    """Tests for _default_overlay_text method."""

    def test_returns_none_when_no_labels(self):
        """Test returns None when no labels are set."""
        with patch('core.screenshot.Path'):
            mgr = ScreenshotManager()

            result = mgr._default_overlay_text()

            assert result is None

    def test_returns_scenario_only(self):
        """Test returns scenario label only."""
        with patch('core.screenshot.Path'):
            mgr = ScreenshotManager()
            mgr.current_scenario_label = "test_scenario"

            result = mgr._default_overlay_text()

            assert result == "test_scenario"

    def test_returns_scenario_and_stage(self):
        """Test returns both scenario and stage labels."""
        with patch('core.screenshot.Path'):
            mgr = ScreenshotManager()
            mgr.current_scenario_label = "test_scenario"
            mgr.current_stage_label = "test_stage"

            result = mgr._default_overlay_text()

            assert result == "test_scenario / test_stage"


class TestCalculateOverlayTop:
    """Tests for _calculate_overlay_top method."""

    def test_returns_default_when_no_rect(self):
        """Test returns default value when no rect."""
        with patch('core.screenshot.Path'):
            mgr = ScreenshotManager()

            result = mgr._calculate_overlay_top(None)

            assert result == 40.0

    def test_returns_default_when_empty_rect(self):
        """Test returns default value when empty rect."""
        with patch('core.screenshot.Path'):
            mgr = ScreenshotManager()

            result = mgr._calculate_overlay_top({})

            assert result == 40.0

    def test_calculates_from_rect_top(self):
        """Test calculates from rect top value."""
        with patch('core.screenshot.Path'):
            mgr = ScreenshotManager()
            rect = {"top": 100.0}

            result = mgr._calculate_overlay_top(rect)

            assert result == 120.0

    def test_ensures_minimum_value(self):
        """Test ensures minimum value of 10."""
        with patch('core.screenshot.Path'):
            mgr = ScreenshotManager()
            rect = {"top": -50.0}

            result = mgr._calculate_overlay_top(rect)

            assert result == 10.0


class TestSetScenario:
    """Tests for set_scenario method."""

    def test_creates_scenario_directory(self):
        """Test creates scenario directory."""
        with patch('core.screenshot.Path') as mock_path_class:
            mock_output_dir = MagicMock()
            mock_scenario_dir = MagicMock()
            mock_output_dir.__truediv__ = MagicMock(return_value=mock_scenario_dir)
            mock_path_class.return_value = mock_output_dir

            mgr = ScreenshotManager()
            mgr.set_scenario("test_scenario")

            mock_scenario_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)
            assert mgr.current_scenario_label == "test_scenario"

    def test_handles_dotted_scenario_name(self):
        """Test handles dotted scenario names (creates nested folders)."""
        with patch('core.screenshot.Path') as mock_path_class:
            mock_output_dir = MagicMock()
            mock_segment1 = MagicMock()
            mock_segment2 = MagicMock()

            # Setup the path chain
            mock_output_dir.__truediv__ = MagicMock(return_value=mock_segment1)
            mock_segment1.__truediv__ = MagicMock(return_value=mock_segment2)
            mock_path_class.return_value = mock_output_dir

            mgr = ScreenshotManager()
            mgr.set_scenario("parent.child")

            mock_segment2.mkdir.assert_called_once_with(parents=True, exist_ok=True)
            assert mgr.current_scenario_label == "parent.child"

    def test_resets_stage_label(self):
        """Test resets stage label when setting scenario."""
        with patch('core.screenshot.Path'):
            mgr = ScreenshotManager()
            mgr.current_stage_label = "old_stage"

            mgr.set_scenario("new_scenario")

            assert mgr.current_stage_label is None

    def test_handles_none_scenario(self):
        """Test handles None scenario (resets to output dir)."""
        with patch('core.screenshot.Path') as mock_path_class:
            mock_output_dir = MagicMock()
            mock_path_class.return_value = mock_output_dir

            mgr = ScreenshotManager()
            mgr.set_scenario(None)

            assert mgr.current_scenario_label is None
            assert mgr.current_output_dir == mock_output_dir


class TestSetStage:
    """Tests for set_stage method."""

    def test_creates_stage_directory(self):
        """Test creates stage directory within scenario."""
        with patch('core.screenshot.Path') as mock_path_class:
            mock_output_dir = MagicMock()
            mock_stage_dir = MagicMock()
            mock_output_dir.__truediv__ = MagicMock(return_value=mock_stage_dir)
            mock_path_class.return_value = mock_output_dir

            mgr = ScreenshotManager()
            mgr.current_scenario_dir = mock_output_dir
            mgr.set_stage("test_stage")

            mock_stage_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)
            assert mgr.current_stage_label == "test_stage"
            assert mgr.current_output_dir == mock_stage_dir

    def test_uses_output_dir_when_no_scenario_set(self):
        """Test uses output dir when no scenario is set."""
        with patch('core.screenshot.Path') as mock_path_class:
            mock_output_dir = MagicMock()
            mock_stage_dir = MagicMock()
            mock_output_dir.__truediv__ = MagicMock(return_value=mock_stage_dir)
            mock_path_class.return_value = mock_output_dir

            mgr = ScreenshotManager()
            mgr.current_scenario_dir = None
            mgr.set_stage("test_stage")

            assert mgr.current_scenario_dir == mock_output_dir

    def test_handles_none_stage(self):
        """Test handles None stage (uses scenario dir)."""
        with patch('core.screenshot.Path') as mock_path_class:
            mock_output_dir = MagicMock()
            mock_path_class.return_value = mock_output_dir

            mgr = ScreenshotManager()
            mgr.current_scenario_dir = mock_output_dir
            mgr.set_stage(None)

            assert mgr.current_stage_label is None
            assert mgr.current_output_dir == mock_output_dir


class TestRunRFHook:
    """Tests for _run_rf_hook method."""

    def test_runs_hook_when_provided(self):
        """Test runs hook when provided."""
        with patch('core.screenshot.Path'):
            mgr = ScreenshotManager()
            hook = MagicMock()

            mgr._run_rf_hook(hook)

            hook.assert_called_once()

    def test_does_nothing_when_hook_is_none(self):
        """Test does nothing when hook is None."""
        with patch('core.screenshot.Path'):
            mgr = ScreenshotManager()

            # Should not raise exception
            mgr._run_rf_hook(None)

    def test_handles_hook_exception(self):
        """Test handles exception from hook."""
        with patch('core.screenshot.Path'):
            mgr = ScreenshotManager()
            hook = MagicMock(side_effect=Exception("Hook error"))

            # Should not raise, just log
            mgr._run_rf_hook(hook)


class TestCapture:
    """Tests for capture method."""

    @patch('core.screenshot.Path')
    def test_captures_screenshot_successfully(self, mock_path_class):
        """Test successful screenshot capture."""
        mock_path = MagicMock()
        mock_filename = MagicMock()
        mock_path.__truediv__ = MagicMock(return_value=mock_filename)
        mock_path_class.return_value = mock_path

        mgr = ScreenshotManager()
        mock_page = MagicMock()

        result = mgr.capture(mock_page, "test_label")

        mock_page.screenshot.assert_called_once()
        assert mgr.sequence == 1
        assert result == mock_filename

    @patch('core.screenshot.Path')
    def test_skips_capture_when_on_demand_false(self, mock_path_class):
        """Test skips capture when onDemand=False."""
        mock_path = MagicMock()
        mock_path_class.return_value = mock_path

        mgr = ScreenshotManager()
        mock_page = MagicMock()

        result = mgr.capture(mock_page, "test_label", onDemand=False)

        mock_page.screenshot.assert_not_called()
        assert result is None
        assert mgr.sequence == 0

    @patch('core.screenshot.Path')
    def test_adds_overlay_when_text_provided(self, mock_path_class):
        """Test adds overlay when text is provided."""
        mock_path = MagicMock()
        mock_path_class.return_value = mock_path

        mgr = ScreenshotManager()
        mgr._add_overlay = MagicMock()
        mgr._remove_overlay = MagicMock()
        mgr._add_timestamp = MagicMock()
        mgr._remove_timestamp = MagicMock()

        mock_page = MagicMock()

        mgr.capture(mock_page, "test", overlay_text="Test Overlay")

        mgr._add_overlay.assert_called_once_with(mock_page, "Test Overlay")
        mgr._remove_overlay.assert_called_once_with(mock_page)

    @patch('core.screenshot.Path')
    def test_handles_page_unavailable_error(self, mock_path_class):
        """Test handles PageUnavailableError gracefully."""
        mock_path = MagicMock()
        mock_path_class.return_value = mock_path

        mgr = ScreenshotManager()
        mock_page = MagicMock()
        mock_page.screenshot.side_effect = PageUnavailableError("Page closed")

        result = mgr.capture(mock_page, "test")

        assert result is None
        assert mgr.sequence == 0

    @patch('core.screenshot.Path')
    def test_retries_on_timeout(self, mock_path_class):
        """Test retries screenshot on timeout."""
        mock_path = MagicMock()
        mock_path_class.return_value = mock_path

        mgr = ScreenshotManager()
        mgr._add_overlay = MagicMock()
        mgr._remove_overlay = MagicMock()
        mgr._add_timestamp = MagicMock()
        mgr._remove_timestamp = MagicMock()

        mock_page = MagicMock()
        # First call times out, second succeeds
        mock_page.screenshot.side_effect = [
            PlaywrightTimeoutError("Timeout"),
            None
        ]

        result = mgr.capture(mock_page, "test")

        # Should have called screenshot twice (original + retry)
        assert mock_page.screenshot.call_count == 2
        assert mgr.sequence == 1


class TestCaptureRFWindow:
    """Tests for capture_rf_window method."""

    @patch('core.screenshot.Path')
    def test_captures_rf_window_successfully(self, mock_path_class):
        """Test successful RF window capture."""
        mock_path = MagicMock()
        mock_path_class.return_value = mock_path

        mgr = ScreenshotManager()
        mgr._get_element_rect = MagicMock(return_value={"top": 100, "right": 500})

        mock_page = MagicMock()
        mock_locator = MagicMock()
        mock_target = MagicMock()
        mock_locator.first = mock_target

        mock_page.locator.return_value = mock_locator

        result = mgr.capture_rf_window(mock_page, "test_rf")

        mock_target.screenshot.assert_called_once()
        assert mgr.sequence == 1

    @patch('core.screenshot.Path')
    def test_runs_pre_and_post_hooks(self, mock_path_class):
        """Test runs pre and post hooks for RF capture."""
        mock_path = MagicMock()
        mock_path_class.return_value = mock_path

        mgr = ScreenshotManager()
        pre_hook = MagicMock()
        post_hook = MagicMock()
        mgr.register_rf_capture_hooks(pre_hook=pre_hook, post_hook=post_hook)
        mgr._get_element_rect = MagicMock(return_value={})

        mock_page = MagicMock()
        mock_locator = MagicMock()
        mock_target = MagicMock()
        mock_locator.first = mock_target
        mock_page.locator.return_value = mock_locator

        mgr.capture_rf_window(mock_page, "test")

        pre_hook.assert_called_once()
        post_hook.assert_called_once()

    @patch('core.screenshot.Path')
    def test_handles_rf_window_timeout(self, mock_path_class):
        """Test handles RF window timeout."""
        mock_path = MagicMock()
        mock_path_class.return_value = mock_path

        mgr = ScreenshotManager()
        mock_page = MagicMock()
        mock_locator = MagicMock()
        mock_target = MagicMock()
        mock_target.wait_for.side_effect = PlaywrightTimeoutError("Timeout")
        mock_locator.first = mock_target
        mock_page.locator.return_value = mock_locator

        result = mgr.capture_rf_window(mock_page, "test")

        assert result is None
        assert mgr.sequence == 0

    @patch('core.screenshot.Path')
    def test_fallback_to_full_page_on_error(self, mock_path_class):
        """Test falls back to full page screenshot on RF window error."""
        mock_path = MagicMock()
        mock_path_class.return_value = mock_path

        mgr = ScreenshotManager()
        mgr._add_timestamp = MagicMock()
        mgr._remove_timestamp = MagicMock()

        mock_page = MagicMock()
        mock_locator = MagicMock()
        mock_locator.first.wait_for.side_effect = Exception("RF window not found")
        mock_page.locator.return_value = mock_locator

        result = mgr.capture_rf_window(mock_page, "test")

        # Should fall back to page screenshot
        mock_page.screenshot.assert_called_once()
        assert mgr.sequence == 1


class TestGetElementRect:
    """Tests for _get_element_rect method."""

    def test_returns_rect_successfully(self):
        """Test returns element rect successfully."""
        with patch('core.screenshot.Path'):
            with patch('core.screenshot.safe_locator_evaluate') as mock_eval:
                mock_eval.return_value = {"top": 10, "left": 20, "right": 100, "bottom": 50}

                mgr = ScreenshotManager()
                mock_locator = MagicMock()

                result = mgr._get_element_rect(mock_locator)

                assert result == {"top": 10, "left": 20, "right": 100, "bottom": 50}

    def test_returns_empty_dict_on_exception(self):
        """Test returns empty dict on exception."""
        with patch('core.screenshot.Path'):
            with patch('core.screenshot.safe_locator_evaluate') as mock_eval:
                mock_eval.side_effect = Exception("Evaluation failed")

                mgr = ScreenshotManager()
                mock_locator = MagicMock()

                result = mgr._get_element_rect(mock_locator)

                assert result == {}
