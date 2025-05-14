# -*- coding: utf-8 -*-
"""
Dashboard API router for Logs.

Provides endpoints to view platform and workflow execution logs.
"""

import logging
import os
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Request

logger = logging.getLogger(__name__)
router = APIRouter()

# Helper function to read log files (simplified)
def read_log_file(log_file_path: str, max_lines: int = 100, search_term: Optional[str] = None) -> List[str]:
    """
    Reads the last `max_lines` from a log file, optionally filtering by a search term.
    NOTE: This is a basic implementation. For production, a proper log management system
    or more robust file reading (e.g., handling large files, rotation) is needed.
    """
    if not os.path.exists(log_file_path):
        logger.warning(f"Log file not found: {log_file_path}")
        return [f"Log file not found: {log_file_path}"]
    
    try:
        with open(log_file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        if search_term:
            lines = [line for line in lines if search_term in line]
            
        # Get the last N lines
        return lines[-max_lines:]
    except Exception as e:
        logger.error(f"Error reading log file {log_file_path}: {e}", exc_info=True)
        return [f"Error reading log file: {str(e)}"]

@router.get("/platform/", summary="View Platform Logs", response_model=List[str])
async def get_platform_logs(
    request: Request,
    log_file_name: str = Query("platform.log.json", description="Name of the platform log file in the logs directory"),
    max_lines: int = Query(100, ge=1, le=1000, description="Maximum number of log lines to return"),
    search: Optional[str] = Query(None, description="Search term to filter log lines")
):
    """
    Retrieves lines from the main platform log file.
    Assumes log files are in a directory specified in the config (e.g., `logs/`).
    """
    platform_config = request.app.state.platform_config
    log_dir = platform_config.get("logging", {}).get("handlers", {}).get("file_json", {}).get("filename")
    if log_dir:
        log_dir = os.path.dirname(log_dir) # Get the directory part
    else:
        log_dir = "logs" # Default if not found in config
        
    log_file_path = os.path.join(log_dir, log_file_name)
    
    logger.info(f"Attempting to read platform log: {log_file_path}")
    return read_log_file(log_file_path, max_lines, search)

@router.get("/workflow/{execution_id}", summary="View Workflow Execution Logs", response_model=List[str])
async def get_workflow_execution_logs(
    request: Request,
    execution_id: str,
    max_lines: int = Query(100, ge=1, le=1000, description="Maximum number of log lines to return"),
    search: Optional[str] = Query(None, description="Search term to filter log lines")
):
    """
    Retrieves logs specific to a workflow execution.
    This requires that workflow executions log to specific files or that logs are filterable by execution_id.
    For this example, we assume logs might contain the execution_id or go to a specific file.
    A more robust solution would involve a centralized logging system that can be queried.
    
    As a simplified approach, this might search the main platform log for the execution_id.
    """
    platform_config = request.app.state.platform_config
    log_dir_config = platform_config.get("logging", {}).get("handlers", {}).get("file_json", {})
    default_log_filename = os.path.basename(log_dir_config.get("filename", "logs/platform.log.json"))

    # For now, we search the main platform log for the execution_id as a simple filter.
    # A better approach would be dedicated log files per execution or a queryable log store.
    logger.info(f"Searching platform logs for execution ID: {execution_id}")
    
    # Use the search parameter of the platform log endpoint effectively
    # This assumes execution_id is part of the log message or structured data.
    # We will use the main platform log file and filter by execution_id.
    
    # Construct the path to the main log file
    log_dir_path = os.path.dirname(log_dir_config.get("filename", "logs/platform.log.json"))
    log_file_path = os.path.join(log_dir_path, default_log_filename)

    # Add execution_id to the search term if a general search is also provided
    effective_search = f"{execution_id}" 
    if search:
        effective_search += f" AND {search}" # This is a simple string search, not a real query language
        logger.info(f"Searching platform log ({log_file_path}) for combined term: 
                    \'{effective_search}\"")
    else:
        logger.info(f"Searching platform log ({log_file_path}) for execution ID: 
                    \'{execution_id}\"")

    return read_log_file(log_file_path, max_lines, effective_search)

logger.info("Dashboard Logs API router created.")

