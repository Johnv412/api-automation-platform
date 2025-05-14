# -*- coding: utf-8 -*-
"""
Dashboard API router for Nodes.

Provides endpoints to list and inspect available nodes in the platform.
"""

import logging
from typing import Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException, Request
# from core.node_registry import NodeRegistry # Will be accessed via request.app.state

logger = logging.getLogger(__name__)
router = APIRouter()

# Dependency to get NodeRegistry (example, can be simplified if always on app.state)
# async def get_node_registry(request: Request) -> NodeRegistry:
#     if not hasattr(request.app.state, "node_registry"):
#         logger.error("NodeRegistry not found in application state.")
#         raise HTTPException(status_code=500, detail="NodeRegistry not configured")
#     return request.app.state.node_registry

@router.get("/", summary="List Available Nodes", response_model=List[Dict[str, Any]])
async def list_available_nodes(request: Request):
    """
    Retrieves a list of all registered node types with their schemas and descriptions.
    """
    try:
        node_registry = request.app.state.node_registry
        if not node_registry:
            logger.error("NodeRegistry not available in app state for /nodes/ endpoint.")
            raise HTTPException(status_code=500, detail="Node registry not initialized")
        
        node_types_info = node_registry.get_node_types()
        # Convert to a list of dicts as expected by response_model
        # The get_node_types already returns a Dict[str, Dict[str, Any]] where the inner dict is the node info
        # We just need the values from the outer dict.
        return list(node_types_info.values())
    except Exception as e:
        logger.error(f"Error retrieving node list: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve node list: {str(e)}")

@router.get("/{node_type_name}", summary="Get Node Details", response_model=Dict[str, Any])
async def get_node_details(request: Request, node_type_name: str):
    """
    Retrieves detailed information (schema, description) for a specific node type.
    """
    try:
        node_registry = request.app.state.node_registry
        if not node_registry:
            raise HTTPException(status_code=500, detail="Node registry not initialized")

        node_types_info = node_registry.get_node_types()
        if node_type_name not in node_types_info:
            raise HTTPException(status_code=404, detail=f"Node type 
                                                  \'{node_type_name}\' not found.")
        return node_types_info[node_type_name]
    except HTTPException: # Re-raise HTTPExceptions directly
        raise
    except Exception as e:
        logger.error(f"Error retrieving details for node type {node_type_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve details for node type {node_type_name}: {str(e)}")

logger.info("Dashboard Nodes API router created.")

