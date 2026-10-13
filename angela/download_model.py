"""Instala o modelo pequeno de reconhecimento de português do Vosk."""
from __future__ import annotations

from pathlib import Path
import shutil
import tempfile
from urllib.request import urlopen
from zipfile import ZipFile

MODEL_NAME = "vosk-model-small-pt-0.3"
MODEL_URL = f"https://alphacephei.com/vosk/models/{MODEL_NAME}.zip"
MODELS_DIR = Path(__file__).resolve().parents[1] / "models"
MODEL_PATH = MODELS_DIR / MODEL_NAME


def install_model() -> Path:
    if MODEL_PATH.is_dir() and (MODEL_PATH / "am").is_dir():
        print(f"Modelo já instalado em {MODEL_PATH}")
        return MODEL_PATH

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    print("Baixando modelo de português (Vosk). É necessário internet apenas nesta etapa...")
    with tempfile.TemporaryDirectory(prefix="angela_model_") as tmp:
        zip_path = Path(tmp) / "model.zip"
        with urlopen(MODEL_URL, timeout=90) as source, zip_path.open("wb") as target:
            shutil.copyfileobj(source, target)
        print("Extraindo modelo...")
        root = MODELS_DIR.resolve()
        with ZipFile(zip_path) as archive:
            for item in archive.infolist():
                dest = (MODELS_DIR / item.filename).resolve()
                if not dest.is_relative_to(root):
                    raise ValueError("Caminho inválido encontrado no arquivo de modelo.")
            archive.extractall(MODELS_DIR)
    if not MODEL_PATH.is_dir() or not (MODEL_PATH / "am").is_dir():
        raise RuntimeError("Falha ao extrair o modelo. Verifique espaço em disco.")
    print(f"Modelo instalado: {MODEL_PATH}")
    return MODEL_PATH


if __name__ == "__main__":
    install_model()
