#!/usr/bin/env python
class ComponentNonexistentError(Exception):
    """Exception raised when the component does not exist."""

    def __init__(self, component_id):
        self.component_id = component_id

    def __str__(self):
        return repr(f'Component with id [{self.component_id}] does not exist.')


class MetricNonexistentError(Exception):
    """Exception raised when the component does not exist."""

    def __init__(self, metric_id):
        self.metric_id = metric_id

    def __str__(self):
        return repr(f'Metric with id [{self.metric_id}] does not exist.')


class ConfigurationValidationError(Exception):
    """Exception raised when there's a validation error."""

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)