"""Download official OpenCV Zoo YuNet/SFace models once, no personal data."""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
from urllib.request import urlopen

from .face_identity import MODEL_ROOT

ASSETS = {
    "face_detection_yunet_2023mar.onnx": (
        "https://huggingface.co/opencv/opencv_zoo/resolve/main/"
        "models/face_detection_yunet/face_detection_yunet_2023mar.onnx?download=true",
        150_000, 1_000_000,
    ),
    "face_recognition_sface_2021dec_int8.onnx": (
        "https://huggingface.co/opencv/opencv_zoo/resolve/main/"
        "models/face_recognition_sface/face_recognition_sface_2021dec_int8.onnx?download=true",
        7_000_000, 20_000_000,
    ),
}


def main() -> None:
    MODEL_ROOT.mkdir(parents=True, exist_ok=True)
    for name, (url, minimum, maximum) in ASSETS.items():
        target = MODEL_ROOT / name
        if target.is_file() and minimum <= target.stat().st_size <= maximum:
            print("MODEL_PRESENT", name, target.stat().st_size)
            continue
        temporary = target.with_suffix(target.suffix + ".download")
        try:
            digest = hashlib.sha256()
            size = 0
            with urlopen(url, timeout=40) as response, temporary.open("wb") as output:
                while True:
                    chunk = response.read(128 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > maximum:
                        raise ValueError("Downloaded model unexpectedly large")
                    digest.update(chunk)
                    output.write(chunk)
            if not minimum <= size <= maximum:
                raise ValueError("Incomplete download (possibly LFS pointer)")
            with temporary.open("rb") as model:
                if model.read(100).lstrip().startswith((b"<", b"version https")):
                    raise ValueError("Expected binary ONNX model")
            os.replace(temporary, target)
            print("MODEL_READY", name, size, digest.hexdigest()[:14])
        finally:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
