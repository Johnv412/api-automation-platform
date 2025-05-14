"""
File Writer Node for API Integration Platform

This module implements:
1. FileWriterNode - Writes data to files in various formats

This node handles different file formats, encoding options, and provides error handling.
"""

import os
import json
import csv
import yaml
import logging
from typing import Dict, Any, Optional, List, Union
import aiofiles
import pandas as pd

from ...core.node_base import NodeBase
from ...core.errors import NodeConfigurationError, NodeExecutionError
from ...core.execution_context import ExecutionContext

logger = logging.getLogger(__name__)

class FileWriterNode(NodeBase):
    """Node for writing data to files in various formats."""

    NODE_TYPE = "FileWriter"

    # Supported file formats (same as reader for consistency)
    SUPPORTED_FORMATS = {
        "json": "application/json",
        "csv": "text/csv",
        "txt": "text/plain",
        "yaml": "application/x-yaml",
        "yml": "application/x-yaml",
        "xml": "application/xml", # Note: XML writing is not implemented beyond plain text
        "html": "text/html",   # Note: HTML writing is not implemented beyond plain text
        "md": "text/markdown", # Note: Markdown writing is not implemented beyond plain text
    }

    def __init__(self, node_id: str, config: Dict[str, Any]):
        super().__init__(node_id, config)

        self.file_path = self.config.get("file_path")
        if not self.file_path:
            raise NodeConfigurationError(f"FileWriterNode {node_id}: file_path is required")

        self.format = self.config.get("format")
        if not self.format:
            _, ext = os.path.splitext(self.file_path)
            self.format = ext.lstrip(".").lower()

        if self.format not in self.SUPPORTED_FORMATS:
            if self.format == 'yml' and 'yaml' in self.SUPPORTED_FORMATS:
                self.format = 'yaml'
            else:
                raise NodeConfigurationError(
                    f"FileWriterNode {node_id}: Unsupported format \'{self.format}\'. "
                    f"Supported formats: {", ".join(self.SUPPORTED_FORMATS.keys())}"
                )

        self.encoding = self.config.get("encoding", "utf-8")
        self.mode = self.config.get("mode", "w") # 'w' for overwrite, 'a' for append
        self.create_dir = self.config.get("create_dir", True)
        self.csv_options = self.config.get("csv_options", {})
        self.json_options = self.config.get("json_options", {})

    def validate_config(self) -> bool:
        return True

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        data_to_write = inputs.get("data")
        if data_to_write is None:
            # Allow writing empty files if data is explicitly an empty string
            if data_to_write != "":
                raise NodeExecutionError(f"FileWriterNode {self.node_id}: No data provided to write.")

        file_path = inputs.get("file_path", self.file_path)

        try:
            if self.create_dir:
                dir_name = os.path.dirname(file_path)
                if dir_name: # Ensure dirname is not empty (e.g. for files in current dir)
                    os.makedirs(dir_name, exist_ok=True)

            logger.info(f"Writing to file: {file_path} as {self.format} for node {self.node_id}")

            bytes_written = 0
            if self.format == "json":
                bytes_written = await self._write_json(file_path, data_to_write)
            elif self.format in ["yaml", "yml"]:
                bytes_written = await self._write_yaml(file_path, data_to_write)
            elif self.format == "csv":
                bytes_written = await self._write_csv(file_path, data_to_write)
            elif self.format in ["txt", "xml", "html", "md"]:
                # Ensure data is string for text-based formats
                if not isinstance(data_to_write, str):
                    try:
                        data_to_write = str(data_to_write)
                    except Exception as e_str:
                        raise NodeExecutionError(f"FileWriterNode {self.node_id}: Could not convert data to string for format {self.format}. Error: {e_str}")
                bytes_written = await self._write_text(file_path, data_to_write)
            else:
                raise NodeExecutionError(f"FileWriterNode {self.node_id}: Unexpected format \'{self.format}\' during execution.")

            return {
                "file_path": file_path,
                "success": True,
                "bytes_written": bytes_written,
                "format": self.format,
            }

        except Exception as e:
            logger.error(f"Error writing to file {file_path} for node {self.node_id}: {str(e)}", exc_info=True)
            raise NodeExecutionError(f"Error writing to file {file_path} for node {self.node_id}: {str(e)}") from e

    async def _write_json(self, file_path: str, data: Union[Dict, List, str]) -> int:
        indent = self.json_options.get("indent", 2)
        sort_keys = self.json_options.get("sort_keys", False)
        # If data is already a JSON string, write it directly
        if isinstance(data, str):
            json_str = data
        else:
            json_str = json.dumps(data, indent=indent, sort_keys=sort_keys)

        async with aiofiles.open(file_path, mode=self.mode, encoding=self.encoding) as f:
            await f.write(json_str)
        return len(json_str.encode(self.encoding))

    async def _write_yaml(self, file_path: str, data: Union[Dict, List, str]) -> int:
        if isinstance(data, str):
            yaml_str = data # Assume it's already a valid YAML string
        else:
            yaml_str = yaml.dump(data, default_flow_style=False)
        async with aiofiles.open(file_path, mode=self.mode, encoding=self.encoding) as f:
            await f.write(yaml_str)
        return len(yaml_str.encode(self.encoding))

    async def _write_csv(self, file_path: str, data: Union[List[Dict], pd.DataFrame, str]) -> int:
        delimiter = self.csv_options.get("delimiter", ",")
        write_header = self.csv_options.get("write_header", True)

        if isinstance(data, str):
            # If data is a string, assume it's pre-formatted CSV content
            # This path might need more robust handling for append mode with headers
            async with aiofiles.open(file_path, mode=self.mode, encoding=self.encoding) as f:
                await f.write(data)
            return len(data.encode(self.encoding))
        else:
            if isinstance(data, list):
                if not data: # Handle empty list of records
                    df = pd.DataFrame()
                else:
                    df = pd.DataFrame(data)
            elif isinstance(data, pd.DataFrame):
                df = data
            else:
                raise NodeExecutionError(f"FileWriterNode {self.node_id}: CSV data must be a list of dicts, a pandas DataFrame, or a pre-formatted string.")

            # For append mode, if file exists and has content, don't write header
            effective_write_header = write_header
            if self.mode == 'a' and os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                effective_write_header = False

            # Use aiofiles for async write with pandas, though pandas itself is sync
            # This is a common pattern: prepare data sync, write async
            csv_buffer = df.to_csv(None, sep=delimiter, index=False, header=effective_write_header, encoding=self.encoding)
            if csv_buffer is None: # Handle empty dataframe case for to_csv
                csv_buffer = ""
            
            async with aiofiles.open(file_path, mode=self.mode, encoding=self.encoding) as f:
                await f.write(csv_buffer)
            return len(csv_buffer.encode(self.encoding))

    async def _write_text(self, file_path: str, data: str) -> int:
        async with aiofiles.open(file_path, mode=self.mode, encoding=self.encoding) as f:
            await f.write(data)
        return len(data.encode(self.encoding))

