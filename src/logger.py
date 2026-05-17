import logging
from logging.handlers import RotatingFileHandler
import sys

def setup_logging(log_file='mailagent.log'):
    """
    Configure and return the root logger with a console and rotating file handler.
    
    Parameters:
        log_file (str): Path to the log file used by the rotating file handler (default: 'mailagent.log').
    
    Returns:
        logging.Logger: The configured root logger set to INFO with a timestamped formatter, a StreamHandler writing to stdout, and a RotatingFileHandler that rotates at 10 MB with up to 5 backups.
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
