from typing import Any
from typing import Dict
from typing import Optional

import os


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


TYPE_NAME_TO_CLASS: Dict[str, TokenProvider] = {
    "ENVIRONMENT_VARIABLE": EnvironmentVariableTokenProvider,
    "TOKEN": ConfigurationFileTokenProvider,
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
