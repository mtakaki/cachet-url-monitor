#!/usr/bin/env python
import abc
import logging
import requests
import timeit
from yaml import load


class Configuration(object):
    """Represents a configuration file, but it also includes the functionality
    of assessing the API and pushing the results to cachet.
    """
    def __init__(self, config_file):
        #TODO(mtakaki|2016-04-26): Needs validation if the config is correct.
        self.config_file = config_file
        self.data = load(file(self.config_file, 'r'))
        self.expectations = [Expectaction.create(expectation) for expectation
                in self.data['endpoint']['expectation']]

    def evaluate(self):
        #TODO(mtakaki|2016-04-27): Add support to configurable timeout.
        try:
            self.request = requests.request(self.data['endpoint']['method'],
                    self.data['endpoint']['url'])
        except requests.ConnectionError:
            logging.warning('The URL is unreachable: %s %s' %
                    (self.data['endpoint']['method'],
                        self.data['endpoint']['url']))
            self.status = 3
            return
        except requests.HTTPError:
            logging.exception('Unexpected HTTP response')
            self.status = 3
            return
        except requests.Timeout:
            logging.warning('Request timed out')
            self.status = 3
            return

        # We, by default, assume the API is healthy.
        self.status = 1
        self.message = ''
        for expectation in self.expectations:
            status = expectation.get_status(self.request)

            # The greater the status is, the worse the state of the API is.
            if status > self.status:
                self.status = status

    def push_status_and_metrics(self):
        params = {'id': self.data['cachet']['component_id'], 'status':
                self.status}
        headers = {'X-Cachet-Token': self.data['cachet']['token']}
        component_request = requests.put('%s/components/%d' %
                (self.data['cachet']['api_url'],
                self.data['cachet']['component_id']),
                params=params, headers=headers)
        if component_request.status_code == 200:
            # Successful update
            logging.info('Component update: status [%d]' % (self.status,))
        else:
            # Failed to update the API status
            logging.warning('Component update failed with status [%d]: API'
                    ' status: [%d]' % (component_request.status_code, self.status))

class Expectaction(object):
    @staticmethod
    def create(configuration):
        expectations = {
                'HTTP_STATUS': HttpStatus,
                'LATENCY': Latency
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


class Latency(Expectaction):
    def __init__(self, configuration):
        self.threshold = configuration['threshold']

    def get_status(self, response):
        if response.elapsed.total_seconds() <= self.threshold:
            return 1
        else:
            return 2

    def get_message(self, response):
        return 'Latency above threshold: %d' % (response.elapsed.total_seconds(),)
