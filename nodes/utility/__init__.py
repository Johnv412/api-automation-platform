# -*- coding: utf-8 -*-
"""
Utility nodes sub-package.

This package is for nodes that provide general utility functions within a workflow,
such as conditional logic, delays, data merging, or custom script execution.

Nodes discovered here will be categorized as 'utility' by the NodeRegistry.
"""

import logging

# Import node classes here to make them discoverable by the NodeRegistry
from .logger_node import LoggerNode

logger = logging.getLogger(__name__)
logger.debug("Nodes Utility sub-package initialized with LoggerNode.")

__all__ = ["LoggerNode"]

