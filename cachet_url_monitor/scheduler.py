#!/usr/bin/env python
import logging
import sys
import time
import copy
from yaml import load

import schedule

from configuration import Configuration


class Agent(object):
    """Monitor agent that will be constantly verifying if the URL is healthy
    and updating the component.
    """

    def __init__(self, configuration, decorators=None):
        self.configuration = configuration
        if decorators is None:
            decorators = []
        self.decorators = decorators

    def execute(self):
        """Will verify the API status and push the status and metrics to the
        cachet server.
        """
        self.configuration.evaluate()
        self.configuration.push_metrics()
        self.configuration.if_trigger_update()

        for decorator in self.decorators:
            decorator.execute(self.configuration)

    def start(self):
        """Sets up the schedule based on the configuration file."""
        schedule.every(self.configuration.data['frequency']).seconds.do(self.execute)


class Decorator(object):
    def execute(self, configuration):
        pass


class UpdateStatusDecorator(Decorator):
    def execute(self, configuration):
        configuration.push_status()


class CreateIncidentDecorator(Decorator):
    def execute(self, configuration):
        configuration.push_incident()


class Scheduler(object):
    def __init__(self, config_file):
        self.logger = logging.getLogger('cachet_url_monitor.scheduler.Scheduler')
        self.configuration = Configuration(config_file)
        self.agent = self.get_agent()

        self.stop = False

    def get_agent(self):
        action_names = {
            'CREATE_INCIDENT': CreateIncidentDecorator,
            'UPDATE_STATUS': UpdateStatusDecorator,
        }
        actions = []
        for action in self.configuration.get_action():
            self.logger.info('Registering action %s' % (action))
            actions.append(action_names[action]())
        return Agent(self.configuration, decorators=actions)

    def start(self):
        self.agent.start()
        self.logger.info('Starting monitor agent...')


def adapter(config_file):
    config = load(open(config_file, 'r'))
    new_config = []
    for endpoint in config['endpoints']:
        new_endpoint = copy.deepcopy(config)
        new_endpoint['cachet']['component_id'] = endpoint.pop('component_id')
        new_endpoint['cachet']['metric_id'] = endpoint.pop('metric_id')
        new_endpoint['endpoint'] = endpoint
        new_endpoint.pop('endpoints')

        new_config.append(new_endpoint)

    return new_config

if __name__ == "__main__":
    FORMAT = "%(levelname)9s [%(asctime)-15s] %(name)s - %(message)s"
    logging.basicConfig(format=FORMAT, level=logging.INFO)
    for handler in logging.root.handlers:
        handler.addFilter(logging.Filter('cachet_url_monitor'))

    if len(sys.argv) <= 1:
        logging.fatal('Missing configuration file argument')
        sys.exit(1)

    endpoints = adapter(sys.argv[1])
    for endpoint in endpoints:
        scheduler = Scheduler(endpoint)
        scheduler.start()

    while True:
        schedule.run_pending()
        time.sleep(1)
