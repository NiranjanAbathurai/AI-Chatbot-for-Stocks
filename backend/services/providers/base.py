"""Abstract base class for AI providers."""

from abc import ABC, abstractmethod


class AIProvider(ABC):
    """Abstract base class that all AI providers must implement."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider name."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider has a valid API key configured."""
        ...

    @abstractmethod
    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        """
        Generate a response from the AI model.

        Args:
            system_prompt: The system/role instruction for the AI.
            user_prompt: The user's message/data to analyze.

        Returns:
            The AI-generated text response.

        Raises:
            Exception: If the API call fails.
        """
        ...
