#!/usr/bin/env python
import unittest
from typing import Dict, List
import unittest.mock as mock # Standard library mock

import requests_mock
from click.testing import CliRunner # For testing Click CLI

from cachet_url_monitor.client import CachetClient, normalize_url, save_config, run_client # Added normalize_url, save_config, run_client
from cachet_url_monitor.exceptions import MetricNonexistentError, ComponentNonexistentError # Added ComponentNonexistentError
from cachet_url_monitor.status import ComponentStatus, IncidentStatus # Added IncidentStatus
import cachet_url_monitor.latency_unit as latency_unit_module # For mocking latency_unit.convert_to_unit

TOKEN: str = "token_123"
CACHET_URL: str = "http://foo.localhost"
JSON: Dict[str, List[Dict[str, int]]] = {"data": [{"id": 1}]}


class TestNormalizeUrl(unittest.TestCase):
    def test_normalize_url_with_http(self):
        self.assertEqual(normalize_url("http://example.com"), "http://example.com")

    def test_normalize_url_with_https(self):
        self.assertEqual(normalize_url("https://example.com"), "https://example.com")

    def test_normalize_url_no_schema(self):
        self.assertEqual(normalize_url("example.com"), "http://example.com")

    def test_normalize_url_mixed_case_schema(self):
        self.assertEqual(normalize_url("HttP://example.com"), "HttP://example.com")


class TestSaveConfig(unittest.TestCase):
    @mock.patch("builtins.open", new_callable=mock.mock_open)
    @mock.patch("cachet_url_monitor.client.dump") # Changed mock path here
    def test_save_config_writes_to_file(self, mock_yaml_dump, mock_open_file):
        config_map = {"key": "value"}
        filename = "test_config.yml"
        
        save_config(config_map, filename)
        
        mock_open_file.assert_called_once_with(filename, "w")
        mock_yaml_dump.assert_called_once_with(config_map, mock_open_file())


class ClientTest(unittest.TestCase):
    def setUp(self):
        self.client = CachetClient("foo.localhost", TOKEN)

    def test_init(self):
        self.assertEqual(self.client.headers, {"X-Cachet-Token": TOKEN}, "Header was not set correctly")
        self.assertEqual(self.client.url, CACHET_URL, "Cachet API URL was set incorrectly")

    @requests_mock.mock()
    def test_get_components(self, m):
        m.get(f"{CACHET_URL}/components", json=JSON, headers={"X-Cachet-Token": TOKEN})
        components = self.client.get_components()

        self.assertEqual(components, [{"id": 1}], "Getting components list is incorrect.")

    @requests_mock.mock()
    def test_get_metrics(self, m):
        m.get(f"{CACHET_URL}/metrics", json=JSON)
        metrics = self.client.get_metrics()

        self.assertEqual(metrics, [{"id": 1}], "Getting metrics list is incorrect.")

    @requests_mock.mock()
    def test_generate_config(self, m):
        def components():
            return {
                "data": [
                    {"id": "1", "name": "apache", "link": "http://abc.def", "enabled": True},
                    {"id": "2", "name": "haproxy", "link": "http://ghi.jkl", "enabled": False},
                    {"id": "3", "name": "nginx", "link": "http://mno.pqr", "enabled": True},
                ]
            }

        m.get(f"{CACHET_URL}/components", json=components(), headers={"X-Cachet-Token": TOKEN})
        config = self.client.generate_config()

        self.assertEqual(
            config,
            {
                "cachet": {"api_url": CACHET_URL, "token": TOKEN},
                "endpoints": [
                    {
                        "name": "apache",
                        "url": "http://abc.def",
                        "method": "GET",
                        "timeout": 1,
                        "expectation": [{"type": "HTTP_STATUS", "status_range": "200-300", "incident": "MAJOR"}],
                        "allowed_fails": 0,
                        "frequency": 30,
                        "component_id": "1",
                        "action": ["CREATE_INCIDENT", "UPDATE_STATUS"],
                        "public_incidents": True,
                    },
                    {
                        "name": "nginx",
                        "url": "http://mno.pqr",
                        "method": "GET",
                        "timeout": 1,
                        "expectation": [{"type": "HTTP_STATUS", "status_range": "200-300", "incident": "MAJOR"}],
                        "allowed_fails": 0,
                        "frequency": 30,
                        "component_id": "3",
                        "action": ["CREATE_INCIDENT", "UPDATE_STATUS"],
                        "public_incidents": True,
                    },
                ],
            },
            "Generated config is incorrect.",
        )

    @requests_mock.mock()
    def test_get_default_metric_value(self, m):
        m.get(f"{CACHET_URL}/metrics/123", json={"data": {"default_value": 0.456}}, headers={"X-Cachet-Token": TOKEN})
        default_metric_value = self.client.get_default_metric_value(123)

        self.assertEqual(default_metric_value, 0.456, "Getting default metric value is incorrect.")

    @requests_mock.mock()
    def test_get_default_metric_value_invalid_id(self, m):
        m.get(f"{CACHET_URL}/metrics/123", headers={"X-Cachet-Token": TOKEN}, status_code=400)
        with self.assertRaises(MetricNonexistentError):
            self.client.get_default_metric_value(123)

    @requests_mock.mock()
    def test_get_component_status(self, m):
        def json():
            return {"data": {"status": ComponentStatus.OPERATIONAL.value}}

        m.get(f"{CACHET_URL}/components/123", json=json(), headers={"X-Cachet-Token": TOKEN})
        status = self.client.get_component_status(123)

        self.assertEqual(status, ComponentStatus.OPERATIONAL, "Getting component status value is incorrect.")

    @requests_mock.mock()
    def test_push_status(self, m):
        m.put(
            f"{CACHET_URL}/components/123?id=123&status={ComponentStatus.PARTIAL_OUTAGE.value}",
            headers={"X-Cachet-Token": TOKEN},
        )
        response = self.client.push_status(123, ComponentStatus.PARTIAL_OUTAGE)

        self.assertTrue(response.ok, "Pushing status value is failed.")
