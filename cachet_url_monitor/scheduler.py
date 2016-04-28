#!/usr/bin/env python
from configuration import Configuration
import logging
import schedule
import sys
import time


class Agent(object):
    def __init__(self, configuration):
        self.configuration = configuration

    def execute(self):
        self.configuration.evaluate()
        self.configuration.push_status_and_metrics()

    def start(self):
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
