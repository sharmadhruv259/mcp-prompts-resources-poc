"""Provide general-purpose Groq chat without MCP access."""

import asyncio

from groq import Groq

from constants.config import GROQ_API_KEY, GROQ_MODEL
from constants.system_prompts import DEFAULT_ASSISTANT_PROMPT


class DefaultAssistant:
    """Generate general chat responses without executing MCP operations.

    Attributes:
        client (Groq): Configured Groq client.
        model (str): Model used for general conversations.

    Functions:
        chat: Generate an assistant response to one user message.
    """

    def __init__(self) -> None:
        """Initialize the Groq client.

        Args:
            None.

        Returns:
            None: Initializes the assistant.

        Raises:
            RuntimeError: If the Groq API key is missing.
        """
        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is missing.")

        self.client = Groq(
            api_key=GROQ_API_KEY,
            timeout=45.0,
        )
        self.model = GROQ_MODEL

    async def chat(self, message: str) -> str:
        """Answer a general question without exposing MCP tools.

        Args:
            message (str): User's message.

        Returns:
            str: Generated assistant response.

        Raises:
            ValueError: If the message is empty.
            RuntimeError: If Groq returns no usable answer.
            Exception: If the Groq API request fails.
        """
        message = message.strip()

        if not message:
            raise ValueError("Message cannot be empty.")

        response = await asyncio.to_thread(
            self.client.chat.completions.create,
            model=self.model,
            temperature=0.5,
            messages=[
                {
                    "role": "system",
                    "content": DEFAULT_ASSISTANT_PROMPT,
                },
                {
                    "role": "user",
                    "content": message,
                },
            ],
        )

        if not response.choices:
            raise RuntimeError("Groq returned no choices.")

        answer = response.choices[0].message.content

        if not answer or not answer.strip():
            raise RuntimeError(
                "Groq returned an empty assistant response."
            )

        return answer.strip()