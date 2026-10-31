"""Visão da webcam com autorização individual e captura de quadro único.

A webcam é aberta SOMENTE depois que a pessoa autoriza uma pergunta visual.
O Qt Multimedia (já usado pelo HUD) fornece um único QVideoFrame; a câmera
é imediatamente desligada em finally. Não grava foto, vídeo ou áudio.
Nenhum modelo recebe pixels sem consentimento no AssistantEngine.
"""
from __future__ import annotations

from io import BytesIO
import os
from pathlib import Path
import re
import subprocess
import sys

from PIL import Image, UnidentifiedImageError

from .actions import normalize
from .command_quality import fold
from .audit_log import record
from .screen_vision import ScreenFrame, VisionError, VisionRequest, analyze_frame
from .perf_metrics import timed

_MAX_DIMENSION = 1280
_MAX_BYTES = 3_000_000
_MAX_QUESTION_CHARS = 400


def parse_camera_request(text: str) -> VisionRequest | None:
    """Identifica pedidos sobre a câmera, nunca perguntas de configuração."""
    if not isinstance(text, str):
        return None
    original = text.strip()
    if not original or len(original) > _MAX_QUESTION_CHARS:
        return None
    spoken = " ".join(re.sub(r"[^a-z0-9]+", " ", normalize(original)).split())
    if re.match(
        r"^(?:como(?! estou\b)|por que|porque|tutorial|ensine|me ensine|"
        r"o que e\b|qual (?:a|o) melhor\b)", spoken
    ):
        return None
    if re.search(
        r"\b(?:configurar|instalar|permissao|desinstalar|consertar|"
        r"desativar|desligar|fechar|parar|paralisa|parar de|"
        r"gravar|filmagem|filmar|stream|transmitir|"
        r"chamada de video|videochamada|camera de seguranca)\b", spoken
    ):
        return None
    cam = re.search(
        r"\b(?:camera|camara|webcam|camera frontal|camera integrada|camera do notebook)\b",
        spoken
    )
    if not cam:
        return None
    # Um pedido para abrir a câmera inicia APENAS a confirmação de foto.
    if not re.search(
        r"\b(?:olha|olhe|ve|ver|veja|vendo|enxerga|enxergue|"
        r"analisa|analise|analisar|mostra|mostre|"
        r"descreve|descreva|foto|fotografia|captura|"
        r"o que|qual|quais|como estou|me veja|me ve|"
        r"liga|ligar|ative|ativar|abra|abre|abrir|pode)\b", spoken
    ):
        return None
    return VisionRequest("camera", original)


def _qt_capture_frame(timeout_ms: int = 4500, *, status_cb=None) -> bytes:
    """Obtém um único JPEG via QVideoSink e encerra a webcam em finally.

    Qt é inicializado dentro da thread que processa o pedido; não move QObjects
    entre threads. QEventLoop local só aguarda um frame ou timeout.
    """
    if sys.platform != "win32":
        raise VisionError("A câmera da Ângela está disponível somente no Windows.")
    from PySide6.QtCore import QCoreApplication, QByteArray, QBuffer, QEventLoop, QIODevice, Qt, QTimer
    from PySide6.QtMultimedia import QCamera, QMediaCaptureSession, QMediaDevices, QVideoSink

    if QCoreApplication.instance() is None:
        raise VisionError("A interface da Ângela precisa estar aberta para usar a câmera.")

    devices = list(QMediaDevices.videoInputs())
    if not devices:
        raise VisionError("Nenhuma webcam foi encontrada. Confira a conexão e as permissões do Windows.")
    try:
        selected_index = int(os.environ.get("ANGELA_CAMERA_INDEX", "0"))
    except ValueError:
        raise VisionError("O índice de webcam configurado é inválido.") from None
    if not (0 <= selected_index < len(devices)):
        raise VisionError("A webcam selecionada não existe. Confira ANGELA_CAMERA_INDEX.")

    camera = QCamera(devices[selected_index])
    session = QMediaCaptureSession()
    sink = QVideoSink()
    event_loop = QEventLoop()
    deadline = QTimer()
    deadline.setSingleShot(True)
    result: list[bytes] = []
    errors: list[str] = []

    def handle_frame(video_frame):
        if result or not video_frame.isValid():
            return
        qimage = video_frame.toImage()
        if qimage.isNull() or qimage.width() < 80 or qimage.height() < 80:
            return
        qimage = qimage.scaled(
            _MAX_DIMENSION, _MAX_DIMENSION,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        storage = QByteArray()
        output = QBuffer(storage)
        try:
            if output.open(QIODevice.OpenModeFlag.WriteOnly) and qimage.save(output, "JPEG", 77):
                data = bytes(storage)
                if 0 < len(data) <= _MAX_BYTES:
                    result.append(data)
        finally:
            output.close()
        if result:
            event_loop.quit()

    def handle_error(_code, _description):
        errors.append("camera_error")
        event_loop.quit()

    sink.videoFrameChanged.connect(handle_frame)
    camera.errorOccurred.connect(handle_error)
    deadline.timeout.connect(event_loop.quit)
    try:
        session.setCamera(camera)
        session.setVideoSink(sink)
        camera.start()
        if status_cb is not None:
            status_cb("Câmera ligada · capturando uma única foto")
        deadline.start(max(1000, min(timeout_ms, 8000)))
        if not result and not errors:
            event_loop.exec()
    except (RuntimeError, OSError, ValueError):
        raise VisionError("Não consegui ligar a webcam. Verifique se outro aplicativo a está usando.") from None
    finally:
        # Solta a webcam SEMPRE, inclusive após timeout e erros de conversão.
        deadline.stop()
        camera.stop()
        session.setVideoSink(None)
        session.setCamera(None)
        if status_cb is not None:
            status_cb("Câmera desligada · foto concluída ou cancelada")

    if errors:
        raise VisionError("A webcam apresentou uma falha. Confira as permissões do Windows.")
    if not result:
        raise VisionError("A webcam não forneceu imagem a tempo. Verifique a tampa ou outro aplicativo.")
    return result[0]


def _isolated_capture_frame(*, status_cb=None) -> bytes:
    """Captura em processo Qt separado para não travar o GIL nem o HUD.

    O filho termina após um JPEG ou é encerrado automaticamente no timeout.
    Imagens transitam apenas por pipes em memória e não aparecem em logs.
    """
    if sys.platform != "win32":
        raise VisionError("A câmera da Ângela está disponível somente no Windows.")
    command = [sys.executable, "-m", "angela.camera_worker"]
    project_root = Path(__file__).resolve().parent.parent
    # Evite expor segredos de API ao processo que somente lê pixels.
    child_env = {
        key: value for key, value in os.environ.items()
        if not any(word in key.upper() for word in (
            "API_KEY", "TOKEN", "PASSWORD", "SECRET", "CREDENTIAL",
        ))
    }
    try:
        if status_cb:
            status_cb("Câmera ligada · capturando uma única foto")
        completed = subprocess.run(
            command, cwd=str(project_root), env=child_env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=14, check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired:
        raise VisionError(
            "A webcam demorou demais. O processo da câmera foi encerrado."
        ) from None
    except (OSError, ValueError):
        raise VisionError(
            "Não consegui iniciar a webcam. Confira as permissões do Windows."
        ) from None
    finally:
        if status_cb:
            status_cb("Câmera desligada · captura concluída ou cancelada")
    if completed.returncode != 0:
        raise VisionError(
            "A webcam não conseguiu obter a foto. Confira se está livre e autorizada."
        )
    if not 0 < len(completed.stdout) <= _MAX_BYTES:
        raise VisionError("A câmera retornou uma imagem inválida.")
    return completed.stdout


def capture_camera(*, frame_provider=None, status_cb=None) -> ScreenFrame:
    """Obtém uma única foto JPEG em memória; frame_provider é só para testes."""
    if frame_provider is None:
        jpeg = _isolated_capture_frame(status_cb=status_cb)
    else:
        jpeg = frame_provider()
    if not isinstance(jpeg, bytes) or not jpeg or len(jpeg) > _MAX_BYTES:
        raise VisionError("A webcam não forneceu uma imagem válida.")
    try:
        with Image.open(BytesIO(jpeg)) as original:
            image = original.convert("RGB")
            image.thumbnail((_MAX_DIMENSION, _MAX_DIMENSION))
            width, height = image.size
            if width < 80 or height < 80:
                raise VisionError("A imagem da webcam está pequena demais.")
            with BytesIO() as buffer:
                image.save(buffer, "JPEG", quality=78, optimize=True)
                payload = buffer.getvalue()
            if not payload or len(payload) > _MAX_BYTES:
                raise VisionError("A imagem da webcam ficou grande demais.")
    except VisionError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, TypeError):
        raise VisionError("A webcam devolveu uma imagem ilegível.") from None
    return ScreenFrame(payload, width, height, "camera")


def camera_question_for_model(spoken: str) -> str:
    """Ask about visual content, not executing the user's UI commands.

    The camera has already been captured after consent. Asking the model
    'activate camera' invites a false capability refusal.
    """
    normalized = fold(spoken)
    if "desenho" in normalized or "figura" in normalized:
        return "Descreva o desenho ou figura visível na foto, em uma frase objetiva."
    if "equacao" in normalized or "expressao matematica" in normalized:
        return ("Leia a equação inteira da foto e, se os símbolos estiverem "
                "legíveis, resolva-a. Se houver símbolos ambíguos, diga quais "
                "e peça uma imagem mais nítida, sem inventar o resultado.")
    if any(term in normalized for term in (
        "o que esta vendo", "o que voce ve", "olhe na camera", "olhe na camara",
        "ativa a camera", "ative a camera", "me veja", "veja pela camera",
    )):
        return "Descreva brevemente o que aparece na foto já capturada."
    return spoken


def clean_camera_analysis(reply: str) -> str:
    """Drop only a false camera-activation disclaimer after actual capture.

    Never fake a scene or turn a failed vision analysis into a successful one.
    """
    if not isinstance(reply, str):
        return ""
    cleaned = reply.strip()
    cleaned = re.sub(
        r"(?is)^não posso ativar a câmera,?\s*pois já estou "
        r"analisando a foto que você enviou\.\s*",
        "", cleaned, count=1
    ).strip()
    return cleaned or reply.strip()


def analyze_camera(request: VisionRequest, api_key: str,
                   *, status_cb=None, capturer=capture_camera,
                   analyzer=analyze_frame, identity_profile=None) -> str:
    """Capture e análise limitadas; nada é salvo em disco ou nos logs."""
    if request.scope != "camera":
        return "Essa solicitação não é de câmera."
    try:
        with timed("camera_capture"):
            frame = capturer(status_cb=status_cb) if status_cb else capturer()
        record("camera_capture", width=frame.width, height=frame.height,
               bytes=len(frame.jpeg_bytes), scope="camera")
        # Após consentimento, comparar localmente somente se houver perfil.
        # Nenhum vetor biométrico é enviado ao modelo remoto.
        matched_name = None
        if identity_profile is not None and identity_profile.enrolled():
            try:
                matched_name = identity_profile.identify(frame.jpeg_bytes)
            except Exception:
                record("face_match_unavailable", category="local")
        with timed("visual_analysis"):
            result = clean_camera_analysis(analyzer(
                frame, camera_question_for_model(request.question), api_key
            ))
        record("camera_analysis", result_ready=bool(result))
        if matched_name == "Rafael":
            return "O rosto parece corresponder ao cadastro de Rafael. " + result
        return result
    except VisionError as exc:
        record("camera_error", category="capture")
        return str(exc)
    except Exception as exc:
        record("camera_error", category=type(exc).__name__)
        return "Não consegui analisar a imagem da câmera. Tente novamente."
