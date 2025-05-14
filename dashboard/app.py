# -*- coding: utf-8 -*-
"""
Main FastAPI application for the Dashboard.

This module sets up the FastAPI application, includes routers,
and provides functions to create and run the dashboard.
"""

import logging
import multiprocessing
import os # Added for path joining
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

# Import routers
from .routers import nodes as nodes_router
from .routers import workflows as workflows_router
from .routers import logs as logs_router

logger = logging.getLogger(__name__)

def create_app(workflow_engine: Any, node_registry: Any, config: Dict[str, Any]) -> FastAPI:
    """
    Creates and configures the FastAPI application for the dashboard.

    Args:
        workflow_engine: Instance of the WorkflowEngine.
        node_registry: Instance of the NodeRegistry.
        config: The main platform configuration dictionary.

    Returns:
        FastAPI: The configured FastAPI application instance.
    """
    dashboard_config = config.get("dashboard", {})
    root_path = dashboard_config.get("root_path", "") # Adjusted default to empty for simpler local dev, can be /dashboard for proxy

    app = FastAPI(
        title=dashboard_config.get("title", "API Integration Platform Dashboard"),
        description=dashboard_config.get("description", "A web interface to monitor and manage the API Integration Platform."),
        version=dashboard_config.get("version", config.get("version", "0.1.0")),
        root_path=root_path 
    )

    app.state.workflow_engine = workflow_engine
    app.state.node_registry = node_registry
    app.state.platform_config = config

    # Determine paths relative to this file for robustness
    dashboard_module_dir = os.path.dirname(__file__)
    static_dir = os.path.join(dashboard_module_dir, "static")
    templates_dir = os.path.join(dashboard_module_dir, "templates")

    try:
        if not os.path.exists(static_dir):
            os.makedirs(static_dir, exist_ok=True)
            logger.info(f"Created static directory: {static_dir}")
        app.mount("/static", StaticFiles(directory=static_dir), name="static")
        logger.info(f"Mounted static files directory: {static_dir}")
    except RuntimeError as e:
        logger.warning(f"Could not mount static files directory 
                       \'{static_dir}\': {e}. Ensure it exists or can be created.")

    try:
        if not os.path.exists(templates_dir):
            os.makedirs(templates_dir, exist_ok=True)
            logger.info(f"Created templates directory: {templates_dir}")
        templates = Jinja2Templates(directory=templates_dir)
        app.state.templates = templates
        logger.info(f"Initialized Jinja2Templates directory: {templates_dir}")
    except Exception as e:
        logger.warning(f"Could not initialize Jinja2Templates directory 
                       \'{templates_dir}\': {e}. Ensure it exists or can be created.")
        app.state.templates = None

    # Include API routers
    app.include_router(nodes_router.router, prefix="/api/nodes", tags=["Nodes API"])
    app.include_router(workflows_router.router, prefix="/api/workflows", tags=["Workflows API"])
    app.include_router(logs_router.router, prefix="/api/logs", tags=["Logs API"])

    # Root path / UI routes
    @app.get("/", tags=["Dashboard UI"])
    async def get_dashboard_home(request: Request):
        if app.state.templates:
            return app.state.templates.TemplateResponse("index.html", {"request": request, "title": "Platform Dashboard"})
        return {"message": "Welcome to the API Integration Platform Dashboard! UI templates not found."}

    @app.get("/nodes", tags=["Dashboard UI"])
    async def get_nodes_page(request: Request):
        if app.state.templates:
            # Data will be fetched by JavaScript from /api/nodes
            return app.state.templates.TemplateResponse("nodes.html", {"request": request, "title": "Available Nodes"})
        return {"message": "Nodes page UI templates not found."}

    @app.get("/workflows", tags=["Dashboard UI"])
    async def get_workflows_page(request: Request):
        if app.state.templates:
            # Data will be fetched by JavaScript from /api/workflows
            return app.state.templates.TemplateResponse("workflows.html", {"request": request, "title": "Workflows"})
        return {"message": "Workflows page UI templates not found."}

    @app.get("/logs", tags=["Dashboard UI"])
    async def get_logs_page(request: Request):
        if app.state.templates:
            # Data will be fetched by JavaScript from /api/logs
            return app.state.templates.TemplateResponse("logs.html", {"request": request, "title": "Platform Logs"})
        return {"message": "Logs page UI templates not found."}

    logger.info("FastAPI dashboard app created with UI routes and API routers.")
    return app

def run_dashboard_in_background(app: FastAPI, host: str = "0.0.0.0", port: int = 5001) -> multiprocessing.Process:
    def run_server():
        logger.info(f"Starting Uvicorn server for dashboard on http://{host}:{port}")
        uvicorn.run(app, host=host, port=port, log_level="info")

    process = multiprocessing.Process(target=run_server, daemon=True)
    process.start()
    logger.info(f"Dashboard server process started in background (PID: {process.pid}).")
    return process

# Standalone testing block (from original file, kept for reference/module testing)
# if __name__ == "__main__":
#     if not logging.getLogger().hasHandlers():
#          logging.basicConfig(level=logging.INFO)
#     logger.info("Running dashboard app.py for standalone testing.")
#     class MockWorkflowEngine: pass
#     class MockNodeRegistry: 
#         def get_node_types(self): return {}
#     mock_config = {"dashboard": {"port": 5002, "title": "Test Dashboard"}, "logging": {"root": {"level": "DEBUG"}}}
#     dashboard_module_dir = os.path.dirname(__file__)
#     static_dir_test = os.path.join(dashboard_module_dir, "static")
#     templates_dir_test = os.path.join(dashboard_module_dir, "templates")
#     if not os.path.exists(static_dir_test): os.makedirs(static_dir_test)
#     if not os.path.exists(templates_dir_test): os.makedirs(templates_dir_test)
#     if not os.path.exists(os.path.join(templates_dir_test, "index.html")):
#         with open(os.path.join(templates_dir_test, "index.html"), "w") as f: f.write("<h1>{{ title }}</h1><p>Test Index</p>")
#     if not os.path.exists(os.path.join(templates_dir_test, "nodes.html")):
#         with open(os.path.join(templates_dir_test, "nodes.html"), "w") as f: f.write("<h1>{{ title }}</h1><p>Test Nodes</p>")
#     if not os.path.exists(os.path.join(templates_dir_test, "workflows.html")):
#         with open(os.path.join(templates_dir_test, "workflows.html"), "w") as f: f.write("<h1>{{ title }}</h1><p>Test Workflows</p>")
#     if not os.path.exists(os.path.join(templates_dir_test, "logs.html")):
#         with open(os.path.join(templates_dir_test, "logs.html"), "w") as f: f.write("<h1>{{ title }}</h1><p>Test Logs</p>")

#     test_app = create_app(MockWorkflowEngine(), MockNodeRegistry(), mock_config)
#     uvicorn.run(test_app, host="127.0.0.1", port=mock_config["dashboard"]["port"])

