#!/usr/bin/env python
import mock
import pytest

from cachet_url_monitor.plugins.token_provider import get_token
from cachet_url_monitor.plugins.token_provider import get_token_provider_by_name
from cachet_url_monitor.plugins.token_provider import AwsSecretsManagerTokenProvider
from cachet_url_monitor.plugins.token_provider import ConfigurationFileTokenProvider
from cachet_url_monitor.plugins.token_provider import EnvironmentVariableTokenProvider
from cachet_url_monitor.plugins.token_provider import InvalidTokenProviderTypeException
from cachet_url_monitor.plugins.token_provider import TokenNotFoundException
from cachet_url_monitor.plugins.token_provider import AwsSecretsManagerTokenRetrievalException

from botocore.exceptions import ClientError


@pytest.fixture()
def mock_boto3():
    with mock.patch("cachet_url_monitor.plugins.token_provider.Session") as _mock_session:
        mock_session = mock.Mock()
        _mock_session.return_value = mock_session

        mock_client = mock.Mock()
        mock_session.client.return_value = mock_client
        yield mock_client


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


def test_get_token_provider_by_name_aws_secrets_manager_type():
    assert get_token_provider_by_name("AWS_SECRETS_MANAGER") == AwsSecretsManagerTokenProvider


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


def test_get_aws_secrets_manager(mock_boto3):
    mock_boto3.get_secret_value.return_value = {"SecretString": '{"token": "my_token"}'}
    token = get_token(
        [{"secret_name": "hq_token", "type": "AWS_SECRETS_MANAGER", "region": "us-west-2", "secret_key": "token"}]
    )
    assert token == "my_token"
    mock_boto3.get_secret_value.assert_called_with(SecretId="hq_token")


def test_get_aws_secrets_manager_incorrect_secret_key(mock_boto3):
    mock_boto3.get_secret_value.return_value = {"SecretString": '{"token": "my_token"}'}
    with pytest.raises(AwsSecretsManagerTokenRetrievalException):
        get_token(
            [
                {
                    "secret_name": "hq_token",
                    "type": "AWS_SECRETS_MANAGER",
                    "region": "us-west-2",
                    "secret_key": "wrong_key",
                }
            ]
        )
    mock_boto3.get_secret_value.assert_called_with(SecretId="hq_token")


def test_get_aws_secrets_manager_binary_secret(mock_boto3):
    mock_boto3.get_secret_value.return_value = {"binary": "it_will_fail"}
    with pytest.raises(AwsSecretsManagerTokenRetrievalException):
        get_token(
            [{"secret_name": "hq_token", "type": "AWS_SECRETS_MANAGER", "region": "us-west-2", "secret_key": "token"}]
        )
    mock_boto3.get_secret_value.assert_called_with(SecretId="hq_token")


def test_get_aws_secrets_manager_resource_not_found_exception(mock_boto3):
    mock_boto3.get_secret_value.side_effect = ClientError(
        error_response={"Error": {"Code": "ResourceNotFoundException"}}, operation_name="get_secret_value"
    )
    with pytest.raises(AwsSecretsManagerTokenRetrievalException):
        get_token(
            [{"secret_name": "hq_token", "type": "AWS_SECRETS_MANAGER", "region": "us-west-2", "secret_key": "token"}]
        )
    mock_boto3.get_secret_value.assert_called_with(SecretId="hq_token")


def test_get_aws_secrets_manager_invalid_request_exception(mock_boto3):
    mock_boto3.get_secret_value.side_effect = ClientError(
        error_response={"Error": {"Code": "InvalidRequestException"}}, operation_name="get_secret_value"
    )
    with pytest.raises(AwsSecretsManagerTokenRetrievalException):
        get_token(
            [{"secret_name": "hq_token", "type": "AWS_SECRETS_MANAGER", "region": "us-west-2", "secret_key": "token"}]
        )
    mock_boto3.get_secret_value.assert_called_with(SecretId="hq_token")


def test_get_aws_secrets_manager_invalid_parameter_exception(mock_boto3):
    mock_boto3.get_secret_value.side_effect = ClientError(
        error_response={"Error": {"Code": "InvalidParameterException"}}, operation_name="get_secret_value"
    )
    with pytest.raises(AwsSecretsManagerTokenRetrievalException):
        get_token(
            [{"secret_name": "hq_token", "type": "AWS_SECRETS_MANAGER", "region": "us-west-2", "secret_key": "token"}]
        )
    mock_boto3.get_secret_value.assert_called_with(SecretId="hq_token")
