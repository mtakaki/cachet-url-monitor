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
        self.configuration.push_status_and_metrics()

    def start(self):
        """Sets up the schedule based on the configuration file."""
        schedule.every(self.configuration.data['frequency']).seconds.do(self.execute)


if __name__ == "__main__":
    if len(sys.argv) <= 1:
        logging.fatal('Missing configuration file argument')
        sys.exit(1)

    configuration = Configuration(sys.argv[1])
    agent = Agent(configuration)

    agent.start()
    logging.info('Starting monitor agent...')
    while True:
        schedule.run_pending()
        time.sleep(configuration.data['frequency'])
