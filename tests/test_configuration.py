#!/usr/bin/env python
import cachet_url_monitor.status
import mock
import unittest
import sys
from requests import ConnectionError,HTTPError,Timeout
sys.modules['requests'] = mock.Mock()
sys.modules['logging'] = mock.Mock()
from cachet_url_monitor.configuration import Configuration

class ConfigurationTest(unittest.TestCase):
    def setUp(self):
        def getLogger(name):
            self.mock_logger = mock.Mock()
            return self.mock_logger
        sys.modules['logging'].getLogger = getLogger

        self.configuration = Configuration('config.yml')
        sys.modules['requests'].Timeout = Timeout
        sys.modules['requests'].ConnectionError = ConnectionError
        sys.modules['requests'].HTTPError = HTTPError

    def test_init(self):
        assert len(self.configuration.data) == 3
        assert len(self.configuration.expectations) == 3

    def test_evaluate(self):
        def total_seconds():
            return 0.1
        def request(method, url, timeout=None):
            response = mock.Mock()
            response.status_code = 200
            response.elapsed = mock.Mock()
            response.elapsed.total_seconds = total_seconds
            response.text = '<body>'
            return response

        sys.modules['requests'].request = request
        self.configuration.evaluate()

        assert self.configuration.status == cachet_url_monitor.status.COMPONENT_STATUS_OPERATIONAL

    def test_evaluate_with_failure(self):
        def total_seconds():
            return 0.1
        def request(method, url, timeout=None):
            response = mock.Mock()
            # We are expecting a 200 response, so this will fail the expectation.
            response.status_code = 400
            response.elapsed = mock.Mock()
            response.elapsed.total_seconds = total_seconds
            response.text = '<body>'
            return response

        sys.modules['requests'].request = request
        self.configuration.evaluate()

        assert self.configuration.status == cachet_url_monitor.status.COMPONENT_STATUS_PARTIAL_OUTAGE

    def test_evaluate_with_timeout(self):
        def request(method, url, timeout=None):
            assert method == 'GET'
            assert url == 'http://localhost:8080/swagger'
            assert timeout == 0.010

            raise Timeout()

        sys.modules['requests'].request = request
        self.configuration.evaluate()

        assert self.configuration.status == cachet_url_monitor.status.COMPONENT_STATUS_PERFORMANCE_ISSUES
        self.mock_logger.warning.assert_called_with('Request timed out')

    def test_evaluate_with_connection_error(self):
        def request(method, url, timeout=None):
            assert method == 'GET'
            assert url == 'http://localhost:8080/swagger'
            assert timeout == 0.010

            raise ConnectionError()

        sys.modules['requests'].request = request
        self.configuration.evaluate()

        assert self.configuration.status == 3
        self.mock_logger.warning.assert_called_with(('The URL is '
            'unreachable: GET http://localhost:8080/swagger'))

    def test_evaluate_with_http_error(self):
        def request(method, url, timeout=None):
            assert method == 'GET'
            assert url == 'http://localhost:8080/swagger'
            assert timeout == 0.010

            raise HTTPError()

        sys.modules['requests'].request = request
        self.configuration.evaluate()

        assert self.configuration.status == 3
        self.mock_logger.exception.assert_called_with(('Unexpected HTTP '
            'response'))

    def test_push_status(self):
        def put(url, params=None, headers=None):
            assert url == 'https://demo.cachethq.io/api/v1/components/1'
            assert params == {'id': 1, 'status': 1}
            assert headers == {'X-Cachet-Token': 'my_token'}

            response = mock.Mock()
            response.status_code = 200
            return response

        sys.modules['requests'].put = put
        self.configuration.status = 1
        self.configuration.push_status()

    def test_push_status_with_failure(self):
        def put(url, params=None, headers=None):
            assert url == 'https://demo.cachethq.io/api/v1/components/1'
            assert params == {'id': 1, 'status': 1}
            assert headers == {'X-Cachet-Token': 'my_token'}

            response = mock.Mock()
            response.status_code = 300
            return response

        sys.modules['requests'].put = put
        self.configuration.status = 1
        self.configuration.push_status()
