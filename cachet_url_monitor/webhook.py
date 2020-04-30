from typing import Dict, Optional

import requests


class Webhook:
    url: str
    params: Dict[str, str]

    def __init__(self, url: str, params: Dict[str, str]):
        self.url = url
        self.params = params

    def push_incident(self, title: str, message: str):
        format_args = {
            "title": title,
            "message": message or title,
        }
        # Interpolate URL and params
        url = self.url.format(**format_args)
        params = {
            name: str(value).format(**format_args)
            for name, value in self.params.items()
        }

        return requests.post(url, params=params)
