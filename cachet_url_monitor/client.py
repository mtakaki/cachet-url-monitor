#!/usr/bin/env python
import requests
from yaml import dump


def normalize_url(url):
    """If passed url doesn't include schema return it with default one - http."""
    if not url.lower().startswith('http'):
        return f'http://{url}'
    return url


class CachetClient(object):
    """Utility class to automatically generate a config file."""
    def __init__(self, url, token):
        self.url = normalize_url(url)
        self.token = token
        self.headers = {'X-Cachet-Token': token}

    def get_components(self):
        """Retrieves all components registered in cachet-hq"""
        return requests.get(f"{self.url}/components", headers=self.headers).json()['data']

    def get_metrics(self):
        """Retrieves all metrics registered in cachet-hq"""
        return requests.get(f"{self.url}/metrics", headers=self.headers).json()['data']

    def generate_config(self, filename):
        components = self.get_components()
        generated_endpoints = [
            {
                'name': component['name'],
                'url': component['link'],
                'method': 'GET',
                'timeout': 0.1,
                'expectation': [
                    {
                        'type': 'HTTP_STATUS',
                        'status_range': '200-300',
                        'incident': 'MAJOR'
                    }
                ],
                'allowed_fails': 0,
                'frequency': 30,
                'component_id': component['id'],
                'action': [
                    'CREATE_INCIDENT',
                    'UPDATE_STATUS',
                ],
                'public_incidents': True,
            } for component in components if component['enabled']
        ]
        generated_config = {
            'cachet': {
                'api_url': self.url,
                'token': self.token,
            },
            'endpoints': generated_endpoints
        }
        with open(filename, 'w') as file:
            dump(generated_config, file)
