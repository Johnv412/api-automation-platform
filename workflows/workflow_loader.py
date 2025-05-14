# -*- coding: utf-8 -*-
"""
Workflow Loader for the API Integration Platform.

This module provides the `WorkflowLoader` class, responsible for reading
workflow definition files (YAML or JSON) from the filesystem and parsing
them into Python dictionary objects that the WorkflowEngine can understand.

It handles:
- Reading files from specified paths.
- Parsing YAML and JSON content.
- Basic structural validation (more detailed validation is done by WorkflowValidator).
"""

import os
import yaml # PyYAML for YAML parsing
import json
import logging
from typing import Dict, Any, Optional

from utils.error_handler import WorkflowDefinitionError

class WorkflowLoader:
    """
    Loads workflow definitions from files.
    """

    def __init__(self, workflow_dir: Optional[str] = "workflows/definitions/"):
        """
        Initializes the WorkflowLoader.

        Args:
            workflow_dir (Optional[str]): The default directory to look for workflow files.
                                          Can be an absolute path or relative to the project root.
        """
        self.logger = logging.getLogger(__name__)
        self.workflow_dir = workflow_dir
        self.logger.info(f"WorkflowLoader initialized. Default workflow directory: {self.workflow_dir}")

    def load_workflow(self, file_path_or_name: str) -> Dict[str, Any]:
        """
        Loads a workflow definition from a given file path or name.

        If a name is provided, it attempts to find the file in the `self.workflow_dir`
        with .yaml, .yml, or .json extensions.

        Args:
            file_path_or_name (str): The absolute/relative path to the workflow file,
                                     or just the name of the workflow (without extension).

        Returns:
            Dict[str, Any]: The parsed workflow definition as a dictionary.

        Raises:
            WorkflowDefinitionError: If the file is not found, cannot be parsed, or is empty.
            FileNotFoundError: If the file does not exist (can be caught specifically).
        """
        file_path = self._resolve_file_path(file_path_or_name)
        self.logger.info(f"Attempting to load workflow definition from: {file_path}")

        if not os.path.exists(file_path):
            self.logger.error(f"Workflow file not found: {file_path}")
            raise FileNotFoundError(f"Workflow definition file not found: {file_path}")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                if not content.strip():
                    raise WorkflowDefinitionError(f"Workflow file is empty: {file_path}")

                if file_path.endswith( (".yaml", ".yml") ):
                    workflow_def = yaml.safe_load(content)
                elif file_path.endswith(".json"):
                    workflow_def = json.loads(content)
                else:
                    raise WorkflowDefinitionError(
                        f"Unsupported file extension for workflow: {file_path}. Must be .yaml, .yml, or .json."
                    )
            
            if not isinstance(workflow_def, dict):
                raise WorkflowDefinitionError(
                    f"Parsed workflow content from {file_path} is not a valid dictionary structure."
                )
            
            if not workflow_def: # Check if the loaded dict is empty
                raise WorkflowDefinitionError(f"Workflow definition in {file_path} is empty or invalid after parsing.")

            self.logger.info(f"Successfully loaded and parsed workflow from: {file_path}")
            # Add file path to definition for context, if not already there
            workflow_def["_source_file"] = os.path.abspath(file_path)
            return workflow_def

        except yaml.YAMLError as e:
            self.logger.error(f"Error parsing YAML workflow file {file_path}: {e}", exc_info=True)
            raise WorkflowDefinitionError(f"Invalid YAML format in {file_path}: {e}") from e
        except json.JSONDecodeError as e:
            self.logger.error(f"Error parsing JSON workflow file {file_path}: {e}", exc_info=True)
            raise WorkflowDefinitionError(f"Invalid JSON format in {file_path}: {e}") from e
        except IOError as e:
            self.logger.error(f"Error reading workflow file {file_path}: {e}", exc_info=True)
            raise WorkflowDefinitionError(f"Could not read workflow file {file_path}: {e}") from e
        except WorkflowDefinitionError: # Re-raise our custom error
            raise
        except Exception as e:
            self.logger.error(f"An unexpected error occurred while loading workflow {file_path}: {e}", exc_info=True)
            raise WorkflowDefinitionError(f"Unexpected error loading workflow {file_path}: {str(e)}") from e

    def _resolve_file_path(self, file_path_or_name: str) -> str:
        """
        Resolves a full file path from a given path or name.
        If it seems like a full path already (absolute or clearly relative with extension),
        it uses it. Otherwise, it searches in `self.workflow_dir`.
        """
        if os.path.isabs(file_path_or_name) or \ 
           ( (".yaml" in file_path_or_name or ".yml" in file_path_or_name or ".json" in file_path_or_name) and \ 
             (os.path.sep in file_path_or_name or (os.altsep and os.altsep in file_path_or_name)) ):
            # Looks like a full or specific relative path
            return file_path_or_name

        # Assume it's a name, search in workflow_dir
        base_path = os.path.join(self.workflow_dir, file_path_or_name)
        possible_extensions = [".yaml", ".yml", ".json"]
        for ext in possible_extensions:
            potential_path = base_path + ext
            if os.path.exists(potential_path):
                self.logger.debug(f"Resolved workflow name 
                                  \'{file_path_or_name}\' to path: {potential_path}")
                return potential_path
            potential_path_no_ext_search = os.path.join(self.workflow_dir, file_path_or_name + ext)
            if os.path.exists(potential_path_no_ext_search):
                 self.logger.debug(f"Resolved workflow name 
                                   \'{file_path_or_name}\' to path: {potential_path_no_ext_search}")
                 return potential_path_no_ext_search
        
        # If not found with extensions, return the original (it might be a path that will fail later, or a name for a non-existent file)
        self.logger.debug(f"Could not resolve 
                          \'{file_path_or_name}\' to an existing file with extensions. Returning as is or with default .yaml: {base_path + '.yaml'}")
        return base_path + ".yaml" # Default to .yaml if just a name is given and nothing found

# Example Usage (illustrative)
# if __name__ == "__main__":
#     logging.basicConfig(level=logging.DEBUG, format=\"%(asctime)s - %(name)s - %(levelname)s - %(message)s")

#     # Create dummy workflow files for testing
#     if not os.path.exists("temp_workflows/definitions"):
#         os.makedirs("temp_workflows/definitions")

#     dummy_yaml_content = {
#         "name": "Test YAML Workflow",
#         "version": "1.0",
#         "start_node_id": "node1",
#         "nodes": [
#             {"id": "node1", "type": "TypeA", "config": {"param": "value1"}, "next_node_id": "node2"},
#             {"id": "node2", "type": "TypeB", "config": {"param": "value2"}, "next_node_id": None}
#         ]
#     }
#     with open("temp_workflows/definitions/my_test_workflow.yaml", "w") as f:
#         yaml.dump(dummy_yaml_content, f)

#     dummy_json_content = {
#         "name": "Test JSON Workflow",
#         "version": "1.0",
#         "start_node_id": "start",
#         "nodes": [
#             {"id": "start", "type": "InputNode", "next_node_id": "end"},
#             {"id": "end", "type": "OutputNode", "next_node_id": None}
#         ]
#     }
#     with open("temp_workflows/definitions/another_workflow.json", "w") as f:
#         json.dump(dummy_json_content, f)
    
#     with open("temp_workflows/definitions/empty_workflow.yaml", "w") as f:
#         f.write("") # Empty file
    
#     with open("temp_workflows/definitions/invalid_yaml.yaml", "w") as f:
#         f.write("name: Test\n  bad_indent: here") # Invalid YAML

#     loader = WorkflowLoader(workflow_dir="temp_workflows/definitions/")

#     print("\n--- Testing YAML load by name ---")
#     try:
#         wf_yaml = loader.load_workflow("my_test_workflow")
#         print(f"Loaded YAML: {wf_yaml.get(\"name\")}")
#         assert wf_yaml.get("name") == "Test YAML Workflow"
#     except Exception as e:
#         print(f"Error: {e}")

#     print("\n--- Testing JSON load by full relative path ---")
#     try:
#         wf_json = loader.load_workflow("temp_workflows/definitions/another_workflow.json")
#         print(f"Loaded JSON: {wf_json.get(\"name\")}")
#         assert wf_json.get("name") == "Test JSON Workflow"
#     except Exception as e:
#         print(f"Error: {e}")

#     print("\n--- Testing non-existent workflow ---")
#     try:
#         loader.load_workflow("non_existent_workflow")
#     except FileNotFoundError as e:
#         print(f"Caught expected error: {e}")
#     except Exception as e:
#         print(f"Unexpected error: {e}")

#     print("\n--- Testing empty workflow file ---")
#     try:
#         loader.load_workflow("empty_workflow.yaml")
#     except WorkflowDefinitionError as e:
#         print(f"Caught expected error: {e}")
#     except Exception as e:
#         print(f"Unexpected error: {e}")
        
#     print("\n--- Testing invalid YAML workflow file ---")
#     try:
#         loader.load_workflow("invalid_yaml.yaml")
#     except WorkflowDefinitionError as e:
#         print(f"Caught expected error: {e}")
#     except Exception as e:
#         print(f"Unexpected error: {e}")

#     # Clean up dummy files
#     # import shutil
#     # shutil.rmtree("temp_workflows")

