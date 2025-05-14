# -*- coding: utf-8 -*-
"""
Routers for the Dashboard API.

This package contains FastAPI routers for different aspects of the platform,
like nodes, workflows, logs, etc.
"""

import logging

logger = logging.getLogger(__name__)

# You can import and re-export routers here if desired for easier access,
# though it's often cleaner to import them directly in app.py.
# Example:
# from .nodes import router as nodes_router
# from .workflows import router as workflows_router
# from .logs import router as logs_router

logger.debug("Dashboard routers package initialized.")

