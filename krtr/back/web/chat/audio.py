"""Validates the voice notes `POST /api/chat/voice` accepts (task 4.9, G8, D6).

Exists so an upload is trusted only after two independent checks agree: the declared
content type must be WebM or MP4 audio, **and** the file's first bytes must be that container's
signature (WebM's EBML header, MP4's `ftyp` box). A renamed executable or an image sent as
`audio/webm` fails. Uploads are read in chunks and stopped past 2 MB, so an oversized file is
never held whole in memory. The audio itself is not kept (processing it is out of scope).
Consumed by `krtr/back/web/routers/chat.py`.
"""

from enum import StrEnum

from fastapi import UploadFile

MAX_AUDIO_BYTES = 2 * 1024 * 1024  # D6: 2 MB, about 60 s of what the browser records.
_READ_CHUNK_BYTES = 64 * 1024

_WEBM_SIGNATURE = b"\x1a\x45\xdf\xa3"  # EBML header, at offset 0.
_MP4_SIGNATURE = b"ftyp"  # The `ftyp` box type, at offset 4 (after the box size).


class AudioFormat(StrEnum):
    """The audio containers the browser recorder produces (WebM/Opus or MP4/AAC)."""

    WEBM = "audio/webm"
    MP4 = "audio/mp4"


class AudioRejection(StrEnum):
    """Why a voice note was rejected, as the route records it."""

    UNSUPPORTED_TYPE = "unsupported_type"  # The declared content type is not WebM or MP4.
    SIGNATURE_MISMATCH = "signature_mismatch"  # The bytes are not the declared container.
    TOO_LARGE = "too_large"
    EMPTY = "empty"


class InvalidAudio(Exception):
    """Raised when an upload is not an acceptable voice note.

    Exists so the reason reaches the route, which answers 413 for TOO_LARGE and 415 otherwise.
    """

    def __init__(self, reason: AudioRejection) -> None:
        """Builds the error for one reason.

        Args:
            reason: Why the upload was rejected.
        """
        super().__init__(reason.value)
        self.reason = reason


def declared_format(content_type: str | None) -> AudioFormat:
    """Reads the container from a content type, ignoring parameters such as `;codecs=opus`.

    Args:
        content_type: The upload's declared content type.

    Returns:
        AudioFormat: the declared container.

    Raises:
        InvalidAudio: UNSUPPORTED_TYPE if it is not WebM or MP4 audio.
    """
    media_type = (content_type or "").split(";", 1)[0].strip().lower()
    try:
        return AudioFormat(media_type)
    except ValueError as error:
        raise InvalidAudio(AudioRejection.UNSUPPORTED_TYPE) from error


def check_signature(audio_format: AudioFormat, head: bytes) -> None:
    """Checks that a file's first bytes are the declared container's signature.

    Args:
        audio_format: The declared container.
        head: The file's first bytes (at least 8 for MP4).

    Returns:
        None.

    Raises:
        InvalidAudio: SIGNATURE_MISMATCH if they are not.
    """
    if audio_format == AudioFormat.WEBM and head.startswith(_WEBM_SIGNATURE):
        return
    if audio_format == AudioFormat.MP4 and head[4:8] == _MP4_SIGNATURE:
        return
    raise InvalidAudio(AudioRejection.SIGNATURE_MISMATCH)


async def read_voice_note(upload: UploadFile) -> AudioFormat:
    """Validates an uploaded voice note: type, signature and size.

    Args:
        upload: The multipart `audio` field.

    Returns:
        AudioFormat: the validated container.

    Raises:
        InvalidAudio: if any check fails.
    """
    audio_format = declared_format(upload.content_type)
    size = 0
    head = b""
    while chunk := await upload.read(_READ_CHUNK_BYTES):
        size += len(chunk)
        if size > MAX_AUDIO_BYTES:
            raise InvalidAudio(AudioRejection.TOO_LARGE)
        head = head or chunk
    if size == 0:
        raise InvalidAudio(AudioRejection.EMPTY)
    check_signature(audio_format, head)
    return audio_format
