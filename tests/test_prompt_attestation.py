"""CI gate: the shipped extraction prompt must be a registered extraction-gym artifact
with a releasable verdict against the current frozen gold version.

The attestation fixture is produced by extraction-gym (reports/release-attestation.json)
and vendored here on each release. This test makes no API calls: it asserts prompt
bytes match the attested artifact and the verdict is releasable (PASS, or NOOP_ROOT
when a loop run could not beat the incumbent beyond noise).
"""

import hashlib
import json
from pathlib import Path

from coffee_value_app.extractor import EXTRACTION_SYSTEM_PROMPT

ATTESTATION_PATH = Path(__file__).parent / "fixtures" / "release_attestation.json"
RELEASABLE_VERDICTS = {"PASS", "NOOP_ROOT"}


def test_shipped_prompt_matches_attested_artifact() -> None:
    attestation = json.loads(ATTESTATION_PATH.read_text(encoding="utf-8"))
    shipped_sha = hashlib.sha256(EXTRACTION_SYSTEM_PROMPT.encode("utf-8")).hexdigest()
    assert shipped_sha == attestation["prompt_sha256"], (
        "Shipped prompt does not match the attested extraction-gym artifact "
        f"{attestation['artifact_id']} (gold {attestation['gold_version']}). "
        "Prompt changes must go through the gym's gate; re-attest before shipping."
    )


def test_attestation_verdict_is_releasable() -> None:
    attestation = json.loads(ATTESTATION_PATH.read_text(encoding="utf-8"))
    assert attestation["verdict"] in RELEASABLE_VERDICTS
    assert attestation["gold_version"]
    assert attestation["gold_page_count"] > 0
