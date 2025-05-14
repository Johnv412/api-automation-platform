"""
Error Handler

This module provides centralized error handling for nodes and workflows.
"""

import logging
import traceback
from typing import Any, Dict, Type, Union

logger = logging.getLogger(__name__)


class NodeError(Exception):
    """
    Exception raised when a node encounters an error during execution.
    """
    
    def __init__(self, message: str, node: Any = None, cause: Exception = None):
        """
        Initialize a NodeError.
        
        Args:
            message: Error message
            node: Node instance that raised the error
            cause: Original exception that caused this error
        """
        self.node = node
        self.cause = cause
        super().__init__(message)


class WorkflowError(Exception):
    """
    Exception raised when a workflow encounters an error during execution.
    """
    
    def __init__(self, message: str, context: Any = None, cause: Exception = None):
        """
        Initialize a WorkflowError.
        
        Args:
            message: Error message
            context: Execution context
            cause: Original exception that caused this error
        """
        self.context = context
        self.cause = cause
        super().__init__(message)


class ValidationError(Exception):
    """
    Exception raised when validation fails.
    """
    
    def __init__(self, message: str, details: Dict[str, Any] = None):
        """
        Initialize a ValidationError.
        
        Args:
            message: Error message
            details: Validation error details
        """
        self.details = details or {}
        super().__init__(message)


def handle_node_error(error: Exception, node: Any) -> None:
    """
    Handle an error from a node execution.
    
    This function decides whether to raise the error or handle it gracefully,
    based on the error type and node configuration.
    
    Args:
        error: Exception that occurred
        node: Node instance that raised the error
    
    Raises:
        NodeError: If the error should be propagated
    """
    # Wrap the error if it"s not already a NodeError
    if not isinstance(error, NodeError):
        error = NodeError(str(error), node, cause=error)
    
    # Log the error
    logger.error(f"Node {node.name} ({node.id}) error: {str(error)}")
    
    # Check if the node has a continue_on_error flag
    continue_on_error = getattr(node, "config", {}).get("continue_on_error", False)
    
    if continue_on_error:
        logger.info(f"Node {node.name} configured to continue on error, proceeding with partial results")
        return
    
    # Check for specific error types that should be handled differently
    if isinstance(error.cause, TimeoutError):
        logger.warning(f"Node {node.name} execution timed out")
        # You could implement custom timeout handling here
    
    # Otherwise, re-raise the error
    raise error


def handle_workflow_error(error: Exception, context: Any) -> None:
    """
    Handle an error from a workflow execution.
    
    This function handles workflow-level errors and implements
    retry logic or failure recovery as needed.
    
    Args:
        error: Exception that occurred
        context: Execution context
    
    Raises:
        WorkflowError: If the error should be propagated
    """
    # Wrap the error if it"s not already a WorkflowError
    if not isinstance(error, WorkflowError):
        error = WorkflowError(str(error), context, cause=error)
    
    # Log the error
    workflow_id = getattr(context, "workflow_id", "unknown")
    execution_id = getattr(context, "execution_id", "unknown")
    
    logger.error(f"Workflow {workflow_id} (execution {execution_id}) error: {str(error)}")
    
    # Get the workflow definition
    workflow_def = getattr(context, "workflow_def", {})
    
    # Check if the workflow has error handling configuration
    error_handling = workflow_def.get("error_handling", {})
    
    # Check for retry configuration
    retry_config = error_handling.get("retry", {})
    max_retries = retry_config.get("max_retries", 0)
    current_retry = getattr(context, "retry_count", 0)
    
    if current_retry < max_retries:
        logger.info(f"Retrying workflow {workflow_id} ({current_retry + 1}/{max_retries})")
        
        # Increment retry count
        setattr(context, "retry_count", current_retry + 1)
        
        # TODO: Implement actual retry logic
        # This would typically involve re-scheduling the workflow execution
        
    # Check for fallback configuration
    fallback = error_handling.get("fallback", {})
    fallback_workflow = fallback.get("workflow")
    
    if fallback_workflow:
        logger.info(f"Executing fallback workflow {fallback_workflow}")
        
        # TODO: Implement fallback logic
        # This would typically involve starting another workflow as a fallback
    
    # Otherwise, just let the error propagate
    raise error


def format_exception(exc: Exception) -> Dict[str, Any]:
    """
    Format an exception for structured logging or API responses.
    
    Args:
        exc: Exception to format
    
    Returns:
        Dictionary with exception details
    """
    result = {
        "type": exc.__class__.__name__,
        "message": str(exc),
        "traceback": traceback.format_exc()
    }
    
    # Add specific fields for known exception types
    if isinstance(exc, NodeError):
        result["node_id"] = getattr(exc.node, "id", None)
        result["node_name"] = getattr(exc.node, "name", None)
        
        if exc.cause:
            result["cause"] = format_exception(exc.cause)
    
    elif isinstance(exc, WorkflowError):
        result["workflow_id"] = getattr(exc.context, "workflow_id", None)
        result["execution_id"] = getattr(exc.context, "execution_id", None)
        
        if exc.cause:
            result["cause"] = format_exception(exc.cause)
    
    elif isinstance(exc, ValidationError):
        result["details"] = exc.details
    
    return result

