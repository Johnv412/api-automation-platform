"""
Workflow Loader and Validator

This module provides functionality for loading, validating, and managing workflow
definitions from various sources (files, JSON objects, etc.).
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional, Set, Tuple, Type, Union
import yaml

# Assuming this file (workflow_components.py) is in the 'core' directory,
# and 'errors.py', 'node_base.py', 'node_registry.py' are also in 'core'.
from .errors import (
    WorkflowValidationError,
    # NodeConfigError, # This specific error is not in the user's workflow_errors.py, will be defined if needed or removed
    WorkflowCycleError,
    WorkflowConnectionError
)
from .node_base import BaseNode # NodeConfig was removed as it's not in node_base.py
from .node_registry import NodeRegistry

logger = logging.getLogger(__name__)

class WorkflowDefinition:
    """Represents a complete workflow definition with nodes and connections."""
    
    def __init__(self, 
                 name: str,
                 description: Optional[str] = None,
                 version: str = "1.0.0",
                 nodes: Dict[str, Dict[str, Any]] = None,
                 connections: List[Dict[str, Any]] = None,
                 metadata: Dict[str, Any] = None):
        self.name = name
        self.description = description or ""
        self.version = version
        self.nodes = nodes or {}
        self.connections = connections or []
        self.metadata = metadata or {}
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowDefinition':
        required_keys = ["name", "nodes"]
        for key in required_keys:
            if key not in data:
                raise WorkflowValidationError(f"Workflow definition missing required key: {key}")
        
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            version=data.get("version", "1.0.0"),
            nodes=data["nodes"],
            connections=data.get("connections", []),
            metadata=data.get("metadata", {})
        )
    
    @classmethod
    def from_file(cls, filepath: str) -> 'WorkflowDefinition':
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Workflow file not found: {filepath}")
        
        file_ext = os.path.splitext(filepath)[1].lower()
        
        try:
            with open(filepath, 'r') as f:
                if file_ext in ('.yaml', '.yml'):
                    data = yaml.safe_load(f)
                elif file_ext == '.json':
                    data = json.load(f)
                else:
                    raise ValueError(f"Unsupported file format: {file_ext}. Use .json, .yml, or .yaml")
            return cls.from_dict(data)
        except (json.JSONDecodeError, yaml.YAMLError) as e:
            raise WorkflowValidationError(f"Invalid workflow file format: {e}")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "nodes": self.nodes,
            "connections": self.connections,
            "metadata": self.metadata
        }
    
    def to_file(self, filepath: str, format_type: str = None) -> None:
        if format_type is None:
            file_ext = os.path.splitext(filepath)[1].lower()
            if file_ext in ('.yaml', '.yml'):
                format_type = 'yaml'
            elif file_ext == '.json':
                format_type = 'json'
            else:
                raise ValueError(f"Unsupported file format: {file_ext}. Use .json, .yml, or .yaml")
        
        data = self.to_dict()
        
        with open(filepath, 'w') as f:
            if format_type == 'yaml':
                yaml.dump(data, f, default_flow_style=False)
            elif format_type == 'json':
                json.dump(data, f, indent=2)
            else:
                raise ValueError(f"Unsupported format type: {format_type}. Use 'json' or 'yaml'")


class WorkflowValidator:
    """Validates workflow definitions against node registry and checks for consistency."""
    
    def __init__(self, node_registry: NodeRegistry):
        self.node_registry = node_registry
    
    def validate_workflow(self, workflow: WorkflowDefinition) -> List[str]:
        errors = []
        if not workflow.nodes:
            errors.append("Workflow must have at least one node")
            return errors
        
        node_errors = self._validate_nodes(workflow.nodes)
        errors.extend(node_errors)
        
        if node_errors:
            return errors # Stop if nodes themselves are invalid
        
        connection_errors = self._validate_connections(workflow.nodes, workflow.connections)
        errors.extend(connection_errors)
        
        try:
            self._check_for_cycles(workflow.nodes, workflow.connections)
        except WorkflowCycleError as e:
            errors.append(str(e))
        
        return errors
    
    def _validate_nodes(self, nodes: Dict[str, Dict[str, Any]]) -> List[str]:
        errors = []
        for node_id, node_def in nodes.items():
            if "type" not in node_def:
                errors.append(f"Node '{node_id}' is missing 'type' attribute")
                continue
            node_type = node_def["type"]
            if not self.node_registry.has_node_type(node_type):
                errors.append(f"Node '{node_id}' has unknown type: '{node_type}'")
                continue
            
            node_class = self.node_registry.get_node_class(node_type)
            config = node_def.get("config", {})
            try:
                # Temporarily instantiate to call validate_config if it exists and is robust
                # This assumes validate_config doesn't have side effects or require full execution context
                node_instance = node_class(node_id, config) # This might raise NodeConfigurationError from node's __init__
                if hasattr(node_instance, 'validate_config') and callable(getattr(node_instance, 'validate_config')):
                    # The user's BaseNode.validate_config() returns bool, not an object with is_valid.
                    # Adapting to the structure in workflow_loader_validator.py which expects an object.
                    # For now, let's assume if validate_config() runs without error, it's valid.
                    # Or, if it returns False, it's an error.
                    is_valid_or_result = node_instance.validate_config()
                    if isinstance(is_valid_or_result, bool) and not is_valid_or_result:
                         errors.append(f"Node '{node_id}' config validation failed (returned False)")
                    # If it returns an object like {is_valid: False, error_message: "..."}
                    elif hasattr(is_valid_or_result, 'is_valid') and not is_valid_or_result.is_valid:
                        errors.append(f"Node '{node_id}' config validation failed: {getattr(is_valid_or_result, 'error_message', 'Unknown error')}")

            except WorkflowValidationError as e: # Catch specific validation errors from node init
                 errors.append(f"Node '{node_id}' config error: {str(e)}")
            except Exception as e:
                # Catching general exceptions during node instantiation for validation purposes
                errors.append(f"Error instantiating node '{node_id}' of type '{node_type}' for validation: {str(e)}")
        return errors

    def _validate_connections(self, 
                             nodes: Dict[str, Dict[str, Any]], 
                             connections: List[Dict[str, Any]]) -> List[str]:
        errors = []
        node_instances = {}
        # Create instances only if node type is known, to get input/output schema if available
        for node_id, node_def in nodes.items():
            node_type = node_def.get("type")
            if node_type and self.node_registry.has_node_type(node_type):
                node_class = self.node_registry.get_node_class(node_type)
                try:
                    node_instances[node_id] = node_class(node_id, node_def.get("config", {}))
                except Exception:
                    pass # Error already caught in _validate_nodes

        for i, conn in enumerate(connections):
            conn_label = f"Connection #{i+1}"
            source_spec = conn.get("from")
            target_spec = conn.get("to")

            if not source_spec or not target_spec:
                errors.append(f"{conn_label} missing 'from' or 'to' attributes.")
                continue

            source_node_id, _ = source_spec.split(".", 1) if "." in source_spec else (source_spec, None)
            target_node_id, target_input_name = target_spec.split(".", 1) if "." in target_spec else (None, None)

            if source_node_id not in nodes:
                errors.append(f"{conn_label} references non-existent source node: '{source_node_id}'.")
            if not target_node_id or target_node_id not in nodes:
                errors.append(f"{conn_label} references non-existent target node: '{target_node_id}'.")
            if not target_input_name:
                 errors.append(f"{conn_label} target '{target_spec}' must specify input name with format 'node_id.input_name'.")
            
            # Further schema validation would go here if nodes define input/output schemas
            # e.g., checking if source_output type matches target_input type

        return errors

    def _check_for_cycles(self, 
                         nodes: Dict[str, Dict[str, Any]], 
                         connections: List[Dict[str, Any]]) -> None:
        graph = {node_id: [] for node_id in nodes}
        for conn in connections:
            source_spec = conn.get("from")
            target_spec = conn.get("to")
            if not source_spec or not target_spec: continue

            source_node_id = source_spec.split(".", 1)[0] if "." in source_spec else source_spec
            target_node_id = target_spec.split(".", 1)[0] if "." in target_spec else None 
            # target_node_id should always exist due to previous checks, but defensive here

            if source_node_id in graph and target_node_id:
                 graph[source_node_id].append(target_node_id)

        visited = set()
        recursion_stack = set()

        for node_id in nodes:
            if node_id not in visited:
                # Pass a copy of the path list to each DFS branch
                if self._dfs_cycle_check_recursive(node_id, graph, visited, recursion_stack, []):
                    # CycleError is raised within the recursive call, so this path might not be hit directly
                    # but kept for logical completeness if _dfs_cycle_check_recursive were to return bool.
                    pass 
        return # No cycle found

    def _dfs_cycle_check_recursive(self, u: str, graph: Dict[str, List[str]], visited: Set[str], recursion_stack: Set[str], current_path: List[str]):
        visited.add(u)
        recursion_stack.add(u)
        current_path.append(u)

        for v in graph.get(u, []):
            if v not in visited:
                if self._dfs_cycle_check_recursive(v, graph, visited, recursion_stack, current_path):
                    return True # Propagate cycle detection
            elif v in recursion_stack:
                # Cycle detected
                try:
                    cycle_start_index = current_path.index(v)
                    cycle_str = " -> ".join(current_path[cycle_start_index:] + [v])
                    raise WorkflowCycleError(f"Workflow contains a cycle: {cycle_str}")
                except ValueError: # Should not happen if logic is correct
                    raise WorkflowCycleError(f"Workflow contains a cycle involving {v} (path reconstruction error)")
        
        current_path.pop()
        recursion_stack.remove(u)
        return False


class WorkflowLoader:
    """Loads, validates, and instantiates workflow definitions."""
    
    def __init__(self, node_registry: NodeRegistry):
        self.node_registry = node_registry
        self.validator = WorkflowValidator(node_registry)
    
    def load_and_validate(self, 
                         source: Union[str, Dict[str, Any], WorkflowDefinition]) -> Tuple[WorkflowDefinition, List[str]]:
        workflow: WorkflowDefinition
        if isinstance(source, str):
            workflow = WorkflowDefinition.from_file(source)
        elif isinstance(source, dict):
            workflow = WorkflowDefinition.from_dict(source)
        elif isinstance(source, WorkflowDefinition):
            workflow = source
        else:
            raise TypeError(f"Unsupported workflow source type: {type(source)}")
        
        errors = self.validator.validate_workflow(workflow)
        return workflow, errors
    
    def instantiate_nodes(self, workflow: WorkflowDefinition) -> Dict[str, BaseNode]:
        node_instances = {}
        for node_id, node_def in workflow.nodes.items():
            node_type = node_def["type"]
            # Assuming validation has passed, so node_type should be in registry
            node_class = self.node_registry.get_node_class(node_type)
            config = node_def.get("config", {})
            node_instances[node_id] = node_class(node_id, config)
        return node_instances

