#!/usr/bin/env python

seconds_per_unit = {"ms": 1000, "milliseconds": 1000, "s": 1, "seconds": 1, "m": float(1) / 60,
                    "minutes": float(1) / 60, "h": float(1) / 3600, "hours": float(1) / 3600}


def convert_to_unit(time_unit, value):
    """
    Will convert the given value from seconds to the given time_unit.

    :param time_unit: The time unit to which the value will be converted to, from seconds.
    This is a string parameter. The unit must be in the short form.
    :param value: The given value that will be converted. This value must be in seconds.
    :return: The converted value.
    """
    return value * seconds_per_unit[time_unit]
