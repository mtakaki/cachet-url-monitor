#!/usr/bin/env python
import mock
import unittest
import sys
sys.modules['requests'] = mock.Mock()
from cachet_url_monitor.configuration import Configuration


class ConfigurationTest(unittest.TestCase):
    def setUp(self):
        self.configuration = Configuration('config.yml')

    def test_init(self):
        assert len(self.configuration.data) == 3
        assert len(self.configuration.expectations) == 2

    def test_evaluate(self):
        def total_seconds():
            return 0.1
        def request(method, url, timeout=None):
            response = mock.Mock()
            response.status_code = 200
            response.elapsed = mock.Mock()
            response.elapsed.total_seconds = total_seconds
            return response

        sys.modules['requests'].request = request
        self.configuration.evaluate()

        assert self.configuration.status == 1
