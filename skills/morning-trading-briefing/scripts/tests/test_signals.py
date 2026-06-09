"""Tests for signals.py — v2.2 snapshot stamp + good/bad signal helpers."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPTS))

from signals import BAD, GOOD, as_of_et, pct_sign, signal, tag  # noqa: E402


# --------------------------------------------------------------------------- #
# as_of_et
# --------------------------------------------------------------------------- #
def test_as_of_et_extracts_time():
    assert as_of_et("2026-05-27 07:14 ET") == "07:14 ET"


def test_as_of_et_handles_24h():
    assert as_of_et("2026-05-27 15:30 ET") == "15:30 ET"


def test_as_of_et_empty():
    assert as_of_et("") == ""
    assert as_of_et(None) == ""


def test_as_of_et_malformed_degrades():
    # No HH:MM → return the trimmed raw rather than crash.
    assert as_of_et("sometime today") == "sometime today"


# --------------------------------------------------------------------------- #
# pct_sign
# --------------------------------------------------------------------------- #
def test_pct_sign_basic():
    assert pct_sign("+0.4%") == 1
    assert pct_sign("-1.2%") == -1
    assert pct_sign("+$420") == 1
    assert pct_sign("-$80") == -1


def test_pct_sign_unknown_is_zero():
    assert pct_sign("—") == 0
    assert pct_sign("") == 0
    assert pct_sign(None) == 0
    assert pct_sign("n/a") == 0


def test_pct_sign_numbers():
    assert pct_sign(1.5) == 1
    assert pct_sign(-3) == -1
    assert pct_sign(0) == 0


def test_pct_sign_accounting_negative():
    assert pct_sign("(1.2%)") == -1


def test_pct_sign_unicode_minus():
    assert pct_sign("−0.5%") == -1


# --------------------------------------------------------------------------- #
# signal — good-for-your-book (standard risk-on)
# --------------------------------------------------------------------------- #
def test_signal_index_up_is_good():
    assert signal("+0.4%", metric="spy") == GOOD
    assert signal("-0.4%", metric="spy") == BAD


def test_signal_vix_up_is_bad():
    # VIX rising is bad for a long book → inverted.
    assert signal("+8%", metric="vix") == BAD
    assert signal("-8%", metric="vix") == GOOD


def test_signal_yield_up_is_bad():
    assert signal("+5", metric="us10y") == BAD
    assert signal("-5", metric="us10y") == GOOD


def test_signal_dxy_up_is_bad():
    assert signal("+0.3%", metric="dxy") == BAD


def test_signal_pnl_up_is_good():
    assert signal("+$420", metric="day_pnl") == GOOD
    assert signal("-$80", metric="day_pnl") == BAD


def test_signal_flat_is_empty():
    assert signal("—", metric="spy") == ""
    assert signal(None) == ""


def test_signal_default_metric_treats_up_as_good():
    # Generic ticker / mover with no special metric → up is good.
    assert signal("+2.1%") == GOOD
    assert signal("-2.1%") == BAD


# --------------------------------------------------------------------------- #
# tag
# --------------------------------------------------------------------------- #
def test_tag_combines_emoji_and_value():
    assert tag("+0.4%", metric="spy") == f"{GOOD} +0.4%"
    assert tag("+8%", metric="vix") == f"{BAD} +8%"


def test_tag_flat_returns_bare_value():
    assert tag("—", metric="spy") == "—"


def test_tag_none_returns_empty():
    assert tag(None) == ""
