"""Regressões de fala pt-BR: rosto/visão, alternativas Vosk e segurança.

Tudo simulado: sem microfone, câmera, áudio armazenado ou API.
"""
from __future__ import annotations

import json
import unittest
from unittest.mock import Mock, patch

from angela.asr_selection import (
    camera_identity_question, choose_recognition, configure_command_recognizer,
)
from angela.face_identity import face_intent
from angela.assistant import AssistantEngine


class Chat:
    available = True
    api_key = "fake"
    history = []

    def ask(self, text):
        return "CHAT_FALLBACK"


class ContextAsrTests(unittest.TestCase):
    def test_latest_misrecognitions_route_to_face_intent(self):
        corpus = {
            "você me reconhece pela câmera": "recognize",
            "você me conhece pela câmera": "recognize",
            "você conhece pela câmera": "recognize",
            "voce me reconhece pela webcam": "recognize",
            "Você me identifica pela câmera?": "recognize",
            "Você me conhece pelo rosto?": "recognize",
        }
        for phrase, expected in corpus.items():
            with self.subTest(phrase=phrase):
                self.assertEqual(face_intent(phrase), expected)

    def test_general_knowledge_is_never_face_recognition(self):
        for phrase in (
            "Você me conhece?",
            "Você conhece o programa Câmera do Windows?",
            "Como funciona o reconhecimento facial?",
            "Você conhece a câmera que eu comprei?",
            "Você me conhece pela internet?",
            "Você pode abrir o navegador?",
        ):
            with self.subTest(phrase=phrase):
                self.assertIsNone(face_intent(phrase))

    def test_latest_transcript_requests_consent_instead_of_groq_hallucination(self):
        engine = AssistantEngine(chat=Chat())
        face = Mock()
        face.enrolled.return_value = True
        engine.face_profile = face
        with patch("angela.camera_vision.capture_camera") as camera:
            reply = engine.reply("você me conhece pela câmera")
            self.assertIn("ativar a câmera", reply)
            self.assertEqual(engine._face_pending[0], "recognize")
            camera.assert_not_called()

    def test_primary_vosk_without_alternatives(self):
        self.assertEqual(choose_recognition(json.dumps({"text": "abra a calculadora"})),
                         ("abra a calculadora", False))

    def test_alternatives_use_acoustic_evidence_not_unconditional_replacement(self):
        data = {"alternatives": [
            {"text": "você me conhece pela câmera", "confidence": 0.87},
            {"text": "você me reconhece pela câmera", "confidence": 0.82},
        ]}
        self.assertEqual(choose_recognition(data),
                         ("você me reconhece pela câmera", True))
        data["alternatives"][1]["confidence"] = 0.51
        self.assertEqual(choose_recognition(data),
                         ("você me conhece pela câmera", False))

    def test_different_actions_not_changed(self):
        cases = [
            ["abra a câmera", "abra a calculadora"],
            ["você me conhece pela internet", "você me reconhece pela câmera"],
            ["conhece a câmera nova", "você me reconhece pela câmera"],
        ]
        for primary, alternative in cases:
            sample = {"alternatives": [
                {"text": primary, "confidence": 0.90},
                {"text": alternative, "confidence": 0.89},
            ]}
            self.assertEqual(choose_recognition(sample), (primary, False))

    def test_only_command_recognizer_requests_multiple_hypotheses(self):
        recognizer = Mock()
        configure_command_recognizer(recognizer)
        recognizer.SetMaxAlternatives.assert_called_once_with(3)

    def test_safe_nonrecognition_query(self):
        self.assertFalse(camera_identity_question("você me conhece?"))
        self.assertTrue(camera_identity_question("você me conhece pela câmera"))


if __name__ == "__main__":
    unittest.main()
