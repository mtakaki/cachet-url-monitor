#!/usr/bin/env python
import abc
import logging
import re
import requests
import time
from yaml import load


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


class Configuration(object):
    """Represents a configuration file, but it also includes the functionality
    of assessing the API and pushing the results to cachet.
    """
    def __init__(self, config_file):
        #TODO(mtakaki#1|2016-04-28): Accept overriding settings using environment
        # variables so we have a more docker-friendly approach.
        self.logger = logging.getLogger('cachet_url_monitor.configuration.Configuration')
        self.config_file = config_file
        self.data = load(file(self.config_file, 'r'))

        self.validate()

        self.logger.info('Monitoring URL: %s %s' %
            (self.data['endpoint']['method'], self.data['endpoint']['url']))
        self.expectations = [Expectaction.create(expectation) for expectation
                in self.data['endpoint']['expectation']]
        for expectation in self.expectations:
            self.logger.info('Registered expectation: %s' % (expectation,))
        self.headers = {'X-Cachet-Token': self.data['cachet']['token']}

    def validate(self):
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
            raise ConfigurationValidationError(('Config file [%s] failed '
                'validation. Missing keys: %s') % (self.config_file,
                ', '.join(configuration_errors)))

    def evaluate(self):
        """Sends the request to the URL set in the configuration and executes
        each one of the expectations, one by one. The status will be updated
        according to the expectation results.
        """
        try:
            self.request = requests.request(self.data['endpoint']['method'],
                    self.data['endpoint']['url'],
                    timeout=self.data['endpoint']['timeout'])
            self.current_timestamp = int(time.time())
        except requests.ConnectionError:
            self.logger.warning('The URL is unreachable: %s %s' %
                    (self.data['endpoint']['method'],
                        self.data['endpoint']['url']))
            self.status = 3
            return
        except requests.HTTPError:
            self.logger.exception('Unexpected HTTP response')
            self.status = 3
            return
        except requests.Timeout:
            self.logger.warning('Request timed out')
            self.status = 3
            return

        # We initially assume the API is healthy.
        self.status = 1
        for expectation in self.expectations:
            status = expectation.get_status(self.request)

            # The greater the status is, the worse the state of the API is.
            if status > self.status:
                self.status = status

    def push_status(self):
        params = {'id': self.data['cachet']['component_id'], 'status':
                self.status}
        component_request = requests.put('%s/components/%d' %
                (self.data['cachet']['api_url'],
                self.data['cachet']['component_id']),
                params=params, headers=self.headers)
        if component_request.ok:
            # Successful update
            self.logger.info('Component update: status [%d]' % (self.status,))
        else:
            # Failed to update the API status
            self.logger.warning('Component update failed with status [%d]: API'
                    ' status: [%d]' % (component_request.status_code, self.status))

    def push_metrics(self):
        if 'metric_id' in self.data['cachet'] and hasattr(self, 'request'):
            params = {'id': self.data['cachet']['metric_id'], 'value':
                    self.request.elapsed.total_seconds(), 'timestamp':
                    self.current_timestamp}
            metrics_request = requests.post('%s/metrics/%d/points' %
                    (self.data['cachet']['api_url'],
                    self.data['cachet']['metric_id']), params=params,
                    headers=self.headers)

            if metrics_request.ok:
                # Successful metrics upload
                self.logger.info('Metric uploaded: %.6f seconds' %
                        (self.request.elapsed.total_seconds(),))
            else:
                self.logger.warning('Metric upload failed with status [%d]' %
                        (metrics_request.status_code,))


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
        self.status = configuration['status']

    def get_status(self, response):
        if response.status_code == self.status:
            return 1
        else:
            return 3

    def get_message(self, response):
        return 'Unexpected HTTP status (%s)' % (response.status_code,)

    def __str__(self):
        return repr('HTTP status: %s' % (self.status,))


class Latency(Expectaction):
    def __init__(self, configuration):
        self.threshold = configuration['threshold']

    def get_status(self, response):
        if response.elapsed.total_seconds() <= self.threshold:
            return 1
        else:
            return 2

    def get_message(self, response):
        return 'Latency above threshold: %.4f' % (response.elapsed.total_seconds(),)

    def __str__(self):
        return repr('Latency threshold: %.4f' % (self.threshold,))


class Regex(Expectaction):
    def __init__(self, configuration):
        self.regex_string = configuration['regex']
        self.regex = re.compile(configuration['regex'])

    def get_status(self, response):
        if self.regex.match(response.text):
            return 1
        else:
            return 3

    def get_message(self, response):
        return 'Regex did not match anything in the body'

    def __str__(self):
        return repr('Regex: %s' % (self.regex_string,))
