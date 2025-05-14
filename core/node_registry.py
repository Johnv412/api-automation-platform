"""
Node Registry

This module defines the NodeRegistry class for registering
and instantiating node types.
"""

import importlib
import inspect
import logging
import os
import pkgutil
from typing import Any, Dict, List, Optional, Type

from core.node_base import NodeBase

logger = logging.getLogger(__name__)


class NodeRegistry:
    """
    Registry for node types.
    
    The NodeRegistry is responsible for:
    - Discovering node types from the nodes package
    - Registering custom node types
    - Creating node instances
    - Providing information about available node types
    """
    
    def __init__(self):
        """Initialize the node registry."""
        self.node_types = {}  # type_name -> node_class
        self._discover_node_types()
        logger.info(f"Node registry initialized with {len(self.node_types)} node types")
    
    def register_node_type(self, type_name: str, node_class: Type[NodeBase]) -> None:
        """
        Register a node type.
        
        Args:
            type_name: Name for the node type
            node_class: Node class (must inherit from NodeBase)
        
        Raises:
            ValueError: If node_class doesn't inherit from NodeBase
        """
        if not issubclass(node_class, NodeBase):
            raise ValueError(f"Node class {node_class.__name__} must inherit from NodeBase")
        
        self.node_types[type_name] = node_class
        logger.debug(f"Registered node type: {type_name}")
    
    def create_node(self, type_name: str, *args, **kwargs) -> Optional[NodeBase]:
        """
        Create a node instance of the specified type.
        
        Args:
            type_name: Node type name
            *args: Positional arguments for the node constructor
            **kwargs: Keyword arguments for the node constructor
        
        Returns:
            Node instance or None if the type is not registered
        
        Raises:
            Exception: If node instantiation fails
        """
        if type_name not in self.node_types:
            logger.warning(f"Unregistered node type: {type_name}")
            # Consider raising an error here or letting the WorkflowEngine handle it
            # For now, returning None as per user's original code
            return None
        
        try:
            node_class = self.node_types[type_name]
            return node_class(*args, **kwargs)
        except Exception as e:
            logger.error(f"Failed to create node of type {type_name}: {str(e)}", exc_info=True)
            raise # Re-raise the exception so it can be handled upstream
    
    def get_node_types(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about all registered node types.
        
        Returns:
            Dictionary mapping type names to node type info
        """
        result = {}
        
        for type_name, node_class in self.node_types.items():
            try:
                # Get node schema from a temporary instance
                # NodeBase __init__ takes optional id, name, description - should be fine with no args
                temp_instance = node_class()
                schema = temp_instance.get_schema() # NodeBase.get_schema() calls abstract methods
                                                  # _get_input_schema, _get_output_schema, _get_config_schema
                                                  # These should have defaults in NodeBase or be implemented
                
                result[type_name] = {
                    "name": type_name,
                    "description": schema.get("description", node_class.__doc__ or ""),
                    "schema": schema,
                    "category": self._get_node_category(node_class)
                }
            except Exception as e:
                logger.warning(f"Failed to get schema for node type {type_name} ({node_class.__name__}): {str(e)}", exc_info=True)
                result[type_name] = {
                    "name": type_name,
                    "description": node_class.__doc__ or "",
                    "category": self._get_node_category(node_class),
                    "schema_error": str(e)
                }
        return result
    
    def _discover_node_types(self) -> None:
        """
        Discover and register node types from the nodes package.
        Assumes this script is run from a context where 'nodes' is importable.
        """
        try:
            # Import nodes package and its submodules for discovery
            import nodes
            # The submodules (api, data, utility) should be imported in nodes/__init__.py
            # or pkgutil needs to be able to find them.
            # User's code: from nodes import api, data, utility
            # This requires nodes/api.py, nodes/data.py, nodes/utility.py OR
            # nodes/__init__.py to do `from . import api` etc. The latter is better for packages.

            nodes_package_path = nodes.__path__ # Path to the 'nodes' directory
            nodes_package_name = nodes.__name__ # 'nodes'

            for importer, modname, ispkg in pkgutil.iter_modules(nodes_package_path, nodes_package_name + "."):
                if ispkg:
                    # This is a sub-package (e.g., nodes.api)
                    sub_package_module = importlib.import_module(modname)
                    category = modname.split(".")[-1] # e.g., 'api'
                    self._discover_nodes_in_module_path(sub_package_module, category)
                else:
                    # This is a module directly under 'nodes' (e.g., nodes.my_single_node.py)
                    # Not the primary structure user defined, but good to handle
                    module = importlib.import_module(modname)
                    self._register_nodes_from_module(module, "general") # Default category

        except ImportError as e:
            logger.warning(f"Failed to import or discover nodes package: {str(e)}. Ensure 'nodes' directory with __init__.py exists and is in PYTHONPATH.", exc_info=True)
        except Exception as e:
            logger.error(f"Unexpected error during node discovery: {str(e)}", exc_info=True)

    def _discover_nodes_in_module_path(self, package_module, category: str) -> None:
        """
        Discover nodes within a specific module path (sub-package like nodes.api).
        """
        for _, modname, ispkg_inner in pkgutil.iter_modules(package_module.__path__, package_module.__name__ + "."):
            if ispkg_inner:
                # Could recurse here if deeper structure is needed, but for now, assume flat structure in api, data, utility
                continue 
            try:
                module = importlib.import_module(modname)
                self._register_nodes_from_module(module, category)
            except ImportError as e:
                logger.warning(f"Failed to import node module {modname} in category {category}: {str(e)}", exc_info=True)
            except Exception as e:
                 logger.error(f"Error processing module {modname} for nodes: {str(e)}", exc_info=True)

    def _register_nodes_from_module(self, module, category: str) -> None:
        """
        Registers all NodeBase subclasses from a given module.
        """
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if inspect.isclass(attr) and \
               issubclass(attr, NodeBase) and \
               attr != NodeBase and \
               not attr_name.startswith("_") and \
               getattr(attr, "__module__", None) == module.__name__: # Ensure class is defined in this module
                
                type_name = attr_name
                if type_name.endswith("Node") and len(type_name) > 4: # Avoid issues with just 
                    type_name = type_name[:-4] # Remove "Node" suffix
