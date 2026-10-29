"""Correções conservadoras de transcrições Vosk com nomes em inglês.

Mantém a frase original intacta quando não há correção específica.
"""
from __future__ import annotations
import re


def correct_transcript(text: str) -> str:
    spoken = text.strip()
    spoken = re.sub(r"^abri (?=(?:as? )?configuraç(?:ão|ões)\b)", "abra ", spoken, flags=re.IGNORECASE)
    spoken = re.sub(r'^abraço\s+(?=(?:o\s+)?canal\s+do\s+youtube\b)',
                    'abra ', spoken, flags=re.IGNORECASE)
    # Corrige 'liste meus projetos' quando Vosk reconhece 'alice'/'este'.
    spoken = re.sub(r'^(?:alice|alise|alisse|este)\s+(?=(?:os\s+)?meus\s+projetos\b)',
                    'liste ', spoken, flags=re.IGNORECASE)
    # Corrige variações observadas no Vosk apenas em contexto inequívoco.
    if re.search(r"\b(?:projetos|pastas)\b", spoken, flags=re.IGNORECASE) and re.search(r"\b(?:meus? softwares?|meus projetos)\b", spoken, flags=re.IGNORECASE):
        spoken = re.sub(r"^(?:este|list|lixo e quase)\s+(?=(?:os |quais )?projetos\b)", "liste ", spoken, flags=re.IGNORECASE)
    replacements = [
        (r"\b(?:bilhete rabi|git rabi|gite rabi|giti rabi|giti hube|gite hub|git hub|guiti rab|giti rub)\b", "GitHub"),
        (r"\b(?:vi es code|v s code|ves code|vence code|viesse code|visual estúdio code|visual estudio code|vis code|viz code|vs cod|vscode)\b", "VS Code"),
        (r"\b(?:gi mail|g mail|je mail|gmeil|gemeio)\b", "Gmail"),
        (r"\b(?:blutufi|blututi|blu tuf|blutu)\b", "Bluetooth"),
        (r"\b(?:no se de|no s s d|no esse esse de|no ssd de)\b", "no SSD D"),
        (r"\b(?:opera g x|opera ge xis|opera gex)\b", "Opera GX"),
    ]
    for pattern, corrected in replacements:
        spoken = re.sub(pattern, corrected, spoken, flags=re.IGNORECASE)
    return spoken
