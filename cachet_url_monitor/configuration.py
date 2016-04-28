import abc
import requests
import timeit
from yaml import load


class Configuration(object):
    def __init__(self, config_file):
        #TODO(mtakaki|2016-04-26): Needs validation if the config is correct.
        self.config_file = config_file
        self.data = load(file(self.config_file, 'r'))
        self.expectations = [Expectaction.create(expectation) for expectation
                in self.data['endpoint']['expectation']]

    def evaluate(self):
        self.request = requests.request(self.data['endpoint']['method'],
                self.data['endpoint']['url'])
        self.status = True
        self.message = ''
        for expectation in self.expectations:
            status = expectation.is_healthy(self.request)
            self.status = self.status and status

    def push_status_and_metrics(self):
        if not self.status:
            params = {'id': self.data['cachet']['component_id'], 'status': 0}
            headers = {'X-Cachet-Token': self.data['cachet']['token']}
            incident_request = requests.post('%s/api/v1/components/%d' %
                    (self.data['cachet']['api_url'],
                    self.data['cachet']['component_id']),
                    params=params, headers=headers)

class Expectaction(object):
    @staticmethod
    def create(configuration):
        expectations = {
                'HTTP_STATUS': HttpStatus,
                'LATENCY': Latency
                }
        return expectations.get(configuration['type'])(configuration)

    @abc.abstractmethod
    def is_healthy(self, response):
        """Returns true if the endpoint is healthy and false if otherwise."""

    @abc.abstractmethod
    def get_message(self, response):
        """Gets the error message."""


class HttpStatus(Expectaction):
    def __init__(self, configuration):
        self.status = configuration['status']

    def is_healthy(self, response):
        return response.status_code == self.status

    def get_message(self, response):
        return 'Unexpected HTTP status (%s)' % (response.status_code,)


class Latency(Expectaction):
    def __init__(self, configuration):
        self.threshold = configuration['threshold']

    def is_healthy(self, response):
        return response.elapsed.total_seconds() <= self.threshold 

    def get_message(self, response):
        return 'Latency above threshold: %d' %
    (response.elapsed.total_seconds(),)
