#!/usr/bin/env python
import mock
import re
import unittest
from cachet_url_monitor.configuration import Expectaction,Latency
from cachet_url_monitor.configuration import HttpStatus,Regex


class LatencyTest(unittest.TestCase):
    def setUp(self):
        self.expectation = Latency({'type': 'LATENCY', 'threshold': 1})

    def test_init(self):
        assert self.expectation.threshold == 1

    def test_get_status_healthy(self):
        def total_seconds():
            return 0.1
        request = mock.Mock()
        elapsed = mock.Mock()
        request.elapsed = elapsed
        elapsed.total_seconds = total_seconds

        assert self.expectation.get_status(request) == 1

    def test_get_status_unhealthy(self):
        def total_seconds():
            return 2
        request = mock.Mock()
        elapsed = mock.Mock()
        request.elapsed = elapsed
        elapsed.total_seconds = total_seconds

        assert self.expectation.get_status(request) == 2

    def test_get_message(self):
        def total_seconds():
            return 0.1
        request = mock.Mock()
        elapsed = mock.Mock()
        request.elapsed = elapsed
        elapsed.total_seconds = total_seconds

        assert self.expectation.get_message(request) == ('Latency above '
        'threshold: 0.1000')


class HttpStatusTest(unittest.TestCase):
    def setUp(self):
        self.expectation = HttpStatus({'type': 'HTTP_STATUS', 'status': 200})

    def test_init(self):
        assert self.expectation.status == 200

    def test_get_status_healthy(self):
        request = mock.Mock()
        request.status_code = 200

        assert self.expectation.get_status(request) == 1

    def test_get_status_unhealthy(self):
        request = mock.Mock()
        request.status_code = 400

        assert self.expectation.get_status(request) == 3

    def test_get_message(self):
        request = mock.Mock()
        request.status_code = 400

        assert self.expectation.get_message(request) == ('Unexpected HTTP '
        'status (400)')


class RegexTest(unittest.TestCase):
    def setUp(self):
        self.expectation = Regex({'type': 'REGEX', 'regex': '.*(find stuff).*'})

    def test_init(self):
        assert self.expectation.regex == re.compile('.*(find stuff).*')

    def test_get_status_healthy(self):
        request = mock.Mock()
        request.text = 'We could find stuff in this body.'

        assert self.expectation.get_status(request) == 1

    def test_get_status_unhealthy(self):
        request = mock.Mock()
        request.text = 'We will not find it here'

        assert self.expectation.get_status(request) == 3

    def test_get_message(self):
        request = mock.Mock()
        request.text = 'We will not find it here'

        assert self.expectation.get_message(request) == ('Regex did not match '
        'anything in the body')
