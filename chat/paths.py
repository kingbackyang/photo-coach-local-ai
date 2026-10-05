"""Keep credentials and runtime state outside the source tree."""
import os
from pathlib import Path


def private_dir():
    override = os.environ.get("INFERENCE_CHAT_HOME")
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt":
        return Path(os.environ["LOCALAPPDATA"]) / "InferenceChat"
    return Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "inference-chat"


def settings_path():
    return Path(os.environ.get("INFERENCE_CHAT_SETTINGS", str(private_dir() / "settings.json")))
