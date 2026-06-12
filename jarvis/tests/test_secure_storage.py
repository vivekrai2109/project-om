from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from agenthub.secure_storage import encryption_enabled, read_json_file, read_text_file, write_json_file, write_text_file


class SecureStorageTests(unittest.TestCase):
    def test_text_round_trip_uses_encrypted_file_when_available(self) -> None:
        with TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "memory" / "notes.md"
            actual_path = write_text_file(target, "owner secret preference")
            self.assertEqual(read_text_file(target), "owner secret preference")
            if encryption_enabled():
                self.assertTrue(str(actual_path).endswith(".enc"))
                self.assertNotIn("owner secret preference", actual_path.read_text(encoding="latin-1", errors="ignore"))
            else:
                self.assertEqual(actual_path, target)

    def test_json_round_trip_uses_encrypted_file_when_available(self) -> None:
        with TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "learning" / "candidate.json"
            payload = {"candidate_id": "train-1", "preferred_output": "safe output"}
            actual_path = write_json_file(target, payload)
            self.assertEqual(read_json_file(target), payload)
            if encryption_enabled():
                self.assertTrue(str(actual_path).endswith(".enc"))


if __name__ == "__main__":
    unittest.main()