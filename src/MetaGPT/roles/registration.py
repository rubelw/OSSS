from __future__ import annotations
import os
from typing import Dict, Any
from metagpt.roles import Role
from metagpt.logs import logger
from .rag.jsonl_retriever import JsonlRagRetriever
from .llm.ollama_client import OllamaChatClient


class RegistrationRole(Role):
    """
    Registration Role for handling user registration and goal setting.
    """

    name: str = "registration"
    agent_id: str = "registration-agent"
    agent_name: str = "Registration"

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
        self.sessions: Dict[str, Dict[str, Any]] = {}

        self.retriever = JsonlRagRetriever(index_path=index_path)

    async def run(self, *args: Any, **kwargs: Any) -> str:
        """
        MetaGPT entrypoint.

        IMPORTANT: this method should return a **plain string** which becomes
        `registration_run["output_preview"]`. The outer OSSS RAG router is
        responsible for wrapping that into:
          answer.message.content, intent, agent_id, agent_name, etc.
        """
        logger.info("RegistrationRole.run starting...")

        query = kwargs.get("query") or (args[0] if args else "")
        session_id = kwargs.get("context_id")
        intent = kwargs.get("intent", "register_new_student")
        context_id = kwargs.get("context_id")

        logger.debug("Received query: %s", query)
        logger.info("Processing with intent=%s context_id=%s", intent, context_id)

        if not session_id:
            # Simple guard: in your a2a call you should set context_id/agent_session_id
            session_id = "registration-session"
            logger.warning("No session_id/context_id provided. Using default=%s", session_id)

        # Initialize per-session state
        if session_id not in self.sessions:
            self.sessions[session_id] = {}
            logger.info("Created new session for user %s", session_id)

        user_data = self.sessions[session_id]

        if "intent" not in user_data:
            user_data["intent"] = "register_new_student"
            logger.info("Intent set to 'register_new_student'")

        if not query:
            query = "Help me register a new student with the school district."
            logger.warning("No query provided. Using default query: %s", query)

        # ---- STEP 1: student's name ----
        if "name" not in user_data:
            user_data["intent"] = intent
            prompt = "Please provide the student's full name."
            user_data["name"] = query
            logger.info("Prompting user for student's name.")
            return prompt

        # ---- STEP 2: grade ----
        if "grade" not in user_data:
            user_data["intent"] = intent
            prompt = f"Thank you, {user_data['name']}. What grade is the student going into?"
            user_data["grade"] = query
            logger.info("Prompting user for student's grade.")
            return prompt

        # ---- STEP 3: dob ----
        if "dob" not in user_data:
            user_data["intent"] = intent
            prompt = "Please provide the student's date of birth (e.g., 2008-05-20)."
            user_data["dob"] = query
            logger.info("Prompting user for student's date of birth.")
            return prompt

        # ---- STEP 4: address ----
        if "address" not in user_data:
            user_data["intent"] = intent
            prompt = "Please provide the student's address."
            user_data["address"] = query
            logger.info("Prompting user for student's address.")
            return prompt

        # ---- STEP 5: parent contact ----
        if "parent_contact" not in user_data:
            user_data["intent"] = intent
            prompt = "Please provide the parent's/guardian's contact information."
            user_data["parent_contact"] = query
            logger.info("Prompting user for parent's contact information.")
            return prompt

        # ---- STEP 6: upload forms ----
        if "forms_uploaded" not in user_data:
            user_data["intent"] = intent
            prompt = (
                f"To complete the registration for {user_data['name']}, please upload the following documents:\n"
                "1. Proof of residency (utility bill, lease agreement, etc.)\n"
                "2. Immunization records\n"
                "3. Birth certificate\n"
                "4. Any other documents required by the district\n\n"
                "Please upload the required documents, or provide confirmation when ready."
            )
            user_data["forms_uploaded"] = False
            logger.info("Prompting user to upload required forms.")
            return prompt

        # ---- STEP 7: confirm forms ----
        if user_data.get("forms_uploaded") is False:
            user_data["intent"] = intent
            prompt = (
                "We received your uploaded documents. Please confirm if all the necessary forms have been uploaded.\n"
                "Once confirmed, we will proceed with the registration process."
            )
            logger.info("Waiting for confirmation of uploaded forms.")
            return prompt

        # ---- STEP 8: summary / confirmation ----
        if "confirmation" not in user_data:
            user_data["intent"] = intent
            confirmation_text = (
                "Thank you for providing the information. Here is a summary of the registration details:\n"
                f"Student's Name: {user_data['name']}\n"
                f"Grade: {user_data['grade']}\n"
                f"Date of Birth: {user_data['dob']}\n"
                f"Address: {user_data['address']}\n"
                f"Parent/Guardian Contact: {user_data['parent_contact']}\n\n"
                "Is this information correct? (Yes/No)"
            )
            user_data["confirmation"] = query.strip().lower()
            logger.info("Prompting user to confirm details.")
            return confirmation_text

        # ---- Finalize / restart ----
        confirmation_response = query.strip().lower()
        if confirmation_response == "yes":
            user_data["intent"] = intent
            logger.info("User confirmed the details; completing registration.")
            final_text = (
                f"Registration complete! Thank you for registering {user_data['name']}."
            )
        else:
            user_data["intent"] = intent
            logger.info("User did not confirm; restarting registration process.")
            final_text = (
                "Let's start the registration again. Please provide the student's name."
            )

        return final_text

    def perform_action(self, action_data: Dict[str, Any]) -> str:
        """
        This method triggers the registration action.

        It could interact with a database or API to register a new user or process
        a registration request. For now, we simulate it by returning a success message.
        """
        logger.info("Performing registration with data: %s", action_data)
        return f"Successfully registered {action_data.get('user_name', 'unknown user')}."
