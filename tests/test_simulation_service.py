"""Tests for services.simulation — on-demand simulation wrapper."""

import pytest

from services.simulation import SIM_DEPTHS, DEFAULT_SIM_DEPTH


class TestSimulationConfig:
    """Test simulation configuration constants."""

    def test_sim_depths_keys(self):
        assert "Quick (100)" in SIM_DEPTHS
        assert "Standard (250)" in SIM_DEPTHS
        assert "Deep (1000)" in SIM_DEPTHS

    def test_sim_depths_values(self):
        assert SIM_DEPTHS["Quick (100)"] == 100
        assert SIM_DEPTHS["Standard (250)"] == 250
        assert SIM_DEPTHS["Deep (1000)"] == 1000

    def test_default_is_not_deep(self):
        """Default should not be Deep to keep initial interactions fast."""
        assert DEFAULT_SIM_DEPTH != "Deep (1000)"
        assert SIM_DEPTHS[DEFAULT_SIM_DEPTH] <= 250
