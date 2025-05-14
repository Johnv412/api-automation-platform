# -*- coding: utf-8 -*-
"""
API Nodes Sub-package.

This package contains nodes that interact with various external APIs.
Each API should ideally have its own module within this package.

Nodes discovered here will be categorized as 'api' by the NodeRegistry.
"""

import logging

logger = logging.getLogger(__name__)

# You can optionally import specific node classes here if you want them
# to be available directly via `from nodes.api import ...`
# For example:
# try:
#     from .github_node import GitHubNode
# except ImportError:
#     logger.warning("Could not import GitHubNode from nodes.api.github_node")

logger.debug("Nodes API sub-package initialized.")

