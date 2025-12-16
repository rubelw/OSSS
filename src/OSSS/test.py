#!/usr/bin/env python3

import os
import re
import logging

# Set up logging configuration
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Directory where LangChain agent files are stored
AGENTS_DIR = "./ai/langchain/agents"

# Regular expression for identifying *_table.py files
TABLE_FILE_PATTERN = re.compile(r".*_table\.py$")

# Code to replace the query_data logic with LangChain registry

def process_file(file_path: str):
    """Processes a single *_table.py file to update it."""
    logger.info(f"Processing file: {file_path}")

    with open(file_path, 'r') as file:
        code = file.read()

    logger.debug("Original code read from file.")

    # Ensure 'from __future__ import annotations' is at the top of the file
    future_import_match = re.search(r'from __future__ import annotations', code)
    if future_import_match:
        logger.info("'from __future__ import annotations' found, moving to the top of the file.")
        code = re.sub(r'from __future__ import annotations', '', code)  # Remove the existing one
        code = "from __future__ import annotations\n" + code  # Add it at the top

    # Remove any potential non-future import that might be before 'from __future__'
    if code.startswith("from __future__ import annotations"):
        code = "from __future__ import annotations\n" + code[len("from __future__ import annotations\n"):]

    # Check if the file uses 'query_data_registry' and remove those imports
    if 'from .query_data.query_data_registry' in code:
        logger.info("Removing 'query_data_registry' import.")
    code = re.sub(r'from .query_data.query_data_registry import .+', '', code)

    # Remove all functions or classes related to query_data registry
    query_data_functions = re.findall(r'(?<=\n)\s*def\s.*?query_data.*\n', code)
    if query_data_functions:
        logger.info(f"Removing {len(query_data_functions)} query_data-related function(s).")
    code = re.sub(r'(?<=\n)\s*def\s.*?query_data.*\n', '', code)

    # Replace the handler fetching logic
    if 'get_handler("addresses")' in code:
        logger.info("Disabling 'get_handler(\"addresses\")' call.")
    code = re.sub(r'get_handler\("addresses"\)', 'None', code)  # Disable handler fetch

    # Look for the registration section and replace query_data registration
    if 'register_handler' in code:
        logger.info("Replacing 'register_handler' with 'register_agent(AddressesTableAgent())'.")
    code = re.sub(r'(register_handler\([^\)]+\))', 'register_agent(AddressesTableAgent())', code)

    # Add the import for langchain registry if it's missing
    if "from OSSS.ai.langchain.registry import register_agent" not in code:
        logger.info("Adding missing import for 'register_agent' from langchain.registry.")
        code = "from OSSS.ai.langchain.registry import register_agent\n" + code

    # Save the modified code back to the file
    with open(file_path, 'w') as file:
        file.write(code)
    logger.info(f"Processed file: {file_path}")


def update_agents_directory(agents_dir: str):
    """Iterate through all files in the langchain/agents directory and update *_table.py files recursively."""
    logger.info(f"Starting to process files in directory: {agents_dir}")
    for root, dirs, files in os.walk(agents_dir):
        logger.debug(f"Checking directory: {root}")
        for file in files:
            if TABLE_FILE_PATTERN.match(file):
                file_path = os.path.join(root, file)
                process_file(file_path)


if __name__ == "__main__":
    # Update the *_table.py files in the agents directory
    logger.info("Script execution started.")
    update_agents_directory(AGENTS_DIR)
    logger.info("Finished processing all *_table.py files.")
