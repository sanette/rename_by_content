"""Tests for date validation helpers in rename_by_content.

`rename_by_content` needs optional third-party modules (``magic``,
``exiftool``) at import time; they are stubbed here when unavailable so
these pure date tests run anywhere.
"""
import datetime
import sys
import types

import pytest

for _name in ("magic", "exiftool"):
    try:
        __import__(_name)
    except ImportError:
        sys.modules[_name] = types.ModuleType(_name)

import rename_by_content as rbc


def test_validate_date_rejects_impossible_day():
    assert rbc.validate_date(31, 2, 2020) is False


def test_validate_date_rejects_impossible_month():
    assert rbc.validate_date(10, 13, 2020) is False


def test_validate_date_accepts_leap_day():
    assert rbc.validate_date(29, 2, 2020) is True


def test_validate_date_accepts_ordinary_date():
    assert rbc.validate_date(3, 12, 2018) is True


def test_date_from_string_does_not_crash_on_impossible_date():
    # Used to raise "ValueError: day is out of range for month".
    result = rbc.date_from_string("Meeting on 31/02/2020 at noon")
    assert result == (datetime.datetime(2020, 1, 1), 2)


def test_date_from_string_still_finds_valid_date():
    assert rbc.date_from_string("Le 03/12/18") == (
        datetime.datetime(2018, 12, 3),
        10,
    )
