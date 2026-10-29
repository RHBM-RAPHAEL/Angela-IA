"""Regressão da visão pela webcam: somente fotos autorizadas e sintéticas."""
from __future__ import annotations

import json
from io import BytesIO
import unittest
from unittest.mock import Mock, patch
from PIL import Image

from angela.assistant import AssistantEngine
from angela.camera_vision import (
    parse_camera_request, capture_camera, analyze_camera, VisionError,
)
from angela.screen_vision import ScreenFrame, VisionRequest, analyze_frame


class FakeChat:
    api_key = "fake-only-test-key"
    available = True

    def __init__(self):
        self.history = []

    def ask(self, question):
        return "Pergunta genérica sem câmera"


class Response:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return json.dumps({
            "choices": [{"message": {"content": "Vejo uma camisa azul."}}]
        }).encode("utf-8")


def make_jpeg(width=640, height=480):
    image = Image.new("RGB", (width, height), (25, 68, 140))
    with BytesIO() as output:
        image.save(output, "JPEG")
        return output.getvalue()


class CameraVisionTests(unittest.TestCase):
    def test_reconhece_pedidos_de_camera(self):
        phrases = [
            "Ângela, você consegue me ver pela câmera?",
            "o que você vê na webcam?",
            "o que estou segurando na câmera?",
            "olha pra mim pela câmera",
            "Ângela, liga a webcam",
            "Ângela, abre minha câmera",
            "analise minha câmera frontal",
            "como estou vestido pela câmera?",
            "olha pela câmera do notebook",
        ]
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                request = parse_camera_request(phrase)
                self.assertIsNotNone(request, phrase)
                self.assertEqual(request.scope, "camera")
                self.assertEqual(request.question, phrase)

    def test_nao_ativar_para_configuracoes_ou_tela(self):
        phrases = [
            "como consertar a câmera?",
            "como configurar minha webcam?",
            "desligue a câmera",
            "transmita minha câmera",
            "grave um vídeo na webcam",
            "abra a calculadora",
            "o que tem na minha tela?",
            "por que a webcam está bloqueada?",
            "qual a melhor câmera para comprar?",
            "o que é uma webcam?",
        ]
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                self.assertIsNone(parse_camera_request(phrase))

    def test_pede_consentimento_sem_abrir_camera(self):
        engine = AssistantEngine(chat=FakeChat())
        with patch("angela.assistant.analyze_camera") as analyzer:
            prompt = engine.reply("Ângela, consegue me ver pela webcam?")
            self.assertIn("webcam", prompt)
            self.assertIn("UMA foto", prompt)
            self.assertIn("Groq", prompt)
            self.assertIn("Você autoriza?", prompt)
            analyzer.assert_not_called()
            self.assertEqual(engine._vision_pending[0].scope, "camera")

    def test_autorizacao_explicita_aciona_uma_foto(self):
        engine = AssistantEngine(chat=FakeChat())
        output = Mock(return_value="Vejo uma pessoa segurando um livro.")
        engine.on_camera_status = Mock()
        with patch("angela.assistant.analyze_camera", output), patch(
            "angela.assistant.analyze_screen"
        ) as screen:
            engine.reply("Ângela, você consegue me ver pela câmera?")
            self.assertEqual(
                engine.reply("sim, pode"),
                "Vejo uma pessoa segurando um livro.",
            )
            screen.assert_not_called()
            output.assert_called_once()
            self.assertEqual(output.call_args.args[0].scope, "camera")
            self.assertEqual(output.call_args.args[1], "fake-only-test-key")
            self.assertIs(output.call_args.kwargs["status_cb"], engine.on_camera_status)
            self.assertIsNone(engine._vision_pending)
            self.assertFalse(engine.last_execution)

    def test_cancelamento_ou_assunto_novo_nao_liga_camera(self):
        for response in ("não", "cancelar"):
            engine = AssistantEngine(chat=FakeChat())
            with patch("angela.assistant.analyze_camera") as analyzer:
                engine.reply("pode me ver pela câmera?")
                self.assertIn("não vou ligar a câmera", engine.reply(response))
                analyzer.assert_not_called()
                self.assertIsNone(engine._vision_pending)
        engine = AssistantEngine(chat=FakeChat())
        with patch("angela.assistant.analyze_camera") as analyzer:
            engine.reply("me veja pela webcam")
            self.assertEqual(engine.reply("oi"), "Estou ouvindo.")
            analyzer.assert_not_called()

    def test_cada_nova_captura_precisa_de_novo_consentimento(self):
        engine = AssistantEngine(chat=FakeChat())
        with patch("angela.assistant.analyze_camera", return_value="Tudo bem") as analyzer:
            engine.reply("o que vê pela webcam?")
            engine.reply("sim")
            self.assertEqual(analyzer.call_count, 1)
            engine.reply("o que vê pela webcam?")
            self.assertEqual(analyzer.call_count, 1)
            engine.reply("não")
            self.assertEqual(analyzer.call_count, 1)

    def test_autorizacao_expira(self):
        engine = AssistantEngine(chat=FakeChat())
        with (
            patch("angela.assistant.time.monotonic", side_effect=[10, 90]),
            patch("angela.assistant.analyze_camera") as analyzer,
        ):
            engine.reply("olha minha webcam")
            self.assertIn("expirou", engine.reply("sim"))
            analyzer.assert_not_called()

    def test_sem_chave_nao_ativa_camera(self):
        chat = FakeChat()
        chat.available = False
        engine = AssistantEngine(chat=chat)
        with patch("angela.assistant.analyze_camera") as analyzer:
            msg = engine.reply("Ângela, você me vê pela câmera?")
            self.assertIn("GROQ_API_KEY", msg)
            self.assertIn("desligada", msg)
            analyzer.assert_not_called()

    def test_rejeita_imagem_corrompida(self):
        with self.assertRaises(VisionError):
            capture_camera(frame_provider=lambda: b"corrupted")
        with self.assertRaises(VisionError):
            capture_camera(frame_provider=lambda: b"")

    def test_comprime_foto_em_memoria_sem_escrever_disco(self):
        original = make_jpeg(2200, 1500)
        frame = capture_camera(frame_provider=lambda: original)
        self.assertEqual(frame.scope, "camera")
        self.assertTrue(frame.jpeg_bytes.startswith(bytes.fromhex("ffd8")))
        self.assertLessEqual(frame.width, 1280)
        self.assertLessEqual(frame.height, 1280)
        self.assertLess(len(frame.jpeg_bytes), 3_000_000)

    def test_erro_de_camera_nao_envia_imagem(self):
        request = VisionRequest("camera", "me veja")
        sender = Mock()
        def bad_camera():
            raise VisionError("Câmera desligada.")
        self.assertIn(
            "Câmera desligada.",
            analyze_camera(request, "key", capturer=bad_camera, analyzer=sender),
        )
        sender.assert_not_called()

    def test_analisador_usando_prompt_de_camera_sem_identificar_pessoa(self):
        frame = ScreenFrame(make_jpeg(), 640, 480, "camera")
        requests = []
        def opener(req, timeout=20):
            requests.append(req)
            return Response()
        msg = analyze_frame(frame, "Que roupa aparece?", "fake-key", opener=opener)
        self.assertIn("camisa azul", msg)
        payload = json.loads(requests[0].data.decode("utf-8"))
        system = payload["messages"][0]["content"]
        self.assertIn("fotografia da webcam", system)
        self.assertIn("Não identifique pessoas", system)
        self.assertIn("Não controle o computador", system)
        self.assertNotIn("fake-key", requests[0].data.decode("utf-8"))

    def test_analise_nao_expoe_pixels_em_logs(self):
        fake_frame = ScreenFrame(make_jpeg(), 640, 480, "camera")
        capturer = Mock(return_value=fake_frame)
        analyzer = Mock(return_value="Vejo um copo.")
        with patch("angela.camera_vision.record") as logs:
            response = analyze_camera(
                VisionRequest("camera", "o que vê?"), "key",
                capturer=capturer, analyzer=analyzer,
            )
        self.assertIn("copo", response)
        self.assertEqual(capturer.call_count, 1)
        self.assertNotIn("jpeg_bytes", str(logs.call_args_list))
        self.assertNotIn("image/jpeg", str(logs.call_args_list))

    def test_status_callback_apenas_na_captura(self):
        status = Mock()
        request = VisionRequest("camera", "me veja")
        captured = Mock(return_value=ScreenFrame(make_jpeg(), 640, 480, "camera"))
        analyzed = Mock(return_value="Foto analisada.")
        answer = analyze_camera(
            request, "key", status_cb=status,
            capturer=captured, analyzer=analyzed,
        )
        self.assertEqual(answer, "Foto analisada.")
        self.assertIs(captured.call_args.kwargs["status_cb"], status)

    def test_erro_fora_do_windows_sem_captura(self):
        with patch("angela.camera_vision.sys.platform", "linux"):
            from angela.camera_vision import _qt_capture_frame
            with self.assertRaises(VisionError):
                _qt_capture_frame()

    @unittest.skipUnless(__import__("importlib").util.find_spec("PySide6"),
                         "Qt Multimedia só é verificado onde está instalado")
    def test_backend_qt_sintetico_liga_e_desliga_camera(self):
        """Testa o QVideoSink sem abrir a webcam física."""
        from PySide6 import QtCore, QtMultimedia
        from PySide6.QtGui import QImage
        from angela.camera_vision import _qt_capture_frame

        camera = Mock()
        session = Mock()
        sink = Mock()
        loop = Mock()
        timer = Mock()
        image = QImage(640, 360, QImage.Format.Format_RGB32)
        image.fill(0xff3566cc)
        video_frame = Mock()
        video_frame.isValid.return_value = True
        video_frame.toImage.return_value = image
        callbacks = []
        sink.videoFrameChanged.connect.side_effect = lambda callback: callbacks.append(callback)
        loop.exec.side_effect = lambda: callbacks[0](video_frame)
        status = Mock()
        with (
            patch.object(QtCore, "QCoreApplication") as app,
            patch.object(QtCore, "QEventLoop", return_value=loop),
            patch.object(QtCore, "QTimer", return_value=timer),
            patch.object(QtMultimedia, "QCamera", return_value=camera),
            patch.object(QtMultimedia, "QMediaCaptureSession", return_value=session),
            patch.object(QtMultimedia, "QVideoSink", return_value=sink),
            patch.object(QtMultimedia, "QMediaDevices") as devices,
        ):
            app.instance.return_value = object()
            devices.videoInputs.return_value = [Mock()]
            jpeg = _qt_capture_frame(status_cb=status)
        self.assertTrue(jpeg.startswith(bytes.fromhex("ffd8")))
        camera.start.assert_called_once()
        camera.stop.assert_called_once()
        self.assertEqual(session.setVideoSink.call_args_list[-1].args, (None,))
        self.assertEqual(status.call_count, 2)
        self.assertIn("Câmera desligada", status.call_args.args[0])

    @unittest.skipUnless(__import__("importlib").util.find_spec("PySide6"),
                         "Qt Multimedia só é verificado onde está instalado")
    def test_backend_qt_timeout_sempre_solta_camera(self):
        """Não deixa câmera presa quando nenhum frame é entregue."""
        from PySide6 import QtCore, QtMultimedia
        from angela.camera_vision import _qt_capture_frame

        camera = Mock()
        session = Mock()
        sink = Mock()
        status = Mock()
        with (
            patch.object(QtCore, "QCoreApplication") as app,
            patch.object(QtCore, "QEventLoop", return_value=Mock()),
            patch.object(QtCore, "QTimer", return_value=Mock()),
            patch.object(QtMultimedia, "QCamera", return_value=camera),
            patch.object(QtMultimedia, "QMediaCaptureSession", return_value=session),
            patch.object(QtMultimedia, "QVideoSink", return_value=sink),
            patch.object(QtMultimedia, "QMediaDevices") as devices,
        ):
            app.instance.return_value = object()
            devices.videoInputs.return_value = [Mock()]
            with self.assertRaises(VisionError):
                _qt_capture_frame(status_cb=status)
        camera.start.assert_called_once()
        camera.stop.assert_called_once()
        self.assertEqual(session.setCamera.call_args_list[-1].args, (None,))
        self.assertIn("desligada", status.call_args.args[0])

    def test_subprocesso_camera_isolado_entrega_jpeg_sem_expor_chave(self):
        import subprocess
        from angela.camera_vision import _isolated_capture_frame
        statuses = []
        completed = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=make_jpeg(), stderr=b""
        )
        with (
            patch("angela.camera_vision.subprocess.run", return_value=completed) as run,
            patch.dict("angela.camera_vision.os.environ", {
                "GROQ_API_KEY": "SECRET-FAKE-ONLY", "ANGELA_CAMERA_INDEX": "0",
            }),
        ):
            image = _isolated_capture_frame(status_cb=statuses.append)
        self.assertEqual(image, completed.stdout)
        self.assertEqual(len(statuses), 2)
        self.assertIn("Câmera desligada", statuses[-1])
        self.assertEqual(run.call_args.args[0][-1], "angela.camera_worker")
        self.assertNotIn("GROQ_API_KEY", run.call_args.kwargs["env"])
        self.assertEqual(run.call_args.kwargs["env"]["ANGELA_CAMERA_INDEX"], "0")
        self.assertEqual(run.call_args.kwargs["timeout"], 14)

    def test_subprocesso_camera_timeout_solta_status(self):
        import subprocess
        from angela.camera_vision import _isolated_capture_frame
        statuses = []
        with patch(
            "angela.camera_vision.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="camera", timeout=14),
        ):
            with self.assertRaisesRegex(VisionError, "demorou demais"):
                _isolated_capture_frame(status_cb=statuses.append)
        self.assertIn("Câmera desligada", statuses[-1])

    def test_subprocesso_camera_falha_nao_envia_imagem(self):
        import subprocess
        from angela.camera_vision import _isolated_capture_frame
        with patch(
            "angela.camera_vision.subprocess.run",
            return_value=subprocess.CompletedProcess([], 2, b"", b"private"),
        ):
            with self.assertRaisesRegex(VisionError, "não conseguiu obter"):
                _isolated_capture_frame()


if __name__ == "__main__":
    unittest.main()
