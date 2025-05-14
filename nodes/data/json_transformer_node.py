"""
JSON Transformer Node

This module provides a node for transforming JSON data using JSONPath expressions
and custom transformation logic.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Union

import jsonpath_ng
import jsonpath_ng.ext as jsonpath
from core.node_base import NodeBase, NodeStatus

logger = logging.getLogger(__name__)


class JsonTransformerNode(NodeBase):
    """
    Node for transforming JSON data using JSONPath and custom transformations.
    
    This node allows:
    - Extracting specific values using JSONPath expressions
    - Mapping values from one structure to another
    - Filtering arrays based on conditions
    - Applying custom transformations (e.g., format dates, calculate values)
    - Combining multiple JSON objects
    """
    
    def __init__(self, node_id: str = None, name: str = None, description: str = None):
        """
        Initialize JSON transformer node.
        
        Args:
            node_id: Unique identifier for the node
            name: Human-readable name for the node
            description: Description of what the node does
        """
        super().__init__(node_id, name, description)
        
        # Compiled JSONPath expressions
        self.compiled_expressions = {}
    
    def _validate_config(self, config: Dict[str, Any]) -> None:
        """
        Validate node configuration.
        
        Args:
            config: Configuration dictionary
        
        Raises:
            ValueError: If configuration is invalid
        """
        # At least one of these configurations must be present
        if not any([
            'mappings' in config,
            'transforms' in config,
            'filter' in config,
            'combine' in config,
            'script' in config
        ]):
            raise ValueError("At least one transformation type (mappings, transforms, filter, combine, or script) must be configured")
        
        # Validate mappings if provided
        if 'mappings' in config:
            mappings = config['mappings']
            if not isinstance(mappings, dict):
                raise ValueError("Mappings must be an object mapping output keys to JSONPath expressions")
            
            # Pre-compile expressions for better performance
            for key, expr in mappings.items():
                try:
                    self.compiled_expressions[key] = jsonpath.parse(expr)
                except Exception as e:
                    raise ValueError(f"Invalid JSONPath expression for key '{key}': {str(e)}")
        
        # Validate transforms if provided
        if 'transforms' in config:
            transforms = config['transforms']
            if not isinstance(transforms, list):
                raise ValueError("Transforms must be an array of transformation objects")
            
            for i, transform in enumerate(transforms):
                if not isinstance(transform, dict):
                    raise ValueError(f"Transform at index {i} must be an object")
                
                if 'source' not in transform:
                    raise ValueError(f"Transform at index {i} is missing 'source' JSONPath expression")
                
                if 'target' not in transform:
                    raise ValueError(f"Transform at index {i} is missing 'target' key")
                
                # Validate operation
                operation = transform.get('operation')
                if operation and operation not in (
                    'toString', 'toNumber', 'toBoolean', 'toDate', 
                    'concat', 'slice', 'split', 'join', 'replace',
                    'add', 'subtract', 'multiply', 'divide', 'round', 'format',
                    'length', 'lowercase', 'uppercase', 'capitalize', 'trim'
                ):
                    raise ValueError(f"Invalid operation '{operation}' in transform at index {i}")
                
                # Pre-compile source expression
                try:
                    expr_key = f"transform_{i}_source"
                    self.compiled_expressions[expr_key] = jsonpath.parse(transform['source'])
                except Exception as e:
                    raise ValueError(f"Invalid source JSONPath expression in transform at index {i}: {str(e)}")
        
        # Validate filter if provided
        if 'filter' in config:
            filter_config = config['filter']
            if not isinstance(filter_config, dict):
                raise ValueError("Filter must be an object")
            
            if 'path' not in filter_config:
                raise ValueError("Filter is missing 'path' JSONPath expression pointing to array")
            
            if 'conditions' not in filter_config or not isinstance(filter_config['conditions'], list):
                raise ValueError("Filter is missing 'conditions' array")
            
            # Pre-compile path expression
            try:
                self.compiled_expressions['filter_path'] = jsonpath.parse(filter_config['path'])
            except Exception as e:
                raise ValueError(f"Invalid path JSONPath expression in filter: {str(e)}")
            
            # Validate conditions
            for i, condition in enumerate(filter_config['conditions']):
                if not isinstance(condition, dict):
                    raise ValueError(f"Condition at index {i} must be an object")
                
                if 'field' not in condition:
                    raise ValueError(f"Condition at index {i} is missing 'field'")
                
                if 'operator' not in condition:
                    raise ValueError(f"Condition at index {i} is missing 'operator'")
                
                if 'value' not in condition:
                    raise ValueError(f"Condition at index {i} is missing 'value'")
                
                operator = condition['operator']
                if operator not in (
                    'eq', 'ne', 'gt', 'lt', 'gte', 'lte', 
                    'contains', 'startsWith', 'endsWith', 'matches'
                ):
                    raise ValueError(f"Invalid operator '{operator}' in condition at index {i}")
        
        # Validate script if provided
        if 'script' in config:
            script = config['script']
            if not isinstance(script, str):
                raise ValueError("Script must be a string containing transformation code")
    
    async def _execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the JSON transformation.
        
        Args:
            input_data: Input data to transform
        
        Returns:
            Transformed output data
        """
        # Get JSON data from input
        json_data = input_data.get('data', {})
        
        # If input_data has a specific source key defined, use that instead
        source_key = self.config.get('source_key')
        if source_key and source_key in input_data:
            json_data = input_data[source_key]
        
        logger.debug(f"Executing JSON transformation on input data")
        
        # Perform transformations
        result = {}
        
        # Apply mappings
        if 'mappings' in self.config:
            result.update(self._apply_mappings(json_data))
        
        # Apply transforms
        if 'transforms' in self.config:
            result.update(self._apply_transforms(json_data))
        
        # Apply filter
        if 'filter' in self.config:
            result['filtered'] = self._apply_filter(json_data)
        
        # Apply combination
        if 'combine' in self.config:
            result.update(self._apply_combine(input_data))
        
        # Apply custom script
        if 'script' in self.config:
            script_result = self._apply_script(json_data, input_data)
            
            # If script returns a dict, merge it with results
            if isinstance(script_result, dict):
                result.update(script_result)
            else:
                # Otherwise store it under 'script_result' key
                result['script_result'] = script_result
        
        # If no transformations were applied, return original data
        if not result:
            result = json_data
        
        return result
    
    def _apply_mappings(self, json_data: Any) -> Dict[str, Any]:
        """
        Apply JSONPath mappings to extract values from input data.
        
        Args:
            json_data: Input data to transform
        
        Returns:
            Dictionary with extracted values
        """
        result = {}
        mappings = self.config['mappings']
        
        for output_key, expr in mappings.items():
            try:
                # Use pre-compiled expression if available
                compiled_expr = self.compiled_expressions.get(output_key)
                if not compiled_expr:
                    compiled_expr = jsonpath.parse(expr)
                
                # Find all matches
                matches = [match.value for match in compiled_expr.find(json_data)]
                
                # Assign based on number of matches
                if not matches:
                    result[output_key] = None
                elif len(matches) == 1:
                    result[output_key] = matches[0]
                else:
                    result[output_key] = matches
                    
            except Exception as e:
                logger.warning(f"Error applying mapping for key '{output_key}': {str(e)}")
                result[output_key] = None
        
        return result
    
    def _apply_transforms(self, json_data: Any) -> Dict[str, Any]:
        """
        Apply transformation operations on extracted values.
        
        Args:
            json_data: Input data to transform
        
        Returns:
            Dictionary with transformed values
        """
        result = {}
        transforms = self.config['transforms']
        
        for i, transform in enumerate(transforms):
            try:
                # Extract value using JSONPath
                expr_key = f"transform_{i}_source"
                compiled_expr = self.compiled_expressions.get(expr_key)
                if not compiled_expr:
                    compiled_expr = jsonpath.parse(transform['source'])
                
                matches = [match.value for match in compiled_expr.find(json_data)]
                value = matches[0] if matches else None
                
                # Apply operation if specified
                operation = transform.get('operation')
                if operation and value is not None:
                    params = transform.get('params', {})
                    value = self._apply_operation(operation, value, params)
                
                # Store result
                result[transform['target']] = value
                
            except Exception as e:
                logger.warning(f"Error applying transform at index {i}: {str(e)}")
                result[transform['target']] = None
        
        return result
    
    def _apply_filter(self, json_data: Any) -> List[Any]:
        """
        Filter array values based on conditions.
        
        Args:
            json_data: Input data containing array to filter
        
        Returns:
            Filtered array
        """
        filter_config = self.config['filter']
        
        try:
            # Get array using JSONPath
            compiled_expr = self.compiled_expressions.get('filter_path')
            if not compiled_expr:
                compiled_expr = jsonpath.parse(filter_config['path'])
            
            matches = [match.value for match in compiled_expr.find(json_data)]
            
            if not matches:
                return []
            
            # Get first match (should be an array)
            array = matches[0]
            if not isinstance(array, list):
                logger.warning(f"Filter path does not point to an array")
                return []
            
            # Apply filter conditions
            conditions = filter_config['conditions']
            filtered = []
            
            for item in array:
                if self._check_conditions(item, conditions):
                    filtered.append(item)
            
            return filtered
            
        except Exception as e:
            logger.warning(f"Error applying filter: {str(e)}")
            return []
    
    def _apply_combine(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Combine multiple JSON objects.
        
        Args:
            input_data: Input data containing objects to combine
        
        Returns:
            Combined object
        """
        combine_config = self.config['combine']
        result = {}
        
        try:
            # Get sources to combine
            sources = combine_config.get('sources', [])
            
            for source in sources:
                # Get source object
                source_key = source.get('key')
                prefix = source.get('prefix', '')
                
                if source_key in input_data:
                    source_data = input_data[source_key]
                    
                    if isinstance(source_data, dict):
                        # Add prefix to keys if specified
                        if prefix:
                            for key, value in source_data.items():
                                result[f"{prefix}{key}"] = value
                        else:
                            # Merge directly
                            result.update(source_data)
            
            return result
            
        except Exception as e:
            logger.warning(f"Error applying combine: {str(e)}")
            return result
    
    def _apply_script(self, json_data: Any, full_input: Dict[str, Any]) -> Any:
        """
        Apply custom transformation script.
        
        Args:
            json_data: Primary input data to transform
            full_input: Full input data object
        
        Returns:
            Script execution result
        """
        script = self.config['script']
        
        try:
            # Create a safe execution environment
            globals_dict = {
                'input_data': json_data,
                'full_input': full_input,
                'result': {}
            }
            
            # Add safe libraries for data manipulation
            import datetime
            import re
            import math
            
            globals_dict.update({
                'datetime': datetime,
                're': re,
                'math': math,
                'json': json
            })
            
            # Execute script
            exec(script, globals_dict)
            
            # Return result
            return globals_dict.get('result', {})
            
        except Exception as e:
            logger.warning(f"Error executing transformation script: {str(e)}")
            return {'error': str(e)}
    
    def _apply_operation(self, operation: str, value: Any, params: Dict[str, Any]) -> Any:
        """
        Apply transformation operation.
        
        Args:
            operation: Operation to apply
            value: Value to transform
            params: Operation parameters
        
        Returns:
            Transformed value
        """
        # String operations
        if operation == 'toString':
            return str(value)
            
        elif operation == 'toNumber':
            try:
                return float(value)
            except (ValueError, TypeError):
                return 0
                
        elif operation == 'toBoolean':
            if isinstance(value, str):
                return value.lower() in ('true', 'yes', '1', 'y')
            return bool(value)
            
        elif operation == 'toDate':
            try:
                import datetime
                format_str = params.get('format', '%Y-%m-%dT%H:%M:%S.%fZ')
                if isinstance(value, str):
                    return datetime.datetime.strptime(value, format_str).isoformat()
                return None
            except Exception:
                return None
                
        elif operation == 'concat':
            prefix = params.get('prefix', '')
            suffix = params.get('suffix', '')
            return f"{prefix}{value}{suffix}"
            
        elif operation == 'slice':
            start = params.get('start', 0)
            end = params.get('end', None)
            if isinstance(value, str) or isinstance(value, list):
                return value[start:end]
            return value
            
        elif operation == 'split':
            if isinstance(value, str):
                delimiter = params.get('delimiter', ',')
                return value.split(delimiter)
            return [value]
            
        elif operation == 'join':
            if isinstance(value, list):
                delimiter = params.get('delimiter', ',')
                return delimiter.join(str(item) for item in value)
            return str(value)
            
        elif operation == 'replace':
            if isinstance(value, str):
                pattern = params.get('pattern', '')
                replacement = params.get('replacement', '')
                return value.replace(pattern, replacement)
            return value
            
        # Math operations
        elif operation == 'add':
            try:
                operand = float(params.get('value', 0))
                return float(value) + operand
            except (ValueError, TypeError):
                return value
                
        elif operation == 'subtract':
            try:
                operand = float(params.get('value', 0))
                return float(value) - operand
            except (ValueError, TypeError):
                return value
                
        elif operation == 'multiply':
            try:
                operand = float(params.get('value', 1))
                return float(value) * operand
            except (ValueError, TypeError):
                return value
                
        elif operation == 'divide':
            try:
                operand = float(params.get('value', 1))
                if operand == 0:
                    return value
                return float(value) / operand
            except (ValueError, TypeError):
                return value
                
        elif operation == 'round':
            try:
                precision = int(params.get('precision', 0))
                return round(float(value), precision)
            except (ValueError, TypeError):
                return value
                
        elif operation == 'format':
            try:
                format_str = params.get('format', '{0}')
                if isinstance(value, (int, float)):
                    return format_str.format(value)
                return value
            except (ValueError, TypeError):
                return value
                
        # Utility operations
        elif operation == 'length':
            if isinstance(value, (str, list, dict)):
                return len(value)
            return 0
            
        elif operation == 'lowercase':
            if isinstance(value, str):
                return value.lower()
            return value
            
        elif operation == 'uppercase':
            if isinstance(value, str):
                return value.upper()
            return value
            
        elif operation == 'capitalize':
            if isinstance(value, str):
                return value.capitalize()
            return value
            
        elif operation == 'trim':
            if isinstance(value, str):
                return value.strip()
            return value
            
        # Default: return value unchanged
        return value
    
    def _check_conditions(self, item: Any, conditions: List[Dict[str, Any]]) -> bool:
        """
        Check if an item matches all filter conditions.
        
        Args:
            item: Item to check
            conditions: List of conditions to apply
        
        Returns:
            True if item matches all conditions, False otherwise
        """
        # For non-dict items, convert to dict with value key
        if not isinstance(item, dict):
            item = {'value': item}
        
        # Check each condition
        for condition in conditions:
            field = condition['field']
            operator = condition['operator']
            expected = condition['value']
            
            # Get field value
            if field in item:
                actual = item[field]
            else:
                # Try to access nested properties
                parts = field.split('.')
                current = item
                for part in parts:
                    if isinstance(current, dict) and part in current:
                        current = current[part]
                    else:
                        current = None
                        break
                actual = current
            
            # Check condition
            if not self._check_condition(actual, operator, expected):
                return False
        
        # All conditions passed
        return True
    
    def _check_condition(self, actual: Any, operator: str, expected: Any) -> bool:
        """
        Check if a value matches a condition.
        
        Args:
            actual: Actual value
            operator: Comparison operator
            expected: Expected value
        
        Returns:
            True if condition is satisfied, False otherwise
        """
        # Handle None values
        if actual is None:
            if operator == 'eq':
                return expected is None
            elif operator == 'ne':
                return expected is not None
            return False
        
        # Equality operators
        if operator == 'eq':
            return actual == expected
        elif operator == 'ne':
            return actual != expected
        
        # Numeric operators
        elif operator in ('gt', 'lt', 'gte', 'lte'):
            try:
                num_actual = float(actual)
                num_expected = float(expected)
                
                if operator == 'gt':
                    return num_actual > num_expected
                elif operator == 'lt':
                    return num_actual < num_expected
                elif operator == 'gte':
                    return num_actual >= num_expected
                elif operator == 'lte':
                    return num_actual <= num_expected
            except (ValueError, TypeError):
                return False
        
        # String operators
        elif operator in ('contains', 'startsWith', 'endsWith', 'matches'):
            # Convert both to strings
            str_actual = str(actual).lower()
            str_expected = str(expected).lower()
            
            if operator == 'contains':
                return str_expected in str_actual
            elif operator == 'startsWith':
                return str_actual.startswith(str_expected)
            elif operator == 'endsWith':
                return str_actual.endswith(str_expected)
            elif operator == 'matches':
                import re
                try:
                    pattern = re.compile(str_expected, re.IGNORECASE)
                    return bool(pattern.search(str_actual))
                except re.error:
                    return False
        
        # Default: condition not satisfied
        return False
    
    def _get_input_schema(self) -> Dict[str, Any]:
        """
        Get the JSON schema for this node's inputs.
        
        Returns:
            Input schema
        """
        return {
            "type": "object",
            "properties": {
                "data": {
                    "type": ["object", "array"],
                    "description": "JSON data to transform"
                }
            }
        }
    
    def _get_output_schema(self) -> Dict[str, Any]:
        """
        Get the JSON schema for this node's outputs.
        
        Returns:
            Output schema
        """
        return {
            "type": "object",
            "description": "Transformed JSON data"
        }
    
    def _get_config_schema(self) -> Dict[str, Any]:
        """
        Get the JSON schema for this node's configuration.
        
        Returns:
            Configuration schema
        """
        return {
            "type": "object",
            "properties": {
                "source_key": {
                    "type": "string",
                    "description": "Key in input data that contains the JSON to transform"
                },
                "mappings": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "string",
                        "description": "JSONPath expression"
                    },
                    "description": "Mapping of output keys to JSONPath expressions"
                },
                "transforms": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["source", "target"],
                        "properties": {
                            "source": {
                                "type": "string",
                                "description": "JSONPath expression to extract value"
                            },
                            "target": {
                                "type": "string",
                                "description": "Output key for transformed value"
                            },
                            "operation": {
                                "type": "string",
                                "enum": [
                                    "toString", "toNumber", "toBoolean", "toDate",
                                    "concat", "slice", "split", "join", "replace",
                                    "add", "subtract", "multiply", "divide", "round", "format",
                                    "length", "lowercase", "uppercase", "capitalize", "trim"
                                ],
                                "description": "Transformation operation"
                            },
                            "params": {
                                "type": "object",
                                "description": "Operation parameters"
                            }
                        }
                    },
                    "description": "List of transformation operations"
                },
                "filter": {
                    "type": "object",
                    "required": ["path", "conditions"],
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "JSONPath expression pointing to array to filter"
                        },
                        "conditions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["field", "operator", "value"],
                                "properties": {
                                    "field": {
                                        "type": "string",
                                        "description": "Field to check"
                                    },
                                    "operator": {
                                        "type": "string",
                                        "enum": [
                                            "eq", "ne", "gt", "lt", "gte", "lte",
                                            "contains", "startsWith", "endsWith", "matches"
                                        ],
                                        "description": "Comparison operator"
                                    },
                                    "value": {
                                        "description": "Value to compare against"
                                    }
                                }
                            },
                            "description": "Filter conditions"
                        }
                    },
                    "description": "Array filtering configuration"
                },
                "combine": {
                    "type": "object",
                    "required": ["sources"],
                    "properties": {
                        "sources": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["key"],
                                "properties": {
                                    "key": {
                                        "type": "string",
                                        "description": "Key in input data containing source object"
                                    },
                                    "prefix": {
                                        "type": "string",
                                        "description": "Prefix to add to keys from this source"
                                    }
                                }
                            },
                            "description": "Source objects to combine"
                        }
                    },
                    "description": "Object combination configuration"
                },
                "script": {
                    "type": "string",
                    "description": "Custom Python script for transformation"
                }
            }
        }

