#!/usr/bin/env python
from configuration import Configuration
import logging
import schedule
import sys
import time


class Agent(object):
    """Monitor agent that will be constantly verifying if the URL is healthy
    and updating the component.
    """

    def __init__(self, configuration):
        self.configuration = configuration

    def execute(self):
        """Will verify the API status and push the status and metrics to the
        cachet server.
        """
        self.configuration.evaluate()
        self.configuration.push_metrics()

    def start(self):
        """Sets up the schedule based on the configuration file."""
        schedule.every(self.configuration.data['frequency']).seconds.do(self.execute)


class UpdateStatusAgent(Agent):
    def __init__(self, configuration):
        super(UpdateStatusAgent, self).__init__(configuration)

    def execute(self):
        super(UpdateStatusAgent, self).execute()
        self.configuration.push_status()


class CreateIncidentAgent(Agent):
    def __init__(self, configuration):
        super(CreateIncidentAgent, self).__init__(configuration)

    def execute(self):
        super(CreateIncidentAgent, self).execute()
        self.configuration.push_incident()


class Scheduler(object):
    def __init__(self, config_file):
        self.logger = logging.getLogger('cachet_url_monitor.scheduler.Scheduler')
        self.configuration = Configuration(config_file)

        if self.configuration.is_create_incident():
            self.agent = CreateIncidentAgent(self.configuration)
        elif self.configuration.is_update_status():
            self.agent = UpdateStatusAgent(self.configuration)
        else:
            self.agent = Agent(self.configuration)

        self.stop = False

    def start(self):
        self.agent.start()
        self.logger.info('Starting monitor agent...')
        while not self.stop:
            schedule.run_pending()
            time.sleep(self.configuration.data['frequency'])


if __name__ == "__main__":
    FORMAT = "%(levelname)9s [%(asctime)-15s] %(name)s - %(message)s"
    logging.basicConfig(format=FORMAT, level=logging.INFO)
    for handler in logging.root.handlers:
        handler.addFilter(logging.Filter('cachet_url_monitor'))

    if len(sys.argv) <= 1:
        logging.fatal('Missing configuration file argument')
        sys.exit(1)

    scheduler = Scheduler(sys.argv[1])
    scheduler.start()
