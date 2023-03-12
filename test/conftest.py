from dataclasses import dataclass
from typing import Optional

import pytest


@pytest.fixture()
def fake_ctx():
    return FakeContext([], [], [])


@dataclass
class FakeContext:
    """Fake discord.py context for testing modules that interact with the text chat."""

    messages: list[str]
    files: list[Optional[str]]
    tts: list[bool]

    async def send(self, content, *, tts=False, file=None):
        self.messages.append(content)
        self.files.append(file)
        self.tts.append(tts)
