"""
Execution Context

This module defines the ExecutionContext class that stores all information
related to a specific workflow execution.
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, Optional


class ExecutionContext:
    """
    Stores all context for a specific workflow execution.
    
    The ExecutionContext maintains the state of a workflow execution,
    including all active nodes, execution results, and metadata.
    """
    
    def __init__(self, workflow_id: str, execution_id: str, 
                workflow_def: Dict[str, Any], trigger_data: Dict[str, Any] = None):
        """
        Initialize a new execution context.
        
        Args:
            workflow_id: ID of the workflow
            execution_id: ID of this execution
            workflow_def: Workflow definition
            trigger_data: Data that triggered the workflow
        """
        self.workflow_id = workflow_id
        self.execution_id = execution_id
        self.workflow_def = workflow_def
        self.trigger_data = trigger_data or {}
        
        # Execution state
        self.status = "created"  # created, running, completed, failed, cancelled
        self.error = None
        self.start_time = None
        self.end_time = None
        self.duration_seconds = 0
        
        # Node tracking
        self.active_nodes = {}  # node_id -> node_instance
        self.node_results = {}  # node_id -> node_result
        
        # Task reference for cancellation
        self.task = None
        
        # Global variables shared across nodes
        self.variables = {}
    
    def set_variable(self, name: str, value: Any) -> None:
        """
        Set a global variable in the execution context.
        
        Args:
            name: Variable name
            value: Variable value
        """
        self.variables[name] = value
    
    def get_variable(self, name: str, default: Any = None) -> Any:
        """
        Get a global variable from the execution context.
        
        Args:
            name: Variable name
            default: Default value if variable doesn\'t exist
        
        Returns:
            Variable value or default
        """
        return self.variables.get(name, default)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the execution context to a dictionary.
        
        Returns:
            Dictionary representation of the execution context
        """
        return {
            "workflow_id": self.workflow_id,
            "execution_id": self.execution_id,
            "status": self.status,
            "error": self.error,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.duration_seconds,
            "active_node_count": len(self.active_nodes),
            "result_node_count": len(self.node_results),
            "variables": {
                k: v for k, v in self.variables.items() 
                if not k.startswith("_")  # Don\'t include private variables
            }
        }

