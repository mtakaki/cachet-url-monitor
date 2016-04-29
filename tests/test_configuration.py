#!/usr/bin/env python
import unittest
from cachet_url_monitor.configuration import Configuration


class ConfigurationTest(unittest.TestCase):
    def test_init(self):
        configuration = Configuration('config.yml')

        assert len(configuration.data) == 3
        assert len(configuration.expectations) == 2
