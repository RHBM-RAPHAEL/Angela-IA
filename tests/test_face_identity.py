"""Facial memory is opt-in and local; tests never open webcam or send images."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from angela.assistant import AssistantEngine
from angela.face_identity import (
    FaceProfile, FaceIdentityError, face_intent, cosine_similarity,
    SIMILARITY_THRESHOLD,
)
from angela.screen_vision import ScreenFrame, VisionRequest
from angela.camera_vision import analyze_camera


def vector(one=0.0, two=0.0):
    return [one, two] + [0.0] * 126


class FakeChat:
    available = True
    api_key = "test-only-key"
    def __init__(self):
        self.history = []
    def ask(self, message):
        return "Mensagem simulada."


class FaceMemoryTests(unittest.TestCase):
    def test_explicit_requests(self):
        self.assertEqual(face_intent("Eu sou o Rafael"), "introduce")
        self.assertEqual(face_intent("Meu nome é Rafael"), "introduce")
        self.assertEqual(face_intent("Cadastre meu rosto"), "enroll")
        self.assertEqual(face_intent("Você me reconhece pela câmera?"), "recognize")
        self.assertEqual(face_intent("Apague meu cadastro facial"), "delete")
        self.assertIsNone(face_intent("Ative a câmera"))
        self.assertIsNone(face_intent("Eu sou o João"))

    def test_store_only_ciphertext_and_match_one_person(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "face_profile.dat"
            extraction = Mock(side_effect=[vector(1, 0), vector(.97, .18), vector(0, 1)])
            store = FaceProfile(
                path, extract=extraction,
                protect=lambda data: b"ENCRYPTED:" + data[::-1],
                unprotect=lambda data: data[len(b"ENCRYPTED:"):][::-1],
            )
            store.enroll(b"fakejpeg", name="Rafael")
            disk = path.read_bytes()
            self.assertTrue(disk.startswith(b"ENCRYPTED"))
            self.assertNotIn(b"Rafael", disk)
            self.assertNotIn(b"embedding", disk)
            self.assertEqual(store.identify(b"fakejpeg"), "Rafael")
            self.assertIsNone(store.identify(b"fakejpeg"))
            self.assertTrue(store.forget())
            self.assertFalse(path.exists())
            self.assertIsNone(store.identify(b"fakejpeg"))

    def test_invalid_embedding(self):
        with self.assertRaises(FaceIdentityError):
            cosine_similarity([0] * 128, [1] * 128)
        self.assertLess(cosine_similarity(vector(1,0), vector(0,1)), SIMILARITY_THRESHOLD)

    def test_introduction_is_not_automatic_camera_capture(self):
        engine = AssistantEngine(chat=FakeChat())
        fake = Mock()
        fake.enrolled.return_value = False
        engine.face_profile = fake
        with patch("angela.camera_vision.capture_camera") as camera:
            reply = engine.reply("Eu sou o Rafael")
            self.assertIn("criptografada", reply)
            camera.assert_not_called()
            self.assertEqual(engine._face_pending[0], "enroll")
            self.assertIn("Não vou acessar", engine.reply("não"))
            camera.assert_not_called()
            fake.enroll.assert_not_called()

    def test_enroll_only_after_explicit_consent(self):
        engine = AssistantEngine(chat=FakeChat())
        fake = Mock()
        fake.enrolled.return_value = False
        engine.face_profile = fake
        frame = ScreenFrame(b"fake-photo", 640, 480, "camera")
        with patch("angela.camera_vision.capture_camera", return_value=frame) as camera:
            engine.reply("Cadastre meu rosto")
            reply = engine.reply("sim")
        self.assertIn("Rosto cadastrado", reply)
        fake.enroll.assert_called_once_with(b"fake-photo", name="Rafael")
        camera.assert_called_once()

    def test_identification_only_after_consent_not_by_name(self):
        engine = AssistantEngine(chat=FakeChat())
        fake = Mock()
        fake.enrolled.return_value = True
        fake.identify.return_value = "Rafael"
        engine.face_profile = fake
        frame = ScreenFrame(b"fake-photo", 640, 480, "camera")
        with patch("angela.camera_vision.capture_camera", return_value=frame) as camera:
            prompt = engine.reply("Você me reconhece pela câmera?")
            self.assertIn("ativar a câmera", prompt)
            camera.assert_not_called()
            result = engine.reply("sim")
        self.assertIn("parece corresponder", result)
        fake.identify.assert_called_once_with(b"fake-photo")
        self.assertIsNone(engine._face_pending)

    def test_mismatch_no_false_identity(self):
        engine = AssistantEngine(chat=FakeChat())
        fake = Mock()
        fake.enrolled.return_value = True
        fake.identify.return_value = None
        engine.face_profile = fake
        with patch("angela.camera_vision.capture_camera",
                   return_value=ScreenFrame(b"fake", 640, 480, "camera")):
            engine.reply("Quem sou eu pela câmera?")
            reply = engine.reply("sim")
        self.assertIn("Não consegui confirmar", reply)
        self.assertNotIn("corresponde ao cadastro", reply)

    def test_delete_requires_confirmation(self):
        engine = AssistantEngine(chat=FakeChat())
        fake = Mock()
        fake.enrolled.return_value = True
        fake.forget.return_value = True
        engine.face_profile = fake
        engine.reply("Apague meu cadastro facial")
        fake.forget.assert_not_called()
        self.assertIn("Apaguei", engine.reply("sim"))
        fake.forget.assert_called_once()

    def test_existing_camera_capture_uses_existing_profile_only(self):
        profile = Mock()
        profile.enrolled.return_value = True
        profile.identify.return_value = "Rafael"
        output = analyze_camera(
            VisionRequest("camera", "olhe minha câmera"), "test",
            capturer=lambda: ScreenFrame(b"jpeg", 640, 480, "camera"),
            analyzer=lambda _frame, _question, _key: "Vejo um caderno.",
            identity_profile=profile,
        )
        self.assertIn("corresponder ao cadastro de Rafael", output)
        self.assertIn("Vejo um caderno", output)
        profile.identify.assert_called_once_with(b"jpeg")


if __name__ == "__main__":
    unittest.main()
