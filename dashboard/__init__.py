# -*- coding: utf-8 -*-
"""
Dashboard package for the API Integration Platform.

This package contains the web interface (Flask or FastAPI based) for
monitoring and managing the platform.
"""

import logging

logger = logging.getLogger(__name__)

# Try to import the main app components to make them available
try:
    from .app import create_app, run_dashboard_in_background
    logger.info("Dashboard app components imported.")
except ImportError as e:
    logger.warning(f"Could not import dashboard app components (create_app, run_dashboard_in_background): {e}. Ensure dashboard/app.py exists.")

logger.debug("Dashboard package initialized.")

