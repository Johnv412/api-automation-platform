"""
Retry Mechanism

This module provides a decorator for implementing retry logic with exponential backoff.
"""

import asyncio
import functools
import logging
import random
import time
from typing import Any, Callable, Optional, Tuple, Type, Union

logger = logging.getLogger(__name__)


def retry_with_backoff(max_retries: int = None, 
                      base_delay: float = None,
                      max_delay: float = None,
                      retry_on: Tuple[Type[Exception], ...] = None,
                      retry_if: Callable[[Exception], bool] = None):
    """
    Decorator for retrying a function with exponential backoff.
    
    Args:
        max_retries: Maximum number of retries (default: from instance or 3)
        base_delay: Base delay in seconds (default: from instance or 1)
        max_delay: Maximum delay in seconds (default: from instance or 10)
        retry_on: Exception types to retry on (default: from instance or (Exception,))
        retry_if: Function to determine if retry should be attempted (default: None)
    
    Returns:
        Decorated function
    
    Example:
        @retry_with_backoff(max_retries=5, base_delay=0.5, max_delay=30)
        async def fetch_data():
            # Function implementation
    """
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(self, *args, **kwargs):
            # Get retry configuration from instance if available
            instance_config = getattr(self, "retry_config", {}) if hasattr(self, "retry_config") else {}
            
            # Use provided values or fall back to instance values or defaults
            retries = max_retries if max_retries is not None else instance_config.get("max_retries", 3)
            delay = base_delay if base_delay is not None else instance_config.get("base_delay", 1)
            max_wait = max_delay if max_delay is not None else instance_config.get("max_delay", 10)
            exceptions = retry_on if retry_on is not None else instance_config.get("retry_on_exceptions", (Exception,))
            
            # Convert single exception to tuple
            if not isinstance(exceptions, tuple):
                exceptions = (exceptions,)
            
            # Initialize attempt counter
            attempt = 0
            
            while True:
                try:
                    return await func(self, *args, **kwargs)
                    
                except exceptions as e:
                    attempt += 1
                    
                    # Check if we should retry
                    should_retry = attempt < retries
                    
                    # If a retry condition function is provided, check it
                    if should_retry and retry_if is not None:
                        should_retry = retry_if(e)
                    
                    if not should_retry:
                        logger.warning(f"Retry limit reached ({attempt}/{retries}) for {func.__name__}")
                        raise
                    
                    # Calculate backoff delay with jitter
                    wait = min(max_wait, delay * (2 ** (attempt - 1)))
                    jitter = random.uniform(0.8, 1.2)
                    wait = wait * jitter
                    
                    logger.info(f"Retrying {func.__name__} after error: {str(e)} (attempt {attempt}/{retries}, waiting {wait:.2f}s)")
                    
                    # Wait before retrying
                    await asyncio.sleep(wait)
        
        @functools.wraps(func)
        def sync_wrapper(self, *args, **kwargs):
            # Get retry configuration from instance if available
            instance_config = getattr(self, "retry_config", {}) if hasattr(self, "retry_config") else {}
            
            # Use provided values or fall back to instance values or defaults
            retries = max_retries if max_retries is not None else instance_config.get("max_retries", 3)
            delay = base_delay if base_delay is not None else instance_config.get("base_delay", 1)
            max_wait = max_delay if max_delay is not None else instance_config.get("max_delay", 10)
            exceptions = retry_on if retry_on is not None else instance_config.get("retry_on_exceptions", (Exception,))
            
            # Convert single exception to tuple
            if not isinstance(exceptions, tuple):
                exceptions = (exceptions,)
            
            # Initialize attempt counter
            attempt = 0
            
            while True:
                try:
                    return func(self, *args, **kwargs)
                    
                except exceptions as e:
                    attempt += 1
                    
                    # Check if we should retry
                    should_retry = attempt < retries
                    
                    # If a retry condition function is provided, check it
                    if should_retry and retry_if is not None:
                        should_retry = retry_if(e)
                    
                    if not should_retry:
                        logger.warning(f"Retry limit reached ({attempt}/{retries}) for {func.__name__}")
                        raise
                    
                    # Calculate backoff delay with jitter
                    wait = min(max_wait, delay * (2 ** (attempt - 1)))
                    jitter = random.uniform(0.8, 1.2)
                    wait = wait * jitter
                    
                    logger.info(f"Retrying {func.__name__} after error: {str(e)} (attempt {attempt}/{retries}, waiting {wait:.2f}s)")
                    
                    # Wait before retrying
                    time.sleep(wait)
        
        # Choose the appropriate wrapper based on the decorated function
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

