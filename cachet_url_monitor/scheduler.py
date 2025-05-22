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
    agent: Agent = Agent(configuration)  # Start with a base Agent
    
    # The order of decoration matters if decorators depend on each other.
    # Current decorators are independent, so order in get_action() is fine.
    # If specific order is needed, sort or process configuration.get_action() here.
    
    processed_decorators: List[Decorator] = []

    for action_name in configuration.get_action():
        if action_name in ACTION_NAMES_DECORATOR_MAP:
            decorator_class = ACTION_NAMES_DECORATOR_MAP[action_name]
            logger.info(f"Wrapping agent with {decorator_class.__name__} for action {action_name}")
            
            # Create new decorator instance
            current_decorator_instance = decorator_class()
            # Set its configuration (if decorators need it directly, though usually they operate via the wrapped agent's config)
            # current_decorator_instance.configuration = configuration # Generally not needed if they call methods on config via execute
            
            # The following line is if decorators had their own 'decorated_agent' attribute to form a chain
            # current_decorator_instance.decorated_agent = agent 
            # agent = current_decorator_instance # Update agent to be the new outermost decorator
            
            # Based on current Agent and Decorator structure:
            # Agent takes a list of decorators to call in its execute method.
            # Decorators don't wrap each other directly by holding a 'decorated_agent' reference.
            # Instead, Agent iterates through a list of decorators.
            processed_decorators.append(current_decorator_instance)
        else:
            logger.warning(f"Unknown action configured: {action_name}. Skipping.")
            
    # Update the agent's list of decorators
    agent.decorators = processed_decorators
    return agent


def validate_config():
    # Ensure config_data is accessible; it's loaded in if __name__ == "__main__":
    # For direct calls (like in tests), config_data needs to be pre-populated or mocked.
    global config_data
    if "endpoints" not in config_data or not isinstance(config_data.get("endpoints"), list):
        fatal_error('The "endpoints" key is mandatory in the configuration file and must be a list.')
        return

    if "cachet" not in config_data or not isinstance(config_data.get("cachet"), dict):
        fatal_error('The "cachet" key is mandatory in the configuration file and must be a dictionary.')
        return

    # If we reach here, config_data['cachet'] exists and is a dict.
    for key in cachet_mandatory_fields:
        if key not in config_data["cachet"]:
            fatal_error(f'The "cachet.{key}" key is mandatory in the configuration file.')
            return


def fatal_error(message: str):
    logging.getLogger("cachet_url_monitor.scheduler").fatal("%s", message)
    sys.exit(1)


def main_logic(argv: List[str]):
    global config_data  # Declare config_data as global to assign to it
    FORMAT = "%(levelname)9s [%(asctime)-15s] %(name)s - %(message)s"
    logging.basicConfig(format=FORMAT, level=logging.INFO)
    for handler in logging.root.handlers:
        handler.addFilter(logging.Filter("cachet_url_monitor"))

    if len(argv) <= 1:
        fatal_error("Missing configuration file argument")
        # fatal_error calls sys.exit, so no need to exit here explicitly for production
        return # Return for testing purposes when fatal_error is mocked

    try:
        # Use argv[1] for the config file path
        config_file_path = argv[1]
        config_data = load(open(config_file_path, "r"), SafeLoader)
    except FileNotFoundError:
        fatal_error(f"File not found: {config_file_path}")
        return # Return for testing

    validate_config() # This will use the global config_data

    webhooks: List[Webhook] = []
    for webhook_conf in config_data.get("webhooks", []): # renamed webhook to webhook_conf
        webhooks.append(Webhook(webhook_conf["url"], webhook_conf.get("params", {})))

    token: str = get_token(config_data["cachet"]["token"])
    api_url: str = os.environ.get("CACHET_API_URL") or config_data["cachet"]["api_url"]
    client: CachetClient = CachetClient(api_url, token)
    
    threads = [] # Keep track of threads for potential join in future, not strictly needed for current tests
    for endpoint_index in range(len(config_data["endpoints"])):
        configuration = Configuration(config_data, endpoint_index, client, webhooks)
        # Pass the specific logger to build_agent
        agent_logger = logging.getLogger("cachet_url_monitor.scheduler.Agent") 
        scheduler_instance = Scheduler(configuration, build_agent(configuration, agent_logger))
        thread = NewThread(scheduler_instance)
        thread.start()
        threads.append(thread)
    
    # In a real daemon, we might want to join threads or have a main loop.
    # For testing, starting them is enough to verify the logic.


if __name__ == "__main__":
    main_logic(sys.argv)
