#!/usr/bin/env python
import unittest

from cachet_url_monitor.exceptions import (
    ComponentNonexistentError,
    MetricNonexistentError,
    ConfigurationValidationError,
)


class TestComponentNonexistentError(unittest.TestCase):
    def test_init(self):
        component_id = 123
        exception = ComponentNonexistentError(component_id)
        self.assertEqual(exception.component_id, component_id)

    def test_str(self):
        component_id = 456
        exception = ComponentNonexistentError(component_id)
        expected_str = repr(f"Component with id [{component_id}] does not exist.")
        self.assertEqual(str(exception), expected_str)


class TestMetricNonexistentError(unittest.TestCase):
    def test_init(self):
        metric_id = "metric_abc"
        exception = MetricNonexistentError(metric_id)
        self.assertEqual(exception.metric_id, metric_id)

    def test_str(self):
        metric_id = "metric_xyz"
        exception = MetricNonexistentError(metric_id)
        expected_str = repr(f"Metric with id [{metric_id}] does not exist.")
        self.assertEqual(str(exception), expected_str)


class TestConfigurationValidationError(unittest.TestCase):
    def test_init(self):
        value = "Invalid API URL"
        exception = ConfigurationValidationError(value)
        self.assertEqual(exception.value, value)

    def test_str(self):
        value = "Missing token"
        exception = ConfigurationValidationError(value)
        expected_str = repr(value)
        self.assertEqual(str(exception), expected_str)


if __name__ == "__main__":
    unittest.main()
