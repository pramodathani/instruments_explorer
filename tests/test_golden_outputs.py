"""Checks that indicator, screener and chart outputs still match the recorded golden files."""

import pytest

from tests import golden_outputs


class TestGoldenOutputs:
    """Compares today's outputs with the golden files recorded before UBI access moved to tradingmachine."""

    @pytest.mark.parametrize('name', golden_outputs.FIXTURE_NAMES)
    def test_outputs_match_golden_file(self, name: str) -> None:
        """Checks one fixture's outputs against its golden file, as text.

        Args:
            name (str): The prices fixture's name.
        """
        outputs = golden_outputs.GoldenOutputs()
        computed = outputs.canonical_text(outputs.compute(name))
        recorded = outputs.read_golden(name)
        assert computed == recorded
