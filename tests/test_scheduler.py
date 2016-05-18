#!/usr/bin/env python
import sys
import unittest

import mock

sys.modules['schedule'] = mock.Mock()
# sys.modules['cachet_url_monitor.configuration.Configuration'] = mock.Mock()
sys.modules['requests'] = mock.Mock()
from cachet_url_monitor.scheduler import Agent, Scheduler


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
        push_status.assert_not_called()

    def test_start(self):
        every = sys.modules['schedule'].every
        self.configuration.data = {'frequency': 5}

        self.agent.start()

        every.assert_called_with(5)


class SchedulerTest(unittest.TestCase):
    @mock.patch('cachet_url_monitor.configuration.Configuration.__init__', mock.Mock(return_value=None))
    @mock.patch('cachet_url_monitor.configuration.Configuration.is_create_incident', mock.Mock(return_value=False))
    def setUp(self):
        def get(url, headers):
            get_return = mock.Mock()
            get_return.ok = True
            get_return.json = mock.Mock()
            get_return.json.return_value = {'data': {'status': 1}}
            return get_return

        sys.modules['requests'].get = get

        self.scheduler = Scheduler('config.yml')

    def test_init(self):
        assert self.scheduler.stop == False

    @mock.patch('cachet_url_monitor.configuration.Configuration', create=True)
    def test_start(self, mock_configuration):
        # TODO(mtakaki|2016-05-01): We need a better way of testing this method.
        # Leaving it as a placeholder.
        mock_configuration.data = {'frequency': 30}
        
        self.scheduler.stop = True
        self.scheduler.start()
