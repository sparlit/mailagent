import logging
from logging.handlers import RotatingFileHandler
import sys

def setup_logging(log_file='mailagent.log'):
    """
    Configure the root logger to output INFO-level logs to stdout and to a rotating log file.
    
    Parameters:
        log_file (str): Path to the rotating log file (default 'mailagent.log').
    
    Returns:
        logging.Logger: The configured root logger.
    """
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Rotating File handler
    file_handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
