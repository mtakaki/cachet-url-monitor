import json
import os
from typing import Any
from typing import Dict
from typing import Optional

from boto3.session import Session
from botocore.exceptions import ClientError


class TokenProvider:
    def __init__(self):
        pass

    def get_token(self) -> Optional[str]:
        pass


class EnvironmentVariableTokenProvider(TokenProvider):
    variable_name: str

    def __init__(self, config_data: Dict[str, Any]):
        self.variable_name = config_data["value"]

    def get_token(self) -> Optional[str]:
        return os.environ.get(self.variable_name)


class ConfigurationFileTokenProvider(TokenProvider):
    def __init__(self, config_data: Dict[str, Any]):
        self.token = config_data["value"]

    def get_token(self) -> Optional[str]:
        return self.token


class AwsSecretsManagerTokenRetrievalException(Exception):
    def __init__(self, message):
        self.message = message

    def __repr__(self):
        return self.message


class AwsSecretsManagerTokenProvider(TokenProvider):
    def __init__(self, config_data: Dict[str, Any]):
        self.secret_name = config_data["secret_name"]
        self.region = config_data["region"]
        self.secret_key = config_data["secret_key"]

    def get_token(self) -> Optional[str]:
        session = Session()
        client = session.client(service_name="secretsmanager", region_name=self.region)
        try:
            get_secret_value_response = client.get_secret_value(SecretId=self.secret_name)
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                raise AwsSecretsManagerTokenRetrievalException(f"The requested secret {self.secret_name} was not found")
            elif e.response["Error"]["Code"] == "InvalidRequestException":
                raise AwsSecretsManagerTokenRetrievalException("The request was invalid")
            elif e.response["Error"]["Code"] == "InvalidParameterException":
                raise AwsSecretsManagerTokenRetrievalException("The request had invalid params")
        else:
            if "SecretString" in get_secret_value_response:
                secret = json.loads(get_secret_value_response["SecretString"])
                try:
                    return secret[self.secret_key]
                except KeyError:
                    raise AwsSecretsManagerTokenRetrievalException(f"Invalid secret_key parameter: {self.secret_key}")
            else:
                raise AwsSecretsManagerTokenRetrievalException(
                    "Invalid secret format. It should be a SecretString, instead of binary."
                )


TYPE_NAME_TO_CLASS: Dict[str, TokenProvider] = {
    "ENVIRONMENT_VARIABLE": EnvironmentVariableTokenProvider,
    "TOKEN": ConfigurationFileTokenProvider,
    "AWS_SECRETS_MANAGER": AwsSecretsManagerTokenProvider,
}


class InvalidTokenProviderTypeException(Exception):
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"Invalid token provider type: {self.name}"


def get_token_provider_by_name(name: str) -> TokenProvider:
    try:
        return TYPE_NAME_TO_CLASS[name]
    except KeyError:
        raise InvalidTokenProviderTypeException(name)


class TokenNotFoundException(Exception):
    def __repr__(self):
        return "Token could not be found"


def get_token(token_config: Dict[str, Any]) -> str:
    token: str
    if type(token_config) == list:
        for token_provider in token_config:
            provider = get_token_provider_by_name(token_provider["type"])(token_provider)
            token = provider.get_token()
            if token:
                return token
        raise TokenNotFoundException()
    else:
        return os.environ.get("CACHET_TOKEN") or token_config
