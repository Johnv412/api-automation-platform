"""
API Integration Platform - Main Entry Point

This module serves as the entry point for the API Integration Platform.
It initializes the core components, loads workflows, and orchestrates execution.
"""

import argparse
import logging # Keep standard logging import
import os
import signal
import sys
import asyncio
from typing import Dict, List, Optional

from core.workflow_engine import WorkflowEngine
from utils.logging_manager import LoggingManager # Import the class
from utils.secure_config import SecureConfigLoader
from workflows.workflow_loader import WorkflowLoader
from workflows.workflow_validator import WorkflowValidator # For validating loaded workflows
from core.node_registry import NodeRegistry # Needed by validator

# Optional dashboard import
try:
    from dashboard.app import create_app, run_dashboard_in_background
    DASHBOARD_AVAILABLE = True
except ImportError:
    DASHBOARD_AVAILABLE = False
    # Logging not set up here yet, so can't log this warning effectively before setup.

class APIIntegrationPlatform:
    """
    Main orchestrator class for the API Integration Platform.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the API Integration Platform.
        """
        # 1. Initialize SecureConfigLoader and load configuration
        self.config_loader = SecureConfigLoader(config_path=config_path)
        self.config = self.config_loader.load_config()

        # 2. Initialize and setup LoggingManager
        # Pass the config_loader instance if LoggingManager needs to access config directly for its setup.
        # Or pass the loaded logging config from self.config.
        logging_config_from_secure_loader = self.config.get("logging") # Assuming logging config is under "logging" key
        self.logging_manager = LoggingManager(logging_config_from_secure_loader)
        self.logging_manager.setup_logging(
            log_level_override=self.config.get("global_log_level") # Example: allow global override from main config
        )
        
        self.logger = self.logging_manager.get_logger(self.__class__.__name__)
        self.logger.info("API Integration Platform initializing...")
        
        if not DASHBOARD_AVAILABLE:
            self.logger.warning("Dashboard dependencies not available. Install with 'pip install .[dashboard]' to enable.")

        # 3. Initialize NodeRegistry (needed by WorkflowValidator and WorkflowEngine)
        self.node_registry = NodeRegistry() 
        self.logger.info(f"NodeRegistry initialized with {len(self.node_registry.node_types)} node types.")

        # 4. Initialize WorkflowLoader and WorkflowValidator
        workflow_definitions_path = self.config.get("workflows", {}).get("definitions_path", "workflows/definitions/")
        self.workflow_loader = WorkflowLoader(workflow_dir=workflow_definitions_path)
        self.workflow_validator = WorkflowValidator(node_registry=self.node_registry)
        self.logger.info(f"WorkflowLoader initialized for directory: {workflow_definitions_path}")

        # 5. Initialize WorkflowEngine
        self.workflow_engine = WorkflowEngine(config=self.config, node_registry=self.node_registry) # Pass node_registry
        self.logger.info("WorkflowEngine initialized.")
        
        self.running = False
        self.dashboard_process = None
        
        signal.signal(signal.SIGINT, self._handle_shutdown_signal)
        signal.signal(signal.SIGTERM, self._handle_shutdown_signal)
        
        self.logger.info("API Integration Platform initialized successfully.")

    async def start_async(self, workflow_name_or_path: Optional[str] = None, run_dashboard: bool = False):
        self.running = True
        self.logger.info("Starting API Integration Platform (async mode)...")

        if run_dashboard and DASHBOARD_AVAILABLE:
            self.logger.info("Attempting to start dashboard...")
            try:
                # Assuming create_app and run_dashboard_in_background are defined in dashboard.app
                app = create_app(workflow_engine=self.workflow_engine, config=self.config)
                # run_dashboard_in_background should handle running Flask/FastAPI in a way that doesn't block asyncio
                self.dashboard_process = run_dashboard_in_background(app, port=self.config.get("dashboard", {}).get("port", 5001))
                self.logger.info(f"Dashboard process started (PID: {self.dashboard_process.pid if self.dashboard_process else 'unknown'}).")
            except Exception as e:
                self.logger.error(f"Failed to start dashboard: {e}", exc_info=True)
        elif run_dashboard and not DASHBOARD_AVAILABLE:
            self.logger.warning("Dashboard requested but not available.")

        try:
            if workflow_name_or_path:
                self.logger.info(f"Attempting to load and run single workflow: {workflow_name_or_path}")
                try:
                    workflow_def = self.workflow_loader.load_workflow(workflow_name_or_path)
                    self.workflow_validator.validate_workflow(workflow_def) # Validate before execution
                    self.logger.info(f"Workflow 
                                     \'{workflow_def.get("name")}\' loaded and validated. Executing...")
                    # WorkflowEngine.execute_workflow is async
                    execution_id = await self.workflow_engine.execute_workflow(workflow_def)
                    self.logger.info(f"Workflow 
                                     \'{workflow_def.get("name")}\' execution started with ID: {execution_id}")
                except FileNotFoundError:
                    self.logger.error(f"Workflow definition file not found: {workflow_name_or_path}")
                except Exception as e:
                    self.logger.error(f"Failed to load, validate, or start workflow 
                                      \'{workflow_name_or_path}\': {e}", exc_info=True)
                    # Decide if platform should stop or continue
            else:
                self.logger.info("Starting WorkflowEngine for scheduled/triggered workflows.")
                # The WorkflowEngine's start method should be non-blocking or run its scheduler in a task.
                # User's WorkflowEngine.start() creates a scheduler task.
                self.workflow_engine.start() 
                self.logger.info("WorkflowEngine started. Platform is active and listening for triggers/schedules.")
            
            # Keep the main platform running if there are ongoing tasks or listeners
            while self.running:
                await asyncio.sleep(1)
            self.logger.info("Platform main loop exited.")

        except asyncio.CancelledError:
            self.logger.info("Platform start_async task was cancelled.")
        except Exception as e:
            self.logger.critical(f"Critical error during platform execution: {e}", exc_info=True)
        finally:
            self.logger.info("Platform shutting down internal components...")
            await self.stop_async() # Ensure cleanup happens

    async def stop_async(self):
        if not self.running and not self.workflow_engine.running: # Check both flags
            self.logger.info("Platform already stopped or not running.")
            return
        
        self.logger.info("Initiating graceful shutdown of API Integration Platform (async)...")
        self.running = False # Signal loops to stop

        if self.workflow_engine:
            self.logger.info("Stopping WorkflowEngine...")
            await self.workflow_engine.stop() # Assuming this is an async method or handles its tasks
            self.logger.info("WorkflowEngine stopped.")

        if self.dashboard_process and self.dashboard_process.is_alive():
            self.logger.info("Stopping dashboard process...")
            self.dashboard_process.terminate()
            try:
                self.dashboard_process.join(timeout=5)
                if self.dashboard_process.is_alive():
                    self.logger.warning("Dashboard process did not terminate gracefully, killing.")
                    self.dashboard_process.kill()
                self.logger.info("Dashboard process stopped.")
            except Exception as e:
                self.logger.error(f"Error stopping dashboard process: {e}", exc_info=True)
        
        self.logger.info("API Integration Platform shutdown complete.")

    def _handle_shutdown_signal(self, signum, frame):
        self.logger.info(f"Received signal {signal.Signals(signum).name}. Initiating shutdown...")
        if self.running:
            # Schedule the async stop function to be run in the event loop.
            # This is crucial if the signal handler is called from a different thread.
            if self.workflow_engine and self.workflow_engine.loop:
                 asyncio.run_coroutine_threadsafe(self.stop_async(), self.workflow_engine.loop)
            else: # Fallback if loop isn't readily available, try to create a new task in current/new loop
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop.create_task(self.stop_async())
                    else:
                        loop.run_until_complete(self.stop_async())
                except RuntimeError: # No event loop
                    asyncio.run(self.stop_async()) # Run in a new event loop as a last resort
        else:
            self.logger.info("Platform was not actively running when shutdown signal received.")

async def main_async_entrypoint():
    args = parse_arguments()
    
    # Setup a basic logger for early messages before platform fully initializes its logging
    # This will be overridden by LoggingManager once platform initializes
    logging.basicConfig(level=os.environ.get("AIP_LOG_LEVEL", "INFO").upper(), 
                        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
    early_logger = logging.getLogger("PlatformBootstrap")

    if args.version:
        # Placeholder for version. Ideally, this would come from a settings file or __version__ var.
        early_logger.info("API Integration Platform v0.1.0 (Placeholder Version)")
        return 0

    platform = None
    try:
        platform = APIIntegrationPlatform(config_path=args.config)
        await platform.start_async(workflow_name_or_path=args.workflow, run_dashboard=args.dashboard)
        return 0
    except KeyboardInterrupt:
        early_logger.info("Keyboard interrupt received. Shutting down...")
        if platform:
            await platform.stop_async()
        return 0
    except Exception as e:
        if platform and platform.logger: # Use platform's logger if available
            platform.logger.critical(f"Fatal error launching or running the platform: {e}", exc_info=True)
        else: # Fallback to early logger or print
            early_logger.critical(f"Fatal error launching or running the platform: {e}", exc_info=True)
        return 1

def parse_arguments():
    parser = argparse.ArgumentParser(description="API Integration Platform - Main Orchestrator")
    parser.add_argument("--config", help="Path to the main configuration file (e.g., config/platform_config.yaml)", default=os.environ.get("AIP_CONFIG_PATH"))
    parser.add_argument("--workflow", help="Name or path of a specific workflow to run on startup.")
    parser.add_argument("--dashboard", action="store_true", help="Start the optional web dashboard.")
    parser.add_argument("--version", action="store_true", help="Show platform version and exit.")
    return parser.parse_args()

if __name__ == "__main__":
    # Set a default for AIP_ENV if not present, for SecureConfigLoader
    if "AIP_ENV" not in os.environ:
        os.environ["AIP_ENV"] = "development"
    
    try:
        asyncio.run(main_async_entrypoint())
        sys.exit(0)
    except Exception as e: 
        # This catches errors if asyncio.run itself fails or if main_async_entrypoint re-raises something uncaught
        print(f"Unhandled critical exception at top level: {e}", file=sys.stderr)
        sys.exit(1)

