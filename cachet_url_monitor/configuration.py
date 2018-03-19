#!/usr/bin/env python
import abc
import copy
import logging
import os
import re
import time

import requests
from yaml import dump
from yaml import load

import latency_unit
import status as st

# This is the mandatory fields that must be in the configuration file in this
# same exact structure.
configuration_mandatory_fields = {
    'endpoint': ['url', 'method', 'timeout', 'expectation'],
    'cachet': ['api_url', 'token', 'component_id'],
    'frequency': []}


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
        return repr('Component with id [%d] does not exist.' % (self.component_id,))


class MetricNonexistentError(Exception):
    """Exception raised when the component does not exist."""

    def __init__(self, metric_id):
        self.metric_id = metric_id

    def __str__(self):
        return repr('Metric with id [%d] does not exist.' % (self.metric_id,))


def get_current_status(endpoint_url, component_id, headers):
    """Retrieves the current status of the component that is being monitored. It will fail if the component does
    not exist or doesn't respond with the expected data.
    :return component status.
    """
    get_status_request = requests.get('%s/components/%s' % (endpoint_url, component_id), headers=headers)

    if get_status_request.ok:
        # The component exists.
        return get_status_request.json()['data']['status']
    else:
        raise ComponentNonexistentError(component_id)


def normalize_url(url):
    """If passed url doesn't include schema return it with default one - http."""
    if not url.lower().startswith('http'):
        return 'http://%s' % url
    return url


class Configuration(object):
    """Represents a configuration file, but it also includes the functionality
    of assessing the API and pushing the results to cachet.
    """

    def __init__(self, config_file):
        self.logger = logging.getLogger('cachet_url_monitor.configuration.Configuration')
        self.config_file = config_file
        self.data = load(file(self.config_file, 'r'))

        # Exposing the configuration to confirm it's parsed as expected.
        self.print_out()

        # We need to validate the configuration is correct and then validate the component actually exists.
        self.validate()

        # We store the main information from the configuration file, so we don't keep reading from the data dictionary.
        self.headers = {'X-Cachet-Token': os.environ.get('CACHET_TOKEN') or self.data['cachet']['token']}

        self.endpoint_method = os.environ.get('ENDPOINT_METHOD') or self.data['endpoint']['method']
        self.endpoint_url = os.environ.get('ENDPOINT_URL') or self.data['endpoint']['url']
        self.endpoint_url = normalize_url(self.endpoint_url)
        self.endpoint_timeout = os.environ.get('ENDPOINT_TIMEOUT') or self.data['endpoint'].get('timeout') or 1

        self.api_url = os.environ.get('CACHET_API_URL') or self.data['cachet']['api_url']
        self.component_id = os.environ.get('CACHET_COMPONENT_ID') or self.data['cachet']['component_id']
        self.metric_id = os.environ.get('CACHET_METRIC_ID') or self.data['cachet'].get('metric_id')

        if self.metric_id is not None:
            self.default_metric_value = self.get_default_metric_value(self.metric_id)

        # The latency_unit configuration is not mandatory and we fallback to seconds, by default.
        self.latency_unit = os.environ.get('LATENCY_UNIT') or self.data['cachet'].get('latency_unit') or 's'

        # We need the current status so we monitor the status changes. This is necessary for creating incidents.
        self.status = get_current_status(self.api_url, self.component_id, self.headers)

        # Get remaining settings
        self.public_incidents = int(
            os.environ.get('CACHET_PUBLIC_INCIDENTS') or self.data['cachet']['public_incidents'])

        self.logger.info('Monitoring URL: %s %s' % (self.endpoint_method, self.endpoint_url))
        self.expectations = [Expectaction.create(expectation) for expectation in self.data['endpoint']['expectation']]
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
        if self.data['cachet'].get('action') is None:
            return []
        else:
            return self.data['cachet']['action']

    def validate(self):
        """Validates the configuration by verifying the mandatory fields are
        present and in the correct format. If the validation fails, a
        ConfigurationValidationError is raised. Otherwise nothing will happen.
        """
        configuration_errors = []
        for key, sub_entries in configuration_mandatory_fields.iteritems():
            if key not in self.data:
                configuration_errors.append(key)

            for sub_key in sub_entries:
                if sub_key not in self.data[key]:
                    configuration_errors.append('%s.%s' % (key, sub_key))

        if ('endpoint' in self.data and 'expectation' in
            self.data['endpoint']):
            if (not isinstance(self.data['endpoint']['expectation'], list) or
                    (isinstance(self.data['endpoint']['expectation'], list) and
                             len(self.data['endpoint']['expectation']) == 0)):
                configuration_errors.append('endpoint.expectation')

        if len(configuration_errors) > 0:
            raise ConfigurationValidationError(
                'Config file [%s] failed validation. Missing keys: %s' % (self.config_file,
                                                                          ', '.join(configuration_errors)))

    def evaluate(self):
        """Sends the request to the URL set in the configuration and executes
        each one of the expectations, one by one. The status will be updated
        according to the expectation results.
        """
        try:
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
        self.logger.info('Current configuration:\n%s' % (self.__repr__()))

    def __repr__(self):
        temporary_data = copy.deepcopy(self.data)
        # Removing the token so we don't leak it in the logs.
        del temporary_data['cachet']['token']
        return dump(temporary_data, default_flow_style=False)

    def push_status(self):
        """Pushes the status of the component to the cachet server. It will update the component
        status based on the previous call to evaluate().
        """
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
                self.logger.info('Metric uploaded: %.6f seconds' % (value,))
            else:
                self.logger.warning('Metric upload failed with status [%d]' %
                                    (metrics_request.status_code,))

    def push_incident(self):
        """If the component status has changed, we create a new incident (if this is the first time it becomes unstable)
        or updates the existing incident once it becomes healthy again.
        """
        if hasattr(self, 'incident_id') and self.status == st.COMPONENT_STATUS_OPERATIONAL:
            # If the incident already exists, it means it was unhealthy but now it's healthy again.
            params = {'status': 4, 'visible': self.public_incidents, 'component_id': self.component_id,
                      'component_status': self.status,
                      'notify': True}

            incident_request = requests.put('%s/incidents/%d' % (self.api_url, self.incident_id), params=params,
                                            headers=self.headers)
            if incident_request.ok:
                # Successful metrics upload
                self.logger.info(
                    'Incident updated, API healthy again: component status [%d], message: "%s"' % (
                        self.status, self.message))
                del self.incident_id
            else:
                self.logger.warning('Incident update failed with status [%d], message: "%s"' % (
                    incident_request.status_code, self.message))
        elif not hasattr(self, 'incident_id') and self.status != st.COMPONENT_STATUS_OPERATIONAL:
            # This is the first time the incident is being created.
            params = {'name': 'URL unavailable', 'message': self.message, 'status': 1, 'visible': self.public_incidents,
                      'component_id': self.component_id, 'component_status': self.status, 'notify': True}
            incident_request = requests.post('%s/incidents' % (self.api_url,), params=params, headers=self.headers)
            if incident_request.ok:
                # Successful incident upload.
                self.incident_id = incident_request.json()['data']['id']
                self.logger.info(
                    'Incident uploaded, API unhealthy: component status [%d], message: "%s"' % (
                        self.status, self.message))
            else:
                self.logger.warning(
                    'Incident upload failed with status [%d], message: "%s"' % (
                        incident_request.status_code, self.message))


class Expectaction(object):
    """Base class for URL result expectations. Any new excpectation should extend
    this class and the name added to create() method.
    """

    @staticmethod
    def create(configuration):
        """Creates a list of expectations based on the configuration types
        list.
        """
        expectations = {
            'HTTP_STATUS': HttpStatus,
            'LATENCY': Latency,
            'REGEX': Regex
        }
        return expectations.get(configuration['type'])(configuration)

    @abc.abstractmethod
    def get_status(self, response):
        """Returns the status of the API, following cachet's component status
        documentation: https://docs.cachethq.io/docs/component-statuses
        """

    @abc.abstractmethod
    def get_message(self, response):
        """Gets the error message."""


class HttpStatus(Expectaction):
    def __init__(self, configuration):
        self.status_range = HttpStatus.parse_range(configuration['status_range'])

    @staticmethod
    def parse_range(range_string):
        statuses = range_string.split("-")
        if len(statuses) == 1:
            # When there was no range given, we should treat the first number as a single status check.
            return (int(statuses[0]), int(statuses[0]) + 1)
        else:
            # We shouldn't look into more than one value, as this is a range value.
            return (int(statuses[0]), int(statuses[1]))

    def get_status(self, response):
        if response.status_code >= self.status_range[0] and response.status_code < self.status_range[1]:
            return st.COMPONENT_STATUS_OPERATIONAL
        else:
            return st.COMPONENT_STATUS_PARTIAL_OUTAGE

    def get_message(self, response):
        return 'Unexpected HTTP status (%s)' % (response.status_code,)

    def __str__(self):
        return repr('HTTP status range: %s' % (self.status_range,))


class Latency(Expectaction):
    def __init__(self, configuration):
        self.threshold = configuration['threshold']

    def get_status(self, response):
        if response.elapsed.total_seconds() <= self.threshold:
            return st.COMPONENT_STATUS_OPERATIONAL
        else:
            return st.COMPONENT_STATUS_PERFORMANCE_ISSUES

    def get_message(self, response):
        return 'Latency above threshold: %.4f seconds' % (response.elapsed.total_seconds(),)

    def __str__(self):
        return repr('Latency threshold: %.4f seconds' % (self.threshold,))


class Regex(Expectaction):
    def __init__(self, configuration):
        self.regex_string = configuration['regex']
        self.regex = re.compile(configuration['regex'], re.UNICODE + re.DOTALL)

    def get_status(self, response):
        if self.regex.match(response.text):
            return st.COMPONENT_STATUS_OPERATIONAL
        else:
            return st.COMPONENT_STATUS_PARTIAL_OUTAGE

    def get_message(self, response):
        return 'Regex did not match anything in the body'

    def __str__(self):
        return repr('Regex: %s' % (self.regex_string,))
