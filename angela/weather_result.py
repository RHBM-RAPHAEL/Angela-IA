"""Previsao ao vivo via Open-Meteo (sem chave ou geolocalizacao do dispositivo).

Erros de rede nao sao convertidos em temperaturas inventadas.
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode
from urllib.request import urlopen
from urllib.error import URLError
import json
import math


class WeatherError(Exception):
    pass


CODES = {
    0: "Céu limpo", 1: "Predominantemente limpo", 2: "Parcialmente nublado",
    3: "Encoberto", 45: "Neblina", 48: "Neblina com geada",
    51: "Garoa fraca", 53: "Garoa", 55: "Garoa forte",
    61: "Chuva fraca", 63: "Chuva", 65: "Chuva forte",
    71: "Neve fraca", 73: "Neve", 75: "Neve forte",
    80: "Pancadas leves", 81: "Pancadas de chuva", 82: "Pancadas fortes",
    95: "Trovoadas", 96: "Trovoadas e granizo", 99: "Granizo forte",
}


@dataclass(frozen=True)
class WeatherResult:
    title: str
    summary: str
    details: str
    source: str = "Dados: Open-Meteo"


def _json_get(url: str, opener, *, timeout: float = 9) -> dict:
    try:
        with opener(url, timeout=timeout) as response:
            payload = response.read(200_000)
        data = json.loads(payload.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("unexpected result")
        return data
    except (URLError, TimeoutError, OSError, ValueError, TypeError, UnicodeError, json.JSONDecodeError):
        raise WeatherError("Não consegui consultar a previsão agora. Verifique a conexão.") from None


def _number(value) -> str:
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        return "indisponível"
    return str(round(value))


def get_weather(city: str, *, opener=None) -> WeatherResult:
    """Consulta a cidade indicada; nao usa IP nem GPS como localizacao."""
    city = str(city).strip()
    if len(city) < 2 or len(city) > 65:
        raise WeatherError("Diga a cidade desejada, por exemplo: previsão do tempo em Itirapina.")
    fetch = opener or urlopen
    geo = _json_get(
        "https://geocoding-api.open-meteo.com/v1/search?" + urlencode(
            {"name": city, "count": 5, "language": "pt", "format": "json"}
        ), fetch,
    )
    options = geo.get("results") or []
    if not options:
        raise WeatherError("Não encontrei essa cidade. Pode repetir o nome?")
    location = next(
        (row for row in options if str(row.get("name", "")).casefold() == city.casefold()),
        options[0],
    )
    try:
        lat = float(location["latitude"])
        lon = float(location["longitude"])
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("invalid coordinates")
    except (KeyError, ValueError, TypeError):
        raise WeatherError("Não encontrei coordenadas confiáveis dessa cidade.") from None
    params = {
        "latitude": lat, "longitude": lon,
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
        "timezone": "auto", "forecast_days": 3,
    }
    forecast = _json_get(
        "https://api.open-meteo.com/v1/forecast?" + urlencode(params), fetch
    )
    current = forecast.get("current") or {}
    daily = forecast.get("daily") or {}
    if not isinstance(current, dict) or not current:
        raise WeatherError("O serviço não retornou a previsão atual.")
    code = current.get("weather_code")
    condition = CODES.get(code, "Condição não identificada")
    title = "Previsão · " + str(location.get("name") or city)[:75]
    if location.get("admin1"):
        title += " · " + str(location["admin1"])[:40]
    temperature = _number(current.get("temperature_2m"))
    feels = _number(current.get("apparent_temperature"))
    humidity = _number(current.get("relative_humidity_2m"))
    wind = _number(current.get("wind_speed_10m"))
    when = str(current.get("time", ""))[:16].replace("T", " às ")
    if temperature == "indisponível":
        raise WeatherError("O serviço não retornou uma temperatura válida.")
    summary = f"Em {location.get('name', city)}, agora faz {temperature} graus. {condition.lower()}."
    lines = [
        f"Agora: {temperature} °C | {condition}",
        f"Sensação térmica: {feels} °C",
        f"Umidade: {humidity}%",
        f"Vento: {wind} km/h",
        f"Atualizado: {when or 'horário não informado'} (hora local da cidade)",
        "",
        "Próximos 3 dias:",
    ]
    days = daily.get("time", []) if isinstance(daily, dict) else []
    for i, date in enumerate(days[:3]):
        def datum(key):
            values = daily.get(key) or []
            return values[i] if i < len(values) else None
        state = CODES.get(datum("weather_code"), "Condição variável")
        lines.append(
            f"{date}: {_number(datum('temperature_2m_min'))} a "
            f"{_number(datum('temperature_2m_max'))} °C, "
            f"chuva {_number(datum('precipitation_probability_max'))}% — {state}"
        )
    if len(days) == 0:
        lines.append("Previsão diária indisponível.")
    return WeatherResult(title=title, summary=summary, details="\n".join(lines))
