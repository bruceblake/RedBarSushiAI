import pytest
from xml.etree import ElementTree as ET

import app.routes.voice as voice_mod


@pytest.fixture(autouse=True)
def disable_async(monkeypatch):
    # Ensure no real async loops or audio processing is invoked
    monkeypatch.setattr(voice_mod, "get_audio_processor", lambda *args, **kwargs: None)
    yield


def make_client(app, client):
    # convenience alias
    return client


def test_handle_menu_questions_dynamic_success(client, monkeypatch):
    # Patch analysis to always select ask_menu intent
    monkeypatch.setattr(
        voice_mod, "analyze_user_input", lambda text: {"intent": "ask_menu"}
    )
    # Patch OpenAI client to return a canned reply
    fake_reply = (
        "Here is our menu: Rolls: SampleRoll at $9.99; "
        "Appetizers: SampleApp at $4.99. "
        "Let me know if you'd like to hear more."
    )

    class FakeResult:
        choices = [
            type(
                "C",
                (object,),
                {"message": type("M", (object,), {"content": fake_reply})},
            )
        ]

    class FakeClient:
        def __init__(self):
            self.chat = type("Chat", (), {})()
            self.chat.completions = type(
                "Comp", (), {"create": lambda *args, **kwargs: FakeResult()}
            )()

    # Ensure OPENAI is enabled
    monkeypatch.setenv("DISABLE_OPENAI", "false")
    # Monkeypatch OpenAI client class
    monkeypatch.setattr(
        voice_mod.openai, "OpenAI", lambda *args, **kwargs: FakeClient()
    )

    # Call endpoint
    resp = client.post("/handle_menu_questions", data={"SpeechResult": "menu"})
    assert resp.status_code == 200
    # Parse TwiML
    tree = ET.fromstring(resp.data)
    say = tree.find(".//Say")
    assert say is not None
    assert say.text == fake_reply


def test_handle_menu_questions_fallback(monkeypatch, client):
    # Monkeypatch analysis to ask menu
    monkeypatch.setattr(
        voice_mod, "analyze_user_input", lambda text: {"intent": "ask_menu"}
    )

    # Dummy agent that raises on init or not
    class DummyAgentBad:
        def __init__(self):
            raise RuntimeError("agent failed")

    monkeypatch.setattr(voice_mod, "OrderParsingAgent", DummyAgentBad)

    # Call endpoint
    resp = client.post("/handle_menu_questions", data={"SpeechResult": "anything"})
    assert resp.status_code == 200
    tree = ET.fromstring(resp.data)
    say = tree.find(".//Say")
    assert say is not None
    text = say.text
    # Should fallback to apology message
    assert text.startswith("Sorry"), f"Unexpected fallback text: {text}"
