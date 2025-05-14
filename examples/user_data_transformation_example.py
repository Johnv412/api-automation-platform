"""
Complete Workflow Example for API Integration Platform

This example demonstrates a complete workflow that:
1. Reads a JSON file containing user data
2. Transforms the data using JSONPath expressions
3. Logs each step of the process
4. Writes the transformed data to a new file

It showcases the integration of all core components:
- Workflow Engine
- File Reader/Writer Nodes
- JSON Transformer Node
- Logger Node
"""

import asyncio
import json
import os
import logging
from pathlib import Path

# Adjust imports based on the assumption that the script is run from the project root
# or the 'api_integration_platform' directory is in PYTHONPATH.
# If 'examples' is a package and run with 'python -m examples.user_data_transformation_example',
# then relative imports like 'from ..core...' would be needed.
# For now, assume script is run as 'python examples/user_data_transformation_example.py' from project root.

from core.workflow_engine import WorkflowEngine
from core.execution_context import ExecutionContext
from nodes.data.json_transformer_node import JSONTransformerNode
from nodes.data.file_reader_node import FileReaderNode
from nodes.data.file_writer_node import FileWriterNode
from nodes.utility.logger_node import LoggerNode

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    """Run the example workflow."""
    logger.info("Starting example workflow for user data transformation")

    # Define base path relative to this script's location if needed, or assume project root execution
    project_root = Path(__file__).parent.parent # Assumes script is in 'examples' subdir of project root
    data_dir = project_root / "data"
    data_dir.mkdir(exist_ok=True)

    sample_data_path = data_dir / "users.json"
    if not sample_data_path.exists():
        create_sample_data(sample_data_path)

    output_dir = project_root / "output" # For generated files
    output_dir.mkdir(exist_ok=True)
    transformed_output_path = output_dir / "transformed_users.json"
    workflow_log_path = output_dir / "user_data_transformation_workflow.log"

    engine = WorkflowEngine() # Assuming WorkflowEngine is appropriately initialized

    # Define the workflow using the structure expected by the WorkflowEngine
    # The WorkflowEngine provided by the user in workflow-engine-py.py seems to expect
    # a dictionary-based definition or a YAML file path.
    # The WorkflowDefinition class here is local to this example script.
    # For this example to run with the provided engine, it might need to generate
    # a YAML/JSON definition first, or the engine needs to support this object structure.
    # Let's assume for now this example script is self-contained in how it defines/runs the workflow,
    # or it would be adapted to use the main platform's workflow definition format.

    workflow_definition_dict = {
        "id": "user_data_transformation_v2",
        "name": "User Data Transformation Workflow Example",
        "nodes": {
            "read_users_file": {
                "node_type": "FileReader",
                "config": {
                    "file_path": str(sample_data_path),
                    "format": "json"
                },
                "id": "read_users_file" # Ensure node ID matches the key
            },
            "transform_user_data": {
                "node_type": "JSONTransformer",
                "config": {
                    "transformations": [
                        {
                            "source_path": "$.users[*]",
                            "result_key": "user_list",
                            "flatten_array": True
                        },
                        {
                            "source_path": "$.user_list[*].subscription.plan",
                            "result_key": "plans",
                            "flatten_array": True,
                            "unique_values": True
                        },
                        {
                            "source_path": "$.user_list[*].tags[*]",
                            "result_key": "all_tags",
                            "flatten_array": True,
                            "unique_values": True
                        },
                        {
                            "source_path": "$.user_list[*]",
                            "result_key": "transformed_users",
                            "flatten_array": True,
                            "mapping": {
                                "user_id": "$.id",
                                "full_name": "$.name",
                                "contact": "$.email",
                                "location": "$.address.city + ', ' + $.address.state",
                                "is_customer": "$.tags[*] ? contains(@, 'customer')",
                                "subscription_type": "$.subscription.plan",
                                "is_active": "$.subscription.active"
                            }
                        }
                    ]
                },
                "id": "transform_user_data"
            },
            "log_workflow_progress": {
                "node_type": "Logger",
                "config": {
                    "level": "info",
                    "outputs": [
                        {"type": "console"},
                        {
                            "type": "file",
                            "config": {
                                "file_path": str(workflow_log_path)
                            }
                        }
                    ],
                    "format": "json",
                    "include_context": True
                },
                "id": "log_workflow_progress"
            },
            "write_output_file": {
                "node_type": "FileWriter",
                "config": {
                    "file_path": str(transformed_output_path),
                    "format": "json",
                    "json_options": {
                        "indent": 2,
                        "sort_keys": True
                    }
                },
                "id": "write_output_file"
            }
        },
        "connections": [
            {
                "source_node": "read_users_file",
                "target_node": "transform_user_data",
                "source_output": "data", # Default output from FileReaderNode
                "target_input": "data"    # Default input for JSONTransformerNode
            },
            {
                "source_node": "read_users_file",
                "target_node": "log_workflow_progress",
                "source_output": "data", # Log the data read
                "target_input": "message" # LoggerNode expects 'message' or 'data' for structured logging
            },
            {
                "source_node": "transform_user_data",
                "target_node": "log_workflow_progress",
                "source_output": "result", # Default output from JSONTransformerNode
                "target_input": "message"
            },
            {
                "source_node": "transform_user_data",
                "target_node": "write_output_file",
                "source_output": "result", # Default output from JSONTransformerNode
                "target_input": "data"    # Default input for FileWriterNode
            }
        ],
        "start_node": "read_users_file" # Explicitly define start node if engine requires
    }

    # This example script would typically save this dict to a YAML/JSON file
    # and then the main.py or WorkflowEngine would load and run that file.
    # For direct execution within this script (if engine supports dict): 
    # This part needs to align with how the user's WorkflowEngine is designed to be invoked.
    # The provided workflow-engine-py.py has an execute_workflow that takes a Workflow object.
    # It also has load_workflow that takes a file path.
    # To make this example runnable with that engine, we'd need to:
    # 1. Save `workflow_definition_dict` to a temporary YAML/JSON file.
    # 2. Load it using `engine.load_workflow(temp_file_path)`.
    # 3. Execute using `await engine.execute_workflow(loaded_workflow_object)`.

    # For demonstration, let's simulate saving and loading if direct dict execution isn't supported
    temp_workflow_file = data_dir / "temp_user_data_transformation.yaml"
    import yaml
    with open(temp_workflow_file, 'w') as f:
        yaml.dump(workflow_definition_dict, f, sort_keys=False)
    logger.info(f"Temporary workflow definition saved to: {temp_workflow_file}")

    try:
        # Assuming NodeRegistry is populated correctly by the time engine is used.
        # This might happen in main.py or a similar central place.
        # For this standalone example, we might need to register nodes manually if not done globally.
        from core.node_registry import NodeRegistry
        node_registry = NodeRegistry()
        node_registry.register_node(FileReaderNode.NODE_TYPE, FileReaderNode)
        node_registry.register_node(JSONTransformerNode.NODE_TYPE, JSONTransformerNode)
        node_registry.register_node(LoggerNode.NODE_TYPE, LoggerNode)
        node_registry.register_node(FileWriterNode.NODE_TYPE, FileWriterNode)
        
        # Pass the node_registry to the engine if it expects it during init or execution
        # The provided workflow_engine.py initializes NodeRegistry internally.

        loaded_workflow = engine.load_workflow(str(temp_workflow_file)) # engine.load_workflow expects a file path
        logger.info(f"Workflow loaded: {loaded_workflow.name}")
        
        # The execute_workflow in the provided engine takes a Workflow object and an optional initial_payload.
        # It creates an ExecutionContext internally.
        result = await engine.execute_workflow(loaded_workflow)
        logger.info(f"Workflow execution completed successfully.")
        logger.info(f"Final result from workflow execution: {json.dumps(result, indent=2)}")
        logger.info(f"Transformed data written to: {transformed_output_path}")
        logger.info(f"Workflow log written to: {workflow_log_path}")

    except Exception as e:
        logger.error(f"Workflow execution failed: {str(e)}", exc_info=True)
    finally:
        if temp_workflow_file.exists():
            os.remove(temp_workflow_file)
            logger.info(f"Cleaned up temporary workflow file: {temp_workflow_file}")

def create_sample_data(file_path: Path):
    """Create sample user data for the example."""
    sample_data = {
        "users": [
            {
                "id": 1,
                "name": "John Doe",
                "email": "john.doe@example.com",
                "address": {
                    "street": "123 Main St",
                    "city": "San Francisco",
                    "state": "CA",
                    "zip": "94105"
                },
                "tags": ["customer", "premium"],
                "subscription": {
                    "plan": "enterprise",
                    "price": 99.99,
                    "active": True,
                    "renewalDate": "2023-12-31"
                }
            },
            {
                "id": 2,
                "name": "Jane Smith",
                "email": "jane.smith@example.com",
                "address": {
                    "street": "456 Oak Ave",
                    "city": "Seattle",
                    "state": "WA",
                    "zip": "98101"
                },
                "tags": ["customer", "trial"],
                "subscription": {
                    "plan": "basic",
                    "price": 9.99,
                    "active": True,
                    "renewalDate": "2023-10-15"
                }
            },
            {
                "id": 3,
                "name": "Bob Johnson",
                "email": "bob.johnson@example.com",
                "address": {
                    "street": "789 Pine Blvd",
                    "city": "New York",
                    "state": "NY",
                    "zip": "10001"
                },
                "tags": ["prospect"],
                "subscription": {
                    "plan": "none",
                    "price": 0,
                    "active": False,
                    "renewalDate": None # JSON null
                }
            }
        ]
    }
    with open(file_path, 'w') as f:
        json.dump(sample_data, f, indent=2)
    logger.info(f"Created sample data at {file_path}")

if __name__ == "__main__":
    asyncio.run(main())

