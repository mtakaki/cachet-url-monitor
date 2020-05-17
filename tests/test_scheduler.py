#!/usr/bin/env python
import unittest

import mock

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


class SchedulerTest(unittest.TestCase):
    @mock.patch("requests.get")
    def setUp(self, mock_requests):
        def get(url, headers):
            get_return = mock.Mock()
            get_return.ok = True
            get_return.json = mock.Mock()
            get_return.json.return_value = {"data": {"status": 1}}
            return get_return

        mock_requests.get = get

        self.agent = mock.MagicMock()

        self.scheduler = Scheduler(
            {
                "endpoints": [
                    {
                        "name": "foo",
                        "url": "http://localhost:8080/swagger",
                        "method": "GET",
                        "expectation": [{"type": "HTTP_STATUS", "status_range": "200 - 300", "incident": "MAJOR"}],
                        "allowed_fails": 0,
                        "component_id": 1,
                        "action": ["CREATE_INCIDENT", "UPDATE_STATUS"],
                        "public_incidents": True,
                        "latency_unit": "ms",
                        "frequency": 30,
                    }
                ],
                "cachet": {"api_url": "https: // demo.cachethq.io / api / v1", "token": "my_token"},
            },
            self.agent,
        )

    def test_init(self):
        self.assertFalse(self.scheduler.stop)

    def test_start(self):
        # TODO(mtakaki|2016-05-01): We need a better way of testing this method.
        # Leaving it as a placeholder.
        self.scheduler.stop = True
        self.scheduler.start()
