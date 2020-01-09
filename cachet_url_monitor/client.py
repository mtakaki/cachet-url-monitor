#!/usr/bin/env python
import requests
from yaml import dump
from cachet_url_monitor import latency_unit, status, exceptions


def normalize_url(url):
    """If passed url doesn't include schema return it with default one - http."""
    if not url.lower().startswith('http'):
        return f'http://{url}'
    return url


class CachetClient(object):
    """Utility class to interact with CahetHQ server."""

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

    def get_default_metric_value(self, metric_id):
        """Returns default value for configured metric."""
        get_metric_request = requests.get(f"{self.api_url}/metrics/{metric_id}", headers=self.headers)

        if get_metric_request.ok:
            return get_metric_request.json()['data']['default_value']
        else:
            raise MetricNonexistentError(metric_id)

    def get_component_status(self, component_id):
        """Retrieves the current status of the given component. It will fail if the component does
        not exist or doesn't respond with the expected data.
        :return component status.
        """
        get_status_request = requests.get(f'{self.url}/components/{component_id}', headers=self.headers)

        if get_status_request.ok:
            # The component exists.
            return status.ComponentStatus(int(get_status_request.json()['data']['status']))
        else:
            raise exceptions.ComponentNonexistentError(component_id)

    def push_status(self, component_id, status):
        """Pushes the status of the component to the cachet server.
        """
        params = {'id': self.component_id, 'status': status}
        return requests.put(f"{self.url}/components/{component_id}", params=params, headers=self.headers)

    def push_metrics(self, metric_id, latency_time_unit, elapsed_time_in_seconds, timestamp):
        """Pushes the total amount of seconds the request took to get a response from the URL.
        """
        value = latency_unit.convert_to_unit(latency_time_unit, elapsed_time_in_seconds)
        params = {'id': metric_id, 'value': value, 'timestamp': timestamp}
        return requests.post(f"{self.url}/metrics/{metric_id}/points", params=params, headers=self.headers)

    def push_incident(self, status_value, is_public_incident, component_id, previous_incident_id=None, message=None):
        """If the component status has changed, we create a new incident (if this is the first time it becomes unstable)
        or updates the existing incident once it becomes healthy again.
        """
        if previous_incident_id and status_value == status.COMPONENT_STATUS_OPERATIONAL:
            # If the incident already exists, it means it was unhealthy but now it's healthy again.
            params = {'status': status.IncidentStatus.FIXED.value, 'visible': is_public_incident,
                      'component_id': component_id, 'component_status': status_value, 'notify': True}

            return requests.put(f'{self.url}/incidents/{previous_incident_id}', params=params, headers=self.headers)
        elif not previous_incident_id and status_value != status.COMPONENT_STATUS_OPERATIONAL:
            # This is the first time the incident is being created.
            params = {'name': 'URL unavailable', 'message': message,
                      'status': status.IncidentStatus.INVESTIGATING.value,
                      'visible': is_public_incident, 'component_id': component_id, 'component_status': status_value,
                      'notify': True}
            return requests.post(f'{self.url}/incidents', params=params, headers=self.headers)
