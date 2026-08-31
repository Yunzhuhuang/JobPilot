"""Read `profile.json` off disk.

Only loading lives here. What the author may claim is `claims.py`; whether the
profile is internally consistent is `validate.py`.
"""

from __future__ import annotations

import json
from pathlib import Path

from jobpilot.config import REPO_ROOT
from jobpilot.profile.schema import Profile

DEFAULT_PROFILE_PATH = REPO_ROOT / "profile.json"
FROZEN_PROFILE_PATH = REPO_ROOT / "fixture" / "profile.json"


def load_profile(path: Path | None = None) -> Profile:
    """Reads and schema-validates a profile.

    Cross-field rules are `validate_profile`'s job -- a file can be
    structurally valid and still claim a tool it has no evidence for.
    """
    path = path or DEFAULT_PROFILE_PATH
    if not path.is_file():
        raise FileNotFoundError(f"profile not found: {path}")
    return Profile.model_validate(json.loads(path.read_text()))
