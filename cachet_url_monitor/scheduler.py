#!/usr/bin/env python
import logging
import sys
import threading
import time

import schedule
from yaml import load

from cachet_url_monitor.configuration import Configuration


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
        schedule.every(self.configuration.endpoint['frequency']).seconds.do(self.execute)


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
    def __init__(self, config_file, endpoint_index):
        self.logger = logging.getLogger('cachet_url_monitor.scheduler.Scheduler')
        self.configuration = Configuration(config_file, endpoint_index)
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
        while not self.stop:
            schedule.run_pending()
            time.sleep(self.configuration.endpoint['frequency'])


class NewThread(threading.Thread):
    def __init__(self, scheduler):
        threading.Thread.__init__(self)
        self.scheduler = scheduler

    def run(self):
        self.scheduler.start()


if __name__ == "__main__":
    FORMAT = "%(levelname)9s [%(asctime)-15s] %(name)s - %(message)s"
    logging.basicConfig(format=FORMAT, level=logging.INFO)
    for handler in logging.root.handlers:
        handler.addFilter(logging.Filter('cachet_url_monitor'))

    if len(sys.argv) <= 1:
        logging.getLogger('cachet_url_monitor.scheduler').fatal('Missing configuration file argument')
        sys.exit(1)

    config_file = load(open(sys.argv[1], 'r'))

    if 'api_url' and 'token' not in config_file['cachet'] or ('endpoints' not in config_file):
        logging.getLogger('cachet_url_monitor.scheduler').fatal('Missing mandatory fields')
        sys.exit(1)

    for i in range(len(config_file['endpoints'])):
        NewThread(Scheduler(config_file, i)).start()
