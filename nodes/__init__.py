# -*- coding: utf-8 -*-
"""
Nodes package for the API Integration Platform.

This package contains all the different types of nodes that can be used
in workflows. Nodes are categorized into sub-packages like 'api', 'data',
'utility', etc., which are automatically scanned by the NodeRegistry.
"""
import logging

logger = logging.getLogger(__name__)

# Attempt to import sub-packages to ensure they are discoverable by NodeRegistry.
# NodeRegistry will then iterate through their modules.
try:
    from . import api
except ImportError:
    logger.warning("Nodes sub-package 'api' not found or could not be imported. Create /nodes/api/__init__.py and node files within.")
try:
    from . import data
except ImportError:
    logger.warning("Nodes sub-package 'data' not found or could not be imported. Create /nodes/data/__init__.py and node files within.")
try:
    from . import utility
except ImportError:
    logger.warning("Nodes sub-package 'utility' not found or could not be imported. Create /nodes/utility/__init__.py and node files within.")

logger.debug("Nodes package initialized.")

