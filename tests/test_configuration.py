#!/usr/bin/env python
import sys
import unittest

import mock
from requests import ConnectionError, HTTPError, Timeout

import cachet_url_monitor.status

sys.modules['requests'] = mock.Mock()
sys.modules['logging'] = mock.Mock()
from cachet_url_monitor.configuration import Configuration
import os


class ConfigurationTest(unittest.TestCase):
    @mock.patch.dict(os.environ, {'CACHET_TOKEN': 'token2'})
    def setUp(self):
        def getLogger(name):
            self.mock_logger = mock.Mock()
            return self.mock_logger

        sys.modules['logging'].getLogger = getLogger

        def get(url, headers):
            get_return = mock.Mock()
            get_return.ok = True
            get_return.json = mock.Mock()
            get_return.json.return_value = {'data': {'status': 1, 'default_value': 0.5}}
            return get_return

        sys.modules['requests'].get = get

        self.configuration = Configuration('config.yml')
        sys.modules['requests'].Timeout = Timeout
        sys.modules['requests'].ConnectionError = ConnectionError
        sys.modules['requests'].HTTPError = HTTPError

    def test_init(self):
        self.assertEqual(len(self.configuration.data), 3, 'Number of root elements in config.yml is incorrect')
        self.assertEqual(len(self.configuration.expectations), 3, 'Number of expectations read from file is incorrect')
        self.assertDictEqual(self.configuration.headers, {'X-Cachet-Token': 'token2'}, 'Header was not set correctly')
        self.assertEqual(self.configuration.api_url, 'https://demo.cachethq.io/api/v1',
                          'Cachet API URL was set incorrectly')
        self.assertDictEqual(self.configuration.endpoint_header, {'SOME-HEADER': 'SOME-VALUE'}, 'Header is incorrect')

    def test_evaluate(self):
        def total_seconds():
            return 0.1

        def request(method, url, headers, timeout=None):
            response = mock.Mock()
            response.status_code = 200
            response.elapsed = mock.Mock()
            response.elapsed.total_seconds = total_seconds
            response.text = '<body>'
            return response

        sys.modules['requests'].request = request
        self.configuration.evaluate()

        self.assertEqual(self.configuration.status, cachet_url_monitor.status.COMPONENT_STATUS_OPERATIONAL,
                          'Component status set incorrectly')

    def test_evaluate_without_header(self):
        def total_seconds():
            return 0.1

        def request(method, url, headers=None, timeout=None):
            response = mock.Mock()
            response.status_code = 200
            response.elapsed = mock.Mock()
            response.elapsed.total_seconds = total_seconds
            response.text = '<body>'
            return response

        sys.modules['requests'].request = request
        self.configuration.evaluate()

        self.assertEqual(self.configuration.status, cachet_url_monitor.status.COMPONENT_STATUS_OPERATIONAL,
                          'Component status set incorrectly')

    def test_evaluate_with_failure(self):
        def total_seconds():
            return 0.1

        def request(method, url, headers, timeout=None):
            response = mock.Mock()
            # We are expecting a 200 response, so this will fail the expectation.
            response.status_code = 400
            response.elapsed = mock.Mock()
            response.elapsed.total_seconds = total_seconds
            response.text = '<body>'
            return response

        sys.modules['requests'].request = request
        self.configuration.evaluate()

        self.assertEqual(self.configuration.status, cachet_url_monitor.status.COMPONENT_STATUS_MAJOR_OUTAGE,
                          'Component status set incorrectly or custom incident status is incorrectly parsed')

    def test_evaluate_with_timeout(self):
        def request(method, url, headers, timeout=None):
            self.assertEqual(method, 'GET', 'Incorrect HTTP method')
            self.assertEqual(url, 'http://localhost:8080/swagger', 'Monitored URL is incorrect')
            self.assertEqual(timeout, 0.010)

            raise Timeout()

        sys.modules['requests'].request = request
        self.configuration.evaluate()

        self.assertEqual(self.configuration.status, cachet_url_monitor.status.COMPONENT_STATUS_PERFORMANCE_ISSUES,
                          'Component status set incorrectly')
        self.mock_logger.warning.assert_called_with('Request timed out')

    def test_evaluate_with_connection_error(self):
        def request(method, url, headers, timeout=None):
            self.assertEqual(method, 'GET', 'Incorrect HTTP method')
            self.assertEqual(url, 'http://localhost:8080/swagger', 'Monitored URL is incorrect')
            self.assertEqual(timeout, 0.010)

            raise ConnectionError()

        sys.modules['requests'].request = request
        self.configuration.evaluate()

        self.assertEqual(self.configuration.status, cachet_url_monitor.status.COMPONENT_STATUS_PARTIAL_OUTAGE,
                          'Component status set incorrectly')
        self.mock_logger.warning.assert_called_with('The URL is unreachable: GET http://localhost:8080/swagger')

    def test_evaluate_with_http_error(self):
        def request(method, url, headers, timeout=None):
            self.assertEqual(method, 'GET', 'Incorrect HTTP method')
            self.assertEqual(url, 'http://localhost:8080/swagger', 'Monitored URL is incorrect')
            self.assertEqual(timeout, 0.010)

            raise HTTPError()

        sys.modules['requests'].request = request
        self.configuration.evaluate()

        self.assertEqual(self.configuration.status, cachet_url_monitor.status.COMPONENT_STATUS_PARTIAL_OUTAGE,
                          'Component status set incorrectly')
        self.mock_logger.exception.assert_called_with('Unexpected HTTP response')

    def test_push_status(self):
        def put(url, params=None, headers=None):
            self.assertEqual(url, 'https://demo.cachethq.io/api/v1/components/1', 'Incorrect cachet API URL')
            self.assertDictEqual(params, {'id': 1, 'status': 1}, 'Incorrect component update parameters')
            self.assertDictEqual(headers, {'X-Cachet-Token': 'token2'}, 'Incorrect component update parameters')

            response = mock.Mock()
            response.status_code = 200
            return response

        sys.modules['requests'].put = put
        self.assertEqual(self.configuration.status, cachet_url_monitor.status.COMPONENT_STATUS_OPERATIONAL,
                          'Incorrect component update parameters')
        self.configuration.push_status()

    def test_push_status_with_failure(self):
        def put(url, params=None, headers=None):
            self.assertEqual(url, 'https://demo.cachethq.io/api/v1/components/1', 'Incorrect cachet API URL')
            self.assertDictEqual(params, {'id': 1, 'status': 1}, 'Incorrect component update parameters')
            self.assertDictEqual(headers, {'X-Cachet-Token': 'token2'}, 'Incorrect component update parameters')

            response = mock.Mock()
            response.status_code = 400
            return response

        sys.modules['requests'].put = put
        self.assertEqual(self.configuration.status, cachet_url_monitor.status.COMPONENT_STATUS_OPERATIONAL,
                          'Incorrect component update parameters')
        self.configuration.push_status()
