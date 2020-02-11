#!/usr/bin/env python
"""
This file defines all the different status different values.
These are all constants and are coupled to cachet's API configuration.
"""
from enum import Enum


class ComponentStatus(Enum):
    UNKNOWN = 0
    OPERATIONAL = 1
    PERFORMANCE_ISSUES = 2
    PARTIAL_OUTAGE = 3
    MAJOR_OUTAGE = 4


INCIDENT_PARTIAL = 'PARTIAL'
INCIDENT_MAJOR = 'MAJOR'
INCIDENT_PERFORMANCE = 'PERFORMANCE'

INCIDENT_MAP = {
    INCIDENT_PARTIAL: ComponentStatus.PARTIAL_OUTAGE,
    INCIDENT_MAJOR: ComponentStatus.MAJOR_OUTAGE,
    INCIDENT_PERFORMANCE: ComponentStatus.PERFORMANCE_ISSUES,
}


class IncidentStatus(Enum):
    SCHEDULED = 0
    INVESTIGATING = 1
    IDENTIFIED = 2
    WATCHING = 3
    FIXED = 4
