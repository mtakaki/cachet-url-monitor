#!/usr/bin/env python
import mock
import unittest
import sys
sys.modules['schedule'] = mock.Mock()
sys.modules['cachet_url_monitor.configuration.Configuration'] = mock.Mock()
from cachet_url_monitor.scheduler import Agent,Scheduler


class AgentTest(unittest.TestCase):
    def setUp(self):
        self.configuration = mock.Mock()
        self.agent = Agent(self.configuration)

    def test_init(self):
        assert self.agent.configuration == self.configuration

    def test_execute(self):
        evaluate = self.configuration.evaluate
        push_status = self.configuration.push_status
        self.agent.execute()

        evaluate.assert_called_once()
        push_status.assert_called_once()

    def test_start(self):
        every = sys.modules['schedule'].every
        self.configuration.data = {'frequency': 5}

        self.agent.start()

        every.assert_called_with(5)


class SchedulerTest(unittest.TestCase):
    def setUp(self):
        self.mock_configuration = sys.modules[('cachet_url_monitor.configuration'
            '.Configuration')]
        self.scheduler = Scheduler('config.yml')

    def test_init(self):
        assert self.scheduler.stop == False

    def test_start(self):
        #TODO(mtakaki|2016-05-01): We need a better way of testing this method.
        # Leaving it as a placeholder.
        self.scheduler.stop = True
        self.scheduler.start()
