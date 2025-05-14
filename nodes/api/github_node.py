"""
GitHub Node

This module provides a node for interacting with the GitHub API.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

import aiohttp
from core.node_base import NodeBase, NodeStatus
from utils.api_client import ApiClient, AuthType

logger = logging.getLogger(__name__)


class GitHubNode(NodeBase):
    """
    Node for interacting with the GitHub API.
    
    This node can perform various GitHub operations including:
    - Fetching repository information
    - Listing issues and pull requests
    - Creating issues, comments, and pull requests
    - Searching repositories, code, issues, and users
    """
    
    def __init__(self, node_id: str = None, name: str = None, description: str = None):
        """
        Initialize GitHub node.
        
        Args:
            node_id: Unique identifier for the node
            name: Human-readable name for the node
            description: Description of what the node does
        """
        super().__init__(node_id, name, description)
        
        # API client
        self.api_client = None
        
        # Default retry configuration
        self.retry_config = {
            "max_retries": 3,
            "base_delay": 1,
            "max_delay": 15,
            "retry_on_exceptions": (ConnectionError, TimeoutError, aiohttp.ClientError)
        }
    
    def _validate_config(self, config: Dict[str, Any]) -> None:
        """
        Validate node configuration.
        
        Args:
            config: Configuration dictionary
        
        Raises:
            ValueError: If configuration is invalid
        """
        # Operation is required
        operation = config.get("operation")
        if not operation:
            raise ValueError("GitHub operation must be specified")
        
        # Validate operation-specific parameters
        if operation == "get_repository":
            if not config.get("owner") or not config.get("repo"):
                raise ValueError("Owner and repo names are required for get_repository operation")
        
        elif operation == "list_issues":
            if not config.get("owner") or not config.get("repo"):
                raise ValueError("Owner and repo names are required for list_issues operation")
        
        elif operation == "search":
            if not config.get("query"):
                raise ValueError("Search query is required for search operation")
            if not config.get("search_type") in ("repositories", "code", "issues", "users"):
                raise ValueError("Invalid search type")
        
        elif operation == "create_issue":
            if not config.get("owner") or not config.get("repo"):
                raise ValueError("Owner and repo names are required for create_issue operation")
            if not config.get("title"):
                raise ValueError("Issue title is required for create_issue operation")
        
        elif operation == "create_pull_request":
            if not config.get("owner") or not config.get("repo"):
                raise ValueError("Owner and repo names are required for create_pull_request operation")
            if not config.get("title") or not config.get("head") or not config.get("base"):
                raise ValueError("Title, head, and base are required for create_pull_request operation")
    
    def _validate_credentials(self, credentials: Dict[str, Any]) -> None:
        """
        Validate authentication credentials.
        
        Args:
            credentials: Authentication credentials
        
        Raises:
            ValueError: If credentials are invalid
        """
        auth_type = credentials.get("auth_type", "token")
        
        if auth_type == "token":
            if not credentials.get("token"):
                raise ValueError("API token is required for token authentication")
        
        elif auth_type == "oauth":
            if not credentials.get("access_token"):
                raise ValueError("Access token is required for OAuth authentication")
    
    async def _execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the GitHub operation.
        
        Args:
            input_data: Input data containing operation parameters
        
        Returns:
            Dictionary containing the operation results
        """
        # Initialize API client if not already done
        if not self.api_client:
            await self._init_api_client()
        
        # Get operation from config
        operation = self.config.get("operation")
        
        # Allow operation override from input
        if "operation" in input_data:
            operation = input_data.get("operation")
        
        logger.info(f"Executing GitHub operation: {operation}")
        
        # Execute the appropriate operation
        if operation == "get_repository":
            return await self._get_repository(input_data)
        
        elif operation == "list_issues":
            return await self._list_issues(input_data)
        
        elif operation == "search":
            return await self._search(input_data)
        
        elif operation == "create_issue":
            return await self._create_issue(input_data)
        
        elif operation == "create_pull_request":
            return await self._create_pull_request(input_data)
        
        else:
            raise ValueError(f"Unsupported GitHub operation: {operation}")
    
    async def _init_api_client(self) -> None:
        """
        Initialize the GitHub API client.
        """
        # Set up authentication
        auth_type = AuthType.BEARER
        auth_config = {}
        
        # Get auth type from credentials
        cred_auth_type = self.credentials.get("auth_type", "token")
        
        if cred_auth_type == "token":
            auth_config["token"] = self.credentials.get("token")
        
        elif cred_auth_type == "oauth":
            auth_config["token"] = self.credentials.get("access_token")
        
        # Create API client
        self.api_client = ApiClient(
            base_url="https://api.github.com",
            auth_type=auth_type,
            auth_config=auth_config,
            timeout=self.config.get("timeout", 30),
            max_retries=self.config.get("max_retries", 3),
            verify_ssl=True
        )
        
        # Initialize session
        await self.api_client.create_session()
    
    async def _get_repository(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get information about a repository.
        
        Args:
            input_data: Input data containing operation parameters
        
        Returns:
            Repository information
        """
        # Get parameters from config and input
        owner = input_data.get("owner", self.config.get("owner"))
        repo = input_data.get("repo", self.config.get("repo"))
        
        if not owner or not repo:
            raise ValueError("Owner and repo names are required")
        
        # Make API request
        endpoint = f"repos/{owner}/{repo}"
        response, status = await self.api_client.get(endpoint)
        
        return {
            "repository": response,
            "status": status
        }
    
    async def _list_issues(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        List issues for a repository.
        
        Args:
            input_data: Input data containing operation parameters
        
        Returns:
            List of issues
        """
        # Get parameters from config and input
        owner = input_data.get("owner", self.config.get("owner"))
        repo = input_data.get("repo", self.config.get("repo"))
        state = input_data.get("state", self.config.get("state", "open"))
        labels = input_data.get("labels", self.config.get("labels"))
        sort = input_data.get("sort", self.config.get("sort", "created"))
        direction = input_data.get("direction", self.config.get("direction", "desc"))
        per_page = input_data.get("per_page", self.config.get("per_page", 30))
        page = input_data.get("page", self.config.get("page", 1))
        
        if not owner or not repo:
            raise ValueError("Owner and repo names are required")
        
        # Prepare parameters
        params = {
            "state": state,
            "sort": sort,
            "direction": direction,
            "per_page": per_page,
            "page": page
        }
        
        if labels:
            if isinstance(labels, list):
                params["labels"] = ",".join(labels)
            else:
                params["labels"] = labels
        
        # Make API request
        endpoint = f"repos/{owner}/{repo}/issues"
        response, status = await self.api_client.get(endpoint, params=params)
        
        return {
            "issues": response,
            "status": status
        }
    
    async def _search(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Search GitHub.
        
        Args:
            input_data: Input data containing operation parameters
        
        Returns:
            Search results
        """
        # Get parameters from config and input
        query = input_data.get("query", self.config.get("query"))
        search_type = input_data.get("search_type", self.config.get("search_type", "repositories"))
        sort = input_data.get("sort", self.config.get("sort"))
        order = input_data.get("order", self.config.get("order", "desc"))
        per_page = input_data.get("per_page", self.config.get("per_page", 30))
        page = input_data.get("page", self.config.get("page", 1))
        
        if not query:
            raise ValueError("Search query is required")
        
        if search_type not in ("repositories", "code", "issues", "users"):
            raise ValueError(f"Invalid search type: {search_type}")
        
        # Prepare parameters
        params = {
            "q": query,
            "order": order,
            "per_page": per_page,
            "page": page
        }
        
        if sort:
            params["sort"] = sort
        
        # Make API request
        endpoint = f"search/{search_type}"
        response, status = await self.api_client.get(endpoint, params=params)
        
        return {
            "search_results": response,
            "status": status
        }
    
    async def _create_issue(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create an issue.
        
        Args:
            input_data: Input data containing operation parameters
        
        Returns:
            Created issue information
        """
        # Get parameters from config and input
        owner = input_data.get("owner", self.config.get("owner"))
        repo = input_data.get("repo", self.config.get("repo"))
        title = input_data.get("title", self.config.get("title"))
        body = input_data.get("body", self.config.get("body", ""))
        labels = input_data.get("labels", self.config.get("labels", []))
        assignees = input_data.get("assignees", self.config.get("assignees", []))
        
        if not owner or not repo:
            raise ValueError("Owner and repo names are required")
        
        if not title:
            raise ValueError("Issue title is required")
        
        # Prepare request body
        json_data = {
            "title": title,
            "body": body
        }
        
        if labels:
            json_data["labels"] = labels
        
        if assignees:
            json_data["assignees"] = assignees
        
        # Make API request
        endpoint = f"repos/{owner}/{repo}/issues"
        response, status = await self.api_client.post(endpoint, json_data=json_data)
        
        return {
            "issue": response,
            "status": status
        }
    
    async def _create_pull_request(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a pull request.
        
        Args:
            input_data: Input data containing operation parameters
        
        Returns:
            Created pull request information
        """
        # Get parameters from config and input
        owner = input_data.get("owner", self.config.get("owner"))
        repo = input_data.get("repo", self.config.get("repo"))
        title = input_data.get("title", self.config.get("title"))
        body = input_data.get("body", self.config.get("body", ""))
        head = input_data.get("head", self.config.get("head"))
        base = input_data.get("base", self.config.get("base"))
        draft = input_data.get("draft", self.config.get("draft", False))
        
        if not owner or not repo:
            raise ValueError("Owner and repo names are required")
        
        if not title or not head or not base:
            raise ValueError("Title, head, and base are required")
        
        # Prepare request body
        json_data = {
            "title": title,
            "body": body,
            "head": head,
            "base": base,
            "draft": draft
        }
        
        # Make API request
        endpoint = f"repos/{owner}/{repo}/pulls"
        response, status = await self.api_client.post(endpoint, json_data=json_data)
        
        return {
            "pull_request": response,
            "status": status
        }
    
    def _cleanup(self) -> None:
        """
        Perform cleanup operations when the node is stopped.
        """
        # Close API client session
        if self.api_client:
            try:
                asyncio.create_task(self.api_client.close_session())
            except Exception as e:
                logger.warning(f"Error closing API client session: {str(e)}")
    
    def _get_input_schema(self) -> Dict[str, Any]:
        """
        Get the JSON schema for this node"s inputs.
        
        Returns:
            Input schema
        """
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["get_repository", "list_issues", "search", "create_issue", "create_pull_request"],
                    "description": "GitHub operation to perform"
                },
                "owner": {
                    "type": "string",
                    "description": "Repository owner (user or organization)"
                },
                "repo": {
                    "type": "string",
                    "description": "Repository name"
                },
                "query": {
                    "type": "string",
                    "description": "Search query"
                },
                "search_type": {
                    "type": "string",
                    "enum": ["repositories", "code", "issues", "users"],
                    "description": "Type of search to perform"
                },
                "title": {
                    "type": "string",
                    "description": "Title for issue or pull request"
                },
                "body": {
                    "type": "string",
                    "description": "Body content for issue or pull request"
                },
                "head": {
                    "type": "string",
                    "description": "Head branch for pull request"
                },
                "base": {
                    "type": "string",
                    "description": "Base branch for pull request"
                },
                "state": {
                    "type": "string",
                    "enum": ["open", "closed", "all"],
                    "description": "Issue state"
                },
                "labels": {
                    "oneOf": [
                        {
                            "type": "string",
                            "description": "Comma-separated list of labels"
                        },
                        {
                            "type": "array",
                            "items": {
                                "type": "string"
                            },
                            "description": "List of labels"
                        }
                    ]
                },
                "assignees": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "List of assignees"
                }
            }
        }
    
    def _get_output_schema(self) -> Dict[str, Any]:
        """
        Get the JSON schema for this node"s outputs.
        
        Returns:
            Output schema
        """
        return {
            "type": "object",
            "properties": {
                "repository": {
                    "type": "object",
                    "description": "Repository information"
                },
                "issues": {
                    "type": "array",
                    "items": {
                        "type": "object"
                    },
                    "description": "List of issues"
                },
                "search_results": {
                    "type": "object",
                    "description": "Search results"
                },
                "issue": {
                    "type": "object",
                    "description": "Created issue information"
                },
                "pull_request": {
                    "type": "object",
                    "description": "Created pull request information"
                },
                "status": {
                    "type": "integer",
                    "description": "HTTP status code"
                }
            }
        }
    
    def _get_config_schema(self) -> Dict[str, Any]:
        """
        Get the JSON schema for this node"s configuration.
        
        Returns:
            Configuration schema
        """
        return {
            "type": "object",
            "required": ["operation"],
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["get_repository", "list_issues", "search", "create_issue", "create_pull_request"],
                    "description": "GitHub operation to perform"
                },
                "owner": {
                    "type": "string",
                    "description": "Repository owner (user or organization)"
                },
                "repo": {
                    "type": "string",
                    "description": "Repository name"
                },
                "state": {
                    "type": "string",
                    "enum": ["open", "closed", "all"],
                    "default": "open",
                    "description": "Issue state"
                },
                "labels": {
                    "oneOf": [
                        {
                            "type": "string",
                            "description": "Comma-separated list of labels"
                        },
                        {
                            "type": "array",
                            "items": {
                                "type": "string"
                            },
                            "description": "List of labels"
                        }
                    ]
                },
                "sort": {
                    "type": "string",
                    "description": "Sort field"
                },
                "direction": {
                    "type": "string",
                    "enum": ["asc", "desc"],
                    "default": "desc",
                    "description": "Sort direction"
                },
                "per_page": {
                    "type": "integer",
                    "default": 30,
                    "minimum": 1,
                    "maximum": 100,
                    "description": "Number of items per page"
                },
                "page": {
                    "type": "integer",
                    "default": 1,
                    "minimum": 1,
                    "description": "Page number"
                },
                "query": {
                    "type": "string",
                    "description": "Search query"
                },
                "search_type": {
                    "type": "string",
                    "enum": ["repositories", "code", "issues", "users"],
                    "default": "repositories",
                    "description": "Type of search to perform"
                },
                "order": {
                    "type": "string",
                    "enum": ["asc", "desc"],
                    "default": "desc",
                    "description": "Sort order"
                },
                "title": {
                    "type": "string",
                    "description": "Title for issue or pull request"
                },
                "body": {
                    "type": "string",
                    "description": "Body content for issue or pull request"
                },
                "assignees": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "List of assignees"
                },
                "head": {
                    "type": "string",
                    "description": "Head branch for pull request"
                },
                "base": {
                    "type": "string",
                    "description": "Base branch for pull request"
                },
                "draft": {
                    "type": "boolean",
                    "default": False,
                    "description": "Whether to create a draft pull request"
                },
                "timeout": {
                    "type": "integer",
                    "default": 30,
                    "minimum": 1,
                    "description": "API request timeout in seconds"
                },
                "max_retries": {
                    "type": "integer",
                    "default": 3,
                    "minimum": 0,
                    "description": "Maximum number of retry attempts"
                },
                "continue_on_error": {
                    "type": "boolean",
                    "default": False,
                    "description": "Whether to continue workflow execution if this node fails"
                }
            }
        }

