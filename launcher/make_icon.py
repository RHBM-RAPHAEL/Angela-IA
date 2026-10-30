"""Transforma o PNG original da Angela em .ico multi-resolucao para Windows."""
from pathlib import Path
from PIL import Image, ImageOps

SOURCE = Path(r"D:\RHBM TechWorks\Meus Softwares\Angela-IA\assets\icone angela.png")
TARGET = Path(__file__).resolve().parent / "assets" / "AngelaAI.ico"

if __name__ == "__main__":
    if not SOURCE.exists():
        raise SystemExit("PNG de origem nao encontrado: " + str(SOURCE))
    with Image.open(SOURCE) as source:
        print("SOURCE", source.size, source.mode)
        image = source.convert("RGBA")
        if image.width != image.height:
            side = max(image.size)
            canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
            canvas.alpha_composite(image, ((side-image.width)//2, (side-image.height)//2))
            image = canvas
        image = ImageOps.contain(image, (256, 256), Image.Resampling.LANCZOS)
        image.save(TARGET, format="ICO", sizes=[
            (16,16), (24,24), (32,32), (48,48),
            (64,64), (128,128), (256,256)
        ])
    with Image.open(TARGET) as icon:
        print("ICON_READY", str(TARGET), "COUNT", len(icon.ico.sizes()),
              "SIZES", sorted(icon.ico.sizes()), "BYTES", TARGET.stat().st_size)
