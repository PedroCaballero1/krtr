"""Stores the text of every chat message and reply in the `messages` table (G17).

Exists as the only code that reads or writes `messages`: it runs the table's `.sql` files and
encrypts each text with AES-256-GCM (`KRTR_MESSAGES_KEY`) before it reaches the database, so
a database leak exposes no conversation. Every read filters by incident *and* customer.
Consumed by `engine/engine.py`; the in-memory store backs the CLI and the tests.
"""

import logging
from typing import Any, Protocol

from krtr.back.ia.messages.artifacts import ConversationMessage, MessageSender
from krtr.back.security.crypto.cipher import AesGcmCipher
from krtr.back.security.crypto.config import CryptoConfig, CryptoEnvironmentVariable
from krtr.back.security.oidc.artifacts import InterfaceLanguage
from krtr.database.neon.client import NeonClient
from krtr.database.queries import load_sql

logger = logging.getLogger(__name__)

TABLE = "messages"
_INSERT_ONE = load_sql(TABLE, "insert_one.sql")
_SELECT_BY_CASE = load_sql(TABLE, "select_by_case.sql")
_PURGE = load_sql(TABLE, "purge.sql")


class MessageStore(Protocol):
    """Appends and lists a case's messages. Consumed by `engine/engine.py`."""

    def append(self, message: ConversationMessage) -> None:
        """Stores one message.

        Args:
            message: The message, with its text in clear.

        Returns:
            None.
        """
        ...

    def list_case(self, customer_id: str, incident_id: str) -> list[ConversationMessage]:
        """Lists one case's messages, oldest first.

        Args:
            customer_id: The case's customer, from the session.
            incident_id: The case.

        Returns:
            list[ConversationMessage]: the messages, empty for another customer's case.
        """
        ...


class InMemoryMessageStore:
    """Keeps messages in a list for the life of the process.

    Exists for the `krtr back ia` CLI and the tests.
    """

    def __init__(self) -> None:
        """Starts with no messages."""
        self.messages: list[ConversationMessage] = []

    def append(self, message: ConversationMessage) -> None:
        """Stores one message.

        Args:
            message: The message.

        Returns:
            None.
        """
        self.messages.append(message)

    def list_case(self, customer_id: str, incident_id: str) -> list[ConversationMessage]:
        """Lists one case's messages, in the order they were stored.

        Args:
            customer_id: The case's customer.
            incident_id: The case.

        Returns:
            list[ConversationMessage]: the case's messages.
        """
        return [
            message
            for message in self.messages
            if (message.customer_id, message.incident_id) == (customer_id, incident_id)
        ]


class NeonMessageStore:
    """Reads and writes `messages` rows, encrypting the text they carry.

    Exists to keep SQL and encryption out of the engine. Built with `from_environment`.
    """

    def __init__(self, client: NeonClient, cipher: AesGcmCipher) -> None:
        """Builds a store on one pooled Neon client and the messages key.

        Args:
            client: The pooled Neon client (`execute_params` / `fetch_all`).
            cipher: The AES-256-GCM cipher for `KRTR_MESSAGES_KEY`.
        """
        self._client = client
        self._cipher = cipher

    @classmethod
    def from_environment(cls) -> "NeonMessageStore":
        """Builds a store from `KRTR_MESSAGES_KEY` and `NEON_DB_HOST`.

        The key is validated before the Neon client is created, so a bad key never leaves a
        connection behind.

        Returns:
            NeonMessageStore: a store bound to the messages key and a new Neon client.

        Raises:
            ValueError: if `KRTR_MESSAGES_KEY` or `NEON_DB_HOST` is missing, or the key is not
                a base64-encoded 32-byte key.
        """
        config = CryptoConfig.from_environment(CryptoEnvironmentVariable.MESSAGES_KEY)
        return cls(client=NeonClient(), cipher=AesGcmCipher(config.decoded_key()))

    def append(self, message: ConversationMessage) -> None:
        """Stores one message, its text encrypted.

        Args:
            message: The message, with its text in clear.

        Returns:
            None.
        """
        self._client.execute_params(
            _INSERT_ONE,
            {
                "message_id": str(message.message_id),
                "incident_id": message.incident_id,
                "customer_id": message.customer_id,
                "sender": message.sender.value,
                "content": self._cipher.encrypt(message.content.encode("utf-8")),
                "language": message.language.value,
                "outcome": message.outcome.value if message.outcome else None,
                "sent_at": message.sent_at,
            },
        )

    def list_case(self, customer_id: str, incident_id: str) -> list[ConversationMessage]:
        """Lists one case's messages, oldest first, decrypting their text.

        Args:
            customer_id: The case's customer, from the session.
            incident_id: The case.

        Returns:
            list[ConversationMessage]: the messages, empty for another customer's case.
        """
        rows = self._client.fetch_all(
            _SELECT_BY_CASE, {"incident_id": incident_id, "customer_id": customer_id}
        )
        return [self._message_from(row) for row in rows]

    def purge_expired(self) -> int:
        """Deletes the messages older than the 3-month retention.

        Exists for the daily `purge_events` job (task 6.5 of the web guide).

        Returns:
            int: how many messages were deleted.
        """
        deleted = self._client.execute_params(_PURGE)
        logger.info("Purged %d expired messages", deleted)
        return deleted

    def _message_from(self, row: tuple[Any, ...]) -> ConversationMessage:
        """Builds a message from a `select_by_case.sql` row, decrypting its text.

        Args:
            row: The row, in the query's column order.

        Returns:
            ConversationMessage: the message.
        """
        message_id, incident_id, customer_id, sender, content, language, outcome, sent_at = row
        return ConversationMessage(
            message_id=message_id,
            incident_id=incident_id,
            customer_id=customer_id,
            sender=MessageSender(sender),
            content=self._cipher.decrypt(bytes(content)).decode("utf-8"),
            language=InterfaceLanguage(language),
            outcome=outcome,
            sent_at=sent_at,
        )
