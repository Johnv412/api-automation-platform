# -*- coding: utf-8 -*-
"""
Workflow Validator for the API Integration Platform.

This module provides the `WorkflowValidator` class, responsible for validating
the structure, integrity, and semantics of a parsed workflow definition.
"""

import logging
from typing import Dict, Any, List, Set

from core.node_registry import NodeRegistry
from utils.error_handler import WorkflowDefinitionError

logger = logging.getLogger(__name__)

class WorkflowValidator:
    """
    Validates workflow definitions.
    """

    def __init__(self, node_registry: NodeRegistry):
        """
        Initializes the WorkflowValidator.

        Args:
            node_registry (NodeRegistry): An instance of the NodeRegistry to check node types.
        """
        self.node_registry = node_registry
        self.logger = logging.getLogger(__name__)

    def validate_workflow(self, workflow_def: Dict[str, Any]) -> None:
        """
        Validates a parsed workflow definition.

        Args:
            workflow_def (Dict[str, Any]): The workflow definition as a dictionary.

        Raises:
            WorkflowDefinitionError: If validation fails.
        """
        self.logger.info(f"Validating workflow: {workflow_def.get("name", "Unnamed Workflow")}")

        self._check_required_top_level_fields(workflow_def)
        
        nodes = workflow_def.get("nodes", [])
        if not isinstance(nodes, list) or not nodes:
            raise WorkflowDefinitionError("Workflow must contain a non-empty list of nodes.")

        node_ids: Set[str] = set()
        for node_config in nodes:
            if not isinstance(node_config, dict):
                raise WorkflowDefinitionError(f"Each item in 'nodes' list must be a dictionary. Found: {type(node_config)}")
            self._validate_node_definition(node_config, node_ids)
        
        start_node_id = workflow_def["start_node_id"]
        if start_node_id not in node_ids:
            raise WorkflowDefinitionError(f"'start_node_id' ('{start_node_id}') does not refer to a defined node ID.")

        # Further validation for graph structure (cycles, reachability) can be added here.
        # For now, we check if all next_node_id and on_failure_node_id point to existing nodes.
        for node_config in nodes:
            next_node = node_config.get("next_node_id")
            if next_node and next_node not in node_ids:
                raise WorkflowDefinitionError(f"Node 
                                              \'{node_config.get("id")}\": 'next_node_id' ('{next_node}') does not refer to a defined node ID.")
            
            failure_node = node_config.get("on_failure_node_id")
            if failure_node and failure_node not in node_ids:
                raise WorkflowDefinitionError(f"Node 
                                              \'{node_config.get("id")}\": 'on_failure_node_id' ('{failure_node}') does not refer to a defined node ID.")

        self.logger.info(f"Workflow '{workflow_def.get("name", "Unnamed Workflow")}' validation successful.")

    def _check_required_top_level_fields(self, workflow_def: Dict[str, Any]) -> None:
        """
        Checks for mandatory fields at the top level of the workflow definition.
        """
        required_fields = ["name", "version", "start_node_id", "nodes"]
        for field in required_fields:
            if field not in workflow_def:
                raise WorkflowDefinitionError(f"Missing required top-level field in workflow definition: '{field}'.")
            if not workflow_def[field] and field != "nodes": # nodes can be empty initially, but checked later
                 if field not in ["description", "author", "creation_date"]: # These can be empty strings
                    raise WorkflowDefinitionError(f"Top-level field '{field}' cannot be empty.")

    def _validate_node_definition(self, node_config: Dict[str, Any], existing_node_ids: Set[str]) -> None:
        """
        Validates a single node definition within the workflow.
        """
        node_id = node_config.get("id")
        if not node_id or not isinstance(node_id, str):
            raise WorkflowDefinitionError(f"Node definition is missing an 'id' or 'id' is not a string: {node_config}")
        
        if node_id in existing_node_ids:
            raise WorkflowDefinitionError(f"Duplicate node ID found: '{node_id}'. Node IDs must be unique within a workflow.")
        existing_node_ids.add(node_id)

        node_type = node_config.get("type")
        if not node_type or not isinstance(node_type, str):
            raise WorkflowDefinitionError(f"Node '{node_id}' is missing a 'type' or 'type' is not a string.")

        if node_type not in self.node_registry.node_types:
            raise WorkflowDefinitionError(f"Node '{node_id}' uses an unregistered node type: '{node_type}'. Available types: {list(self.node_registry.node_types.keys())}")
        
        # Validate node-specific configuration against its schema (if available)
        # This is a more advanced step and requires the node's schema to be well-defined.
        node_class = self.node_registry.node_types[node_type]
        try:
            # Create a temporary instance to get its config schema
            # This assumes NodeBase and its children can be instantiated without args for schema retrieval
            temp_node_instance = node_class()
            config_schema = temp_node_instance._get_config_schema() # Accessing protected member for schema
            if config_schema and config_schema != {"type": "object"}: # If a meaningful schema is defined
                # Here you would use a JSON schema validator like `jsonschema`
                # For now, we'll skip this complex validation part.
                # self._validate_config_against_schema(node_config.get("config", {}), config_schema, node_id)
                pass # Placeholder for jsonschema validation
        except Exception as e:
            self.logger.warning(f"Could not retrieve or validate config schema for node '{node_id}' of type '{node_type}': {e}") 

        if "config" in node_config and not isinstance(node_config["config"], dict):
            raise WorkflowDefinitionError(f"Node '{node_id}': 'config' field, if present, must be a dictionary.")

        if "credential_name" in node_config and not isinstance(node_config["credential_name"], str):
            raise WorkflowDefinitionError(f"Node '{node_id}': 'credential_name' field, if present, must be a string.")

        if "input_mapping" in node_config and not isinstance(node_config["input_mapping"], dict):
            raise WorkflowDefinitionError(f"Node '{node_id}': 'input_mapping' field, if present, must be a dictionary.")

    # def _validate_config_against_schema(self, config_data: Dict[str, Any], schema: Dict[str, Any], node_id: str) -> None:
    #     """Uses jsonschema to validate node config against its schema."""
    #     try:
    #         from jsonschema import validate, exceptions
    #         validate(instance=config_data, schema=schema)
    #     except ImportError:
    #         self.logger.warning("jsonschema library not installed. Skipping detailed node config validation.")
    #     except exceptions.ValidationError as e:
    #         raise WorkflowDefinitionError(f"Node '{node_id}' config validation failed: {e.message}")

# Example Usage (illustrative, assumes NodeRegistry is available)
# if __name__ == "__main__":
#     logging.basicConfig(level=logging.DEBUG)
#     # Mock NodeRegistry and a dummy node type for testing
#     class DummyNode(NodeBase):
#         async def _execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]: return {}
#         def _validate_config(self, config: Dict[str, Any]) -> None: pass
#         def _get_config_schema(self) -> Dict[str, Any]: 
#             return {"type": "object", "properties": {"param1": {"type": "string"}}, "required": ["param1"]}

#     mock_registry = NodeRegistry() # This would normally discover nodes
#     mock_registry.register_node_type("DummyNode", DummyNode) 
    
#     validator = WorkflowValidator(mock_registry)

#     valid_wf = {
#         "name": "Test Workflow",
#         "version": "1.0",
#         "start_node_id": "node1",
#         "nodes": [
#             {"id": "node1", "type": "DummyNode", "config": {"param1": "hello"}, "next_node_id": "node2"},
#             {"id": "node2", "type": "DummyNode", "config": {"param1": "world"}, "next_node_id": None}
#         ]
#     }
#     try:
#         validator.validate_workflow(valid_wf)
#         print("Valid workflow validated successfully.")
#     except WorkflowDefinitionError as e:
#         print(f"Validation failed for valid_wf: {e}")

#     invalid_wf_missing_start = {
#         "name": "Test Workflow",
#         "version": "1.0",
#         # "start_node_id": "node1", # Missing
#         "nodes": []
#     }
#     try:
#         validator.validate_workflow(invalid_wf_missing_start)
#     except WorkflowDefinitionError as e:
#         print(f"Caught expected error for invalid_wf_missing_start: {e}")

#     invalid_wf_bad_node_type = {
#         "name": "Test Workflow",
#         "version": "1.0",
#         "start_node_id": "node1",
#         "nodes": [
#             {"id": "node1", "type": "NonExistentNode"}
#         ]
#     }
#     try:
#         validator.validate_workflow(invalid_wf_bad_node_type)
#     except WorkflowDefinitionError as e:
#         print(f"Caught expected error for invalid_wf_bad_node_type: {e}")

#     invalid_wf_duplicate_id = {
#         "name": "Test Workflow",
#         "version": "1.0",
#         "start_node_id": "node1",
#         "nodes": [
#             {"id": "node1", "type": "DummyNode", "config": {"param1": "val"}},
#             {"id": "node1", "type": "DummyNode", "config": {"param1": "val2"}}
#         ]
#     }
#     try:
#         validator.validate_workflow(invalid_wf_duplicate_id)
#     except WorkflowDefinitionError as e:
#         print(f"Caught expected error for invalid_wf_duplicate_id: {e}")

