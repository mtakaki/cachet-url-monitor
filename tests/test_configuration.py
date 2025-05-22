#!/usr/bin/env python
import mock
import pytest
import requests
import requests_mock
from yaml import load, SafeLoader

import cachet_url_monitor.exceptions
import cachet_url_monitor.status
from cachet_url_monitor.webhook import Webhook

from cachet_url_monitor.configuration import Configuration
import os


@pytest.fixture()
def mock_client():
    client = mock.Mock()
    client.get_component_status.return_value = cachet_url_monitor.status.ComponentStatus.OPERATIONAL
    yield client


@pytest.fixture()
def config_file():
    with open(os.path.join(os.path.dirname(__file__), "configs/config.yml"), "rt") as yaml_file:
        config_file_data = load(yaml_file, SafeLoader)
        yield config_file_data


@pytest.fixture()
def header_config_file():
    with open(os.path.join(os.path.dirname(__file__), "configs/config_header.yml"), "rt") as yaml_file:
        config_file_data = load(yaml_file, SafeLoader)
        yield config_file_data


@pytest.fixture()
def multiple_urls_config_file():
    with open(os.path.join(os.path.dirname(__file__), "configs/config_multiple_urls.yml"), "rt") as yaml_file:
        config_file_data = load(yaml_file, SafeLoader)
        yield config_file_data


@pytest.fixture()
def invalid_config_file():
    with open(os.path.join(os.path.dirname(__file__), "configs/config_invalid_type.yml"), "rt") as yaml_file:
        config_file_data = load(yaml_file, SafeLoader)
        yield config_file_data


@pytest.fixture()
def webhooks_config_file():
    with open(os.path.join(os.path.dirname(__file__), "configs/config_webhooks.yml"), "rt") as yaml_file:
        config_file_data = load(yaml_file, SafeLoader)
        yield config_file_data


@pytest.fixture()
def insecure_config_file():
    with open(os.path.join(os.path.dirname(__file__), "configs/config_insecure.yml"), "rt") as yaml_file:
        config_file_data = load(yaml_file, SafeLoader)
        yield config_file_data


@pytest.fixture()
def missing_name_config_file():
    with open(os.path.join(os.path.dirname(__file__), "configs/config_missing_name.yml"), "rt") as yaml_file:
        config_file_data = load(yaml_file, SafeLoader)
        yield config_file_data


@pytest.fixture()
def metric_config_file():
    with open(os.path.join(os.path.dirname(__file__), "configs/config_metric.yml"), "rt") as yaml_file:
        config_file_data = load(yaml_file, SafeLoader)
        yield config_file_data


@pytest.fixture()
def missing_latency_unit_config_file():
    with open(os.path.join(os.path.dirname(__file__), "configs/config_default_latency_unit.yml"), "rt") as yaml_file:
        config_file_data = load(yaml_file, SafeLoader)
        yield config_file_data


@pytest.fixture()
def mock_logger_module():
    with mock.patch("cachet_url_monitor.configuration.logging") as _mock_logger:
        yield _mock_logger


@pytest.fixture()
def mock_logger(mock_logger_module):
    _mock_logger = mock.Mock()
    mock_logger_module.getLogger.return_value = _mock_logger
    yield _mock_logger


@pytest.fixture()
def configuration(config_file, mock_client, mock_logger):
    yield Configuration(config_file, 0, mock_client)


@pytest.fixture()
def insecure_configuration(insecure_config_file, mock_client, mock_logger):
    yield Configuration(insecure_config_file, 0, mock_client)


@pytest.fixture()
def header_configuration(header_config_file, mock_client, mock_logger):
    yield Configuration(header_config_file, 0, mock_client)


@pytest.fixture()
def webhooks_configuration(webhooks_config_file, mock_client, mock_logger):
    webhooks = []
    for webhook in webhooks_config_file.get("webhooks", []):
        webhooks.append(Webhook(webhook["url"], webhook.get("params", {})))
    yield Configuration(webhooks_config_file, 0, mock_client, webhooks)


@pytest.fixture()
def multiple_urls_configuration(multiple_urls_config_file, mock_client, mock_logger):
    yield [
        Configuration(multiple_urls_config_file, index, mock_client)
        for index in range(len(multiple_urls_config_file["endpoints"]))
    ]


def test_init(configuration, mock_client):
    assert len(configuration.data) == 2, "Number of root elements in config.yml is incorrect"
    assert len(configuration.expectations) == 3, "Number of expectations read from file is incorrect"
    assert configuration.latency_unit == "ms"
    mock_client.get_default_metric_value.assert_not_called()


def test_init_timeout_zero_becomes_one(config_file, mock_client, mock_logger):
    # Test that timeout: 0 in config results in endpoint_timeout = 1
    # Create a deepcopy to avoid modifying the fixture for other tests
    config_data = config_file.copy() 
    config_data["endpoints"] = [config_file["endpoints"][0].copy()] # Deepcopy the endpoint too

    config_data["endpoints"][0]["timeout"] = 0
    
    # Ensure mock_client.get_component_status is properly set up, as it's called in __init__
    mock_client.get_component_status.return_value = cachet_url_monitor.status.ComponentStatus.OPERATIONAL
    
    conf = Configuration(config_data, 0, mock_client)
    assert conf.endpoint_timeout == 1


def test_init_with_header(header_configuration):
    assert len(header_configuration.data) == 2, "Number of root elements in config.yml is incorrect"
    assert len(header_configuration.expectations) == 3, "Number of expectations read from file is incorrect"
    assert header_configuration.endpoint_header == {"SOME-HEADER": "SOME-VALUE"}, "Header is incorrect"
    assert header_configuration.latency_unit == "ms"


def test_init_missing_latency_unit(missing_latency_unit_config_file, mock_client):
    configuration = Configuration(missing_latency_unit_config_file, 0, mock_client)
    assert configuration.latency_unit == "s"


def test_init_unknown_status(config_file, mock_client):
    mock_client.get_component_status.return_value = cachet_url_monitor.status.ComponentStatus.UNKNOWN
    configuration = Configuration(config_file, 0, mock_client)

    assert configuration.previous_status == cachet_url_monitor.status.ComponentStatus.UNKNOWN


def test_init_missing_name(missing_name_config_file, mock_client):
    with pytest.raises(cachet_url_monitor.configuration.ConfigurationValidationError):
        Configuration(missing_name_config_file, 0, mock_client)


def test_init_with_metric_id(metric_config_file, mock_client):
    mock_client.get_default_metric_value.return_value = 0.456
    configuration = Configuration(metric_config_file, 0, mock_client)

    assert (
        configuration.default_metric_value == 0.456
    ), "Default metric was not set during init"
    mock_client.get_default_metric_value.assert_called_once_with(3)


def test_init_timeout_zero_becomes_one(config_file, mock_client, mock_logger):
    # Test that timeout: 0 in config results in endpoint_timeout = 1
    config_with_zero_timeout = config_file.copy()
    # Ensure the endpoint exists and has a timeout to modify
    assert "endpoints" in config_with_zero_timeout
    assert len(config_with_zero_timeout["endpoints"]) > 0
    config_with_zero_timeout["endpoints"][0]["timeout"] = 0
    
    # Mock get_component_status as it's called in Configuration.__init__
    mock_client.get_component_status.return_value = cachet_url_monitor.status.ComponentStatus.OPERATIONAL
    
    conf = Configuration(config_with_zero_timeout, 0, mock_client)
    assert conf.endpoint_timeout == 1


def test_init_allowed_fails_zero(config_file, mock_client, mock_logger):
    # Test that allowed_fails: 0 in config results in self.allowed_fails = 0
    import copy # Ensure copy is imported
    config_data = copy.deepcopy(config_file) # Use deepcopy for nested dicts

    config_data["endpoints"][0]["allowed_fails"] = 0
    
    # Ensure mock_client.get_component_status is properly set up, as it's called in __init__
    mock_client.get_component_status.return_value = cachet_url_monitor.status.ComponentStatus.OPERATIONAL
    
    conf = Configuration(config_data, 0, mock_client)
    assert conf.allowed_fails == 0


def test_evaluate(configuration):
    with requests_mock.mock() as m:
        m.get("http://localhost:8080/swagger", text="<body>")
        configuration.evaluate()

        assert (
            configuration.status == cachet_url_monitor.status.ComponentStatus.OPERATIONAL
        ), "Component status set incorrectly"
        assert (
            m.last_request.verify == True
        )


def test_evaluate_insecure(insecure_configuration):
    with requests_mock.mock() as m:
        m.get("http://localhost:8080/swagger", text="<body>")
        insecure_configuration.evaluate()

        assert (
            insecure_configuration.status == cachet_url_monitor.status.ComponentStatus.OPERATIONAL
        ), "Component status set incorrectly"
        assert (
            m.last_request.verify == False
        )


def test_evaluate_without_header(configuration):
    with requests_mock.mock() as m:
        m.get("http://localhost:8080/swagger", text="<body>")
        configuration.evaluate()

        assert (
            configuration.status == cachet_url_monitor.status.ComponentStatus.OPERATIONAL
        ), "Component status set incorrectly"


def test_evaluate_with_header(header_configuration):
    with requests_mock.mock() as m:
        m.get("http://localhost:8080/swagger", text="<body>", headers={'SOME-HEADER': 'SOME-VALUE'})
        header_configuration.evaluate()

        assert (
            header_configuration.status == cachet_url_monitor.status.ComponentStatus.OPERATIONAL
        ), "Component status set incorrectly"


def test_evaluate_with_failure(configuration):
    with requests_mock.mock() as m:
        m.get("http://localhost:8080/swagger", text="<body>", status_code=400)
        configuration.evaluate()

        assert (
            configuration.status == cachet_url_monitor.status.ComponentStatus.MAJOR_OUTAGE
        ), "Component status set incorrectly or custom incident status is incorrectly parsed"


def test_evaluate_with_timeout(configuration, mock_logger):
    with requests_mock.mock() as m:
        m.get("http://localhost:8080/swagger", exc=requests.Timeout)
        configuration.evaluate()

        assert (
            configuration.status == cachet_url_monitor.status.ComponentStatus.PERFORMANCE_ISSUES
        ), "Component status set incorrectly"
        mock_logger.warning.assert_called_with("Request timed out")


def test_evaluate_with_connection_error(configuration, mock_logger):
    with requests_mock.mock() as m:
        m.get("http://localhost:8080/swagger", exc=requests.ConnectionError)
        configuration.evaluate()

        assert (
            configuration.status == cachet_url_monitor.status.ComponentStatus.PARTIAL_OUTAGE
        ), "Component status set incorrectly"
        mock_logger.warning.assert_called_with("The URL is unreachable: GET http://localhost:8080/swagger")


def test_evaluate_with_http_error(configuration, mock_logger):
    with requests_mock.mock() as m:
        m.get("http://localhost:8080/swagger", exc=requests.HTTPError)
        configuration.evaluate()

        assert (
            configuration.status == cachet_url_monitor.status.ComponentStatus.PARTIAL_OUTAGE
        ), "Component status set incorrectly"
        mock_logger.exception.assert_called_with("Unexpected HTTP response")


def test_webhooks(webhooks_configuration, mock_logger, mock_client):
    assert len(webhooks_configuration.webhooks) == 2
    push_incident_response = mock.Mock()
    push_incident_response.ok = False
    mock_client.push_incident.return_value = push_incident_response
    with requests_mock.mock() as m:
        m.get("http://localhost:8080/swagger", exc=requests.HTTPError)
        m.post("https://push.example.com/foo%20is%20unavailable", text="")
        m.post("https://push.example.com/message?token=%3Capptoken%3E&title=foo+is+unavailable", text="")
        webhooks_configuration.evaluate()

        assert (
            webhooks_configuration.status == cachet_url_monitor.status.ComponentStatus.PARTIAL_OUTAGE
        ), "Component status set incorrectly"
        mock_logger.exception.assert_called_with("Unexpected HTTP response")
        webhooks_configuration.push_incident()
        mock_logger.info.assert_called_with(
            "Webhook https://push.example.com/message?token=<apptoken> triggered with foo unavailable"
        )


def test_push_status(configuration, mock_client):
    mock_client.get_component_status.return_value = cachet_url_monitor.status.ComponentStatus.PARTIAL_OUTAGE
    push_status_response = mock.Mock()
    mock_client.push_status.return_value = push_status_response
    push_status_response.ok = True
    configuration.previous_status = cachet_url_monitor.status.ComponentStatus.PARTIAL_OUTAGE
    configuration.status = cachet_url_monitor.status.ComponentStatus.OPERATIONAL

    configuration.push_status()

    mock_client.push_status.assert_called_once_with(1, cachet_url_monitor.status.ComponentStatus.OPERATIONAL)


def test_push_status_with_new_failure(configuration, mock_client):
    mock_client.get_component_status.return_value = cachet_url_monitor.status.ComponentStatus.OPERATIONAL
    push_status_response = mock.Mock()
    mock_client.push_status.return_value = push_status_response
    push_status_response.ok = False
    configuration.status = cachet_url_monitor.status.ComponentStatus.PARTIAL_OUTAGE

    configuration.push_status()

    mock_client.push_status.assert_called_once_with(1, cachet_url_monitor.status.ComponentStatus.PARTIAL_OUTAGE)


def test_push_status_same_status(configuration, mock_client):
    mock_client.get_component_status.return_value = cachet_url_monitor.status.ComponentStatus.OPERATIONAL
    configuration.status = cachet_url_monitor.status.ComponentStatus.OPERATIONAL

    configuration.push_status()

    mock_client.push_status.assert_not_called()


def test_init_multiple_urls(multiple_urls_configuration):
    expected_method = ["GET", "POST"]
    expected_url = ["http://localhost:8080/swagger", "http://localhost:8080/bar"]

    assert len(multiple_urls_configuration) == 2
    for index in range(len(multiple_urls_configuration)):
        config = multiple_urls_configuration[index]
        assert len(config.data) == 2, "Number of root elements in config.yml is incorrect"
        assert len(config.expectations) == 1, "Number of expectations read from file is incorrect"

        assert expected_method[index] == config.endpoint_method
        assert expected_url[index] == config.endpoint_url


def test_init_invalid_configuration(invalid_config_file, mock_client):
    with pytest.raises(cachet_url_monitor.configuration.ConfigurationValidationError):
        Configuration(invalid_config_file, 0, mock_client)


# Tests for __init__ defaults
def test_init_defaults_timeout(config_file, mock_client, mock_logger):
    # Test that timeout: 0 in config results in endpoint_timeout = 1
    config_with_zero_timeout = config_file.copy()
    config_with_zero_timeout["endpoints"][0]["timeout"] = 0
    conf = Configuration(config_with_zero_timeout, 0, mock_client)
    assert conf.endpoint_timeout == 1

def test_init_defaults_allowed_fails(config_file, mock_client, mock_logger):
    # Modify config_file to remove allowed_fails
    config_without_allowed_fails = config_file.copy()
    del config_without_allowed_fails["endpoints"][0]["allowed_fails"]
    conf = Configuration(config_without_allowed_fails, 0, mock_client)
    assert conf.allowed_fails == 0

def test_init_webhooks_none(config_file, mock_client, mock_logger):
    conf = Configuration(config_file, 0, mock_client, webhooks=None)
    assert conf.webhooks == []

# Test for evaluate verify default
def test_evaluate_default_verify_true(configuration):
    # This test is similar to test_evaluate, ensuring verify=True is default
    # The 'configuration' fixture uses a config that doesn't specify 'insecure'
    with requests_mock.mock() as m:
        m.get("http://localhost:8080/swagger", text="<body>")
        configuration.evaluate()
        assert m.last_request.verify is True


# Tests for if_trigger_update
def test_if_trigger_update_not_operational_fails_less_than_allowed(configuration, mock_logger):
    configuration.status = cachet_url_monitor.status.ComponentStatus.PARTIAL_OUTAGE
    configuration.allowed_fails = 3
    configuration.current_fails = 1
    configuration.trigger_update = True # Ensure it starts as True
    configuration.message = "Initial message" # Ensure message attribute exists

    configuration.if_trigger_update()
    assert configuration.trigger_update is False
    assert configuration.current_fails == 2 # Incremented
    mock_logger.warning.assert_called_with("Failure #2 with threshold set to 3")

def test_if_trigger_update_not_operational_fails_equals_allowed(configuration, mock_logger):
    configuration.status = cachet_url_monitor.status.ComponentStatus.PARTIAL_OUTAGE
    configuration.allowed_fails = 3
    configuration.current_fails = 2 # Will become 3
    configuration.trigger_update = True
    configuration.message = "Initial message"

    configuration.if_trigger_update()
    # According to code: if current_fails (3) <= allowed_fails (3), trigger_update is False.
    assert configuration.trigger_update is False 
    assert configuration.current_fails == 3
    mock_logger.warning.assert_called_with("Failure #3 with threshold set to 3")

def test_if_trigger_update_not_operational_fails_greater_than_allowed(configuration, mock_logger):
    configuration.status = cachet_url_monitor.status.ComponentStatus.PARTIAL_OUTAGE
    configuration.allowed_fails = 1
    configuration.current_fails = 1 # Will become 2
    configuration.trigger_update = False # Start as False, should become True
    configuration.message = "Initial message"
    
    configuration.if_trigger_update() # current_fails becomes 2. 2 <= 1 is False. So it goes to the else block.
    assert configuration.trigger_update is True 
    assert configuration.current_fails == 0 
    mock_logger.warning.assert_called_with("Failure #2 with threshold set to 1")


def test_if_trigger_update_operational(configuration):
    configuration.status = cachet_url_monitor.status.ComponentStatus.OPERATIONAL
    configuration.current_fails = 2 # Some previous fails
    configuration.allowed_fails = 3
    configuration.trigger_update = False # Assume it was false

    configuration.if_trigger_update()
    assert configuration.trigger_update is True
    assert configuration.current_fails == 0


# Tests for push_status
def test_push_status_trigger_update_false(configuration, mock_client, mock_logger):
    configuration.trigger_update = False # Explicitly set for test clarity
    configuration.previous_status = cachet_url_monitor.status.ComponentStatus.OPERATIONAL
    configuration.status = cachet_url_monitor.status.ComponentStatus.MAJOR_OUTAGE
    configuration.message = "Initial message"
    
    configuration.push_status()
    # The `previous_status` is updated regardless of `trigger_update` if they were different.
    # No API calls should be made if trigger_update is false.
    mock_client.get_component_status.assert_not_called()
    mock_client.push_status.assert_not_called()
    
def test_push_status_same_as_api(configuration, mock_client, mock_logger):
    current_status = cachet_url_monitor.status.ComponentStatus.MAJOR_OUTAGE
    configuration.status = current_status
    configuration.previous_status = cachet_url_monitor.status.ComponentStatus.OPERATIONAL 
    configuration.trigger_update = True
    configuration.message = "Initial message"

    # Reset mock from __init__ call, then set new return_value for the call inside push_status
    mock_client.get_component_status.reset_mock() 
    mock_client.get_component_status.return_value = current_status 

    configuration.push_status()

    mock_client.get_component_status.assert_called_once_with(configuration.component_id)
    mock_client.push_status.assert_not_called()

def test_push_status_api_call_fails(configuration, mock_client, mock_logger):
    configuration.status = cachet_url_monitor.status.ComponentStatus.MAJOR_OUTAGE
    configuration.previous_status = cachet_url_monitor.status.ComponentStatus.OPERATIONAL
    configuration.trigger_update = True
    configuration.message = "Initial message"
    
    # Reset mock from __init__ call, then set new return_value for the call inside push_status
    mock_client.get_component_status.reset_mock()
    mock_client.get_component_status.return_value = cachet_url_monitor.status.ComponentStatus.OPERATIONAL
    
    mock_response = mock.Mock()
    mock_response.ok = False
    mock_response.status_code = 500
    mock_client.push_status.return_value = mock_response

    configuration.push_status()
    mock_logger.warning.assert_called_with(
        f"Component update failed with HTTP status: 500. API status: {configuration.status}"
    )

# Tests for push_metrics
def test_push_metrics_no_metric_id(configuration, mock_client):
    configuration.metric_id = None # Ensure no metric_id
    # Simulate that evaluate ran and set up self.request
    configuration.request = mock.Mock() 
    configuration.request.elapsed.total_seconds.return_value = 1.0
    configuration.current_timestamp = 12345

    configuration.push_metrics()
    mock_client.push_metrics.assert_not_called()

def test_push_metrics_no_request_attribute(configuration, mock_client):
    # Ensure metric_id is set
    configuration.metric_id = 123 
    if hasattr(configuration, 'request'):
        delattr(configuration, 'request') # Ensure no request attribute

    configuration.push_metrics()
    mock_client.push_metrics.assert_not_called()

def test_push_metrics_api_call_fails(configuration, mock_client, mock_logger):
    configuration.metric_id = 123
    configuration.request = mock.Mock()
    configuration.request.elapsed.total_seconds.return_value = 1.23
    configuration.current_timestamp = 1234567890
    configuration.latency_unit = "s"

    mock_response = mock.Mock()
    mock_response.ok = False
    mock_response.status_code = 500
    mock_client.push_metrics.return_value = mock_response

    configuration.push_metrics()
    mock_logger.warning.assert_called_with(f"Metric upload failed with status [{mock_response.status_code}]")


# Tests for trigger_webhooks
@pytest.mark.parametrize("status,expected_title_segment", [
    (cachet_url_monitor.status.ComponentStatus.PERFORMANCE_ISSUES, "degraded"),
    (cachet_url_monitor.status.ComponentStatus.OPERATIONAL, "OK"),
    (cachet_url_monitor.status.ComponentStatus.MAJOR_OUTAGE, "unavailable"),
])
def test_trigger_webhooks_title_generation(configuration, mock_logger, status, expected_title_segment):
    configuration.status = status
    # Mock endpoint name for title generation
    configuration.endpoint["name"] = "TestService"
    configuration.message = "Webhook test message" # Ensure self.message exists
    
    mock_webhook_instance = mock.Mock(spec=Webhook)
    mock_webhook_response = mock.Mock()
    mock_webhook_response.ok = True
    mock_webhook_instance.push_incident.return_value = mock_webhook_response
    configuration.webhooks = [mock_webhook_instance]
    
    # Needed by get_incident_title
    configuration.messages = default_messages = {
        "incident_outage": "{name} is unavailable",
        "incident_operational": "{name} is operational",
        "incident_performance": "{name} has degraded performance",
    }


    configuration.trigger_webhooks()

    # Check that the title passed to webhook contains the expected segment
    args, _ = mock_webhook_instance.push_incident.call_args
    actual_title = args[0] # First arg is title
    assert expected_title_segment in actual_title.lower()
    mock_logger.info.assert_called() # Check some log happened

def test_trigger_webhooks_push_fails(configuration, mock_logger):
    configuration.status = cachet_url_monitor.status.ComponentStatus.MAJOR_OUTAGE
    configuration.endpoint["name"] = "TestService"
    configuration.messages = {"incident_outage": "{name} is unavailable"}
    configuration.message = "Webhook failure test message"


    mock_webhook_instance = mock.Mock(spec=Webhook)
    mock_webhook_instance.url = "http://failedwebhook.com"
    mock_webhook_response = mock.Mock()
    mock_webhook_response.ok = False
    mock_webhook_response.status_code = 503
    mock_webhook_instance.push_incident.return_value = mock_webhook_response
    configuration.webhooks = [mock_webhook_instance]

    configuration.trigger_webhooks()

    mock_logger.warning.assert_called_with(f"Webhook http://failedwebhook.com failed with status [503]")


# Tests for push_incident
def test_push_incident_trigger_update_false(configuration, mock_client):
    configuration.trigger_update = False
    configuration.push_incident()
    mock_client.push_incident.assert_not_called()

@mock.patch.object(Configuration, 'trigger_webhooks')
def test_push_incident_create_api_call_fails(mock_trigger_webhooks, configuration, mock_client, mock_logger):
    configuration.trigger_update = True
    configuration.status = cachet_url_monitor.status.ComponentStatus.MAJOR_OUTAGE
    configuration.message = "Creating incident - API fail"
    # Ensure incident_id does not exist
    if hasattr(configuration, 'incident_id'):
        delattr(configuration, 'incident_id')
    
    mock_response = mock.Mock()
    mock_response.ok = False
    mock_response.status_code = 500
    mock_client.push_incident.return_value = mock_response

    configuration.push_incident()
    
    mock_client.push_incident.assert_called_once()
    mock_logger.warning.assert_called_with(
        f'Incident upload failed with status [{mock_response.status_code}], message: "{configuration.message}"'
    )
    mock_trigger_webhooks.assert_called_once() # Webhooks should still be triggered

@mock.patch.object(Configuration, 'trigger_webhooks')
def test_push_incident_update_api_call_fails(mock_trigger_webhooks, configuration, mock_client, mock_logger):
    configuration.trigger_update = True
    configuration.status = cachet_url_monitor.status.ComponentStatus.OPERATIONAL
    configuration.incident_id = 12345 # Existing incident
    configuration.message = "Updating incident - API fail"
    
    mock_response = mock.Mock()
    mock_response.ok = False
    mock_response.status_code = 500
    mock_client.push_incident.return_value = mock_response

    configuration.push_incident()

    mock_client.push_incident.assert_called_once()
    mock_logger.warning.assert_called_with(
        f'Incident update failed with status [{mock_response.status_code}], message: "{configuration.message}"'
    )
    mock_trigger_webhooks.assert_called_once() # Webhooks should still be triggered

@mock.patch.object(Configuration, 'trigger_webhooks')
def test_push_incident_update_successful_deletes_id(mock_trigger_webhooks, configuration, mock_client, mock_logger):
    configuration.trigger_update = True
    configuration.status = cachet_url_monitor.status.ComponentStatus.OPERATIONAL
    configuration.incident_id = 12345 
    configuration.endpoint["name"] = "TestService" # For get_incident_title
    configuration.messages = {"incident_operational": "{name} is operational"}
    configuration.message = "Incident resolved successfully"


    mock_response = mock.Mock()
    mock_response.ok = True
    mock_client.push_incident.return_value = mock_response

    configuration.push_incident()

    assert not hasattr(configuration, 'incident_id')
    mock_logger.info.assert_called_with(
        f'Incident updated, API healthy again: component status [{configuration.status}], message: "{configuration.message}"'
    )
    mock_trigger_webhooks.assert_called_once()

@mock.patch.object(Configuration, 'trigger_webhooks')
def test_push_incident_calls_trigger_webhooks_on_create(mock_trigger_webhooks, configuration, mock_client):
    configuration.trigger_update = True
    configuration.status = cachet_url_monitor.status.ComponentStatus.MAJOR_OUTAGE
    configuration.message = "Creating incident for webhook test"
    if hasattr(configuration, 'incident_id'):
        delattr(configuration, 'incident_id')
    
    mock_response = mock.Mock()
    mock_response.ok = True
    mock_response.json.return_value = {"data": {"id": 67890}} # For setting self.incident_id
    mock_client.push_incident.return_value = mock_response
    
    configuration.push_incident()
    mock_trigger_webhooks.assert_called_once()
    assert configuration.incident_id == 67890

@mock.patch.object(Configuration, 'trigger_webhooks')
def test_push_incident_calls_trigger_webhooks_on_resolve(mock_trigger_webhooks, configuration, mock_client):
    configuration.trigger_update = True
    configuration.status = cachet_url_monitor.status.ComponentStatus.OPERATIONAL
    configuration.incident_id = 12345 
    configuration.message = "Resolving incident for webhook test"
    
    mock_response = mock.Mock()
    mock_response.ok = True
    mock_client.push_incident.return_value = mock_response

    configuration.push_incident()
    mock_trigger_webhooks.assert_called_once()
