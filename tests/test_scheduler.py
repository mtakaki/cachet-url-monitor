#!/usr/bin/env python
import unittest

import mock

from cachet_url_monitor.scheduler import Agent, Scheduler, validate_config, fatal_error
import cachet_url_monitor.scheduler

# Ensure config_data exists in the scheduler module for patching.
# It's normally created when the script is run directly.
if not hasattr(cachet_url_monitor.scheduler, 'config_data'):
    cachet_url_monitor.scheduler.config_data = None


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

    @mock.patch("cachet_url_monitor.scheduler.time.sleep")
    def test_start_loop_and_stop(self, mock_sleep):
        # The 'frequency' is part of the endpoint configuration within the main configuration object.
        # The setUp for SchedulerTest creates a scheduler with a full configuration dictionary.
        # We need to access that configuration to get the endpoint frequency.
        # The scheduler is self.scheduler. The configuration dict is self.scheduler.configuration.
        # The list of endpoints is self.scheduler.configuration['endpoints'].
        # Let's assume the first endpoint's frequency for this test.
        
        # Correctly access the endpoint configuration used by the Scheduler instance
        # The Scheduler's __init__ receives the raw config dict, not a Configuration object.
        # The Configuration object is created later, within the main_logic or when a Scheduler is part of NewThread.
        # For this test, we need to ensure self.scheduler.configuration (the dict) has the frequency.
        # Or, more accurately, the Scheduler.start method uses self.configuration.endpoint["frequency"].
        # This implies that self.scheduler.configuration should be a Configuration object, not a dict.
        # Let's adjust SchedulerTest.setUp to reflect this.

        # For this test, let's assume self.scheduler.configuration is a Mock that has an endpoint attribute.
        mock_configuration_object = mock.Mock()
        mock_configuration_object.endpoint = {"frequency": 10} # Sample frequency
        self.scheduler.configuration = mock_configuration_object # Override with a mock Configuration
        
        self.scheduler.agent = mock.Mock() 
        self.scheduler.stop = False 

        call_count = 0
        def execute_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                self.scheduler.stop = True
        
        self.scheduler.agent.execute.side_effect = execute_side_effect
        
        expected_frequency = mock_configuration_object.endpoint["frequency"]

        self.scheduler.start()

        self.assertEqual(self.scheduler.agent.execute.call_count, 3)
        mock_sleep.assert_has_calls([mock.call(expected_frequency)] * 2) 
        self.assertTrue(self.scheduler.stop)


class NewThreadTests(unittest.TestCase):
    def test_run_calls_scheduler_start(self):
        mock_scheduler = mock.Mock()
        from cachet_url_monitor.scheduler import NewThread 
        
        thread_instance = NewThread(mock_scheduler)
        thread_instance.run()
        
        mock_scheduler.start.assert_called_once()


class SchedulerLogicTests(unittest.TestCase):
    def setUp(self):
        self.mock_configuration = mock.Mock()
        self.mock_decorated_agent = mock.Mock()
        self.mock_logger = mock.Mock()
        # Mock the get_action method for build_agent tests
        self.mock_configuration.get_action.return_value = []

    def test_update_status_decorator(self):
        from cachet_url_monitor.scheduler import UpdateStatusDecorator

        decorator = UpdateStatusDecorator()
        # decorator.configuration = self.mock_configuration # Not needed as config is passed to execute
        # decorator.decorated_agent = self.mock_decorated_agent # Decorators in this system don't chain this way
        decorator.execute(self.mock_configuration)
        self.mock_configuration.push_status.assert_called_once()
        # self.mock_decorated_agent.execute.assert_called_once() # Decorators don't call decorated_agent.execute

    def test_create_incident_decorator(self):
        from cachet_url_monitor.scheduler import CreateIncidentDecorator

        decorator = CreateIncidentDecorator()
        decorator.execute(self.mock_configuration)
        self.mock_configuration.push_incident.assert_called_once()

    def test_push_metrics_decorator(self):
        from cachet_url_monitor.scheduler import PushMetricsDecorator

        decorator = PushMetricsDecorator()
        decorator.execute(self.mock_configuration)
        self.mock_configuration.push_metrics.assert_called_once()

    def test_build_agent_no_actions(self):
        from cachet_url_monitor.scheduler import build_agent, Agent
        from cachet_url_monitor.scheduler import UpdateStatusDecorator, CreateIncidentDecorator, PushMetricsDecorator

        self.mock_configuration.get_action.return_value = []
        agent = build_agent(self.mock_configuration, self.mock_logger)

        self.assertIsInstance(agent, Agent)
        self.assertEqual(len(agent.decorators), 0)
        # Check that it's not an instance of decorators if not configured.
        # This check is more about the agent instance itself, not its internal list.
        self.assertNotIsInstance(agent, UpdateStatusDecorator) 


    def test_build_agent_update_status_action(self):
        from cachet_url_monitor.scheduler import build_agent, Agent, UpdateStatusDecorator

        self.mock_configuration.get_action.return_value = ["UPDATE_STATUS"]
        agent = build_agent(self.mock_configuration, self.mock_logger)

        self.assertIsInstance(agent, Agent)
        self.assertEqual(len(agent.decorators), 1)
        self.assertIsInstance(agent.decorators[0], UpdateStatusDecorator)

    def test_build_agent_create_incident_action(self):
        from cachet_url_monitor.scheduler import build_agent, Agent, CreateIncidentDecorator

        self.mock_configuration.get_action.return_value = ["CREATE_INCIDENT"]
        agent = build_agent(self.mock_configuration, self.mock_logger)

        self.assertIsInstance(agent, Agent)
        self.assertEqual(len(agent.decorators), 1)
        self.assertIsInstance(agent.decorators[0], CreateIncidentDecorator)

    def test_build_agent_push_metrics_action(self):
        from cachet_url_monitor.scheduler import build_agent, Agent, PushMetricsDecorator

        self.mock_configuration.get_action.return_value = ["PUSH_METRICS"]
        agent = build_agent(self.mock_configuration, self.mock_logger)

        self.assertIsInstance(agent, Agent)
        self.assertEqual(len(agent.decorators), 1)
        self.assertIsInstance(agent.decorators[0], PushMetricsDecorator)

    def test_build_agent_all_actions(self):
        from cachet_url_monitor.scheduler import build_agent, Agent
        from cachet_url_monitor.scheduler import UpdateStatusDecorator, CreateIncidentDecorator, PushMetricsDecorator

        self.mock_configuration.get_action.return_value = ["UPDATE_STATUS", "CREATE_INCIDENT", "PUSH_METRICS"]
        agent = build_agent(self.mock_configuration, self.mock_logger)

        self.assertIsInstance(agent, Agent)
        self.assertEqual(len(agent.decorators), 3)
        self.assertIsInstance(agent.decorators[0], UpdateStatusDecorator)
        self.assertIsInstance(agent.decorators[1], CreateIncidentDecorator)
        self.assertIsInstance(agent.decorators[2], PushMetricsDecorator)

    def test_build_agent_unknown_action(self):
        # Test that unknown actions are ignored and valid ones are still applied
        from cachet_url_monitor.scheduler import build_agent, Agent, UpdateStatusDecorator
        
        self.mock_configuration.get_action.return_value = ["UNKNOWN_ACTION", "UPDATE_STATUS"]
        agent = build_agent(self.mock_configuration, self.mock_logger)
        
        self.assertIsInstance(agent, Agent)
        self.assertEqual(len(agent.decorators), 1)
        self.assertIsInstance(agent.decorators[0], UpdateStatusDecorator)


class ValidateConfigTests(unittest.TestCase):
    @mock.patch("cachet_url_monitor.scheduler.fatal_error")
    @mock.patch("cachet_url_monitor.scheduler.config_data", {}) # Patch module global
    def test_validate_config_no_endpoints_key(self, mock_fatal_error):
        validate_config()
        mock_fatal_error.assert_called_once_with('The "endpoints" key is mandatory in the configuration file and must be a list.')

    @mock.patch("cachet_url_monitor.scheduler.fatal_error")
    @mock.patch("cachet_url_monitor.scheduler.config_data", {"endpoints": None})
    def test_validate_config_endpoints_is_none(self, mock_fatal_error):
        validate_config()
        mock_fatal_error.assert_called_once_with('The "endpoints" key is mandatory in the configuration file and must be a list.')

    @mock.patch("cachet_url_monitor.scheduler.fatal_error")
    @mock.patch("cachet_url_monitor.scheduler.config_data", {"endpoints": []}) # No 'cachet' key
    def test_validate_config_no_cachet_key(self, mock_fatal_error):
        validate_config()
        mock_fatal_error.assert_called_once_with('The "cachet" key is mandatory in the configuration file and must be a dictionary.')

    @mock.patch("cachet_url_monitor.scheduler.fatal_error")
    @mock.patch("cachet_url_monitor.scheduler.config_data", {"endpoints": [], "cachet": {"token": "xyz"}}) # api_url missing
    def test_validate_config_cachet_api_url_missing(self, mock_fatal_error):
        validate_config()
        mock_fatal_error.assert_called_once_with(
            'The "cachet.api_url" key is mandatory in the configuration file.'
        )

    @mock.patch("cachet_url_monitor.scheduler.fatal_error")
    @mock.patch("cachet_url_monitor.scheduler.config_data", {"endpoints": [], "cachet": {"api_url": "http://foo"}}) # token missing
    def test_validate_config_cachet_token_missing(self, mock_fatal_error):
        validate_config()
        mock_fatal_error.assert_called_once_with(
            'The "cachet.token" key is mandatory in the configuration file.'
        )

    @mock.patch("cachet_url_monitor.scheduler.fatal_error")
    @mock.patch("cachet_url_monitor.scheduler.config_data", {"endpoints": [], "cachet": {"api_url": "http://foo", "token": "xyz"}})
    def test_validate_config_valid_minimal(self, mock_fatal_error):
        validate_config()
        mock_fatal_error.assert_not_called()


class FatalErrorTests(unittest.TestCase):
    @mock.patch("cachet_url_monitor.scheduler.sys.exit")
    @mock.patch("cachet_url_monitor.scheduler.logging.getLogger")
    def test_fatal_error_logs_and_exits(self, mock_get_logger, mock_sys_exit):
        from cachet_url_monitor.scheduler import fatal_error
        mock_logger_instance = mock.Mock()
        mock_get_logger.return_value = mock_logger_instance

        test_message = "This is a fatal error test"
        fatal_error(test_message)

        mock_get_logger.assert_called_once_with("cachet_url_monitor.scheduler")
        mock_logger_instance.fatal.assert_called_once_with("%s", test_message)
        mock_sys_exit.assert_called_once_with(1)


# Tests for the main_logic function (refactored from if __name__ == "__main__")
class MainLogicTests(unittest.TestCase):
    @mock.patch("cachet_url_monitor.scheduler.fatal_error")
    @mock.patch("cachet_url_monitor.scheduler.logging") # Mock logging module
    def test_main_logic_missing_config_arg(self, mock_logging, mock_fatal_error):
        cachet_url_monitor.scheduler.main_logic(['scheduler.py'])
        mock_fatal_error.assert_called_once_with("Missing configuration file argument")

    @mock.patch("cachet_url_monitor.scheduler.fatal_error")
    @mock.patch("builtins.open", side_effect=FileNotFoundError)
    @mock.patch("cachet_url_monitor.scheduler.logging")
    def test_main_logic_file_not_found(self, mock_logging, mock_open, mock_fatal_error):
        cachet_url_monitor.scheduler.main_logic(['scheduler.py', 'nonexistent.yml'])
        mock_open.assert_called_once_with('nonexistent.yml', 'r')
        mock_fatal_error.assert_called_once_with("File not found: nonexistent.yml")

    @mock.patch("cachet_url_monitor.scheduler.NewThread")
    @mock.patch("cachet_url_monitor.scheduler.build_agent")
    @mock.patch("cachet_url_monitor.scheduler.Configuration")
    @mock.patch("cachet_url_monitor.scheduler.CachetClient")
    @mock.patch("cachet_url_monitor.scheduler.os.environ.get", return_value=None) # No CACHET_API_URL env
    @mock.patch("cachet_url_monitor.scheduler.get_token", return_value="resolved_token_from_get_token")
    @mock.patch("cachet_url_monitor.scheduler.validate_config") # Assume validation passes
    @mock.patch("cachet_url_monitor.scheduler.load")
    @mock.patch("builtins.open", new_callable=mock.mock_open, read_data="dummy_yaml")
    @mock.patch("cachet_url_monitor.scheduler.logging") 
    @mock.patch("cachet_url_monitor.scheduler.fatal_error") 
    def test_main_logic_valid_config_one_endpoint_no_webhooks(
            self, mock_fatal_error, mock_logging, mock_open, mock_yaml_load, mock_validate_config,
            mock_get_token, mock_os_environ_get, mock_cachet_client, mock_configuration,
            mock_build_agent, mock_new_thread):
        
        sample_config = {
            "endpoints": [{"name": "ep1", "url": "http://ep1.com"}], 
            "cachet": {"api_url": "http://cachet.api", "token": "file_token"}
        }
        mock_yaml_load.return_value = sample_config
        
        mock_thread_instance = mock.Mock()
        mock_new_thread.return_value = mock_thread_instance
        mock_config_instance = mock.Mock()
        mock_configuration.return_value = mock_config_instance
        mock_agent_instance = mock.Mock()
        mock_build_agent.return_value = mock_agent_instance
        mock_client_instance = mock.Mock()
        mock_cachet_client.return_value = mock_client_instance

        cachet_url_monitor.scheduler.main_logic(['scheduler.py', 'config.yml'])

        mock_fatal_error.assert_not_called()
        mock_open.assert_called_once_with('config.yml', 'r')
        mock_yaml_load.assert_called_once()
        mock_validate_config.assert_called_once()
        mock_get_token.assert_called_once_with("file_token")
        mock_os_environ_get.assert_called_once_with("CACHET_API_URL")
        mock_cachet_client.assert_called_once_with("http://cachet.api", "resolved_token_from_get_token")
        
        mock_configuration.assert_called_once_with(sample_config, 0, mock_client_instance, [])
        
        # Check that getLogger was called for the Agent
        mock_logging.getLogger.assert_any_call("cachet_url_monitor.scheduler.Agent")
        # Ensure build_agent was called with the logger returned by getLogger
        mock_build_agent.assert_called_once_with(mock_config_instance, mock_logging.getLogger.return_value)
        
        self.assertEqual(mock_new_thread.call_count, 1)
        scheduler_arg = mock_new_thread.call_args[0][0] 
        self.assertEqual(scheduler_arg.configuration, mock_config_instance)
        self.assertEqual(scheduler_arg.agent, mock_agent_instance)
        
        mock_thread_instance.start.assert_called_once()

    @mock.patch("cachet_url_monitor.scheduler.NewThread")
    @mock.patch("cachet_url_monitor.scheduler.CachetClient")
    @mock.patch("cachet_url_monitor.scheduler.os.environ.get", return_value="http://env.api.url") 
    @mock.patch("cachet_url_monitor.scheduler.get_token", return_value="resolved_token")
    @mock.patch("cachet_url_monitor.scheduler.validate_config")
    @mock.patch("cachet_url_monitor.scheduler.load")
    @mock.patch("builtins.open", new_callable=mock.mock_open)
    @mock.patch("cachet_url_monitor.scheduler.logging")
    # Minimal other mocks for this specific test focus
    @mock.patch("cachet_url_monitor.scheduler.Configuration")
    @mock.patch("cachet_url_monitor.scheduler.build_agent")
    def test_main_logic_uses_env_var_for_api_url(
            self, mock_build_agent, mock_configuration, mock_logging, mock_open, mock_yaml_load, mock_validate_config,
            mock_get_token, mock_os_environ_get, mock_cachet_client, mock_new_thread):
        
        sample_config = {
            "endpoints": [{"name": "ep1", "url": "http://ep1.com"}],
            "cachet": {"api_url": "http://config.api.url", "token": "file_token"}
        }
        mock_yaml_load.return_value = sample_config
        mock_new_thread.return_value = mock.Mock() 

        cachet_url_monitor.scheduler.main_logic(['scheduler.py', 'config.yml'])
        
        mock_cachet_client.assert_called_once_with("http://env.api.url", "resolved_token")

    @mock.patch("cachet_url_monitor.scheduler.NewThread")
    @mock.patch("cachet_url_monitor.scheduler.Webhook") 
    @mock.patch("cachet_url_monitor.scheduler.Configuration")
    @mock.patch("cachet_url_monitor.scheduler.CachetClient")
    @mock.patch("cachet_url_monitor.scheduler.os.environ.get", return_value=None)
    @mock.patch("cachet_url_monitor.scheduler.get_token", return_value="resolved_token")
    @mock.patch("cachet_url_monitor.scheduler.validate_config")
    @mock.patch("cachet_url_monitor.scheduler.load")
    @mock.patch("builtins.open", new_callable=mock.mock_open)
    @mock.patch("cachet_url_monitor.scheduler.logging")
    # Minimal other mocks
    @mock.patch("cachet_url_monitor.scheduler.build_agent")
    def test_main_logic_with_webhooks(
            self, mock_build_agent, mock_logging, mock_open, mock_yaml_load, mock_validate_config,
            mock_get_token, mock_os_environ_get, mock_cachet_client,
            mock_configuration, mock_webhook_class, mock_new_thread):

        sample_config = {
            "endpoints": [{"name": "ep1"}],
            "cachet": {"api_url": "url", "token": "token_val"},
            "webhooks": [
                {"url": "http://webhook1.com", "params": {"p1": "v1"}},
                {"url": "http://webhook2.com"} 
            ]
        }
        mock_yaml_load.return_value = sample_config
        mock_new_thread.return_value = mock.Mock()
        mock_client_instance = mock.Mock()
        mock_cachet_client.return_value = mock_client_instance
        
        webhook_instances = []
        def webhook_side_effect(*args, **kwargs):
            instance = mock.Mock()
            webhook_instances.append(instance)
            return instance
        mock_webhook_class.side_effect = webhook_side_effect

        cachet_url_monitor.scheduler.main_logic(['scheduler.py', 'config.yml'])

        mock_webhook_class.assert_any_call("http://webhook1.com", {"p1": "v1"})
        mock_webhook_class.assert_any_call("http://webhook2.com", {})
        self.assertEqual(mock_webhook_class.call_count, 2)
        
        mock_configuration.assert_called_once_with(sample_config, 0, mock_client_instance, webhook_instances)

    @mock.patch("cachet_url_monitor.scheduler.NewThread")
    @mock.patch("cachet_url_monitor.scheduler.build_agent")
    @mock.patch("cachet_url_monitor.scheduler.Configuration")
    @mock.patch("cachet_url_monitor.scheduler.CachetClient")
    @mock.patch("cachet_url_monitor.scheduler.os.environ.get", return_value=None)
    @mock.patch("cachet_url_monitor.scheduler.get_token", return_value="resolved_token")
    @mock.patch("cachet_url_monitor.scheduler.validate_config")
    @mock.patch("cachet_url_monitor.scheduler.load")
    @mock.patch("builtins.open", new_callable=mock.mock_open)
    @mock.patch("cachet_url_monitor.scheduler.logging")
    def test_main_logic_multiple_endpoints(
            self, mock_logging, mock_open, mock_yaml_load, mock_validate_config,
            mock_get_token, mock_os_environ_get, mock_cachet_client,
            mock_configuration, mock_build_agent, mock_new_thread):

        sample_config = {
            "endpoints": [{"name": "ep1"}, {"name": "ep2"}], 
            "cachet": {"api_url": "url", "token": "token_val"}
        }
        mock_yaml_load.return_value = sample_config
        
        mock_thread_instance = mock.Mock()
        mock_new_thread.return_value = mock_thread_instance
        mock_config_instance1 = mock.Mock(name="config_ep1")
        mock_config_instance2 = mock.Mock(name="config_ep2")
        mock_configuration.side_effect = [mock_config_instance1, mock_config_instance2]
        mock_agent_instance1 = mock.Mock(name="agent_ep1")
        mock_agent_instance2 = mock.Mock(name="agent_ep2")
        mock_build_agent.side_effect = [mock_agent_instance1, mock_agent_instance2]
        mock_client_instance = mock.Mock()
        mock_cachet_client.return_value = mock_client_instance

        cachet_url_monitor.scheduler.main_logic(['scheduler.py', 'config.yml'])

        self.assertEqual(mock_configuration.call_count, 2)
        mock_configuration.assert_any_call(sample_config, 0, mock_client_instance, [])
        mock_configuration.assert_any_call(sample_config, 1, mock_client_instance, [])
        
        self.assertEqual(mock_build_agent.call_count, 2)
        # Check that getLogger was called for the Agent (at least once, it will be called multiple times)
        mock_logging.getLogger.assert_any_call("cachet_url_monitor.scheduler.Agent")
        # Ensure getLogger was called for each endpoint's agent
        self.assertEqual(mock_logging.getLogger.call_count, 2 * 2) # Called by main_logic for Agent + by Scheduler init for Scheduler
                                                                # Actually, main_logic calls it for Agent, Scheduler init calls it for Scheduler
                                                                # So, for 2 endpoints, getLogger("...Agent") is 2, getLogger("...Scheduler") is 2.
                                                                # Let's be more specific with call_args if needed, or check count for specific arg.
        
        # Get the list of calls to logging.getLogger
        getLogger_calls = mock_logging.getLogger.call_args_list
        agent_logger_calls = [call for call in getLogger_calls if call[0][0] == "cachet_url_monitor.scheduler.Agent"]
        self.assertEqual(len(agent_logger_calls), 2) # Ensure getLogger for Agent was called twice

        # Ensure build_agent was called with the logger returned by getLogger for Agent
        # The return_value of mock_logging.getLogger will be the same mock if not configured otherwise
        mock_build_agent.assert_any_call(mock_config_instance1, mock_logging.getLogger.return_value)
        mock_build_agent.assert_any_call(mock_config_instance2, mock_logging.getLogger.return_value)

        self.assertEqual(mock_new_thread.call_count, 2)
        scheduler_arg0 = mock_new_thread.call_args_list[0][0][0]
        scheduler_arg1 = mock_new_thread.call_args_list[1][0][0]
        self.assertEqual(scheduler_arg0.configuration, mock_config_instance1)
        self.assertEqual(scheduler_arg0.agent, mock_agent_instance1)
        self.assertEqual(scheduler_arg1.configuration, mock_config_instance2)
        self.assertEqual(scheduler_arg1.agent, mock_agent_instance2)

        self.assertEqual(mock_thread_instance.start.call_count, 2)