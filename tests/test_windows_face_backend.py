"""Testes Windows com biometria FICTÍCIA e imagem preta, sem webcam."""
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from angela.face_identity import FaceProfile, MODEL_ROOT, DETECTOR, RECOGNIZER


@unittest.skipUnless(sys.platform == "win32", "DPAPI e OpenCV são validados no Windows")
class WindowsFaceBackendTests(unittest.TestCase):
    def test_dpapi_encryption_with_synthetic_vector(self):
        with TemporaryDirectory() as folder:
            target = Path(folder) / "dummy_face.dat"
            reference = [1.0] + [0.0] * 127
            profile = FaceProfile(path=target, extract=lambda _image: reference)
            profile.enroll(b"NOT_A_REAL_FACE", name="Rafael")
            encrypted = target.read_bytes()
            self.assertNotIn(b"embedding", encrypted)
            self.assertNotIn(b"Rafael", encrypted)
            self.assertEqual(profile.identify(b"NOT_A_REAL_FACE"), "Rafael")
            self.assertTrue(profile.forget())
            self.assertFalse(target.exists())

    def test_models_load_without_camera(self):
        import cv2
        import numpy as np
        self.assertTrue(DETECTOR.is_file())
        self.assertTrue(RECOGNIZER.is_file())
        detector = cv2.FaceDetectorYN.create(
            str(DETECTOR), "", (640,480), score_threshold=0.85,
        )
        recognizer = cv2.FaceRecognizerSF.create(str(RECOGNIZER), "")
        self.assertIsNotNone(recognizer)
        status, faces = detector.detect(np.zeros((480,640,3), dtype=np.uint8))
        self.assertIsNone(faces, "Imagem sem rosto não deve ser identificada")
