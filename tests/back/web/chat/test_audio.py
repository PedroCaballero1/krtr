"""Tests the voice note checks: declared type, magic bytes and size must all agree."""

import asyncio
import io

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from krtr.back.web.chat.audio import (
    MAX_AUDIO_BYTES,
    AudioFormat,
    AudioRejection,
    InvalidAudio,
    read_voice_note,
)

WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 100
MP4 = b"\x00\x00\x00\x20ftypisom" + b"\x00" * 100
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100


def upload(content: bytes, content_type: str) -> UploadFile:
    """Builds an upload as FastAPI hands it to the route."""
    return UploadFile(
        io.BytesIO(content), filename="note", headers=Headers({"content-type": content_type})
    )


def rejection(content: bytes, content_type: str) -> AudioRejection:
    """Validates an upload that must be rejected and returns why."""
    with pytest.raises(InvalidAudio) as raised:
        asyncio.run(read_voice_note(upload(content, content_type)))
    return raised.value.reason


@pytest.mark.parametrize(
    ("content", "content_type", "expected"),
    [
        (WEBM, "audio/webm;codecs=opus", AudioFormat.WEBM),
        (WEBM, "audio/webm", AudioFormat.WEBM),
        (MP4, "audio/mp4", AudioFormat.MP4),
    ],
)
def test_what_the_browser_records_is_accepted(
    content: bytes, content_type: str, expected: AudioFormat
) -> None:
    """Chrome/Firefox record WebM/Opus and Safari MP4/AAC; both must pass."""
    assert asyncio.run(read_voice_note(upload(content, content_type))) == expected


def test_a_disguised_file_is_rejected_by_its_bytes() -> None:
    """An image declared as audio/webm fails the magic-bytes check."""
    assert rejection(PNG, "audio/webm") == AudioRejection.SIGNATURE_MISMATCH


def test_the_bytes_must_match_the_declared_container() -> None:
    """MP4 bytes declared as WebM are as suspicious as any other mismatch."""
    assert rejection(MP4, "audio/webm") == AudioRejection.SIGNATURE_MISMATCH


@pytest.mark.parametrize(
    "content_type", ["image/png", "audio/mpeg", "application/octet-stream", ""]
)
def test_other_declared_types_are_rejected(content_type: str) -> None:
    """Only the two containers the recorder produces are accepted."""
    assert rejection(WEBM, content_type) == AudioRejection.UNSUPPORTED_TYPE


def test_a_note_over_2_mb_is_rejected() -> None:
    """D6: 2 MB at most, counted while reading."""
    assert rejection(WEBM + b"\x00" * MAX_AUDIO_BYTES, "audio/webm") == AudioRejection.TOO_LARGE


def test_a_note_of_exactly_2_mb_is_accepted() -> None:
    """The limit is inclusive."""
    content = WEBM + b"\x00" * (MAX_AUDIO_BYTES - len(WEBM))

    assert asyncio.run(read_voice_note(upload(content, "audio/webm"))) == AudioFormat.WEBM


def test_an_empty_note_is_rejected() -> None:
    """A recording that captured nothing is not a message."""
    assert rejection(b"", "audio/webm") == AudioRejection.EMPTY
