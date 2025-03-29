import logging
import os

# Create a logs directory if it doesn't exist
log_dir = "/home/meetonweekend"
os.makedirs(log_dir, exist_ok=True)


def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)  # Set the logging level

    # Create a console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)  # Log level for console

    # Create a file handler
    file_handler = logging.FileHandler(os.path.join(log_dir, "app.log"))
    file_handler.setLevel(logging.DEBUG)  # Log level for file

    # Create a formatter and set it for both handlers
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    # Add the handlers to the logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
