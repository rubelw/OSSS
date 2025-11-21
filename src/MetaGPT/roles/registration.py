from __future__ import annotations
import os
from typing import List, Dict, Any
from metagpt.roles import Role
from metagpt.logs import logger
from .rag.jsonl_retriever import JsonlRagRetriever
from .llm.ollama_client import OllamaChatClient

class RegistrationRole(Role):
    """
    Registration Role for handling user registration and goal setting.
    """

    name: str = "registration"

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

        # Initialize Ollama config
        base_url = os.getenv("OLLAMA_BASE_URL", "http://host.containers.internal:11434")
        model = os.getenv("OLLAMA_MODEL", "llama3.2")

        logger.info(
            "RegistrationRole initializing with Ollama base_url=%s model=%s",
            base_url,
            model,
        )

        self.llm = OllamaChatClient(
            base_url=base_url,
            model=model,
        )

        # RAG index location
        index_path = os.getenv(
            "RAG_INDEX_PATH",
            "/vector_indexes/main/embeddings.jsonl",
        )

        # Initialize session tracking
        self.sessions = {}

        self.retriever = JsonlRagRetriever(index_path=index_path)

    async def run(self, *args: Any, **kwargs: Any) -> str:
        """
        Entry point used by metagpt_server /run.
        Walk the requestor through the registration process, including document uploads.
        """
        logger.info("RegistrationRole.run starting...")

        # Extract the query, session_id, intent, and context_id from kwargs or args
        query = kwargs.get("query") or (args[0] if args else "")
        session_id = kwargs.get("context_id")  # Track session to persist responses
        intent = kwargs.get("intent", "register_new_student")  # Default to register_new_student if not provided
        context_id = kwargs.get("context_id")  # Make sure context_id is retrieved

        logger.debug("Received query: %s", query)
        logger.info(f"Processing with intent: {intent}, context_id: {context_id}")

        # Initialize user session if not provided
        if session_id not in self.sessions:
            self.sessions[session_id] = {}
            logger.info("Created new session for user %s", session_id)

        user_data = self.sessions[session_id]  # Track user responses during session

        # Ensure the intent is set to register_new_student at the start
        if "intent" not in user_data:
            user_data["intent"] = "register_new_student"  # Set intent for new student registration
            logger.info("Intent set to 'register_new_student'")

        if not query:
            # Fallback message
            query = "Help me register a new student with the school district."
            logger.warning("No query provided. Using default query: %s", query)

        # Step 1: Ask for the student's name
        if "name" not in user_data:
            user_data["intent"] = intent  # Set the dynamic intent here
            prompt = "Please provide the student's full name."
            user_data["name"] = query
            logger.info("Prompting user for student's name.")
            return prompt

        # Step 2: Ask for the student's grade level
        if "grade" not in user_data:
            user_data["intent"] = intent  # Set the dynamic intent here
            prompt = f"Thank you, {user_data['name']}. What grade is the student going into?"
            user_data["grade"] = query
            logger.info("Prompting user for student's grade.")
            return prompt

        # Step 3: Ask for the student's date of birth
        if "dob" not in user_data:
            user_data["intent"] = intent  # Set the dynamic intent here
            prompt = "Please provide the student's date of birth (e.g., 2008-05-20)."
            user_data["dob"] = query
            logger.info("Prompting user for student's date of birth.")
            return prompt

        # Step 4: Ask for the student's address
        if "address" not in user_data:
            user_data["intent"] = intent  # Set the dynamic intent here
            prompt = "Please provide the student's address."
            user_data["address"] = query
            logger.info("Prompting user for student's address.")
            return prompt

        # Step 5: Ask for the parent's/guardian's contact information
        if "parent_contact" not in user_data:
            user_data["intent"] = intent  # Set the dynamic intent here
            prompt = "Please provide the parent's/guardian's contact information."
            user_data["parent_contact"] = query
            logger.info("Prompting user for parent's contact information.")
            return prompt

        # Step 6: Ask the user to upload required forms
        if "forms_uploaded" not in user_data:
            user_data["intent"] = intent  # Set the dynamic intent here
            prompt = (
                "To complete the registration for John Doe, please upload the following documents:\n"
                "1. Proof of residency (utility bill, lease agreement, etc.)\n"
                "2. Immunization records\n"
                "3. Birth certificate\n"
                "4. Any other documents required by the district\n\n"
                "Please upload the required documents, or provide confirmation when ready."
            )
            user_data["forms_uploaded"] = False  # Initial state for forms
            logger.info("Prompting user to upload required forms.")
            return prompt

        # Step 7: Confirm uploaded documents and proceed
        if "forms_uploaded" in user_data and user_data["forms_uploaded"] is False:
            user_data["intent"] = intent  # Set the dynamic intent here
            prompt = (
                "We received your uploaded documents. Please confirm if all the necessary forms have been uploaded.\n"
                "Once confirmed, we will proceed with the registration process."
            )
            logger.info("Waiting for confirmation of uploaded forms.")
            return prompt

        # Step 8: Final confirmation and completing registration
        if "confirmation" not in user_data:
            user_data["intent"] = intent  # Set the dynamic intent here
            confirmation = (
                f"Thank you for providing the information. Here is a summary of the registration details:\n"
                f"Student's Name: {user_data['name']}\n"
                f"Grade: {user_data['grade']}\n"
                f"Date of Birth: {user_data['dob']}\n"
                f"Address: {user_data['address']}\n"
                f"Parent/Guardian Contact: {user_data['parent_contact']}\n\n"
                "Is this information correct? (Yes/No)"
            )
            user_data["confirmation"] = query.strip().lower()
            logger.info("Prompting user to confirm details.")
            return confirmation

        # If user confirms, finalize registration
        if "confirmation" in user_data:
            confirmation_response = query.strip().lower()
            if confirmation_response == "yes":
                user_data["intent"] = intent  # Set the dynamic intent here
                logger.info("User confirmed the details; completing registration.")
                return f"Registration complete! Thank you for registering {user_data['name']}."
            else:
                user_data["intent"] = intent  # Set the dynamic intent here
                logger.info("User did not confirm; restarting registration process.")
                return "Let's start the registration again. Please provide the student's name."

        # If everything is complete, return a failure message
        return "Something went wrong during the registration process."

    def perform_action(self, action_data: Dict[str, Any]) -> str:
        """
        This method triggers the registration action.

        It could interact with a database or API to register a new user or process
        a registration request. For now, we simulate it by returning a success message.
        """

        # For demonstration purposes, we will just log the registration action
        logger.info(f"Performing registration with data: {action_data}")

        # Simulate registration logic, for example, calling an API or database insert
        # In a real scenario, you would interact with your database or API here
        registration_result = f"Successfully registered {action_data.get('user_name', 'unknown user')}."

        return registration_result