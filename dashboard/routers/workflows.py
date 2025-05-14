# -*- coding: utf-8 -*-
"""
Dashboard API router for Workflows.

Provides endpoints to list workflow definitions, view execution history,
and potentially manage workflow instances.
"""

import logging
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Query
# from core.workflow_engine import WorkflowEngine # Accessed via request.app.state
# from workflows.workflow_loader import WorkflowLoader # Accessed via request.app.state

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/definitions/", summary="List Workflow Definitions", response_model=List[Dict[str, Any]])
async def list_workflow_definitions(request: Request):
    """
    Retrieves a list of all available workflow definitions.
    """
    try:
        workflow_loader = request.app.state.workflow_loader
        if not workflow_loader:
            raise HTTPException(status_code=500, detail="WorkflowLoader not initialized")
        
        definitions = workflow_loader.list_available_workflows()
        # The loader returns a list of dicts, each with name, path, and potentially basic info
        # We might want to load and return the full definition for each, or just basic info
        # For now, returning what list_available_workflows provides.
        return definitions
    except Exception as e:
        logger.error(f"Error retrieving workflow definitions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve workflow definitions: {str(e)}")

@router.get("/definitions/{workflow_name_or_path:path}", summary="Get Workflow Definition Details", response_model=Dict[str, Any])
async def get_workflow_definition_details(request: Request, workflow_name_or_path: str):
    """
    Retrieves the detailed definition for a specific workflow.
    The path parameter allows for names like "my_workflow.yaml" or "subdir/my_workflow.yaml".
    """
    try:
        workflow_loader = request.app.state.workflow_loader
        if not workflow_loader:
            raise HTTPException(status_code=500, detail="WorkflowLoader not initialized")
        
        workflow_def = workflow_loader.load_workflow(workflow_name_or_path)
        if not workflow_def:
            raise HTTPException(status_code=404, detail=f"Workflow definition 
                                                  \'{workflow_name_or_path}\' not found.")
        return workflow_def
    except FileNotFoundError:
         raise HTTPException(status_code=404, detail=f"Workflow definition file 
                                               \'{workflow_name_or_path}\' not found.")
    except Exception as e:
        logger.error(f"Error retrieving workflow definition 
                     \'{workflow_name_or_path}\": {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve workflow definition: {str(e)}")

@router.get("/executions/", summary="List Workflow Execution History", response_model=List[Dict[str, Any]])
async def list_workflow_executions(
    request: Request, 
    limit: int = Query(20, ge=1, le=100, description="Number of execution records to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
):
    """
    Retrieves a list of past and currently active workflow executions.
    This requires the WorkflowEngine to store execution history.
    """
    try:
        workflow_engine = request.app.state.workflow_engine
        if not workflow_engine:
            raise HTTPException(status_code=500, detail="WorkflowEngine not initialized")
        
        # Assuming WorkflowEngine has a method like get_all_execution_history
        # This method needs to be implemented in WorkflowEngine
        history = await workflow_engine.get_all_execution_history(limit=limit, offset=offset)
        return history
    except Exception as e:
        logger.error(f"Error retrieving workflow execution history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve workflow execution history: {str(e)}")

@router.get("/executions/{execution_id}", summary="Get Workflow Execution Details", response_model=Dict[str, Any])
async def get_workflow_execution_details(request: Request, execution_id: str):
    """
    Retrieves detailed information for a specific workflow execution.
    """
    try:
        workflow_engine = request.app.state.workflow_engine
        if not workflow_engine:
            raise HTTPException(status_code=500, detail="WorkflowEngine not initialized")
        
        # Assuming WorkflowEngine has a method like get_execution_details
        # This method needs to be implemented in WorkflowEngine
        execution_details = await workflow_engine.get_execution_details(execution_id)
        if not execution_details:
            raise HTTPException(status_code=404, detail=f"Workflow execution 
                                                  \'{execution_id}\' not found.")
        return execution_details
    except HTTPException: # Re-raise HTTPExceptions directly
        raise
    except Exception as e:
        logger.error(f"Error retrieving details for workflow execution 
                     \'{execution_id}\": {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve execution details: {str(e)}")

# Placeholder for triggering a workflow (requires careful consideration of security and parameters)
# @router.post("/definitions/{workflow_name_or_path:path}/trigger", summary="Trigger a Workflow")
# async def trigger_workflow(request: Request, workflow_name_or_path: str, payload: Optional[Dict[str, Any]] = None):
#     try:
#         workflow_loader = request.app.state.workflow_loader
#         workflow_engine = request.app.state.workflow_engine
#         workflow_validator = request.app.state.workflow_validator # Assuming it's on app.state

#         if not all([workflow_loader, workflow_engine, workflow_validator]):
#             raise HTTPException(status_code=500, detail="Core components not initialized")

#         workflow_def = workflow_loader.load_workflow(workflow_name_or_path)
#         if not workflow_def:
#             raise HTTPException(status_code=404, detail=f"Workflow 
#                                                   \'{workflow_name_or_path}\' not found.")
        
#         workflow_validator.validate_workflow(workflow_def) # Validate before execution
        
#         # The `execute_workflow` method in WorkflowEngine might need to accept an initial payload
#         execution_id = await workflow_engine.execute_workflow(workflow_def, initial_payload=payload)
#         return {"message": f"Workflow 
#                           \'{workflow_def.get("name")}\' triggered successfully.", "execution_id": execution_id}
#     except WorkflowDefinitionError as e:
#         raise HTTPException(status_code=400, detail=f"Invalid workflow definition: {str(e)}")
#     except Exception as e:
#         logger.error(f"Error triggering workflow 
#                      \'{workflow_name_or_path}\": {e}", exc_info=True)
#         raise HTTPException(status_code=500, detail=f"Failed to trigger workflow: {str(e)}")

logger.info("Dashboard Workflows API router created.")

