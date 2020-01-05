#!/usr/bin/env python
import abc
import copy
import logging
import os
import re
import time

import requests
from yaml import dump

import cachet_url_monitor.latency_unit as latency_unit
import cachet_url_monitor.status as st

# This is the mandatory fields that must be in the configuration file in this
# same exact structure.
configuration_mandatory_fields = ['url', 'method', 'timeout', 'expectation', 'component_id', 'frequency']


class ConfigurationValidationError(Exception):
    """Exception raised when there's a validation error."""

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class ComponentNonexistentError(Exception):
    """Exception raised when the component does not exist."""

    def __init__(self, component_id):
        self.component_id = component_id

    def __str__(self):
        return repr(f'Component with id [{self.component_id}] does not exist.')


class MetricNonexistentError(Exception):
    """Exception raised when the component does not exist."""

    def __init__(self, metric_id):
        self.metric_id = metric_id

    def __str__(self):
        return repr(f'Metric with id [{self.metric_id}] does not exist.')


def get_current_status(endpoint_url, component_id, headers):
    """Retrieves the current status of the component that is being monitored. It will fail if the component does
    not exist or doesn't respond with the expected data.
    :return component status.
    """
    get_status_request = requests.get(f'{endpoint_url}/components/{component_id}', headers=headers)

    if get_status_request.ok:
        # The component exists.
        return int(get_status_request.json()['data']['status'])
    else:
        raise ComponentNonexistentError(component_id)


def normalize_url(url):
    """If passed url doesn't include schema return it with default one - http."""
    if not url.lower().startswith('http'):
        return f'http://{url}'
    return url


class Configuration(object):
    """Represents a configuration file, but it also includes the functionality
    of assessing the API and pushing the results to cachet.
    """

    def __init__(self, config_file, endpoint_index):
        self.endpoint_index = endpoint_index
        self.data = config_file
        self.endpoint = self.data['endpoints'][endpoint_index]
        self.current_fails = 0
        self.trigger_update = True

        if 'name' not in self.endpoint:
            # We have to make this mandatory, otherwise the logs are confusing when there are multiple URLs.
            raise ConfigurationValidationError('name')

        self.logger = logging.getLogger(f'cachet_url_monitor.configuration.Configuration.{self.endpoint["name"]}')

        # Exposing the configuration to confirm it's parsed as expected.
        self.print_out()

        # We need to validate the configuration is correct and then validate the component actually exists.
        self.validate()

        # We store the main information from the configuration file, so we don't keep reading from the data dictionary.
        self.headers = {'X-Cachet-Token': os.environ.get('CACHET_TOKEN') or self.data['cachet']['token']}

        self.endpoint_method = self.endpoint['method']
        self.endpoint_url = self.endpoint['url']
        self.endpoint_url = normalize_url(self.endpoint_url)
        self.endpoint_timeout = self.endpoint.get('timeout') or 1
        self.endpoint_header = self.endpoint.get('header') or None
        self.allowed_fails = self.endpoint.get('allowed_fails') or 0

        self.api_url = os.environ.get('CACHET_API_URL') or self.data['cachet']['api_url']
        self.component_id = self.endpoint['component_id']
        self.metric_id = self.endpoint.get('metric_id')

        if self.metric_id is not None:
            self.default_metric_value = self.get_default_metric_value(self.metric_id)

        # The latency_unit configuration is not mandatory and we fallback to seconds, by default.
        self.latency_unit = self.data['cachet'].get('latency_unit') or 's'

        # We need the current status so we monitor the status changes. This is necessary for creating incidents.
        self.status = get_current_status(self.api_url, self.component_id, self.headers)
        self.previous_status = self.status

        # Get remaining settings
        self.public_incidents = int(self.endpoint['public_incidents'])

        self.logger.info('Monitoring URL: %s %s' % (self.endpoint_method, self.endpoint_url))
        self.expectations = [Expectation.create(expectation) for expectation in self.endpoint['expectation']]
        for expectation in self.expectations:
            self.logger.info('Registered expectation: %s' % (expectation,))

    def get_default_metric_value(self, metric_id):
        """Returns default value for configured metric."""
        get_metric_request = requests.get('%s/metrics/%s' % (self.api_url, metric_id), headers=self.headers)

        if get_metric_request.ok:
            return get_metric_request.json()['data']['default_value']
        else:
            raise MetricNonexistentError(metric_id)

    def get_action(self):
        """Retrieves the action list from the configuration. If it's empty, returns an empty list.
        :return: The list of actions, which can be an empty list.
        """
        if self.endpoint.get('action') is None:
            return []
        else:
            return self.endpoint['action']

    def validate(self):
        """Validates the configuration by verifying the mandatory fields are
        present and in the correct format. If the validation fails, a
        ConfigurationValidationError is raised. Otherwise nothing will happen.
        """
        configuration_errors = []
        for key in configuration_mandatory_fields:
            if key not in self.endpoint:
                configuration_errors.append(key)

        if 'expectation' in self.endpoint:
            if (not isinstance(self.endpoint['expectation'], list) or
                    (isinstance(self.endpoint['expectation'], list) and
                     len(self.endpoint['expectation']) == 0)):
                configuration_errors.append('endpoint.expectation')

        if len(configuration_errors) > 0:
            raise ConfigurationValidationError(
                'Endpoint [%s] failed validation. Missing keys: %s' % (self.endpoint,
                                                                       ', '.join(configuration_errors)))

    def evaluate(self):
        """Sends the request to the URL set in the configuration and executes
        each one of the expectations, one by one. The status will be updated
        according to the expectation results.
        """
        try:
            if self.endpoint_header is not None:
                self.request = requests.request(self.endpoint_method, self.endpoint_url, timeout=self.endpoint_timeout,
                                                headers=self.endpoint_header)
            else:
                self.request = requests.request(self.endpoint_method, self.endpoint_url, timeout=self.endpoint_timeout)
            self.current_timestamp = int(time.time())
        except requests.ConnectionError:
            self.message = 'The URL is unreachable: %s %s' % (self.endpoint_method, self.endpoint_url)
            self.logger.warning(self.message)
            self.status = st.COMPONENT_STATUS_PARTIAL_OUTAGE
            return
        except requests.HTTPError:
            self.message = 'Unexpected HTTP response'
            self.logger.exception(self.message)
            self.status = st.COMPONENT_STATUS_PARTIAL_OUTAGE
            return
        except requests.Timeout:
            self.message = 'Request timed out'
            self.logger.warning(self.message)
            self.status = st.COMPONENT_STATUS_PERFORMANCE_ISSUES
            return

        # We initially assume the API is healthy.
        self.status = st.COMPONENT_STATUS_OPERATIONAL
        self.message = ''
        for expectation in self.expectations:
            status = expectation.get_status(self.request)

            # The greater the status is, the worse the state of the API is.
            if status > self.status:
                self.status = status
                self.message = expectation.get_message(self.request)
                self.logger.info(self.message)

    def print_out(self):
        self.logger.info(f'Current configuration:\n{self.__repr__()}')

    def __repr__(self):
        temporary_data = copy.deepcopy(self.data)
        # Removing the token so we don't leak it in the logs.
        del temporary_data['cachet']['token']
        temporary_data['endpoints'] = temporary_data['endpoints'][self.endpoint_index]

        return dump(temporary_data, default_flow_style=False)

    def if_trigger_update(self):
        """
        Checks if update should be triggered - trigger it for all operational states
        and only for non-operational ones above the configured threshold (allowed_fails).
        """

        if self.status != 1:
            self.current_fails = self.current_fails + 1
            self.logger.warning(f'Failure #{self.current_fails} with threshold set to {self.allowed_fails}')
            if self.current_fails <= self.allowed_fails:
                self.trigger_update = False
                return
        self.current_fails = 0
        self.trigger_update = True

    def push_status(self):
        """Pushes the status of the component to the cachet server. It will update the component
        status based on the previous call to evaluate().
        """
        if self.previous_status == self.status:
            return
        self.previous_status = self.status

        if not self.trigger_update:
            return

        self.api_component_status = get_current_status(self.api_url, self.component_id, self.headers)

        if self.status == self.api_component_status:
            return

        params = {'id': self.component_id, 'status': self.status}
        component_request = requests.put('%s/components/%d' % (self.api_url, self.component_id), params=params,
                                         headers=self.headers)
        if component_request.ok:
            # Successful update
            self.logger.info('Component update: status [%d]' % (self.status,))
        else:
            # Failed to update the API status
            self.logger.warning('Component update failed with status [%d]: API'
                                ' status: [%d]' % (component_request.status_code, self.status))

    def push_metrics(self):
        """Pushes the total amount of seconds the request took to get a response from the URL.
        It only will send a request if the metric id was set in the configuration.
        In case of failed connection trial pushes the default metric value.
        """
        if 'metric_id' in self.data['cachet'] and hasattr(self, 'request'):
            # We convert the elapsed time from the request, in seconds, to the configured unit.
            value = self.default_metric_value if self.status != 1 else latency_unit.convert_to_unit(self.latency_unit,
                                                                                                    self.request.elapsed.total_seconds())
            params = {'id': self.metric_id, 'value': value,
                      'timestamp': self.current_timestamp}
            metrics_request = requests.post('%s/metrics/%d/points' % (self.api_url, self.metric_id), params=params,
                                            headers=self.headers)

            if metrics_request.ok:
                # Successful metrics upload
                self.logger.info('Metric uploaded: %.6f %s' % (value, self.latency_unit))
            else:
                self.logger.warning(f'Metric upload failed with status [{metrics_request.status_code}]')

    def push_incident(self):
        """If the component status has changed, we create a new incident (if this is the first time it becomes unstable)
        or updates the existing incident once it becomes healthy again.
        """
        if not self.trigger_update:
            return
        if hasattr(self, 'incident_id') and self.status == st.COMPONENT_STATUS_OPERATIONAL:
            # If the incident already exists, it means it was unhealthy but now it's healthy again.
            params = {'status': 4, 'visible': self.public_incidents, 'component_id': self.component_id,
                      'component_status': self.status,
                      'notify': True}

            incident_request = requests.put(f'{self.api_url}/incidents/{self.incident_id}', params=params,
                                            headers=self.headers)
            if incident_request.ok:
                # Successful metrics upload
                self.logger.info(
                    f'Incident updated, API healthy again: component status [{self.status}], message: "{self.message}"')
                del self.incident_id
            else:
                self.logger.warning(
                    f'Incident update failed with status [{incident_request.status_code}], message: "{self.message}"')
        elif not hasattr(self, 'incident_id') and self.status != st.COMPONENT_STATUS_OPERATIONAL:
            # This is the first time the incident is being created.
            params = {'name': 'URL unavailable', 'message': self.message, 'status': 1, 'visible': self.public_incidents,
                      'component_id': self.component_id, 'component_status': self.status, 'notify': True}
            incident_request = requests.post(f'{self.api_url}/incidents', params=params, headers=self.headers)
            if incident_request.ok:
                # Successful incident upload.
                self.incident_id = incident_request.json()['data']['id']
                self.logger.info(
                    f'Incident uploaded, API unhealthy: component status [{self.status}], message: "{self.message}"')
            else:
                self.logger.warning(
                    f'Incident upload failed with status [{incident_request.status_code}], message: "{self.message}"')


class Expectation(object):
    """Base class for URL result expectations. Any new expectation should extend
    this class and the name added to create() method.
    """

    @staticmethod
    def create(configuration):
        """Creates a list of expectations based on the configuration types
        list.
        """
        # If a need expectation is created, this is where we need to add it.
        expectations = {
            'HTTP_STATUS': HttpStatus,
            'LATENCY': Latency,
            'REGEX': Regex
        }
        return expectations.get(configuration['type'])(configuration)

    def __init__(self, configuration):
        self.incident_status = self.parse_incident_status(configuration)

    @abc.abstractmethod
    def get_status(self, response):
        """Returns the status of the API, following cachet's component status
        documentation: https://docs.cachethq.io/docs/component-statuses
        """

    @abc.abstractmethod
    def get_message(self, response):
        """Gets the error message."""

    @abc.abstractmethod
    def get_default_incident(self):
        """Returns the default status when this incident happens."""

    def parse_incident_status(self, configuration):
        return st.INCIDENT_MAP.get(configuration.get('incident', None), self.get_default_incident())


class HttpStatus(Expectation):
    def __init__(self, configuration):
        self.status_range = HttpStatus.parse_range(configuration['status_range'])
        super(HttpStatus, self).__init__(configuration)

    @staticmethod
    def parse_range(range_string):
        if isinstance(range_string, int):
            # This happens when there's no range and no dash character, it will be parsed as int already.
            return range_string, range_string + 1

        statuses = range_string.split("-")
        if len(statuses) == 1:
            # When there was no range given, we should treat the first number as a single status check.
            return int(statuses[0]), int(statuses[0]) + 1
        else:
            # We shouldn't look into more than one value, as this is a range value.
            return int(statuses[0]), int(statuses[1])

    def get_status(self, response):
        if self.status_range[0] <= response.status_code < self.status_range[1]:
            return st.COMPONENT_STATUS_OPERATIONAL
        else:
            return self.incident_status

    def get_default_incident(self):
        return st.COMPONENT_STATUS_PARTIAL_OUTAGE

    def get_message(self, response):
        return f'Unexpected HTTP status ({response.status_code})'

    def __str__(self):
        return repr(f'HTTP status range: [{self.status_range[0]}, {self.status_range[1]}[')


class Latency(Expectation):
    def __init__(self, configuration):
        self.threshold = configuration['threshold']
        super(Latency, self).__init__(configuration)

    def get_status(self, response):
        if response.elapsed.total_seconds() <= self.threshold:
            return st.COMPONENT_STATUS_OPERATIONAL
        else:
            return self.incident_status

    def get_default_incident(self):
        return st.COMPONENT_STATUS_PERFORMANCE_ISSUES

    def get_message(self, response):
        return 'Latency above threshold: %.4f seconds' % (response.elapsed.total_seconds(),)

    def __str__(self):
        return repr('Latency threshold: %.4f seconds' % (self.threshold,))


class Regex(Expectation):
    def __init__(self, configuration):
        self.regex_string = configuration['regex']
        self.regex = re.compile(configuration['regex'], re.UNICODE + re.DOTALL)
        super(Regex, self).__init__(configuration)

    def get_status(self, response):
        if self.regex.match(response.text):
            return st.COMPONENT_STATUS_OPERATIONAL
        else:
            return self.incident_status

    def get_default_incident(self):
        return st.COMPONENT_STATUS_PARTIAL_OUTAGE

    def get_message(self, response):
        return 'Regex did not match anything in the body'

    def __str__(self):
        return repr(f'Regex: {self.regex_string}')
