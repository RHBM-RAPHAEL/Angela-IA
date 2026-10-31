"""Opt-in local face enrollment and comparison, never remote authentication.

Images are processed in memory and discarded. Face templates are protected
with Windows DPAPI CurrentUser. No name is assigned just from spoken claims.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import math
import os
from pathlib import Path
import re
import sys
from tempfile import NamedTemporaryFile

from .command_quality import fold

MODEL_ROOT = Path(__file__).resolve().parent.parent / "models" / "face"
DETECTOR = MODEL_ROOT / "face_detection_yunet_2023mar.onnx"
RECOGNIZER = MODEL_ROOT / "face_recognition_sface_2021dec_int8.onnx"
PROFILE = Path.home() / "AppData" / "Local" / "AngelaAI" / "face_profile.dat"
SIMILARITY_THRESHOLD = 0.50


class FaceIdentityError(Exception):
    pass


def face_intent(text: str) -> str | None:
    """Explicit intro, enroll, verify and deletion requests."""
    if not isinstance(text, str) or len(text) > 250:
        return None
    s = fold(text)
    s = re.sub(r"^(?:angela|anjela|ei angela)\s+", "", s).strip()
    if re.fullmatch(r"(?:eu sou(?: o)?|meu nome e|me chamo|pode me chamar de)\s+rafael", s):
        return "introduce"
    if re.search(r"\b(?:apague|apagar|exclua|excluir|esqueca|remova|remover)\b", s) and re.search(
        r"\b(?:meu rosto|meu cadastro facial|minha biometria|referencia facial)\b", s
    ):
        return "delete"
    if re.search(r"\b(?:cadastre|cadastrar|memorize|memoriz[ae]|guarde|registr[ae]|salve|salvar)\b", s) and re.search(
        r"\b(?:meu rosto|minha face|reconhecimento facial)\b", s
    ):
        return "enroll"
    # "Você me conhece pela câmera?" pode ser erro acústico de "reconhece".
    # Tratar somente na pergunta explícita SOBRE a câmera/rosto.
    if re.fullmatch(r"(?:voce\s+)?(?:me\s+)?(?:conhece|conhecer)\s+(?:me\s+)?(?:pela|pelo|na|no|por|atraves da|atraves do)\s+(?:camera|webcam|face|rosto)", s):
        return "recognize"
    if re.search(r"\b(?:reconhec[ae]|reconhecer|identifiqu[ae]|identifica|identificar|quem sou eu|sabe quem sou|sabe quem eu sou)\b", s) and (
        re.search(r"\b(?:rosto|face|camera|webcam|me)\b", s) or "quem sou eu" in s or "sabe quem sou" in s
    ):
        return "recognize"
    return None


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def _blob(data: bytes):
    buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    return _Blob(len(data), buffer), buffer


def _dpapi(data: bytes, *, decrypt: bool) -> bytes:
    if sys.platform != "win32":
        raise FaceIdentityError("O cadastro facial protegido exige Windows.")
    if not data or len(data) > 20_000:
        raise FaceIdentityError("Cadastro facial inválido.")
    source, keep = _blob(data)
    result = _Blob()
    library = ctypes.WinDLL("crypt32", use_last_error=True)
    free = ctypes.WinDLL("kernel32", use_last_error=True).LocalFree
    method = library.CryptUnprotectData if decrypt else library.CryptProtectData
    if decrypt:
        method.argtypes = [ctypes.POINTER(_Blob), ctypes.c_void_p, ctypes.c_void_p,
                           ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD,
                           ctypes.POINTER(_Blob)]
        success = method(ctypes.byref(source), None, None, None, None, 0,
                         ctypes.byref(result))
    else:
        method.argtypes = [ctypes.POINTER(_Blob), ctypes.c_wchar_p,
                           ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                           wintypes.DWORD, ctypes.POINTER(_Blob)]
        success = method(ctypes.byref(source), "AngelaAI local face", None,
                         None, None, 0, ctypes.byref(result))
    if not success:
        raise FaceIdentityError("Não foi possível proteger seu cadastro facial.")
    try:
        return ctypes.string_at(result.pbData, result.cbData)
    finally:
        free.argtypes = [ctypes.c_void_p]
        free(result.pbData)


def _normalize(vec) -> list[float]:
    try:
        values = [float(x) for x in vec]
    except (ValueError, TypeError):
        raise FaceIdentityError("Modelo biométrico inválido.") from None
    if not 32 <= len(values) <= 1024 or not all(math.isfinite(x) for x in values):
        raise FaceIdentityError("Modelo biométrico inválido.")
    magnitude = math.sqrt(sum(x * x for x in values))
    if magnitude < 1e-9:
        raise FaceIdentityError("Não consegui calcular o rosto.")
    return [x / magnitude for x in values]


def embedding_from_jpeg(jpeg: bytes) -> list[float]:
    """Local YuNet+SFace: exactly one clear face, no image stored."""
    if not DETECTOR.is_file() or not RECOGNIZER.is_file():
        raise FaceIdentityError("Os modelos faciais locais ainda não estão instalados.")
    if not isinstance(jpeg, bytes) or not 0 < len(jpeg) <= 3_000_000:
        raise FaceIdentityError("Imagem inválida.")
    try:
        import cv2
        import numpy as np
    except ImportError:
        raise FaceIdentityError("O módulo OpenCV não está instalado.") from None
    image = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None or min(image.shape[:2]) < 80:
        raise FaceIdentityError("Não consegui ler a foto.")
    try:
        detector = cv2.FaceDetectorYN.create(
            str(DETECTOR), "", (image.shape[1], image.shape[0]),
            score_threshold=0.85
        )
        _status, faces = detector.detect(image)
        if faces is None or len(faces) != 1:
            raise FaceIdentityError("Preciso ver um único rosto bem iluminado.")
        face = faces[0]
        if float(face[2]) < 100 or float(face[3]) < 100:
            raise FaceIdentityError("Aproxime o rosto da câmera.")
        model = cv2.FaceRecognizerSF.create(str(RECOGNIZER), "")
        features = model.feature(model.alignCrop(image, face)).reshape(-1).tolist()
        return _normalize(features)
    except FaceIdentityError:
        raise
    except (ValueError, RuntimeError, cv2.error):
        raise FaceIdentityError("Não consegui extrair um rosto confiável.") from None


def cosine_similarity(first, second) -> float:
    left, right = _normalize(first), _normalize(second)
    if len(left) != len(right):
        return -1.0
    return sum(x*y for x,y in zip(left,right))


class FaceProfile:
    def __init__(self, path=None, *, extract=None, protect=None, unprotect=None):
        self.path = Path(path) if path else PROFILE
        self.extract = extract or embedding_from_jpeg
        self.protect = protect or (lambda data: _dpapi(data, decrypt=False))
        self.unprotect = unprotect or (lambda data: _dpapi(data, decrypt=True))

    def enrolled(self) -> bool:
        return self.path.is_file()

    def enroll(self, jpeg: bytes, *, name: str = "Rafael") -> None:
        if name != "Rafael":
            raise FaceIdentityError("Só Rafael pode ser cadastrado neste perfil.")
        values = _normalize(self.extract(jpeg))
        payload = json.dumps({"v":1,"name":name,"embedding":values},
                             separators=(",",":")).encode("utf-8")
        ciphertext = self.protect(payload)
        if not isinstance(ciphertext, bytes) or not ciphertext:
            raise FaceIdentityError("Não foi possível proteger o cadastro.")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = None
        try:
            with NamedTemporaryFile(dir=self.path.parent, prefix="face_",
                                    suffix=".tmp", delete=False) as handle:
                temp = Path(handle.name)
                handle.write(ciphertext)
            os.replace(temp, self.path)
        finally:
            if temp is not None:
                temp.unlink(missing_ok=True)

    def identify(self, jpeg: bytes) -> str | None:
        if not self.enrolled():
            return None
        try:
            profile = json.loads(self.unprotect(self.path.read_bytes()).decode("utf-8"))
            if profile.get("v") != 1 or profile.get("name") != "Rafael":
                raise ValueError("unknown version")
            reference = _normalize(profile["embedding"])
        except (TypeError, ValueError, KeyError, UnicodeError):
            raise FaceIdentityError("Seu cadastro facial precisa ser refeito.") from None
        observed = self.extract(jpeg)
        return "Rafael" if cosine_similarity(reference, observed) >= SIMILARITY_THRESHOLD else None

    def forget(self) -> bool:
        if not self.path.exists():
            return False
        self.path.unlink()
        return True
