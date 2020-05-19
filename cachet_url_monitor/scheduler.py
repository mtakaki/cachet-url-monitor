#!/usr/bin/env python
import logging
import sys
import threading
import time
import os
from typing import List

from yaml import load, SafeLoader

from cachet_url_monitor.client import CachetClient
from cachet_url_monitor.configuration import Configuration
from cachet_url_monitor.webhook import Webhook
from cachet_url_monitor.plugins.token_provider import get_token

cachet_mandatory_fields = ["api_url", "token"]


class Decorator(object):
    """Defines the actions a user can configure to be executed when there's an incident."""

    def execute(self, configuration: Configuration):
        pass


class UpdateStatusDecorator(Decorator):
    """Updates the component status when an incident happens."""

    def execute(self, configuration: Configuration):
        configuration.push_status()


class CreateIncidentDecorator(Decorator):
    """Creates an incident entry on cachet when an incident happens."""

    def execute(self, configuration: Configuration):
        configuration.push_incident()


class PushMetricsDecorator(Decorator):
    """Updates the URL latency metric."""

    def execute(self, configuration: Configuration):
        configuration.push_metrics()


ACTION_NAMES_DECORATOR_MAP = {
    "CREATE_INCIDENT": CreateIncidentDecorator,
    "UPDATE_STATUS": UpdateStatusDecorator,
    "PUSH_METRICS": PushMetricsDecorator,
}


class Agent(object):
    """Monitor agent that will be constantly verifying if the URL is healthy
    and updating the component.
    """

    configuration: Configuration
    decorators: List[Decorator]

    def __init__(self, configuration: Configuration, decorators: List[Decorator] = None):
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


class Scheduler(object):
    logger: logging.Logger
    configuration: Configuration
    agent: Agent
    stop: bool

    def __init__(self, configuration: Configuration, agent):
        self.logger = logging.getLogger("cachet_url_monitor.scheduler.Scheduler")
        self.configuration = configuration
        self.agent = agent
        self.stop = False

    def start(self):
        self.logger.info("Starting monitor agent...")
        while not self.stop:
            self.agent.execute()
            time.sleep(self.configuration.endpoint["frequency"])


class NewThread(threading.Thread):
    scheduler: Scheduler

    def __init__(self, scheduler: Scheduler):
        threading.Thread.__init__(self)
        self.scheduler = scheduler

    def run(self):
        self.scheduler.start()


def build_agent(configuration: Configuration, logger: logging.Logger):
    actions: List[Decorator] = []
    for action in configuration.get_action():
        logger.info(f"Registering action {action}")
        actions.append(ACTION_NAMES_DECORATOR_MAP[action]())
    return Agent(configuration, decorators=actions)


def validate_config():
    if "endpoints" not in config_data.keys():
        fatal_error("Endpoints is a mandatory field")

    if config_data["endpoints"] is None:
        fatal_error("Endpoints array can not be empty")

    for key in cachet_mandatory_fields:
        if key not in config_data["cachet"]:
            fatal_error("Missing cachet mandatory fields")


def fatal_error(message: str):
    logging.getLogger("cachet_url_monitor.scheduler").fatal("%s", message)
    sys.exit(1)


if __name__ == "__main__":
    FORMAT = "%(levelname)9s [%(asctime)-15s] %(name)s - %(message)s"
    logging.basicConfig(format=FORMAT, level=logging.INFO)
    for handler in logging.root.handlers:
        handler.addFilter(logging.Filter("cachet_url_monitor"))

    if len(sys.argv) <= 1:
        fatal_error("Missing configuration file argument")
        sys.exit(1)

    try:
        config_data = load(open(sys.argv[1], "r"), SafeLoader)
    except FileNotFoundError:
        fatal_error(f"File not found: {sys.argv[1]}")
        sys.exit(1)

    validate_config()

    webhooks: List[Webhook] = []
    for webhook in config_data.get("webhooks", []):
        webhooks.append(Webhook(webhook["url"], webhook.get("params", {})))

    token: str = get_token(config_data["cachet"]["token"])
    api_url: str = os.environ.get("CACHET_API_URL") or config_data["cachet"]["api_url"]
    client: CachetClient = CachetClient(api_url, token)
    for endpoint_index in range(len(config_data["endpoints"])):
        configuration = Configuration(config_data, endpoint_index, client, webhooks)
        NewThread(
            Scheduler(configuration, build_agent(configuration, logging.getLogger("cachet_url_monitor.scheduler")))
        ).start()
