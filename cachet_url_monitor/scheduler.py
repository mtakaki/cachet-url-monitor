#!/usr/bin/env python
import logging
import sys
import threading
import time
import os

from yaml import load, SafeLoader

from cachet_url_monitor.client import CachetClient
from cachet_url_monitor.configuration import Configuration
from cachet_url_monitor.webhook import Webhook

cachet_mandatory_fields = ['api_url', 'token']


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
        self.configuration.if_trigger_update()

        for decorator in self.decorators:
            decorator.execute(self.configuration)

class Decorator(object):
    """Defines the actions a user can configure to be executed when there's an incident."""

    def execute(self, configuration):
        pass


class UpdateStatusDecorator(Decorator):
    """Updates the component status when an incident happens."""

    def execute(self, configuration):
        configuration.push_status()


class CreateIncidentDecorator(Decorator):
    """Creates an incident entry on cachet when an incident happens."""

    def execute(self, configuration):
        configuration.push_incident()


class PushMetricsDecorator(Decorator):
    """Updates the URL latency metric."""

    def execute(self, configuration):
        configuration.push_metrics()


class Scheduler(object):
    def __init__(self, configuration, agent):
        self.logger = logging.getLogger('cachet_url_monitor.scheduler.Scheduler')
        self.configuration = configuration
        self.agent = agent
        self.stop = False

    def start(self):
        self.logger.info('Starting monitor agent...')
        while not self.stop:
            self.agent.execute()
            time.sleep(self.configuration.endpoint['frequency'])


class NewThread(threading.Thread):
    def __init__(self, scheduler):
        threading.Thread.__init__(self)
        self.scheduler = scheduler

    def run(self):
        self.scheduler.start()


def build_agent(configuration, logger):
    action_names = {
        'CREATE_INCIDENT': CreateIncidentDecorator,
        'UPDATE_STATUS': UpdateStatusDecorator,
        'PUSH_METRICS': PushMetricsDecorator,
    }
    actions = []
    for action in configuration.get_action():
        logger.info(f'Registering action {action}')
        actions.append(action_names[action]())
    return Agent(configuration, decorators=actions)


def validate_config():
    if 'endpoints' not in config_data.keys():
        fatal_error('Endpoints is a mandatory field')

    if config_data['endpoints'] is None:
        fatal_error('Endpoints array can not be empty')

    for key in cachet_mandatory_fields:
        if key not in config_data['cachet']:
            fatal_error('Missing cachet mandatory fields')


def fatal_error(message):
    logging.getLogger('cachet_url_monitor.scheduler').fatal("%s", message)
    sys.exit(1)


if __name__ == "__main__":
    FORMAT = "%(levelname)9s [%(asctime)-15s] %(name)s - %(message)s"
    logging.basicConfig(format=FORMAT, level=logging.INFO)
    for handler in logging.root.handlers:
        handler.addFilter(logging.Filter('cachet_url_monitor'))

    if len(sys.argv) <= 1:
        logging.getLogger('cachet_url_monitor.scheduler').fatal('Missing configuration file argument')
        sys.exit(1)

    try:
        config_data = load(open(sys.argv[1], 'r'), SafeLoader)
    except FileNotFoundError:
        logging.getLogger('cachet_url_monitor.scheduler').fatal(f'File not found: {sys.argv[1]}')
        sys.exit(1)

    validate_config()

    webhooks = []
    for webhook in config_data.get('webhooks', []):
        webhooks.append(Webhook(webhook['url'], webhook.get('params', {})))

    for endpoint_index in range(len(config_data['endpoints'])):
        token = os.environ.get('CACHET_TOKEN') or config_data['cachet']['token']
        api_url = os.environ.get('CACHET_API_URL') or config_data['cachet']['api_url']
        configuration = Configuration(config_data, endpoint_index, CachetClient(api_url, token), webhooks)
        NewThread(Scheduler(configuration,
                            build_agent(configuration, logging.getLogger('cachet_url_monitor.scheduler')))).start()
