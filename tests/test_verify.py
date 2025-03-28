#!/usr/bin/env python3

import json
import logging
from pathlib import Path

import pytest
from utils.verify import verify_proof


def test_verify_proofs():
    """Test that
    - all proofs in mock_lean_repository_proofs.json are valid
    - all proofs in mock_lean_repository_non_proofs.json are invalid
    """

    # Get the mock repository directory and proofs file
    repo_dir = Path(__file__).parent / "mock_lean_repository"
    proofs_file = Path(__file__).parent / "mock_lean_repository_proofs.json"
    non_proofs_file = Path(__file__).parent / "mock_lean_repository_non_proofs.json"

    # Get Lean version from lean-toolchain
    toolchain_path = repo_dir / "lean-toolchain"
    toolchain_content = toolchain_path.read_text().strip()
    lean_version = toolchain_content.split(":", 1)[1]

    # Verify proofs: make sure no false negatives
    with open(proofs_file) as f:
        proofs = json.load(f)

    for proof_entry in proofs:
        location = proof_entry["location"]
        proof = proof_entry["proof"]

        # Verify the proof
        is_valid = verify_proof(repo_dir, lean_version, location, proof)

        # Assert that the proof is valid
        assert is_valid, (
            f"Proof failed verification for {location['file']} at line {location['start_line']}"
        )

    # Verify non-proofs: make sure no false positives
    with open(non_proofs_file) as f:
        non_proofs = json.load(f)

    for proof_entry in non_proofs:
        location = proof_entry["location"]
        proof = proof_entry["proof"]

        # Verify the proof
        is_valid = verify_proof(repo_dir, lean_version, location, proof)

        # Assert that the proof is invalid
        assert not is_valid, (
            f"Non-proof passed verification for {location['file']} at line {location['start_line']}"
        )
