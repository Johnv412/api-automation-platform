"""
Error definitions for the workflow engine.

This module defines custom exceptions used throughout the workflow engine.
"""

class WorkflowError(Exception):
    """Base class for all workflow-related errors."""
    pass


class WorkflowValidationError(WorkflowError):
    """Error raised when workflow validation fails."""
    pass


class NodeConfigError(WorkflowError):
    """Error raised when node configuration is invalid."""
    pass


class WorkflowCycleError(WorkflowError):
    """Error raised when a cycle is detected in the workflow graph."""
    pass


class WorkflowConnectionError(WorkflowError):
    """Error raised when there's an issue with node connections."""
    pass


class NodeTypeNotFoundError(WorkflowError):
    """Error raised when a requested node type is not found in the registry."""
    pass


class NodeExecutionError(WorkflowError):
    """Error raised when there's an issue executing a node."""
    def __init__(self, node_id: str, original_error: Exception):
        self.node_id = node_id
        self.original_error = original_error
        super().__init__(f"Error executing node '{node_id}': {str(original_error)}")


class WorkflowExecutionError(WorkflowError):
    """Error raised when there's an issue executing the workflow."""
    pass

