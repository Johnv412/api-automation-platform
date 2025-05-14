"""
File Reader Node for API Integration Platform

This module implements:
1. FileReaderNode - Reads data from files in various formats (JSON, CSV, TXT, etc.)

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

class FileReaderNode(NodeBase):
    """Node for reading data from files in various formats."""

    NODE_TYPE = "FileReader"

    # Supported file formats
    SUPPORTED_FORMATS = {
        "json": "application/json",
        "csv": "text/csv",
        "txt": "text/plain",
        "yaml": "application/x-yaml",
        "yml": "application/x-yaml",
        "xml": "application/xml", # Note: XML reading is not implemented in the provided code beyond plain text
        "html": "text/html",   # Note: HTML reading as structured data is not implemented beyond plain text
        "md": "text/markdown", # Note: Markdown reading as structured data is not implemented beyond plain text
    }

    def __init__(self, node_id: str, config: Dict[str, Any]):
        super().__init__(node_id, config)

        self.file_path = self.config.get("file_path")
        if not self.file_path:
            raise NodeConfigurationError(f"FileReaderNode {node_id}: file_path is required")

        self.format = self.config.get("format")
        if not self.format:
            _, ext = os.path.splitext(self.file_path)
            self.format = ext.lstrip('.').lower()

        if self.format not in self.SUPPORTED_FORMATS:
            # Check if it's a common alias like 'yml' for 'yaml'
            if self.format == 'yml' and 'yaml' in self.SUPPORTED_FORMATS:
                self.format = 'yaml'
            else:
                raise NodeConfigurationError(
                    f"FileReaderNode {node_id}: Unsupported format '{self.format}'. "
                    f"Supported formats: {', '.join(self.SUPPORTED_FORMATS.keys())}"
                )

        self.encoding = self.config.get("encoding", "utf-8")
        self.csv_options = self.config.get("csv_options", {})
        self.json_options = self.config.get("json_options", {})

    def validate_config(self) -> bool:
        return True

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        file_path = inputs.get("file_path", self.file_path)

        try:
            # Prefer context.file_exists if available and implemented for async checks
            # Fallback to os.path.exists for synchronous check if context method not available/suitable
            # For this example, assuming os.path.exists is sufficient for now.
            if not os.path.exists(file_path):
                raise NodeExecutionError(f"File not found: {file_path}")

            logger.info(f"Reading file: {file_path} as {self.format} for node {self.node_id}")

            data: Any
            if self.format == "json":
                data = await self._read_json(file_path)
            elif self.format in ["yaml", "yml"]:
                data = await self._read_yaml(file_path)
            elif self.format == "csv":
                data = await self._read_csv(file_path)
            elif self.format in ["txt", "xml", "html", "md"]:
                data = await self._read_text(file_path)
            else:
                raise NodeExecutionError(f"FileReaderNode {self.node_id}: Unexpected format '{self.format}' during execution.")

            return {
                "data": data,
                "format": self.format,
                "file_path": file_path,
                "content_type": self.SUPPORTED_FORMATS.get(self.format, "text/plain"),
            }

        except Exception as e:
            logger.error(f"Error reading file {file_path} for node {self.node_id}: {str(e)}", exc_info=True)
            raise NodeExecutionError(f"Error reading file {file_path} for node {self.node_id}: {str(e)}") from e

    async def _read_json(self, file_path: str) -> Union[Dict, List]:
        async with aiofiles.open(file_path, mode='r', encoding=self.encoding) as f:
            content = await f.read()
        parse_float = self.json_options.get("parse_float", float)
        parse_int = self.json_options.get("parse_int", int)
        return json.loads(content, parse_float=parse_float, parse_int=parse_int)

    async def _read_yaml(self, file_path: str) -> Union[Dict, List]:
        async with aiofiles.open(file_path, mode='r', encoding=self.encoding) as f:
            content = await f.read()
        return yaml.safe_load(content)

    async def _read_csv(self, file_path: str) -> List[Dict]:
        delimiter = self.csv_options.get("delimiter", ",")
        has_header = self.csv_options.get("has_header", True)
        df = pd.read_csv(
            file_path,
            delimiter=delimiter,
            header=0 if has_header else None,
            encoding=self.encoding,
            keep_default_na=False,
            na_values=['']
        )
        return df.to_dict(orient="records")

    async def _read_text(self, file_path: str) -> str:
        async with aiofiles.open(file_path, mode='r', encoding=self.encoding) as f:
            return await f.read()

