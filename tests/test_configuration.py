#!/usr/bin/env python
import sys

import mock
import pytest
import requests
import requests_mock
from yaml import load, SafeLoader

import cachet_url_monitor.exceptions
import cachet_url_monitor.status
from cachet_url_monitor.webhook import Webhook

sys.modules['logging'] = mock.Mock()
from cachet_url_monitor.configuration import Configuration
import os


@pytest.fixture()
def mock_client():
    client = mock.Mock()
    client.get_component_status.return_value = cachet_url_monitor.status.ComponentStatus.OPERATIONAL
    yield client


@pytest.fixture()
def config_file():
    with open(os.path.join(os.path.dirname(__file__), 'configs/config.yml'), 'rt') as yaml_file:
        config_file_data = load(yaml_file, SafeLoader)
        yield config_file_data


@pytest.fixture()
def multiple_urls_config_file():
    with open(os.path.join(os.path.dirname(__file__), 'configs/config_multiple_urls.yml'), 'rt') as yaml_file:
        config_file_data = load(yaml_file, SafeLoader)
        yield config_file_data


@pytest.fixture()
def invalid_config_file():
    with open(os.path.join(os.path.dirname(__file__), 'configs/config_invalid_type.yml'), 'rt') as yaml_file:
        config_file_data = load(yaml_file, SafeLoader)
        yield config_file_data


@pytest.fixture()
def webhooks_config_file():
    with open(os.path.join(os.path.dirname(__file__), 'configs/config_webhooks.yml'), 'rt') as yaml_file:
        config_file_data = load(yaml_file, SafeLoader)
        yield config_file_data


@pytest.fixture()
def mock_logger():
    mock_logger = mock.Mock()

    def getLogger(name):
        return mock_logger

    sys.modules['logging'].getLogger = getLogger
    yield mock_logger


@pytest.fixture()
def configuration(config_file, mock_client, mock_logger):
    yield Configuration(config_file, 0, mock_client)


@pytest.fixture()
def webhooks_configuration(webhooks_config_file, mock_client, mock_logger):
    webhooks = []
    for webhook in webhooks_config_file.get('webhooks', []):
        webhooks.append(Webhook(webhook['url'], webhook.get('params', {})))
    yield Configuration(webhooks_config_file, 0, mock_client, webhooks)


@pytest.fixture()
def multiple_urls_configuration(multiple_urls_config_file, mock_client, mock_logger):
    yield [Configuration(multiple_urls_config_file, index, mock_client) for index in
           range(len(multiple_urls_config_file['endpoints']))]


def test_init(configuration):
    assert len(configuration.data) == 2, 'Number of root elements in config.yml is incorrect'
    assert len(configuration.expectations) == 3, 'Number of expectations read from file is incorrect'
    assert configuration.endpoint_header == {'SOME-HEADER': 'SOME-VALUE'}, 'Header is incorrect'
    assert configuration.latency_unit == 'ms'


def test_init_unknown_status(config_file, mock_client):
    mock_client.get_component_status.return_value = cachet_url_monitor.status.ComponentStatus.UNKNOWN
    configuration = Configuration(config_file, 0, mock_client)

    assert configuration.previous_status == cachet_url_monitor.status.ComponentStatus.UNKNOWN


def test_evaluate(configuration):
    with requests_mock.mock() as m:
        m.get('http://localhost:8080/swagger', text='<body>')
        configuration.evaluate()

        assert configuration.status == cachet_url_monitor.status.ComponentStatus.OPERATIONAL, 'Component status set incorrectly'


def test_evaluate_without_header(configuration):
    with requests_mock.mock() as m:
        m.get('http://localhost:8080/swagger', text='<body>')
        configuration.evaluate()

        assert configuration.status == cachet_url_monitor.status.ComponentStatus.OPERATIONAL, 'Component status set incorrectly'


def test_evaluate_with_failure(configuration):
    with requests_mock.mock() as m:
        m.get('http://localhost:8080/swagger', text='<body>', status_code=400)
        configuration.evaluate()

        assert configuration.status == cachet_url_monitor.status.ComponentStatus.MAJOR_OUTAGE, 'Component status set incorrectly or custom incident status is incorrectly parsed'


def test_evaluate_with_timeout(configuration, mock_logger):
    with requests_mock.mock() as m:
        m.get('http://localhost:8080/swagger', exc=requests.Timeout)
        configuration.evaluate()

        assert configuration.status == cachet_url_monitor.status.ComponentStatus.PERFORMANCE_ISSUES, 'Component status set incorrectly'
        mock_logger.warning.assert_called_with('Request timed out')


def test_evaluate_with_connection_error(configuration, mock_logger):
    with requests_mock.mock() as m:
        m.get('http://localhost:8080/swagger', exc=requests.ConnectionError)
        configuration.evaluate()

        assert configuration.status == cachet_url_monitor.status.ComponentStatus.PARTIAL_OUTAGE, 'Component status set incorrectly'
        mock_logger.warning.assert_called_with('The URL is unreachable: GET http://localhost:8080/swagger')


def test_evaluate_with_http_error(configuration, mock_logger):
    with requests_mock.mock() as m:
        m.get('http://localhost:8080/swagger', exc=requests.HTTPError)
        configuration.evaluate()

        assert configuration.status == cachet_url_monitor.status.ComponentStatus.PARTIAL_OUTAGE, 'Component status set incorrectly'
        mock_logger.exception.assert_called_with('Unexpected HTTP response')


def test_webhooks(webhooks_configuration, mock_logger, mock_client):
    assert len(webhooks_configuration.webhooks) == 2
    push_incident_response = mock.Mock()
    push_incident_response.ok = False
    mock_client.push_incident.return_value = push_incident_response
    with requests_mock.mock() as m:
        m.get('http://localhost:8080/swagger', exc=requests.HTTPError)
        m.post('https://push.example.com/foo%20is%20unavailable', text='')
        m.post('https://push.example.com/message?token=%3Capptoken%3E&title=foo+is+unavailable', text='')
        webhooks_configuration.evaluate()

        assert webhooks_configuration.status == cachet_url_monitor.status.ComponentStatus.PARTIAL_OUTAGE, 'Component status set incorrectly'
        mock_logger.exception.assert_called_with('Unexpected HTTP response')
        webhooks_configuration.push_incident()
        mock_logger.info.assert_called_with('Webhook https://push.example.com/message?token=<apptoken> triggered with foo unavailable')


def test_push_status(configuration, mock_client):
    mock_client.get_component_status.return_value = cachet_url_monitor.status.ComponentStatus.PARTIAL_OUTAGE
    push_status_response = mock.Mock()
    mock_client.push_status.return_value = push_status_response
    push_status_response.ok = True
    configuration.previous_status = cachet_url_monitor.status.ComponentStatus.PARTIAL_OUTAGE
    configuration.status = cachet_url_monitor.status.ComponentStatus.OPERATIONAL

    configuration.push_status()

    mock_client.push_status.assert_called_once_with(1, cachet_url_monitor.status.ComponentStatus.OPERATIONAL)


def test_push_status_with_new_failure(configuration, mock_client):
    mock_client.get_component_status.return_value = cachet_url_monitor.status.ComponentStatus.OPERATIONAL
    push_status_response = mock.Mock()
    mock_client.push_status.return_value = push_status_response
    push_status_response.ok = False
    configuration.status = cachet_url_monitor.status.ComponentStatus.PARTIAL_OUTAGE

    configuration.push_status()

    mock_client.push_status.assert_called_once_with(1, cachet_url_monitor.status.ComponentStatus.PARTIAL_OUTAGE)


def test_push_status_same_status(configuration, mock_client):
    mock_client.get_component_status.return_value = cachet_url_monitor.status.ComponentStatus.OPERATIONAL
    configuration.status = cachet_url_monitor.status.ComponentStatus.OPERATIONAL

    configuration.push_status()

    mock_client.push_status.assert_not_called()


def test_init_multiple_urls(multiple_urls_configuration):
    expected_method = ['GET', 'POST']
    expected_url = ['http://localhost:8080/swagger', 'http://localhost:8080/bar']

    assert len(multiple_urls_configuration) == 2
    for index in range(len(multiple_urls_configuration)):
        config = multiple_urls_configuration[index]
        assert len(config.data) == 2, 'Number of root elements in config.yml is incorrect'
        assert len(config.expectations) == 1, 'Number of expectations read from file is incorrect'

        assert expected_method[index] == config.endpoint_method
        assert expected_url[index] == config.endpoint_url


def test_init_invalid_configuration(invalid_config_file, mock_client):
    with pytest.raises(cachet_url_monitor.configuration.ConfigurationValidationError):
        Configuration(invalid_config_file, 0, mock_client)
