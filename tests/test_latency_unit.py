#!/usr/bin/env python

from cachet_url_monitor.latency_unit import convert_to_unit


def test_convert_to_unit_ms():
    assert convert_to_unit("ms", 1) == 1000


def test_convert_to_unit_s():
    assert convert_to_unit("s", 20) == 20


def test_convert_to_unit_m():
    assert convert_to_unit("m", 3) == float(3) / 60


def test_convert_to_unit_h():
    assert convert_to_unit("h", 7200) == 2
