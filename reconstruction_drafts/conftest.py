"""Keep reconstructed, unverified test drafts out of routine pytest collection.

This file affects only the reconstruction_drafts directory. The source
transcriptions must remain available for fidelity review without being
mistaken for validated unit tests.

Run validated tests from tests/; drafts must be promoted only after original
source verification and dependency-installed integration testing.
"""

collect_ignore_glob = ["test_*.py"]
