#!/usr/bin/env python
import mock
import pytest

from cachet_url_monitor.plugins.token_provider import get_token
from cachet_url_monitor.plugins.token_provider import get_token_provider_by_name
from cachet_url_monitor.plugins.token_provider import ConfigurationFileTokenProvider
from cachet_url_monitor.plugins.token_provider import EnvironmentVariableTokenProvider
from cachet_url_monitor.plugins.token_provider import InvalidTokenProviderTypeException
from cachet_url_monitor.plugins.token_provider import TokenNotFoundException


def test_configuration_file_token_provider():
    token_provider = ConfigurationFileTokenProvider({"value": "my_token", "type": "TOKEN"})
    assert token_provider.get_token() == "my_token"


@mock.patch("cachet_url_monitor.plugins.token_provider.os")
def test_environment_variable_token_provider(mock_os):
    mock_os.environ.get.return_value = "my_token"
    token_provider = EnvironmentVariableTokenProvider({"value": "HQ_TOKEN", "type": "ENVIRONMENT_VARIABLE"})
    assert token_provider.get_token() == "my_token"
    mock_os.environ.get.assert_called_with("HQ_TOKEN")


def test_get_token_provider_by_name_token_type():
    assert get_token_provider_by_name("TOKEN") == ConfigurationFileTokenProvider


def test_get_token_provider_by_name_environment_variable_type():
    assert get_token_provider_by_name("ENVIRONMENT_VARIABLE") == EnvironmentVariableTokenProvider


def test_get_token_provider_by_name_invalid_type():
    with pytest.raises(InvalidTokenProviderTypeException) as exception_info:
        get_token_provider_by_name("WRONG")

    assert exception_info.value.__repr__() == "Invalid token provider type: WRONG"


@mock.patch("cachet_url_monitor.plugins.token_provider.os")
def test_get_token_first_succeeds(mock_os):
    mock_os.environ.get.return_value = "my_token_env_var"
    token = get_token([{"value": "HQ_TOKEN", "type": "ENVIRONMENT_VARIABLE"}, {"value": "my_token", "type": "TOKEN"}])
    assert token == "my_token_env_var"
    mock_os.environ.get.assert_called_with("HQ_TOKEN")


@mock.patch("cachet_url_monitor.plugins.token_provider.os")
def test_get_token_second_succeeds(mock_os):
    mock_os.environ.get.return_value = None
    token = get_token([{"value": "HQ_TOKEN", "type": "ENVIRONMENT_VARIABLE"}, {"value": "my_token", "type": "TOKEN"}])
    assert token == "my_token"
    mock_os.environ.get.assert_called_with("HQ_TOKEN")


@mock.patch("cachet_url_monitor.plugins.token_provider.os")
def test_get_token_no_token_found(mock_os):
    mock_os.environ.get.return_value = None
    with pytest.raises(TokenNotFoundException):
        get_token([{"value": "HQ_TOKEN", "type": "ENVIRONMENT_VARIABLE"}])
    mock_os.environ.get.assert_called_with("HQ_TOKEN")


def test_get_token_string_configuration():
    token = get_token("my_token")
    assert token == "my_token"
