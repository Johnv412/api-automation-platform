# API Integration Platform

## Overview

The API Integration Platform is a modular, secure, and scalable Python-based framework designed to connect various APIs and automate data workflows. It allows users to define custom nodes (API connectors), create complex workflow pipelines, and process data across multiple services, similar to platforms like Zapier, Make, or n8n, but built from scratch with enterprise-level flexibility, performance, and control.

This platform is architected for maintainability, extensibility, and robust error handling, making it suitable for powering critical backend infrastructure.

## Features

- **Modular Node Architecture**: Easily create and integrate custom nodes for any API or service. Includes API interaction nodes (e.g., GitHub) and data processing nodes (e.g., JSON Transformer).
- **Dynamic Workflow Engine**: Define complex data processing pipelines using a simple YAML/JSON format.
- **Secure Configuration Management**: Enhanced environment-aware configuration loading for sensitive data and API keys, supporting `.env` files, YAML/JSON configs, and environment-specific overrides.
- **Robust Logging System**: Enhanced structured JSON logging for comprehensive monitoring and debugging, with configurable levels and handlers.
- **Centralized Error Handling**: Improved custom exceptions and global handlers for resilient operations, with clear distinction between node and workflow errors.
- **Retry Mechanisms**: Enhanced retry logic with exponential backoff, configurable per node or globally, applicable to API clients and other operations.
- **Asynchronous Operations**: Leverages `asyncio` for non-blocking I/O and improved performance.
- **Web Dashboard (Optional)**: A FastAPI-based web interface to monitor nodes, workflows, and logs.
- **Containerization Support**: Dockerfile and Docker Compose for easy deployment and scaling.

## Architecture

The platform follows a clean, modular architecture:

- **Core**: Contains the fundamental components like `NodeBase`, `WorkflowEngine`, `NodeRegistry`, and `ExecutionContext`.
- **Nodes**: Houses individual connector modules categorized by type:
    -   `api/`: For external API interactions (e.g., `GitHubNode`).
    -   `data/`: For data transformation and manipulation (e.g., `JsonTransformerNode`).
    -   `utility/`: For general-purpose workflow utilities.
- **Workflows**: Manages workflow definitions (`.yaml` files) and the `WorkflowLoader` and `WorkflowValidator`.
- **Utils**: Provides shared utilities for API clients, secure configuration, logging, error handling, and retry mechanisms. All utilities have been enhanced based on user feedback.
- **Config**: Stores environment-specific configuration files (e.g., `development.yaml`, `production.yaml`).
- **Dashboard (Optional)**: A FastAPI application providing a web UI for monitoring and management.
- **Tests**: Directory for unit and integration tests.

## Folder Structure

```
api_integration_platform/
├── config/                     # Configuration files
│   └── development.yaml
│   └── production.yaml.example
├── core/                       # Core platform logic
│   ├── __init__.py
│   ├── auth_manager.py
│   ├── execution_context.py
│   ├── node_base.py
│   ├── node_registry.py
│   └── workflow_engine.py
├── dashboard/                  # Optional FastAPI web dashboard
│   ├── __init__.py
│   ├── app.py
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── logs.py
│   │   ├── nodes.py
│   │   └── workflows.py
│   ├── static/
│   │   └── style.css
│   └── templates/
│       ├── index.html
│       ├── logs.html
│       ├── nodes.html
│       └── workflows.html
├── logs/                       # Log files
├── nodes/                      # Custom node implementations
│   ├── __init__.py
│   ├── api/                    # Nodes for external APIs
│   │   ├── __init__.py
│   │   └── github_node.py      # Example GitHub API node (Updated)
│   ├── data/                   # Nodes for data transformation
│   │   ├── __init__.py
│   │   └── json_transformer_node.py # New JSON Transformer Node
│   └── utility/                # Utility nodes
│       └── __init__.py
├── tests/                      # Unit and integration tests
│   └── __init__.py
├── utils/                      # Shared utility modules (All Updated)
│   ├── __init__.py
│   ├── api_client.py
│   ├── error_handler.py
│   ├── logging_manager.py
│   ├── retry_mechanism.py
│   └── secure_config.py
├── workflows/                  # Workflow management
│   ├── __init__.py
│   ├── definitions/
│   │   ├── __init__.py
│   │   └── github_pr_weather.yaml
│   ├── workflow_loader.py
│   └── workflow_validator.py
├── .env.example                # Example environment variables file
├── Dockerfile                  # For building the Docker image
├── docker-compose.yml          # For running the platform with Docker Compose
├── main.py                     # Main entry point for the platform
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

## Prerequisites

- Python 3.11+
- Docker and Docker Compose (for containerized deployment)
- `pip` for installing Python packages

## Setup and Installation

1.  **Clone the Repository (if applicable)**:
    ```bash
    # git clone <repository_url>
    # cd api_integration_platform
    ```
    (If you received this as a codebase, ensure all files are in a directory named `api_integration_platform`)

2.  **Set up Environment Variables**:
    Copy the example environment file and customize it:
    ```bash
    cp .env.example .env
    ```
    Edit `.env` to include your actual API keys, tokens, and other configurations as needed. The enhanced `SecureConfigLoader` now robustly loads these.

3.  **Install Dependencies**:
    It is highly recommended to use a virtual environment:
    ```bash
    python3.11 -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    pip install -r requirements.txt
    ```

## Running the Platform

### 1. Directly with Python

The `main.py` script is the entry point.

-   **Set Environment for Configuration**: The `SecureConfigLoader` uses the `AIP_ENV` environment variable (default: "development") to determine which configuration file to load from the `config/` directory (e.g., `development.yaml`, `production.yaml`).
    ```bash
    export AIP_ENV="development" # or "production"
    ```
-   **Basic Run (starts workflow engine for scheduled/triggered tasks)**:
    The enhanced `logging_manager.py` will provide structured logs.
    ```bash
    python main.py
    ```
-   **Run with Dashboard**: To start the platform and the web dashboard (default port 5001):
    ```bash
    python main.py --dashboard
    ```
-   **Run a Specific Workflow on Startup**:
    ```bash
    python main.py --workflow workflows/definitions/github_pr_weather.yaml
    ```
-   **Specify a Configuration File**: Overrides the `AIP_CONFIG_PATH` environment variable or default.
    ```bash
    python main.py --config config/custom_config.yaml
    ```
-   **Show Version**:
    ```bash
    python main.py --version
    ```

### 2. Using Docker Compose (Recommended for Development/Production)

Docker Compose simplifies running the platform and any associated services.

-   **Build and Start Containers**:
    Ensure your `.env` file is configured, as `docker-compose.yml` can use it.
    ```bash
    docker-compose up --build
    ```
    To run in detached mode:
    ```bash
    docker-compose up -d --build
    ```
-   **Accessing the Dashboard**: If started with the dashboard, it will typically be available at `http://localhost:5001`.
-   **Viewing Logs**:
    ```bash
    docker-compose logs -f api_platform
    ```
-   **Stopping Containers**:
    ```bash
    docker-compose down
    ```

## Configuration

-   **Main Configuration Files**: Located in `config/` (e.g., `development.yaml`). The active configuration is determined by `AIP_ENV`.
-   **Secure Configuration**: The updated `utils/secure_config.py` handles loading YAML files, `.env` files, and environment variables with a clear precedence.
-   **Environment Variables**: Critical settings, especially secrets, should be managed via environment variables. `AIP_` prefixed variables are automatically loaded (e.g., `AIP_GITHUB_TOKEN` becomes `github.token` in config if not set elsewhere).

## Adding New Nodes

Nodes are the building blocks for interacting with APIs or performing custom logic.

1.  **Inherit from `NodeBase`**: Create a new Python class that inherits from `core.node_base.NodeBase`.
2.  **Implement Abstract Methods**: As defined in `NodeBase` (`_execute`, `_get_input_schema`, etc.).
3.  **Placement**: Place your new node file in `nodes/api/`, `nodes/data/`, or `nodes/utility/`.
4.  **Registration**: The `NodeRegistry` automatically discovers nodes.

Refer to `nodes/api/github_node.py` (updated) and `nodes/data/json_transformer_node.py` (new) for examples.

### New Node: JSON Transformer (`JsonTransformerNode`)

-   **Location**: `nodes/data/json_transformer_node.py`
-   **Purpose**: Provides powerful JSON data transformation capabilities within a workflow.
-   **Features**:
    -   **JSONPath Mappings**: Extract and map values using JSONPath expressions.
    -   **Field Transformations**: Apply operations like `toString`, `toNumber`, `toDate`, `concat`, `slice`, `split`, `join`, `replace`, math operations, string case changes, etc.
    -   **Array Filtering**: Filter arrays based on complex conditions.
    -   **Object Combination**: Merge multiple JSON objects.
    -   **Custom Scripting**: Execute custom Python scripts for complex transformations, with access to input data and safe libraries (`datetime`, `re`, `math`, `json`).
-   **Configuration**: Defined in the workflow, specifying `mappings`, `transforms`, `filter`, `combine`, or `script`.
    ```yaml
    # Example snippet for a workflow definition
    nodes:
      - id: transform_data
        type: JsonTransformer # Or whatever it's registered as
        name: "Transform User Data"
        config:
          source_key: "raw_user_data" # Key in input containing JSON to transform
          mappings:
            userId: "$.id"
            fullName: "$.name.first + ' ' + $.name.last" # Example of simple expression
          transforms:
            - source: "$.profile.age"
              target: "age_in_months"
              operation: "multiply"
              params:
                value: 12
            - source: "$.registered_date"
              target: "formatted_date"
              operation: "toDate"
              params:
                format: "%Y-%m-%d"
          filter:
            path: "$.orders[*]" # JSONPath to an array
            conditions:
              - field: "status"
                operator: "eq"
                value: "completed"
              - field: "amount"
                operator: "gt"
                value: 100
          script: |
            # Custom Python script
            # result is a dict that gets merged
            result['custom_field'] = input_data.get('some_value', '') * 2
            if full_input.get('workflow_metadata', {}).get('is_test'):
                result['is_test_run'] = True
    ```

## Defining Workflows

Workflows define the sequence of node executions and data flow.

1.  **Format**: YAML (or JSON).
2.  **Location**: `workflows/definitions/`.
3.  **Structure**: Includes `name`, `version`, `start_node_id`, and a list of `nodes` with their `id`, `type`, `config`, `input_mapping`, `next_node_id`, etc.

Refer to `workflows/definitions/github_pr_weather.yaml` for an example.

## Enhanced Utilities

-   **`utils/api_client.py`**: Now more robust with configurable retry mechanisms inherited from node or global settings.
-   **`utils/error_handler.py`**: Improved error classes (`NodeError`, `WorkflowError`, `ValidationError`) and handling logic, including formatting exceptions for logs/API responses.
-   **`utils/logging_manager.py`**: Enhanced structured JSON logging with `JsonFormatter` and `LoggerAdapter` for contextual information. Supports configuration via file and environment variables.
-   **`utils/retry_mechanism.py`**: Provides a flexible `@retry_with_backoff` decorator for both async and sync functions, with configurable retries, delays, and specific exception handling.
-   **`utils/secure_config.py`**: More robust loading of configurations from YAML/JSON files, `.env` files, and environment variables, with clear precedence and support for environment-specific files (e.g., `config/development.yaml`).

## Using the Dashboard

If started with the `--dashboard` flag, the web dashboard provides a UI for:

-   **Access**: Typically `http://localhost:5001`.
-   **Features**: View available nodes (including the new `JsonTransformerNode`), workflow definitions, execution history, and logs.

## Logging

-   **Structured Logging**: Uses the enhanced `logging_manager.py` for structured JSON logs.
-   **Log Output**: Console and rotating files in `logs/`.
-   **Configuration**: Customizable in main config files (e.g., `config/development.yaml` under `logging`).

## Testing

The `/tests` directory is structured for unit and integration tests. (Test implementation is ongoing).

## Contributing

(Guidelines for contributing to be added if this were an open project.)

## Future Enhancements

-   AI-driven workflow generation and optimization.
-   More sophisticated `AuthManager` with integration for external secret stores.
-   Advanced scheduling and triggering options for workflows.
-   Real-time progress updates in the dashboard via WebSockets.
-   Plugin system for extending platform capabilities beyond nodes.
-   Comprehensive test suite.

---

This README provides a comprehensive guide to understanding, setting up, and using the API Integration Platform. For enterprise deployment, ensure all configurations, especially security and logging, are reviewed and hardened according to your organization's policies.

