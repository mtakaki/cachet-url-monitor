#!/usr/bin/env python
import unittest
from typing import Dict, List

import requests_mock

from cachet_url_monitor.client import CachetClient
from cachet_url_monitor.status import ComponentStatus

TOKEN: str = 'token_123'
CACHET_URL: str = 'http://foo.localhost'
JSON: Dict[str, List[Dict[str, int]]] = {'data': [{'id': 1}]}


class ClientTest(unittest.TestCase):
    def setUp(self):
        self.client = CachetClient('foo.localhost', TOKEN)

    def test_init(self):
        self.assertEqual(self.client.headers, {'X-Cachet-Token': TOKEN}, 'Header was not set correctly')
        self.assertEqual(self.client.url, CACHET_URL, 'Cachet API URL was set incorrectly')

    @requests_mock.mock()
    def test_get_components(self, m):
        m.get(f'{CACHET_URL}/components', json=JSON, headers={'X-Cachet-Token': TOKEN})
        components = self.client.get_components()

        self.assertEqual(components, [{'id': 1}],
                         'Getting components list is incorrect.')

    @requests_mock.mock()
    def test_get_metrics(self, m):
        m.get(f'{CACHET_URL}/metrics', json=JSON)
        metrics = self.client.get_metrics()

        self.assertEqual(metrics, [{'id': 1}],
                         'Getting metrics list is incorrect.')

    @requests_mock.mock()
    def test_generate_config(self, m):
        def components():
            return {
                'data': [
                    {
                        'id': '1',
                        'name': 'apache',
                        'link': 'http://abc.def',
                        'enabled': True
                    },
                    {
                        'id': '2',
                        'name': 'haproxy',
                        'link': 'http://ghi.jkl',
                        'enabled': False
                    },
                    {
                        'id': '3',
                        'name': 'nginx',
                        'link': 'http://mno.pqr',
                        'enabled': True
                    }
                ]
            }

        m.get(f'{CACHET_URL}/components', json=components(), headers={'X-Cachet-Token': TOKEN})
        config = self.client.generate_config()

        self.assertEqual(config, {
            'cachet': {
                'api_url': CACHET_URL,
                'token': TOKEN
            },
            'endpoints': [
                {
                    'name': 'apache',
                    'url': 'http://abc.def',
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
                    'component_id': '1',
                    'action': [
                        'CREATE_INCIDENT',
                        'UPDATE_STATUS',
                    ],
                    'public_incidents': True,
                },
                {
                    'name': 'nginx',
                    'url': 'http://mno.pqr',
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
                    'component_id': '3',
                    'action': [
                        'CREATE_INCIDENT',
                        'UPDATE_STATUS',
                    ],
                    'public_incidents': True,
                }
            ]
        }, 'Generated config is incorrect.')

    @requests_mock.mock()
    def test_get_default_metric_value(self, m):
        def json():
            return {
                'data': {
                    'default_value': 0.456
                }
            }

        m.get(f'{CACHET_URL}/metrics/123', json=json(), headers={'X-Cachet-Token': TOKEN})
        default_metric_value = self.client.get_default_metric_value(123)

        self.assertEqual(default_metric_value, 0.456,
                         'Getting default metric value is incorrect.')

    @requests_mock.mock()
    def test_get_component_status(self, m):
        def json():
            return {
                'data': {
                    'status': ComponentStatus.OPERATIONAL.value
                }
            }

        m.get(f'{CACHET_URL}/components/123', json=json(), headers={'X-Cachet-Token': TOKEN})
        status = self.client.get_component_status(123)

        self.assertEqual(status, ComponentStatus.OPERATIONAL,
                         'Getting component status value is incorrect.')
