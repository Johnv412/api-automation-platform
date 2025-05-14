"""
Logger Node for API Integration Platform

This module implements a Logger Node that:
1. Logs messages at different severity levels (debug, info, warning, error)
2. Supports various output destinations (console, file, external services)
3. Provides structured logging with context information
4. Allows for log filtering and formatting
"""

import logging
import json
import os
import time
from typing import Dict, Any, Optional, List, Union
import aiofiles
from datetime import datetime

from ...core.node_base import NodeBase
from ...core.errors import NodeConfigurationError, NodeExecutionError
from ...core.execution_context import ExecutionContext

# Configure root logger if not already configured by a central logging_manager
# This basicConfig is a fallback and might be overridden by a more sophisticated setup.
if not logging.getLogger().hasHandlers():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

logger = logging.getLogger(__name__) # Use module-specific logger

class LoggerNode(NodeBase):
    """Node for logging messages in workflows."""

    NODE_TYPE = "Logger"

    LOG_LEVELS = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "critical": logging.CRITICAL
    }

    OUTPUT_TYPES = [
        "console",
        "file",
        "memory",
        "webhook"
    ]

    def __init__(self, node_id: str, config: Dict[str, Any]):
        super().__init__(node_id, config)

        self.level = self.config.get("level", "info").lower()
        if self.level not in self.LOG_LEVELS:
            raise NodeConfigurationError(
                f"LoggerNode {node_id}: Invalid log level \'{self.level}\'. "
                f"Valid levels: {", ".join(self.LOG_LEVELS.keys())}"
            )
        self.log_level_int = self.LOG_LEVELS[self.level]

        self.outputs = self.config.get("outputs", [{"type": "console"}])
        for output_conf in self.outputs:
            output_type = output_conf.get("type")
            if output_type not in self.OUTPUT_TYPES:
                raise NodeConfigurationError(
                    f"LoggerNode {node_id}: Invalid output type \'{output_type}\'. "
                    f"Valid types: {", ".join(self.OUTPUT_TYPES)}"
                )

        self.log_format = self.config.get("format", "json") # Renamed from 'format' to 'log_format' to avoid conflict
        self.include_context = self.config.get("include_context", True)
        self.max_memory_logs = self.config.get("max_memory_logs", 1000)

        self.memory_logs: List[Dict[str, Any]] = []
        self.file_handlers: Dict[str, logging.FileHandler] = {}

        # Setup file handlers during init if configured to avoid race conditions in async execute
        # This part is tricky with async file I/O for logging; standard logging is mostly sync.
        # For simplicity, we'll use standard sync file handlers here.
        # If truly async file logging is needed, aiofiles would be used directly in _log_to_file
        # and not via logging.FileHandler.
        for output_conf in self.outputs:
            if output_conf.get("type") == "file":
                self._setup_file_handler_sync(output_conf.get("config", {}))

    def validate_config(self) -> bool:
        return True # Basic validation done in __init__

    def _setup_file_handler_sync(self, config: Dict[str, Any]):
        file_path = config.get("file_path")
        if not file_path:
            raise NodeConfigurationError(f"LoggerNode {self.node_id}: File output requires a file_path")

        # Ensure directory exists
        log_dir = os.path.dirname(file_path)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        handler = logging.FileHandler(
            filename=file_path,
            mode=config.get("mode", "a"),
            encoding=config.get("encoding", "utf-8")
        )

        if self.log_format == "json":
            # For JSON, we typically log the raw JSON string as the message
            formatter = logging.Formatter("%(message)s")
        else:
            pattern = config.get("format_pattern", "%(asctime)s - %(levelname)s - %(name)s - %(message)s")
            formatter = logging.Formatter(pattern)
        handler.setFormatter(formatter)
        handler.setLevel(self.log_level_int)

        # Get a unique logger for this file handler to avoid duplicate messages if node is used multiple times
        # or if other parts of the system configure the root logger.
        file_logger_name = f"{__name__}.file.{file_path.replace('/', '_').replace('.', '_')}"
        file_specific_logger = logging.getLogger(file_logger_name)
        file_specific_logger.propagate = False # Stop propagation to avoid double logging if root logger is also configured
        file_specific_logger.addHandler(handler)
        file_specific_logger.setLevel(self.log_level_int)
        self.file_handlers[file_path] = handler # Store handler for potential cleanup

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        message = inputs.get("message")
        if message is None:
            raise NodeExecutionError(f"LoggerNode {self.node_id}: No message provided to log")

        current_level_str = inputs.get("level", self.level).lower()
        if current_level_str not in self.LOG_LEVELS:
            current_level_str = self.level # Fallback to node's default level
        current_log_level_int = self.LOG_LEVELS[current_level_str]

        additional_data = inputs.get("data", {})

        timestamp = datetime.now().isoformat()
        log_entry: Dict[str, Any] = {
            "timestamp": timestamp,
            "level": current_level_str,
            "message": message,
            "node_id": self.node_id,
            "node_type": self.NODE_TYPE
        }

        if self.include_context and context:
            log_entry["context"] = {
                "workflow_id": context.workflow_id,
                "execution_id": context.execution_id,
                # Potentially add current_step_id if available in context
            }

        if additional_data:
            log_entry["data"] = additional_data

        for output_conf in self.outputs:
            output_type = output_conf.get("type")
            output_config = output_conf.get("config", {})

            if output_type == "console":
                self._log_to_console(log_entry, current_log_level_int)
            elif output_type == "file":
                # Using sync file handlers set up in __init__
                await self._log_to_file_sync(log_entry, output_config, current_log_level_int)
            elif output_type == "memory":
                self._log_to_memory(log_entry)
            elif output_type == "webhook":
                await self._log_to_webhook(log_entry, output_config)

        return {"success": True, "log_entry_summary": {"message": message, "level": current_level_str}}

    def _log_to_console(self, log_entry: Dict[str, Any], log_level_int: int):
        if self.log_format == "json":
            formatted_message = json.dumps(log_entry)
        else:
            # Simplified text format for console
            formatted_message = f"{log_entry['message']}"
            if log_entry.get('data'):
                formatted_message += f" - Data: {json.dumps(log_entry['data'])}"
        logger.log(log_level_int, formatted_message)

    async def _log_to_file_sync(self, log_entry: Dict[str, Any], config: Dict[str, Any], log_level_int: int):
        file_path = config.get("file_path")
        if not file_path:
            logger.warning(f"LoggerNode {self.node_id}: file_path missing for file output config.")
            return

        file_logger_name = f"{__name__}.file.{file_path.replace('/', '_').replace('.', '_')}"
        file_specific_logger = logging.getLogger(file_logger_name)

        if self.log_format == "json":
            log_line = json.dumps(log_entry)
        else:
            # For text format, the formatter on the handler will take care of it.
            log_line = log_entry["message"]
            if log_entry.get("data"):
                 log_line += f" ##DATA## {json.dumps(log_entry.get('data'))}" # Make data distinct

        # The actual logging call using the specific logger for that file
        file_specific_logger.log(log_level_int, log_line)

    def _log_to_memory(self, log_entry: Dict[str, Any]):
        self.memory_logs.append(log_entry)
        if len(self.memory_logs) > self.max_memory_logs:
            self.memory_logs = self.memory_logs[-self.max_memory_logs:]

    async def _log_to_webhook(self, log_entry: Dict[str, Any], config: Dict[str, Any]):
        webhook_url = config.get("url")
        if not webhook_url:
            logger.warning(f"LoggerNode {self.node_id}: Webhook URL not configured.")
            return

        import aiohttp # Local import for optional dependency
        headers = config.get("headers", {"Content-Type": "application/json"})
        payload = log_entry
        custom_fields = config.get("custom_fields", {})
        if custom_fields:
            payload.update(custom_fields)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload, headers=headers) as response:
                    if response.status >= 400:
                        error_text = await response.text()
                        logger.error(
                            f"LoggerNode {self.node_id}: Error sending log to webhook {webhook_url}. "
                            f"Status: {response.status}, Response: {error_text[:200]}" # Limit response length
                        )
        except aiohttp.ClientError as e:
            logger.error(f"LoggerNode {self.node_id}: HTTP client error sending log to webhook {webhook_url}: {e}")
        except Exception as e:
            logger.error(f"LoggerNode {self.node_id}: Generic error sending log to webhook {webhook_url}: {e}", exc_info=True)

    def get_memory_logs(self, level: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        filtered = self.memory_logs
        if level:
            level_lower = level.lower()
            filtered = [log for log in self.memory_logs if log.get("level") == level_lower]
        return filtered[-limit:]

    async def cleanup(self):
        # This method would be called by the workflow engine if nodes need explicit cleanup
        for handler in self.file_handlers.values():
            handler.close()
        self.file_handlers.clear()
        logger.info(f"LoggerNode {self.node_id} cleaned up file handlers.")

# Example usage (for testing purposes, not part of the node execution)
if __name__ == '__main__':
    async def main():
        # Example config for LoggerNode
        config_console = {
            "level": "info",
            "outputs": [{"type": "console"}],
            "format": "text"
        }
        logger_node_console = LoggerNode("test_logger_console", config_console)
        await logger_node_console.execute({"message": "Hello from console logger!", "data": {"user": "test"}}, ExecutionContext("wf1", "exec1"))

        config_file_json = {
            "level": "debug",
            "outputs": [{
                "type": "file",
                "config": {
                    "file_path": "/tmp/test_log.json",
                    "mode": "a"
                }
            }],
            "format": "json",
            "include_context": True
        }
        logger_node_file_json = LoggerNode("test_logger_file_json", config_file_json)
        await logger_node_file_json.execute({"message": "This is a JSON debug message.", "level": "debug"}, ExecutionContext("wf2", "exec2"))
        await logger_node_file_json.execute({"message": "Another JSON info message.", "data": {"value": 123}}, ExecutionContext("wf2", "exec2"))

        config_file_text = {
            "level": "info",
            "outputs": [{
                "type": "file",
                "config": {
                    "file_path": "/tmp/test_log.txt",
                    "format_pattern": "%(asctime)s [%(levelname)s] %(message)s"
                }
            }],
            "format": "text"
        }
        logger_node_file_text = LoggerNode("test_logger_file_text", config_file_text)
        await logger_node_file_text.execute({"message": "Plain text log entry."}, ExecutionContext("wf3", "exec3"))

        # Cleanup (important for file handlers)
        await logger_node_file_json.cleanup()
        await logger_node_file_text.cleanup()

    import asyncio
    asyncio.run(main())

