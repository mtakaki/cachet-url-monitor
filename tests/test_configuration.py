#!/usr/bin/env python
import sys
import unittest

import mock
import pytest
import requests
import requests_mock
from yaml import load, SafeLoader

import cachet_url_monitor.status
from cachet_url_monitor.client import CachetClient
import cachet_url_monitor.exceptions

sys.modules['logging'] = mock.Mock()
from cachet_url_monitor.configuration import Configuration
import os


class ConfigurationTest(unittest.TestCase):
    client: CachetClient
    configuration: Configuration

    def setUp(self):
        def getLogger(name):
            self.mock_logger = mock.Mock()
            return self.mock_logger

        sys.modules['logging'].getLogger = getLogger
        self.client = mock.Mock()
        # We set the initial status to OPERATIONAL.
        self.client.get_component_status.return_value = cachet_url_monitor.status.ComponentStatus.OPERATIONAL
        self.configuration = Configuration(
            load(open(os.path.join(os.path.dirname(__file__), 'configs/config.yml'), 'rt'), SafeLoader), 0, self.client,
            'token2')

    def test_init(self):
        self.assertEqual(len(self.configuration.data), 2, 'Number of root elements in config.yml is incorrect')
        self.assertEqual(len(self.configuration.expectations), 3, 'Number of expectations read from file is incorrect')
        self.assertDictEqual(self.configuration.headers, {'X-Cachet-Token': 'token2'}, 'Header was not set correctly')
        self.assertDictEqual(self.configuration.endpoint_header, {'SOME-HEADER': 'SOME-VALUE'}, 'Header is incorrect')

    @requests_mock.mock()
    def test_evaluate(self, m):
        m.get('http://localhost:8080/swagger', text='<body>')
        self.configuration.evaluate()

        self.assertEqual(self.configuration.status, cachet_url_monitor.status.ComponentStatus.OPERATIONAL,
                         'Component status set incorrectly')

    @requests_mock.mock()
    def test_evaluate_without_header(self, m):
        m.get('http://localhost:8080/swagger', text='<body>')
        self.configuration.evaluate()

        self.assertEqual(self.configuration.status, cachet_url_monitor.status.ComponentStatus.OPERATIONAL,
                         'Component status set incorrectly')

    @requests_mock.mock()
    def test_evaluate_with_failure(self, m):
        m.get('http://localhost:8080/swagger', text='<body>', status_code=400)
        self.configuration.evaluate()

        self.assertEqual(self.configuration.status, cachet_url_monitor.status.ComponentStatus.MAJOR_OUTAGE,
                         'Component status set incorrectly or custom incident status is incorrectly parsed')

    @requests_mock.mock()
    def test_evaluate_with_timeout(self, m):
        m.get('http://localhost:8080/swagger', exc=requests.Timeout)
        self.configuration.evaluate()

        self.assertEqual(self.configuration.status, cachet_url_monitor.status.ComponentStatus.PERFORMANCE_ISSUES,
                         'Component status set incorrectly')
        self.mock_logger.warning.assert_called_with('Request timed out')

    @requests_mock.mock()
    def test_evaluate_with_connection_error(self, m):
        m.get('http://localhost:8080/swagger', exc=requests.ConnectionError)
        self.configuration.evaluate()

        self.assertEqual(self.configuration.status, cachet_url_monitor.status.ComponentStatus.PARTIAL_OUTAGE,
                         'Component status set incorrectly')
        self.mock_logger.warning.assert_called_with('The URL is unreachable: GET http://localhost:8080/swagger')

    @requests_mock.mock()
    def test_evaluate_with_http_error(self, m):
        m.get('http://localhost:8080/swagger', exc=requests.HTTPError)
        self.configuration.evaluate()

        self.assertEqual(self.configuration.status, cachet_url_monitor.status.ComponentStatus.PARTIAL_OUTAGE,
                         'Component status set incorrectly')
        self.mock_logger.exception.assert_called_with('Unexpected HTTP response')

    def test_push_status(self):
        self.client.get_component_status.return_value = cachet_url_monitor.status.ComponentStatus.OPERATIONAL
        push_status_response = mock.Mock()
        self.client.push_status.return_value = push_status_response
        push_status_response.ok = True
        self.configuration.status = cachet_url_monitor.status.ComponentStatus.PARTIAL_OUTAGE

        self.configuration.push_status()

        self.client.push_status.assert_called_once_with(1, cachet_url_monitor.status.ComponentStatus.OPERATIONAL)

    def test_push_status_with_failure(self):
        self.client.get_component_status.return_value = cachet_url_monitor.status.ComponentStatus.OPERATIONAL
        push_status_response = mock.Mock()
        self.client.push_status.return_value = push_status_response
        push_status_response.ok = False
        self.configuration.status = cachet_url_monitor.status.ComponentStatus.PARTIAL_OUTAGE

        self.configuration.push_status()

        self.client.push_status.assert_called_once_with(1, cachet_url_monitor.status.ComponentStatus.OPERATIONAL)

    def test_push_status_same_status(self):
        self.client.get_component_status.return_value = cachet_url_monitor.status.ComponentStatus.OPERATIONAL
        self.configuration.status = cachet_url_monitor.status.ComponentStatus.OPERATIONAL

        self.configuration.push_status()

        self.client.push_status.assert_not_called()


class ConfigurationMultipleUrlTest(unittest.TestCase):
    @mock.patch.dict(os.environ, {'CACHET_TOKEN': 'token2'})
    def setUp(self):
        config_yaml = load(open(os.path.join(os.path.dirname(__file__), 'configs/config_multiple_urls.yml'), 'rt'),
                           SafeLoader)
        self.client = []
        self.configuration = []

        for index in range(len(config_yaml['endpoints'])):
            client = mock.Mock()
            self.client.append(client)
            self.configuration.append(Configuration(config_yaml, index, client, 'token2'))

    def test_init(self):
        expected_method = ['GET', 'POST']
        expected_url = ['http://localhost:8080/swagger', 'http://localhost:8080/bar']

        for index in range(len(self.configuration)):
            config = self.configuration[index]
            self.assertEqual(len(config.data), 2, 'Number of root elements in config.yml is incorrect')
            self.assertEqual(len(config.expectations), 1, 'Number of expectations read from file is incorrect')
            self.assertDictEqual(config.headers, {'X-Cachet-Token': 'token2'}, 'Header was not set correctly')

            self.assertEqual(expected_method[index], config.endpoint_method)
            self.assertEqual(expected_url[index], config.endpoint_url)


class ConfigurationNegativeTest(unittest.TestCase):
    @mock.patch.dict(os.environ, {'CACHET_TOKEN': 'token2'})
    def test_init(self):
        with pytest.raises(cachet_url_monitor.configuration.ConfigurationValidationError):
            self.configuration = Configuration(
                load(open(os.path.join(os.path.dirname(__file__), 'configs/config_invalid_type.yml'), 'rt'),
                     SafeLoader), 0, mock.Mock(), 'token2')
