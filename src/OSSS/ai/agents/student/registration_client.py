from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

# Dedicated logger for all outbound registration-service calls.
# This logger should give you a full trace of everything that leaves your system
# for the A2A registration endpoint — payloads, status codes, failures, retries, etc.
logger = logging.getLogger("OSSS.ai.agents.registration.client")


class RegistrationServiceClient:
    """
    Thin async HTTP wrapper for the A2A registration endpoint.

    Why this class exists
    ---------------------
    - We want the agent to stay focused on *intent, dialog, and state logic*.
    - We want the HTTP mechanics — retries, timeouts, serialization,
      logging, error handling — to be *separated out*.
    - This improves testability: the agent can be tested by injecting a mock
      client that simulates HTTP behavior without touching the network.
    - It also centralizes outbound HTTP behavior for future enhancements,
      such as:
          * retry/backoff
          * circuit breakers
          * signing or auth headers
          * tracing / OpenTelemetry
          * custom timeouts
          * pooling persistent client connections

    Architecture notes
    -------------------
    - The agent calls this client with a simple dict.
    - This client sends that to `POST /admin/registration`.
    - The caller receives an `httpx.Response` or an exception.
    - No parsing, interpretation, or normalization happens here — that stays
      inside the agent (`registration_agent.py`).

    Error philosophy
    ----------------
    - Network errors raise `httpx.HTTPError` (timeouts, refused connection).
    - HTTP 4xx/5xx raise `httpx.HTTPStatusError`.
    - Both are logged at ERROR level and re-raised.
    - Zero silent failures.
    """

    def __init__(self, base_url: str) -> None:
        """
        Initialize the client.

        Parameters
        ----------
        base_url : str
            Base URL of the A2A registration service.

            Examples
            --------
            - "http://a2a:8086" for Docker Compose
            - "http://a2a.default.svc.cluster.local:8086" for Kubernetes
            - "https://registration.schooldistrict.com" for production

        Why strip trailing slashes?
        ---------------------------
        - If the user accidentally passes "http://a2a:8086/",
          we don't want to create URLs like "/admin/registration" → double slashes.
        - `.rstrip("/")` ensures consistent and predictable URL joining.
        """
        if not base_url:
            raise ValueError("RegistrationServiceClient requires a non-empty base_url")

        # Normalize for safety: "https://example.com/" -> "https://example.com"
        self._base_url = base_url.rstrip("/")

        logger.debug(
            "[RegistrationServiceClient.__init__] Initialized client with base_url=%s",
            self._base_url,
        )

    # ------------------------------------------------------------------
    # register()
    # ------------------------------------------------------------------
    async def register(self, payload: Dict[str, Any]) -> httpx.Response:
        """
        Perform the registration POST request.

        Parameters
        ----------
        payload : Dict[str, Any]
            A JSON-serializable dictionary that fully describes the
            registration request your agent wishes to send.

        Returns
        -------
        httpx.Response
            The raw HTTP response (whether JSON, text, HTML, etc. — no assumptions).

        Raises (VERY important)
        -----------------------
        httpx.HTTPStatusError
            - If the HTTP response code is not 2xx.
            - This includes 400, 404, 500, etc.
            - The response body is included in the exception for debugging.

        httpx.HTTPError
            - For ANY network issues:
                * timeout
                * DNS failure
                * connection refused
                * early disconnect
                * SSL/TLS negotiation issues
            - These are NOT wrapped — the caller (your agent) must catch them.

        Logging
        -------
        INFO:
            - Logs the HTTP method + URL
            - Logs the response status code
        DEBUG:
            - Logs the payload being sent
            - Logs (truncated) response text for traceability
        ERROR:
            - Logs details about network errors and server-side failures

        Why return the raw httpx.Response?
        ----------------------------------
        - Parsing happens inside the agent, not here.
        - The agent may want to:
            * Inspect headers
            * Inspect raw bytes
            * Perform multi-step extraction
        - Keeping this layer "dumb" avoids mixing responsibilities.
        """
        # Construct full endpoint URL
        url = f"{self._base_url}/admin/registration"

        # Record the outbound attempt
        logger.info("[RegistrationServiceClient] POST %s", url)
        logger.debug("[RegistrationServiceClient] Payload: %s", payload)

        # Create a new AsyncClient for each call.
        # Pros:
        #   - Simple
        #   - No need to worry about reusing closed clients
        #   - Works perfectly for < a few hundred RPS
        # Cons:
        #   - Less efficient for very high-throughput workloads.
        #     (You can optimize later by injecting a persistent client.)
        async with httpx.AsyncClient(timeout=60) as client:
            try:
                resp = await client.post(url, json=payload)

            except httpx.HTTPError as e:
                # HTTPError includes:
                #   - Connection problems
                #   - Timeout
                #   - Invalid URL
                #   - TLS issues
                logger.error(
                    "[RegistrationServiceClient] Network/transport error during POST %s: %s",
                    url,
                    e,
                )
                raise  # rethrow to be handled by the agent

        # At this point, a network-level error did NOT occur.
        # Now we inspect HTTP status codes.

        logger.info("[RegistrationServiceClient] Response status=%s", resp.status_code)
        logger.debug(
            "[RegistrationServiceClient] Response text (truncated to 2000 chars): %s",
            resp.text[:2000],
        )

        # Let httpx raise for non-2xx responses.
        # You get an httpx.HTTPStatusError, which contains:
        #   - request
        #   - response
        #   - status code
        #   - full body (!!!)
        try:
            resp.raise_for_status()

        except httpx.HTTPStatusError as e:
            # Before rethrowing, log useful debugging info including status code
            # and the first 2k characters of the response body.
            logger.error(
                "[RegistrationServiceClient] A2A returned non-2xx status=%s body=%r",
                resp.status_code,
                resp.text[:2000],
            )
            raise

        # Successful 2xx response
        return resp
