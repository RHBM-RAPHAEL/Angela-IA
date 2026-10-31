"""Safe mixed Portuguese/English proper-name interpretation for the pt-BR ASR.

This is a *postprocessor*, not a multilingual acoustic model. It repairs
specific phonetic outputs only when there is strong lexical evidence.
Never guess an executable, URL, or an arbitrary name from vague phrases.
"""
from __future__ import annotations

import re

from .actions import normalize


_NAMES: tuple[tuple[str, str], ...] = (
    ("Spotify",
     r"spotify|spotifai|spotifay|spotifi|spotfy|espotifai|"
     r"espotifay|espotifi|esportifai|esporte\s+fai|esporte\s+fine|"
     r"esporte\s+fai\s+no|spot\s+fai|spot\s+fy|espoti\s+fai"),
    ("Valorant",
     r"valorant|valorante|valoran|valoranti|valourant|valourante|"
     r"valo\s+rant|valo\s+rante|valor\s+ant|valor\s+ante|"
     r"valo\s+rente|valor\s+rante"),
    ("Discord", r"discord|discort|discorde|dis\s+cord"),
    ("Roblox", r"roblox|roblocks|robloquis|ro\s+blox"),
    ("Steam", r"steam|stim|stiem|istim|is\s+tim"),
    ("YouTube", r"youtube|you\s+tube|iu\s+tube|iutube|iu\s+tubi"),
    ("GitHub", r"github|git\s+hub|guiti\s+hub|gite\s+hub"),
    ("VS Code", r"vs\s+code|vscode|v\s+s\s+code|vi\s+es\s+code|"
                r"visual\s+studio\s+code|visual\s+estudio\s+code"),
)
_COMPILED = tuple((label, re.compile(r"\b(?:" + alternatives + r")\b"))
                  for label, alternatives in _NAMES)

# Strong acoustic spelling evidence is safe to canonicalize without assuming
# intent. "esporte" alone, "valor", "curso", "steam" as vapor are never guessed.
_MISHEARD_CUES = {
    "Spotify": r"\b(?:esporte|espot|espotifi|spot|esportifai)\b",
    "Valorant": r"\b(?:valor|valora|valorante|valoran|valo|valorem)\b",
    "Discord": r"\b(?:discort|discorde|discor)\b",
    "Roblox": r"\b(?:roblocks|robloquis|roblox|roblo)\b",
    "Steam": r"\b(?:stim|steam|stiem|istim)\b",
    "YouTube": r"\b(?:iu|iutube|youtube|tubi)\b",
    "GitHub": r"\b(?:git|gite|guiti|github)\b",
    "VS Code": r"\b(?:viesse|vence|verso|code|estudio|studio|visual)\b",
}
_ACTION = re.compile(r"^(?:abra|abre|abrir|inicie|inicia|iniciar|execute|"
                     r"executa|acesse|acessar|feche|fecha|fechar|"
                     r"jogue|jogar|iniciar o jogo|"
                     r"coloque|tocar|toque|"
                     r"quero jogar|quero abrir|quero ouvir|"
                     r"pode abrir|poderia abrir|voce pode abrir)\b")


def canonicalize_names(text: str) -> str:
    """Repair phonetic English proper names, leave other speech unchanged."""
    if not isinstance(text, str) or not 0 < len(text) <= 450:
        return text
    normalized = normalize(text)
    if not any(regex.search(normalized) for _, regex in _COMPILED):
        return text
    result = text
    for label, pattern in _COMPILED:
        # Evaluate span against the original with case-insensitive accents
        # already handled by normalized matching; use original char positions
        # only if normalization did not change string length.
        folded = normalize(result)
        matches = list(pattern.finditer(folded))
        if not matches or len(folded) != len(result):
            # Regex on original covers accents in variations with same glyphs,
            # but for special accent folds use a boundary-preserving tokenizer.
            tokenized = re.findall(r"\S+|\s+", result)
            # For these uncommon strings, avoid changing unrelated words.
            canonical = re.compile(pattern.pattern.replace("estudio", "est[úu]dio"),
                                   re.IGNORECASE)
            result = canonical.sub(label, result)
            continue
        for match in reversed(matches):
            result = result[:match.start()] + label + result[match.end():]
    return result


def recognized_named_app(text: str) -> str | None:
    """An explicit user request that contains exactly one recognizable app.

    Used for n-best hypothesis selection. Do not infer intent from standalone
    nouns or other peoples' mentions of a game.
    """
    spoken = normalize(text)
    spoken = re.sub(r"^(?:(?:oi|ei)\s+)?(?:angela|anjela)\s+", "", spoken)
    if not _ACTION.match(spoken):
        return None
    mentioned = [
        label for label, regex in _COMPILED
        if regex.search(spoken)
    ]
    return mentioned[0] if len(mentioned) == 1 else None


def prefer_better_english_hypothesis(
    primary: str, alternative: str, *, delta: float
) -> bool:
    """Only prefer a near-tied ASR alternative with an unambiguous exact name.

    Protects against 'abra o esporte' being silently converted into Spotify
    unless the alternate result really contains 'Spotify' as heard by Vosk.
    """
    if not 0 <= delta <= 0.10:
        return False
    target = recognized_named_app(alternative)
    if target not in {"Spotify", "Valorant", "Discord", "Roblox", "Steam", "YouTube", "GitHub", "VS Code"}:
        return False
    folded_alt = normalize(alternative)
    if not re.search(r"\b" + re.escape(normalize(target)) + r"\b", folded_alt):
        return False
    norm = normalize(primary)
    if not _ACTION.match(norm):
        return False
    # Distinctive initial action must not change (open != close).
    p_open = bool(re.match(r"^(?:abra|abre|abrir|inicie|inicia|iniciar|execute|executa|acesse|acessar|quero abrir|pode abrir|poderia abrir)\b", norm))
    a_norm = normalize(alternative)
    a_open = bool(re.match(r"^(?:abra|abre|abrir|inicie|inicia|iniciar|execute|executa|acesse|acessar|quero abrir|pode abrir|poderia abrir)\b", a_norm))
    if p_open != a_open:
        return False
    present = recognized_named_app(primary)
    if present is not None and present != target:
        return False
    if present == target:
        return False  # Main hypothesis already conveys the correct app.
    if not re.search(_MISHEARD_CUES[target], norm):
        return False  # Not acoustic variants of this specific product.
    # Both hypotheses must be short and refer to similar utterance lengths.
    if len(norm.split()) > 17 or abs(len(norm.split()) - len(a_norm.split())) > 3:
        return False
    return True
