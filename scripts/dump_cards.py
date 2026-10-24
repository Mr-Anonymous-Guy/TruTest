"""
scripts/dump_cards.py – Export ASI:One Interactive Card Payloads (Phase 5)
========================================================================
Exports playground-ready JSON card payloads to docs/cards/*.json using
real demo pairs (Demo A: Trustworthy, Demo B: Likely Overfit).
Prints the ASI:One Card Playground URL for manual rendering verification.
"""

import json
from pathlib import Path
import sys

# Ensure repository root is on sys.path
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))

from agents.cards import (
    create_audit_details_card,
    create_parameter_form_card,
    create_results_card,
    create_strategy_picker_card,
)


def export_cards() -> None:
    docs_cards_dir = repo_root / "docs" / "cards"
    docs_cards_dir.mkdir(parents=True, exist_ok=True)

    demo_pair_path = repo_root / "data" / "demo_pair.json"
    results_path = repo_root / "data" / "demo_pair_results.json"

    with open(demo_pair_path, "r", encoding="utf-8") as f:
        demo_specs = json.load(f)

    with open(results_path, "r", encoding="utf-8") as f:
        demo_results = json.load(f)

    cards_to_dump = {}

    # 1. Examples Picker Carousel Card
    picker_meta = create_strategy_picker_card()
    cards_to_dump["01_examples_picker.json"] = {
        "card_kind": "carousel",
        "card_protocol_version": "1",
        "card_payload": json.loads(picker_meta.metadata["card_payload"]),
    }

    # 2. Demo A: Results Card
    spec_a = demo_specs["demo_a"]
    audit_a = demo_results["demo_a"]
    bt_a = audit_a["base_metrics"]
    res_a_meta = create_results_card("demo-a-sample-id", spec_a, bt_a, audit_a)
    cards_to_dump["02_results_card_demo_a.json"] = {
        "card_kind": "detail",
        "card_protocol_version": "1",
        "card_payload": json.loads(res_a_meta.metadata["card_payload"]),
    }

    # 3. Demo A: Audit Detail Card
    audit_a_meta = create_audit_details_card("demo-a-sample-id", spec_a, audit_a, bt_a)
    cards_to_dump["03_audit_card_demo_a.json"] = {
        "card_kind": "detail",
        "card_protocol_version": "1",
        "card_payload": json.loads(audit_a_meta.metadata["card_payload"]),
    }

    # 4. Demo B: Results Card
    spec_b = demo_specs["demo_b"]
    audit_b = demo_results["demo_b"]
    bt_b = audit_b["base_metrics"]
    res_b_meta = create_results_card("demo-b-sample-id", spec_b, bt_b, audit_b)
    cards_to_dump["04_results_card_demo_b.json"] = {
        "card_kind": "detail",
        "card_protocol_version": "1",
        "card_payload": json.loads(res_b_meta.metadata["card_payload"]),
    }

    # 5. Demo B: Audit Detail Card
    audit_b_meta = create_audit_details_card("demo-b-sample-id", spec_b, audit_b, bt_b)
    cards_to_dump["05_audit_card_demo_b.json"] = {
        "card_kind": "detail",
        "card_protocol_version": "1",
        "card_payload": json.loads(audit_b_meta.metadata["card_payload"]),
    }

    # 6. Parameter Form Card
    form_meta = create_parameter_form_card(partial_spec={"ticker": "RELIANCE.NS", "params": {"fast": 50, "slow": 200}})
    cards_to_dump["06_parameter_form.json"] = {
        "card_kind": "form",
        "card_protocol_version": "1",
        "card_payload": json.loads(form_meta.metadata["card_payload"]),
    }

    print("=" * 70)
    print("Exporting Phase 5 ASI:One Card Payloads to docs/cards/")
    print("=" * 70)

    for filename, payload in cards_to_dump.items():
        file_path = docs_cards_dir / filename
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        print(f"  [OK] Written: {file_path.name}")

    print("\nVerification Playground:")
    print("  -> https://asi1.ai/developer/card-playground")
    print("=" * 70)


if __name__ == "__main__":
    export_cards()
