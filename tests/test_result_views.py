"""Regressoes do roteamento visual; sem abrir navegador ou consultar rede real."""
import json
import os
import unittest
from unittest.mock import Mock, patch

from angela.assistant import AssistantEngine
from angela.result_routing import plan_result_request, youtube_video_id
from angela.weather_result import WeatherError, WeatherResult, get_weather
from angela.voice_coordinator import VoiceCoordinator
from angela.result_window import safe_video_url


class Response:
    def __init__(self, data):
        self.data = data
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, limit=None):
        return json.dumps(self.data).encode("utf-8")


class FakeChat:
    def __init__(self):
        self.history = []
        self.available = False
        self.questions = []
    def ask(self, question):
        self.questions.append(question)
        return "Uma explicação sobre Python e seus usos."


def fake_weather_opener(url, timeout=9):
    if "geocoding" in url:
        return Response({"results": [{
            "name": "Itirapina", "admin1": "São Paulo",
            "latitude": -22.25, "longitude": -47.82,
        }]})
    return Response({
        "current": {
            "temperature_2m": 25.2, "apparent_temperature": 26.5,
            "relative_humidity_2m": 71, "wind_speed_10m": 7,
            "weather_code": 2, "time": "2026-10-29T13:30",
        },
        "daily": {
            "time": ["2026-10-29", "2026-10-30", "2026-10-31"],
            "temperature_2m_max": [28, 27, 25],
            "temperature_2m_min": [17, 18, 16],
            "precipitation_probability_max": [20, 60, 15],
            "weather_code": [2, 63, 1],
        },
    })


class ResultRoutingTests(unittest.TestCase):
    def test_weather_formal_and_simple(self):
        for text in [
            "Ângela, por favor, me mostre a previsão do tempo em Itirapina",
            "Mostre a temperatura em Itirapina",
            "Você pode me mostrar o clima em Itirapina?",
        ]:
            with self.subTest(text=text):
                result = plan_result_request(text)
                self.assertIsNotNone(result)
                self.assertEqual(result.kind, "weather")
                self.assertEqual(result.subject, "itirapina")

    def test_weather_sem_cidade_exige_configuracao(self):
        with patch.dict(os.environ, {"ANGELA_WEATHER_CITY": ""}):
            result = plan_result_request("me mostre a previsão do tempo")
            self.assertEqual(result.kind, "weather")
            self.assertFalse(result.subject)

    def test_weather_com_cidade_configurada(self):
        with patch.dict(os.environ, {"ANGELA_WEATHER_CITY": "Itirapina"}):
            result = plan_result_request("mostre a previsão do tempo")
            self.assertEqual(result.subject, "Itirapina")

    def test_hora_fica_na_voz(self):
        result = plan_result_request("me mostre a hora atual")
        self.assertEqual(result.kind, "voice")
        engine = AssistantEngine(chat=FakeChat())
        self.assertIn("Agora são", engine.reply("mostre a hora"))
        self.assertIsNone(engine.last_result_view)

    def test_video_direto_e_busca(self):
        direct = plan_result_request(
            "Mostre o vídeo https://youtu.be/dQw4w9WgXcQ"
        )
        self.assertEqual(direct.kind, "video")
        self.assertEqual(direct.url, "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ")
        search = plan_result_request("Me mostre um vídeo de programação Python")
        self.assertEqual(search.kind, "video")
        self.assertIn("youtube.com/results?search_query=", search.url)
        self.assertIn("python", search.url)

    def test_hostile_video_urls_rejected(self):
        for url in [
            "https://youtube.com.evil.test/watch?v=dQw4w9WgXcQ",
            "http://youtu.be/dQw4w9WgXcQ",
            "https://user:pass@youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ.fake",
        ]:
            self.assertIsNone(youtube_video_id("Mostre o vídeo " + url))
        self.assertFalse(safe_video_url("javascript:alert(1)"))
        self.assertFalse(safe_video_url("https://youtube.com.evil.test/watch"))
        self.assertTrue(safe_video_url("https://www.youtube.com/results?search_query=python"))

    def test_generic_text_has_window_payload(self):
        chat = FakeChat()
        engine = AssistantEngine(chat=chat)
        reply = engine.reply("Ângela, mostre para mim a diferença entre Python e Java")
        self.assertEqual(engine.last_result_view["kind"], "text")
        self.assertIn("Python", engine.last_result_view["text"])
        self.assertNotIn("<script>", engine.last_result_view["text"])
        self.assertTrue(reply)
        self.assertEqual(len(chat.questions), 1)
        self.assertIsNone(engine.last_panel)
        engine.reply("Oi")
        self.assertIsNone(engine.last_result_view)

    def test_existing_actions_not_intercepted(self):
        for phrase in (
            "Abra calculadora", "Abra YouTube", "me mostre meus projetos",
            "o que aparece na minha tela?", "me mostre a câmera",
        ):
            self.assertIsNone(plan_result_request(phrase))

    def test_search_prefers_browser(self):
        engine = AssistantEngine(chat=FakeChat())
        with patch("angela.assistant.webbrowser.open", return_value=True) as opener:
            msg = engine.reply("Me mostre os resultados da busca sobre inteligência artificial")
        self.assertIn("navegador", msg)
        self.assertIn("https://www.google.com/search?q=", opener.call_args.args[0])
        self.assertIsNone(engine.last_result_view)

    def test_photo_search_uses_browser_images(self):
        engine = AssistantEngine(chat=FakeChat())
        with patch("angela.assistant.webbrowser.open", return_value=True) as opener:
            msg = engine.reply("mostre fotos de pugs pretos")
        self.assertIn("imagens", msg)
        self.assertIn("&tbm=isch", opener.call_args.args[0])
        self.assertIsNone(engine.last_result_view)

    def test_website_request_prefers_browser(self):
        plan = plan_result_request("me mostre o site do github")
        self.assertEqual(plan.kind, "browser")
        self.assertEqual(plan.subject, "github")

    def test_video_result_does_not_open_browser_unasked(self):
        engine = AssistantEngine(chat=FakeChat())
        with patch("angela.assistant.webbrowser.open") as opener:
            msg = engine.reply("mostre vídeo de computação")
        self.assertIn("janela", msg)
        self.assertEqual(engine.last_result_view["kind"], "video")
        opener.assert_not_called()

    def test_weather_renders_real_provider_data(self):
        data = get_weather("Itirapina", opener=fake_weather_opener)
        self.assertIn("25 graus", data.summary)
        self.assertIn("Próximos 3 dias", data.details)
        self.assertIn("Open-Meteo", data.source)
        engine = AssistantEngine(chat=FakeChat())
        with patch("angela.assistant.get_weather", return_value=data):
            answer = engine.reply("Me mostre previsão do tempo em Itirapina")
        self.assertIn("25 graus", answer)
        self.assertEqual(engine.last_result_view["kind"], "weather")
        self.assertIn("2026-10-30", engine.last_result_view["text"])

    def test_provider_error_does_not_make_up_weather(self):
        engine = AssistantEngine(chat=FakeChat())
        with patch("angela.assistant.get_weather", side_effect=WeatherError("Sem internet")):
            response = engine.reply("mostre a previsão do tempo em Itirapina")
        self.assertIn("Sem internet", response)
        self.assertIsNone(engine.last_result_view)

    def test_no_city_no_call(self):
        engine = AssistantEngine(chat=FakeChat())
        with (
            patch.dict(os.environ, {"ANGELA_WEATHER_CITY": ""}),
            patch("angela.assistant.get_weather", side_effect=WeatherError("Diga uma cidade")) as getter,
        ):
            response = engine.reply("mostre a previsão do tempo")
        self.assertIn("cidade", response)
        getter.assert_called_once_with("")

    def test_coordinator_delivers_view_on_gui_poll(self):
        states = Mock()
        coord = VoiceCoordinator(states)
        coord.listener = Mock()
        coord.active = True
        coord.on_result_view = Mock()
        payload = {"kind": "text", "text": "Resposta"}
        coord.events.put(("result_view", payload))
        coord.poll()
        coord.on_result_view.assert_called_once_with(payload)
        coord.stop()
        coord.events.put(("result_view", payload))
        coord.poll()
        coord.on_result_view.assert_called_once()

    def test_error_in_result_window_keeps_voice_flow(self):
        coord = VoiceCoordinator(Mock())
        coord.listener = Mock()
        coord.active = True
        coord.on_result_view = Mock(side_effect=RuntimeError("janela"))
        coord.on_reply = Mock()
        coord.events.put(("result_view", {"kind": "text"}))
        coord.events.put(("reply", "Pronto"))
        with patch.object(coord, "_speak_async") as speak:
            coord.poll()
        coord.on_reply.assert_called_once_with("Pronto")
        speak.assert_called_once()

    def test_worker_emits_window_before_voice_response(self):
        engine = Mock()
        engine.reply.return_value = "Pronto"
        engine.last_interpretation = None
        engine.last_execution = False
        engine.last_panel = None
        engine.last_result_view = {"kind": "weather", "title": "Tempo"}
        coord = VoiceCoordinator(Mock())
        coord.active = True
        coord.engine = engine
        coord.listener = Mock()
        targets = []
        def capture_thread(*args, **kwargs):
            thread = Mock()
            thread.start.side_effect = lambda: targets.append(kwargs["target"])
            return thread
        with patch("angela.voice_coordinator.threading.Thread", side_effect=capture_thread):
            coord._reply_async("mostre o tempo")
        targets[0]()
        events = []
        while not coord.events.empty():
            events.append(coord.events.get_nowait()[0])
        self.assertIn("result_view", events)
        self.assertLess(events.index("result_view"), events.index("reply"))


if __name__ == "__main__":
    unittest.main()
