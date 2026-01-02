"""
Logging utilities for the LTRC Manager API.

This module provides centralized logging configuration and utilities.
"""

import logging
import sys
from typing import Optional

def setup_logging(level: Optional[str] = None) -> logging.Logger:
    """
    Set up logging configuration.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        
    Returns:
        Configured logger instance
    """
    if level is None:
        level = "INFO"
    
    # Configure logging format
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Set up basic configuration
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("ltrc_manager.log")
        ]
    )
    
    # Create and return logger
    logger = logging.getLogger("ltrc_manager")
    logger.info(f"Logging initialized at {level.upper()} level")
    
    return logger

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name.
    
    Args:
        name: Logger name
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)
