#!/usr/bin/env python
import mock
import unittest
import sys
sys.modules['schedule'] = mock.Mock()
from cachet_url_monitor.scheduler import Agent


class AgentTest(unittest.TestCase):
    def setUp(self):
        self.configuration = mock.Mock()
        self.agent = Agent(self.configuration)

    def test_init(self):
        assert self.agent.configuration == self.configuration

    def test_execute(self):
        evaluate = self.configuration.evaluate
        push_status_and_metrics = self.configuration.push_status_and_metrics
        self.agent.execute()

        evaluate.assert_called_once()
        push_status_and_metrics.assert_called_once()

    def test_start(self):
        every = sys.modules['schedule'].every
        self.configuration.data = {'frequency': 5}

        self.agent.start()

        every.assert_called_with(5)
