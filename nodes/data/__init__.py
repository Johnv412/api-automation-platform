# -*- coding: utf-8 -*-
"""
Data processing nodes sub-package.

This package is intended to house nodes that perform data transformation,
manipulation, filtering, or other data-centric operations within a workflow.

Nodes discovered here will be categorized as 'data' by the NodeRegistry.
"""

import logging

# Import node classes here to make them discoverable by the NodeRegistry
from .json_transformer_node import JsonTransformerNode # Assuming this was integrated earlier
from .file_reader_node import FileReaderNode
from .file_writer_node import FileWriterNode

logger = logging.getLogger(__name__)
logger.debug("Nodes Data sub-package initialized with JsonTransformerNode, FileReaderNode, FileWriterNode.")

__all__ = ["JsonTransformerNode", "FileReaderNode", "FileWriterNode"]

