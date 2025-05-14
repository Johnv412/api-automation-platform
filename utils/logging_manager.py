"""
Logging Manager

This module provides structured logging functionality for the API Integration Platform.
"""

import json
import logging
import logging.config
import os
import sys
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

# Configure default logger
logger = logging.getLogger(__name__)


def setup_logging(config_path: str = None, log_level: str = None) -> None:
    """
    Configure logging for the application.
    
    Args:
        config_path: Path to logging configuration file
        log_level: Override for log level
    """
    # Default logging configuration
    default_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
            },
            "json": {
                "format": "%(message)s",
                "class": "utils.logging_manager.JsonFormatter"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "DEBUG",
                "formatter": "standard",
                "stream": "ext://sys.stdout"
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "INFO",
                "formatter": "json",
                "filename": "logs/app.log",
                "maxBytes": 10485760,  # 10 MB
                "backupCount": 10
            }
        },
        "loggers": {
            "": {
                "handlers": ["console", "file"],
                "level": "INFO",
                "propagate": True
            }
        }
    }
    
    # Create logs directory if it doesn"t exist
    os.makedirs("logs", exist_ok=True)
    
    # Load custom logging config if provided
    config = default_config
    if config_path and os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                import yaml
                custom_config = yaml.safe_load(f)
                config = custom_config
        except Exception as e:
            print(f"Error loading logging config: {str(e)}")
    
    # Override log level if provided
    if log_level:
        config["loggers"][""]["level"] = log_level.upper()
    
    # Apply configuration
    try:
        logging.config.dictConfig(config)
        logger.info("Logging configured successfully")
    except Exception as e:
        print(f"Error configuring logging: {str(e)}")
        # Set up basic logging as fallback
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            handlers=[logging.StreamHandler(sys.stdout)]
        )
        logger.warning("Falling back to basic logging configuration")


class JsonFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.
    """
    
    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "thread": record.thread,
            "process": record.process
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info)
            }
        
        # Add extra fields
        if hasattr(record, "data"):
            log_data.update(record.data)
        
        return json.dumps(log_data)


class LoggerAdapter(logging.LoggerAdapter):
    """
    Logger adapter for adding context to log records.
    """
    
    def process(self, msg, kwargs):
        # Add extra data to log record
        extra = kwargs.get("extra", {})
        extra.setdefault("data", {})
        
        # Add adapter context
        extra["data"].update(self.extra)
        
        # Update kwargs
        kwargs["extra"] = extra
        return msg, kwargs


def get_logger(name: str, **context) -> LoggerAdapter:
    """
    Get a logger with context.
    
    Args:
        name: Logger name
        **context: Context data to include in all log messages
    
    Returns:
        Logger adapter with context
    """
    logger = logging.getLogger(name)
    return LoggerAdapter(logger, context)


def log_execution_event(event_type: str, 
                        workflow_id: str = None,
                        execution_id: str = None,
                        node_id: str = None,
                        details: Dict[str, Any] = None) -> None:
    """
    Log a workflow or node execution event.
    
    Args:
        event_type: Type of event (workflow_start, workflow_complete, node_start, etc.)
        workflow_id: Workflow ID
        execution_id: Execution ID
        node_id: Node ID (optional)
        details: Additional event details
    """
    event_logger = logging.getLogger("execution_events")
    
    event_data = {
        "event_type": event_type,
        "timestamp": datetime.utcnow().isoformat(),
        "workflow_id": workflow_id,
        "execution_id": execution_id,
        "node_id": node_id
    }
    
    if details:
        event_data.update(details)
    
    # Log event
    event_logger.info(event_type, extra={"data": event_data})
    
    # TODO: In a production system, consider sending events to a monitoring system

