from dataclasses import dataclass


@dataclass(slots=True)
class WMIObject:
    """Base class representing a WMI object"""
