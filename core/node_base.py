# -*- coding: utf-8 -*-
"""
Base class for all nodes in the API Integration Platform.

All custom nodes (API connectors, data transformers, utility functions, etc.)
must inherit from this `NodeBase` class and implement its abstract methods.
This ensures a consistent interface for the WorkflowEngine to manage and
execute nodes.

Key responsibilities of a Node:
- Initialization: Setting up with configuration and context.
- Execution: Performing its specific task (e.g., API call, data manipulation).
- State Management: Handling its internal state if necessary.
- Error Handling: Gracefully managing errors and reporting them.
- Configuration Validation: Ensuring its provided configuration is valid.
"""

from abc import ABC, abstractmethod
import logging
from enum import Enum

# from core.execution_context import ExecutionContext # To be created
# from utils.secure_config import SecureConfigLoader # To be created

class NodeStatus(Enum):
    """Possible status values for a node within a workflow execution."""
    PENDING = "pending"
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    STOPPED = "stopped"

class NodeBase(ABC):
    """
    Abstract base class for all workflow nodes.

    Attributes:
        node_id (str): A unique identifier for this node instance within a workflow.
        node_name (str): A human-readable name for this node type.
        config (dict): Configuration parameters for this node instance.
        logger (logging.Logger): Logger instance for this node.
        status (NodeStatus): The current status of the node.
        start_time (datetime | None): Timestamp when the node started execution.
        end_time (datetime | None): Timestamp when the node finished execution.
        execution_duration (float | None): Duration of the node execution in seconds.
        # context (ExecutionContext): The execution context for the current workflow run.
    """

    def __init__(self, node_id: str, node_name: str, config: dict, logger_name: str = "NodeBase"):
        """
        Initializes the NodeBase.

        Args:
            node_id (str): The unique ID for this node instance.
            node_name (str): The human-readable name or type of the node.
            config (dict): Configuration specific to this node instance.
            logger_name (str): The name for the logger, defaults to NodeBase.
                                Derived classes should provide a more specific name.
        """
        self.node_id = node_id
        self.node_name = node_name
        self.config = config if config is not None else {}
        self.logger = logging.getLogger(f"{logger_name}.{self.node_name}.{self.node_id}")
        self.status = NodeStatus.PENDING
        self.start_time = None
        self.end_time = None
        self.execution_duration = None
        # self.context = None # Will be set by the WorkflowEngine before execution

        self.logger.info(f"Node initialized: ID=\"{self.node_id}\", Name=\"{self.node_name}\", ConfigKeys={list(self.config.keys())})")

    # def set_execution_context(self, context: ExecutionContext):
    #     """Sets the execution context for the node."""
    #     self.context = context
    #     self.logger.debug(f"Execution context set for node {self.node_id}")

    def get_config(self, key: str, default=None):
        """
        Retrieves a configuration value for the node.

        Args:
            key (str): The configuration key.
            default: The default value if the key is not found.

        Returns:
            The configuration value or the default.
        """
        return self.config.get(key, default)

    @abstractmethod
    def validate_config(self) -> bool:
        """
        Validates the node's configuration.

        Derived classes must implement this method to ensure all required
        configuration parameters are present and valid before execution.

        Returns:
            bool: True if the configuration is valid, False otherwise.

        Raises:
            ValueError: If the configuration is invalid.
        """
        self.logger.debug(f"Validating configuration for node {self.node_id}")
        # Example: if 'required_param' not in self.config:
        #     self.logger.error("Missing 'required_param' in configuration.")
        #     raise ValueError("Missing 'required_param' in configuration.")
        return True # Placeholder

    @abstractmethod
    async def setup(self):
        """
        Performs any setup required before the node can run.

        This could include initializing API clients, connecting to databases,
        or loading resources. This method is called once before the first run.
        It can be an async method if I/O operations are involved.
        """
        self.logger.info(f"Setting up node {self.node_id}...")
        self.status = NodeStatus.INITIALIZING
        # Example: self.api_client = SomeAPIClient(self.get_config('api_key'))
        self.status = NodeStatus.READY
        pass

    @abstractmethod
    async def run(self, input_data: dict | None = None) -> dict:
        """
        Executes the primary logic of the node.

        This method is called by the WorkflowEngine. It receives input data
        from the previous node (or initial workflow input) and should return
        its output data, which will be passed to the next node.
        It must be an async method to support non-blocking I/O operations.

        Args:
            input_data (dict | None): Data passed from the previous node or workflow input.
                                      The structure of this dict depends on the preceding node's output.

        Returns:
            dict: The output data from this node's execution. The structure of this
                  dict will be the input for the subsequent node.
                  It should typically include a 'status' (e.g., 'success', 'failure')
                  and 'data' or 'error' keys.
        """
        self.logger.info(f"Running node {self.node_id} with input keys: {list(input_data.keys()) if input_data else 'None'}")
        # Example: result = await self.api_client.fetch_data(input_data.get('query'))
        # return {"status": "success", "data": result}
        return {"status": "success", "data": "Node executed successfully (placeholder)"} # Placeholder

    async def stop(self):
        """
        Performs any cleanup required when the node is stopped or the workflow ends.

        This could include closing connections, releasing resources, etc.
        This method is optional to override if no specific cleanup is needed.
        It can be an async method if I/O operations are involved.
        """
        self.logger.info(f"Stopping node {self.node_id}...")
        self.status = NodeStatus.STOPPED
        pass

    def _handle_error(self, error: Exception, message: str | None = None) -> dict:
        """
        Standardized error handling for the node.

        Args:
            error (Exception): The exception object.
            message (str | None): An optional custom message to log.

        Returns:
            dict: A dictionary representing the error, suitable for output.
        """
        error_message = message if message else str(error)
        self.logger.error(f"Error in node {self.node_id}: {error_message}", exc_info=True)
        self.status = NodeStatus.FAILED
        return {
            "status": "failure",
            "error": error_message,
            "error_type": type(error).__name__
        }

# Example of a simple derived node (for testing purposes, would be in a separate file)
# class MySimpleNode(NodeBase):
#     def __init__(self, node_id: str, config: dict):
#         super().__init__(node_id, "MySimpleNode", config, logger_name="MySimpleNode")

#     def validate_config(self) -> bool:
#         super().validate_config()
#         if "message" not in self.config:
#             self.logger.error("Configuration missing 'message' field.")
#             raise ValueError("Configuration for MySimpleNode must include a 'message' field.")
#         return True

#     async def setup(self):
#         await super().setup()
#         self.logger.info("MySimpleNode setup complete.")

#     async def run(self, input_data: dict | None = None) -> dict:
#         await super().run(input_data)
#         message_to_log = self.get_config("message", "Default message")
#         self.logger.info(f"MySimpleNode is running. Message: {message_to_log}")
#         output = f"MySimpleNode processed: {message_to_log}. Input was: {input_data}"
#         return {"status": "success", "data": output}

#     async def stop(self):
#         await super().stop()
#         self.logger.info("MySimpleNode stopped.")

# if __name__ == '__main__':
#     # Basic test for NodeBase and MySimpleNode
#     import asyncio

#     logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

#     async def test_node():
#         node_config = {"message": "Hello from config!"}
#         simple_node = MySimpleNode(node_id="test_simple_001", config=node_config)

#         try:
#             simple_node.validate_config()
#             await simple_node.setup()
#             result = await simple_node.run({"input_key": "input_value"})
#             print(f"Node run result: {result}")
#         except Exception as e:
#             print(f"An error occurred: {e}")
#         finally:
#             await simple_node.stop()

#     asyncio.run(test_node())

