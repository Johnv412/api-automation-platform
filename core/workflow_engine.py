"""
Workflow Engine

This module defines the WorkflowEngine class that orchestrates the execution
of workflows, manages node dependencies, and handles workflow lifecycle.
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Type, Union

from core.execution_context import ExecutionContext
from core.node_base import NodeBase, NodeStatus
from core.node_registry import NodeRegistry
from utils.error_handler import WorkflowError, handle_workflow_error
from utils.logging_manager import log_execution_event

logger = logging.getLogger(__name__)


class WorkflowStatus(Enum):
    """Possible status values for a workflow."""
    REGISTERED = "registered"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class WorkflowEngine:
    """
    Orchestrates the execution of workflows.
    
    The WorkflowEngine is responsible for:
    - Managing workflow execution lifecycle
    - Handling dependencies between nodes
    - Processing data flow between nodes
    - Managing concurrency and parallel execution
    - Handling errors and retries at the workflow level
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the workflow engine.
        
        Args:
            config: Global configuration dictionary
        """
        self.config = config
        self.node_registry = NodeRegistry()
        
        # Workflow tracking
        self.workflows = {}  # id -> workflow definition
        self.workflow_status = {}  # id -> WorkflowStatus
        self.active_executions = {}  # execution_id -> execution context
        
        # Concurrency controls
        self.max_concurrent_workflows = config.get("engine", {}).get("max_concurrent_workflows", 10)
        self.execution_semaphore = asyncio.Semaphore(self.max_concurrent_workflows)
        
        # Event loop
        self.loop = None
        self.running = False
        self.scheduler_task = None
        
        logger.info(f"Workflow engine initialized with max concurrency: {self.max_concurrent_workflows}")
    
    def register_workflow(self, workflow_def: Dict[str, Any]) -> str:
        """
        Register a workflow definition with the engine.
        
        Args:
            workflow_def: Workflow definition dictionary
        
        Returns:
            The workflow ID
        
        Raises:
            WorkflowError: If the workflow definition is invalid
        """
        try:
            # Validate workflow definition
            self._validate_workflow_def(workflow_def)
            
            workflow_id = workflow_def.get("id", str(uuid.uuid4()))
            workflow_def["id"] = workflow_id
            
            self.workflows[workflow_id] = workflow_def
            self.workflow_status[workflow_id] = WorkflowStatus.REGISTERED
            
            logger.info(f"Workflow \'{workflow_def.get('name', workflow_id)}\' ({workflow_id}) registered")
            return workflow_id
            
        except Exception as e:
            logger.error(f"Failed to register workflow: {str(e)}")
            raise WorkflowError(f"Failed to register workflow: {str(e)}")
    
    def start(self) -> None:
        """
        Start the workflow engine and scheduler.
        """
        if self.running:
            logger.warning("Workflow engine is already running")
            return
        
        logger.info("Starting workflow engine")
        self.running = True
        
        # Get or create event loop
        try:
            self.loop = asyncio.get_event_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
        
        # Start workflow scheduler
        self.scheduler_task = self.loop.create_task(self._scheduler())
        
        logger.info("Workflow engine started")
    
    def stop(self) -> None:
        """
        Stop the workflow engine gracefully.
        """
        if not self.running:
            return
        
        logger.info("Stopping workflow engine")
        self.running = False
        
        # Stop active workflows
        for execution_id, context in list(self.active_executions.items()):
            logger.info(f"Stopping workflow execution {execution_id}")
            self.stop_workflow_execution(execution_id)
        
        # Cancel scheduler
        if self.scheduler_task:
            self.scheduler_task.cancel()
        
        logger.info("Workflow engine stopped")
    
    async def execute_workflow(self, workflow_def: Dict[str, Any], trigger_data: Dict[str, Any] = None) -> str:
        """
        Execute a workflow.
        
        Args:
            workflow_def: Workflow definition
            trigger_data: Optional data that triggered the workflow
        
        Returns:
            Execution ID
        """
        # Register workflow if not already registered
        workflow_id = workflow_def.get("id")
        if workflow_id not in self.workflows:
            workflow_id = self.register_workflow(workflow_def)
        
        execution_id = str(uuid.uuid4())
        
        # Create execution context
        context = ExecutionContext(
            workflow_id=workflow_id,
            execution_id=execution_id,
            workflow_def=workflow_def,
            trigger_data=trigger_data or {}
        )
        
        # Store in active executions
        self.active_executions[execution_id] = context
        
        # Update workflow status
        self.workflow_status[workflow_id] = WorkflowStatus.RUNNING
        
        # Start execution in a separate task to not block
        logger.info(f"Starting workflow \'{workflow_def.get('name', workflow_id)}\' execution {execution_id}")
        
        # Acquire concurrency semaphore
        async with self.execution_semaphore:
            execution_task = self.loop.create_task(self._execute_workflow_internal(context))
            context.task = execution_task
        
        return execution_id
    
    def stop_workflow_execution(self, execution_id: str) -> None:
        """
        Stop a running workflow execution.
        
        Args:
            execution_id: The execution ID to stop
        """
        if execution_id not in self.active_executions:
            logger.warning(f"No active execution with ID {execution_id}")
            return
        
        context = self.active_executions[execution_id]
        
        # Cancel the execution task
        if context.task and not context.task.done():
            context.task.cancel()
        
        # Mark workflow as stopped
        workflow_id = context.workflow_id
        self.workflow_status[workflow_id] = WorkflowStatus.STOPPED
        
        # Stop all active nodes
        for node in context.active_nodes.values():
            try:
                node.stop()
            except Exception as e:
                logger.error(f"Error stopping node {node.id}: {str(e)}")
        
        logger.info(f"Workflow execution {execution_id} stopped")
    
    def get_workflow_status(self, workflow_id: str) -> Optional[str]:
        """
        Get the current status of a workflow.
        
        Args:
            workflow_id: The workflow ID
        
        Returns:
            Status string or None if workflow not found
        """
        if workflow_id not in self.workflow_status:
            return None
        
        return self.workflow_status[workflow_id].value
    
    def get_execution_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed status of a workflow execution.
        
        Args:
            execution_id: The execution ID
        
        Returns:
            Status dictionary or None if execution not found
        """
        if execution_id not in self.active_executions:
            # Check in historical executions (could be stored in a database)
            return None
        
        context = self.active_executions[execution_id]
        
        return {
            "execution_id": execution_id,
            "workflow_id": context.workflow_id,
            "workflow_name": context.workflow_def.get("name", "Unnamed"),
            "status": context.status,
            "start_time": context.start_time.isoformat() if context.start_time else None,
            "end_time": context.end_time.isoformat() if context.end_time else None,
            "duration_seconds": context.duration_seconds,
            "nodes": {
                node_id: {
                    "status": node.status.value,
                    "start_time": node.start_time.isoformat() if node.start_time else None,
                    "end_time": node.end_time.isoformat() if node.end_time else None,
                    "duration": node.execution_duration
                } for node_id, node in context.active_nodes.items()
            },
            "error": context.error
        }
    
    async def _scheduler(self) -> None:
        """
        Workflow scheduler that handles periodic and event-driven workflows.
        """
        logger.info("Workflow scheduler started")
        
        while self.running:
            try:
                # Check for scheduled workflows that need to be executed
                current_time = datetime.utcnow()
                
                for workflow_id, workflow_def in self.workflows.items():
                    # Skip workflows that are already running
                    if self.workflow_status.get(workflow_id) == WorkflowStatus.RUNNING:
                        continue
                    
                    # Check if workflow is scheduled to run
                    schedule = workflow_def.get("schedule", {})
                    if not schedule:
                        continue
                    
                    # Check schedule type
                    if schedule.get("type") == "interval":
                        interval_seconds = schedule.get("interval_seconds", 0)
                        if interval_seconds <= 0:
                            continue
                        
                        # Check last execution time
                        last_execution = workflow_def.get("last_execution_time")
                        if last_execution:
                            last_execution = datetime.fromisoformat(last_execution)
                            next_execution = last_execution + timedelta(seconds=interval_seconds)
                            
                            if current_time >= next_execution:
                                await self.execute_workflow(workflow_def)
                                # Update last execution time
                                workflow_def["last_execution_time"] = current_time.isoformat()
                        else:
                            # First execution
                            await self.execute_workflow(workflow_def)
                            workflow_def["last_execution_time"] = current_time.isoformat()
                
                # Sleep for a short interval before checking again
                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                logger.info("Workflow scheduler cancelled")
                break
            except Exception as e:
                logger.error(f"Error in workflow scheduler: {str(e)}")
                await asyncio.sleep(5)  # Sleep longer on error
    
    async def _execute_workflow_internal(self, context: ExecutionContext) -> Dict[str, Any]:
        """
        Internal method to execute a workflow.
        
        Args:
            context: The execution context
        
        Returns:
            Workflow execution results
        """
        workflow_id = context.workflow_id
        execution_id = context.execution_id
        workflow_def = context.workflow_def
        
        try:
            logger.info(f"Starting workflow execution {execution_id} for workflow {workflow_id}")
            context.start_time = datetime.utcnow()
            context.status = "running"
            
            # Log execution start
            log_execution_event(
                event_type="workflow_start",
                workflow_id=workflow_id,
                execution_id=execution_id,
                details={
                    "workflow_name": workflow_def.get("name", "Unnamed"),
                    "trigger_data": context.trigger_data
                }
            )
            
            # Initialize all nodes first
            await self._initialize_workflow_nodes(context)
            
            # Execute the workflow nodes in dependency order
            result = await self._execute_workflow_nodes(context)
            
            # Mark workflow as completed
            self.workflow_status[workflow_id] = WorkflowStatus.COMPLETED
            context.status = "completed"
            context.end_time = datetime.utcnow()
            context.duration_seconds = (context.end_time - context.start_time).total_seconds()
            
            # Log execution completion
            log_execution_event(
                event_type="workflow_complete",
                workflow_id=workflow_id,
                execution_id=execution_id,
                details={
                    "duration_seconds": context.duration_seconds,
                    "node_count": len(context.active_nodes)
                }
            )
            
            logger.info(f"Workflow execution {execution_id} completed successfully")
            return result
            
        except asyncio.CancelledError:
            # Workflow was cancelled
            logger.info(f"Workflow execution {execution_id} was cancelled")
            context.status = "cancelled"
            context.end_time = datetime.utcnow()
            context.duration_seconds = (context.end_time - context.start_time).total_seconds()
            
            # Log cancellation
            log_execution_event(
                event_type="workflow_cancelled",
                workflow_id=workflow_id,
                execution_id=execution_id,
                details={
                    "duration_seconds": context.duration_seconds
                }
            )
            
            # Re-raise to propagate cancellation
            raise
            
        except Exception as e:
            # Handle workflow errors
            context.status = "failed"
            context.error = str(e)
            context.end_time = datetime.utcnow()
            context.duration_seconds = (context.end_time - context.start_time).total_seconds()
            
            # Mark workflow as failed
            self.workflow_status[workflow_id] = WorkflowStatus.FAILED
            
            # Log execution failure
            log_execution_event(
                event_type="workflow_error",
                workflow_id=workflow_id,
                execution_id=execution_id,
                details={
                    "error": str(e),
                    "duration_seconds": context.duration_seconds
                }
            )
            
            logger.error(f"Workflow execution {execution_id} failed: {str(e)}")
            
            # Custom error handling
            handle_workflow_error(e, context)
            
            # Re-raise the exception
            raise WorkflowError(f"Workflow execution failed: {str(e)}")
            
        finally:
            # Clean up resources
            try:
                # Remove from active executions
                self.active_executions.pop(execution_id, None)
                
            except Exception as cleanup_error:
                logger.error(f"Error during workflow cleanup: {str(cleanup_error)}")
    
    async def _initialize_workflow_nodes(self, context: ExecutionContext) -> None:
        """
        Initialize all nodes in the workflow.
        
        Args:
            context: The execution context
        """
        workflow_def = context.workflow_def
        nodes_def = workflow_def.get("nodes", {})
        
        for node_id, node_def in nodes_def.items():
            # Get node type
            node_type = node_def.get("type")
            if not node_type:
                raise WorkflowError(f"Node {node_id} is missing type definition")
            
            # Create node instance
            node_instance = self.node_registry.create_node(
                node_type,
                node_id=node_id,
                name=node_def.get("name", node_id),
                description=node_def.get("description", "")
            )
            
            if not node_instance:
                raise WorkflowError(f"Failed to create node of type {node_type}")
            
            # Configure the node
            node_config = node_def.get("config", {})
            node_credentials = node_def.get("credentials", {})
            
            try:
                node_instance.configure(node_config, node_credentials)
                
                # Store in active nodes
                context.active_nodes[node_id] = node_instance
                
            except Exception as e:
                logger.error(f"Failed to configure node {node_id}: {str(e)}")
                raise WorkflowError(f"Failed to configure node {node_id}: {str(e)}")
    
    async def _execute_workflow_nodes(self, context: ExecutionContext) -> Dict[str, Any]:
        """
        Execute all nodes in the workflow in dependency order.
        
        Args:
            context: The execution context
        
        Returns:
            Workflow execution results
        """
        workflow_def = context.workflow_def
        execution_id = context.execution_id
        
        # Build execution plan based on node dependencies
        execution_plan = self._build_execution_plan(workflow_def)
        
        # Initialize results storage
        context.node_results = {}
        
        # Process execution plan levels in order
        for level, node_ids in enumerate(execution_plan):
            logger.debug(f"Executing level {level} with nodes: {', '.join(node_ids)}")
            
            # Nodes at the same level can be executed in parallel
            tasks = []
            
            for node_id in node_ids:
                node = context.active_nodes.get(node_id)
                if not node:
                    logger.warning(f"Node {node_id} not found in active nodes")
                    continue
                
                # Prepare input data for the node
                input_data = self._prepare_node_input(node_id, context)
                
                # Create execution task
                task = self._execute_node(node, input_data, execution_id, context)
                tasks.append(task)
            
            # Wait for all nodes at this level to complete
            if tasks:
                node_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results and handle exceptions
                for i, result in enumerate(node_results):
                    node_id = node_ids[i]
                    
                    if isinstance(result, Exception):
                        logger.error(f"Node {node_id} execution failed: {str(result)}")
                        
                        # Check if the node is required for workflow completion
                        if self._is_node_required(node_id, workflow_def):
                            raise WorkflowError(f"Required node {node_id} failed: {str(result)}")
                            
                        # For non-required nodes, store the error but continue
                        context.node_results[node_id] = {
                            "error": str(result),
                            "status": "failed"
                        }
                    else:
                        # Store successful result
                        context.node_results[node_id] = result
        
        # Return final workflow results
        return self._prepare_workflow_output(context)
    
    async def _execute_node(self, node: NodeBase, input_data: Dict[str, Any], 
                           execution_id: str, context: ExecutionContext) -> Dict[str, Any]:
        """
        Execute a single node.
        
        Args:
            node: Node instance to execute
            input_data: Input data for the node
            execution_id: Current execution ID
            context: Execution context
        
        Returns:
            Node execution results
        """
        try:
            logger.info(f"Executing node {node.name} ({node.id})")
            
            # Log node execution start
            log_execution_event(
                event_type="node_start",
                workflow_id=context.workflow_id,
                execution_id=execution_id,
                node_id=node.id,
                details={
                    "node_type": node.__class__.__name__,
                    "node_name": node.name
                }
            )
            
            # Execute the node
            result = await node.execute(input_data, execution_id)
            
            # Log node execution completion
            log_execution_event(
                event_type="node_complete",
                workflow_id=context.workflow_id,
                execution_id=execution_id,
                node_id=node.id,
                details={
                    "duration_seconds": node.execution_duration,
                    "status": node.status.value
                }
            )
            
            return result
            
        except Exception as e:
            # Log node execution failure
            log_execution_event(
                event_type="node_error",
                workflow_id=context.workflow_id,
                execution_id=execution_id,
                node_id=node.id,
                details={
                    "error": str(e),
                    "duration_seconds": node.execution_duration if hasattr(node, "execution_duration") else 0
                }
            )
            
            logger.error(f"Node {node.name} ({node.id}) execution failed: {str(e)}")
            raise
    
    def _build_execution_plan(self, workflow_def: Dict[str, Any]) -> List[List[str]]:
        """
        Build an execution plan based on node dependencies.
        
        The execution plan is a list of levels, where each level is a list of
        node IDs that can be executed in parallel.
        
        Args:
            workflow_def: Workflow definition
        
        Returns:
            Execution plan as a list of levels
        """
        nodes_def = workflow_def.get("nodes", {})
        edges = workflow_def.get("edges", [])
        
        # Build dependency graph
        dependencies = {node_id: set() for node_id in nodes_def}
        
        for edge in edges:
            source = edge.get("source")
            target = edge.get("target")
            
            if source and target:
                # Target depends on source
                dependencies[target].add(source)
        
        # Build execution plan using topological sort
        execution_plan = []
        remaining_nodes = set(dependencies.keys())
        
        while remaining_nodes:
            # Find nodes with no dependencies
            level = []
            for node_id in list(remaining_nodes):
                if not dependencies[node_id]:
                    level.append(node_id)
                    remaining_nodes.remove(node_id)
            
            if not level:
                # Cyclic dependency detected
                cycle_nodes = ", ".join(remaining_nodes)
                raise WorkflowError(f"Cyclic dependency detected among nodes: {cycle_nodes}")
            
            execution_plan.append(level)
            
            # Remove executed nodes from dependencies
            for node_id in remaining_nodes:
                for executed_node in level:
                    dependencies[node_id].discard(executed_node)
        
        return execution_plan
    
    def _prepare_node_input(self, node_id: str, context: ExecutionContext) -> Dict[str, Any]:
        """
        Prepare input data for a node based on workflow definition and previous results.
        
        Args:
            node_id: Node ID
            context: Execution context
        
        Returns:
            Input data for the node
        """
        workflow_def = context.workflow_def
        edges = workflow_def.get("edges", [])
        
        # Start with trigger data
        input_data = {
            "trigger": context.trigger_data
        }
        
        # Add results from upstream nodes
        for edge in edges:
            if edge.get("target") == node_id:
                source_node = edge.get("source")
                if source_node in context.node_results:
                    # Get source node results
                    source_result = context.node_results[source_node]
                    
                    # Check for output mapping
                    output_path = edge.get("source_output", "output")
                    
                    # Apply mapping if specified
                    if output_path == "output":
                        # Use entire output
                        input_data[source_node] = source_result
                    else:
                        # Extract specific output field
                        parts = output_path.split('.')
                        value = source_result
                        for part in parts:
                            if isinstance(value, dict) and part in value:
                                value = value[part]
                            else:
                                value = None
                                break
                        
                        # Add to target input
                        input_path = edge.get("target_input", source_node)
                        input_data[input_path] = value
        
        return input_data
    
    def _prepare_workflow_output(self, context: ExecutionContext) -> Dict[str, Any]:
        """
        Prepare the final workflow output.
        
        Args:
            context: Execution context
        
        Returns:
            Workflow output
        """
        workflow_def = context.workflow_def
        outputs = workflow_def.get("outputs", {})
        
        # If no specific outputs are defined, return all node results
        if not outputs:
            return {
                "results": context.node_results,
                "metadata": {
                    "workflow_id": context.workflow_id,
                    "execution_id": context.execution_id,
                    "start_time": context.start_time.isoformat() if context.start_time else None,
                    "end_time": context.end_time.isoformat() if context.end_time else None,
                    "duration_seconds": context.duration_seconds,
                    "status": context.status
                }
            }
        
        # Build output according to definition
        result = {}
        
        for output_name, output_def in outputs.items():
            node_id = output_def.get("node")
            output_path = output_def.get("path", "output")
            
            if node_id in context.node_results:
                node_result = context.node_results[node_id]
                
                # Extract value using path
                if output_path == "output":
                    # Use entire output
                    result[output_name] = node_result
                else:
                    # Extract specific output field
                    parts = output_path.split('.')
                    value = node_result
                    for part in parts:
                        if isinstance(value, dict) and part in value:
                            value = value[part]
                        else:
                            value = None
                            break
                    
                    result[output_name] = value
        
        # Add metadata
        result["__metadata__"] = {
            "workflow_id": context.workflow_id,
            "execution_id": context.execution_id,
            "start_time": context.start_time.isoformat() if context.start_time else None,
            "end_time": context.end_time.isoformat() if context.end_time else None,
            "duration_seconds": context.duration_seconds,
            "status": context.status
        }
        
        return result
    
    def _is_node_required(self, node_id: str, workflow_def: Dict[str, Any]) -> bool:
        """
        Check if a node is required for workflow completion.
        
        Args:
            node_id: Node ID to check
            workflow_def: Workflow definition
        
        Returns:
            True if the node is required, False otherwise
        """
        # Check if node is marked as required
        nodes_def = workflow_def.get("nodes", {})
        node_def = nodes_def.get(node_id, {})
        
        if node_def.get("required", True):
            return True
        
        # Check if node is used in workflow outputs
        outputs = workflow_def.get("outputs", {})
        for output_def in outputs.values():
            if output_def.get("node") == node_id:
                return True
        
        # Check if there are downstream nodes that depend on this node
        edges = workflow_def.get("edges", [])
        for edge in edges:
            if edge.get("source") == node_id:
                target_node = edge.get("target")
                if self._is_node_required(target_node, workflow_def):
                    return True
        
        return False
    
    def _validate_workflow_def(self, workflow_def: Dict[str, Any]) -> None:
        """
        Validate a workflow definition.
        
        Args:
            workflow_def: Workflow definition to validate
        
        Raises:
            WorkflowError: If validation fails
        """
        # Check required fields
        if not workflow_def.get("nodes"):
            raise WorkflowError("Workflow must define at least one node")
        
        nodes_def = workflow_def.get("nodes", {})
        edges = workflow_def.get("edges", [])
        
        # Validate nodes
        for node_id, node_def in nodes_def.items():
            if not node_def.get("type"):
                raise WorkflowError(f"Node {node_id} is missing type definition")
            
            # Check if node type is registered
            if not self.node_registry.has_node_type(node_def.get("type")):
                raise WorkflowError(f"Node type {node_def.get('type')} for node {node_id} is not registered")
        
        # Validate edges
        for edge in edges:
            if not edge.get("source") or not edge.get("target"):
                raise WorkflowError("Edge definition is missing source or target")
            
            if edge.get("source") not in nodes_def:
                raise WorkflowError(f"Edge source node {edge.get('source')} not found in workflow")
            
            if edge.get("target") not in nodes_def:
                raise WorkflowError(f"Edge target node {edge.get('target')} not found in workflow")
        
        # Check for cycles
        try:
            self._build_execution_plan(workflow_def)
        except WorkflowError as e:
            if "Cyclic dependency" in str(e):
                raise WorkflowError(f"Workflow definition contains a cycle: {str(e)}")
            raise

