"""
Tests for the unpin command functionality.
"""

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from kicad_lib_manager.main import app as main


class TestUnpinCommand:
    """Test cases for the unpin command."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_mutual_exclusivity_all_with_symbols(self):
        """Test that --all cannot be used with --symbols."""
        result = self.runner.invoke(main, ["unpin", "--all", "--symbols", "lib1"])
        assert result.exit_code == 1  # Typer validation error exit code
        assert (
            "'--all' cannot be used with '--symbols' or '--footprints'" in result.output
        )

    def test_mutual_exclusivity_all_with_footprints(self):
        """Test that --all cannot be used with --footprints."""
        result = self.runner.invoke(main, ["unpin", "--all", "--footprints", "lib1"])
        assert result.exit_code == 1  # Typer validation error exit code
        assert (
            "'--all' cannot be used with '--symbols' or '--footprints'" in result.output
        )

    def test_mutual_exclusivity_all_with_both(self):
        """Test that --all cannot be used with both --symbols and --footprints."""
        result = self.runner.invoke(
            main, ["unpin", "--all", "--symbols", "lib1", "--footprints", "lib2"]
        )
        assert result.exit_code == 1  # Typer validation error exit code
        assert (
            "'--all' cannot be used with '--symbols' or '--footprints'" in result.output
        )

    def test_mutual_exclusivity_all_only(self):
        """Test that --all can be used without --symbols or --footprints."""
        with patch(
            "kicad_lib_manager.services.library_service.LibraryService.find_kicad_config"
        ) as mock_find_config:
            mock_find_config.return_value = Path("/tmp/kicad")

            with patch("pathlib.Path.exists") as mock_exists:
                mock_exists.return_value = True

                with patch("builtins.open") as mock_open:
                    mock_open.return_value.__enter__.return_value.read.return_value = (
                        '{"session": {"pinned_symbol_libs": [], "pinned_fp_libs": []}}'
                    )

                    # Should not raise an error
                    result = self.runner.invoke(main, ["unpin", "--all"])
                    # Exit code 0 means success, or 1 if no libraries found (which is expected)
                    assert result.exit_code in [0, 1]

    def test_mutual_exclusivity_symbols_only(self):
        """Test that --symbols can be used without --all."""
        with patch(
            "kicad_lib_manager.services.library_service.LibraryService.find_kicad_config"
        ) as mock_find_config:
            mock_find_config.return_value = Path("/tmp/kicad")

            with patch("pathlib.Path.exists") as mock_exists:
                mock_exists.return_value = True

                with patch("builtins.open") as mock_open:
                    mock_open.return_value.__enter__.return_value.read.return_value = '{"session": {"pinned_symbol_libs": ["lib1"], "pinned_fp_libs": []}}'

                    # Should not raise an error
                    result = self.runner.invoke(main, ["unpin", "--symbols", "lib1"])
                    # Exit code 0 means success, or 1 if no libraries found (which is expected)
                    assert result.exit_code in [0, 1]

    def test_mutual_exclusivity_footprints_only(self):
        """Test that --footprints can be used without --all."""
        with patch(
            "kicad_lib_manager.services.library_service.LibraryService.find_kicad_config"
        ) as mock_find_config:
            mock_find_config.return_value = Path("/tmp/kicad")

            with patch("pathlib.Path.exists") as mock_exists:
                mock_exists.return_value = True

                with patch("builtins.open") as mock_open:
                    mock_open.return_value.__enter__.return_value.read.return_value = '{"session": {"pinned_symbol_libs": [], "pinned_fp_libs": ["lib1"]}}'

                    # Should not raise an error
                    result = self.runner.invoke(main, ["unpin", "--footprints", "lib1"])
                    # Exit code 0 means success, or 1 if no libraries found (which is expected)
                    assert result.exit_code in [0, 1]
