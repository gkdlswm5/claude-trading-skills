"""Tests for sparkline.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sparkline import pct_change, spark_label, sparkline  # noqa: E402


def test_sparkline_basic():
    s = sparkline([1, 2, 3, 4, 5, 6, 7, 8])
    assert s == "▁▂▃▄▅▆▇█"
    assert len(s) == 8


def test_sparkline_flat():
    assert sparkline([5, 5, 5]) == "▁▁▁"


def test_sparkline_empty():
    assert sparkline([]) == ""
    assert sparkline([None, "x"]) == ""


def test_pct_change():
    assert pct_change([100, 110]) == 10.0
    assert pct_change([4.40, 4.49]) is not None
    assert pct_change([5]) is None
    assert pct_change([0, 5]) is None  # avoid div-by-zero


def test_spark_label():
    out = spark_label("10Y", [4.40, 4.45, 4.49], unit="%")
    assert out.startswith("10Y ")
    assert "4.49%" in out
    assert "+2.0%" in out
    assert "3pt" in out


def test_spark_label_empty():
    assert spark_label("X", []) == ""
