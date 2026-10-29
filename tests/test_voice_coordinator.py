"""Transições de escuta sem microfone ou TTS de verdade."""
import unittest
from unittest.mock import Mock, patch

from angela.states import AngelaState
from angela.voice_coordinator import VoiceCoordinator


class VoiceCoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.states = Mock()
        self.coordinator = VoiceCoordinator(self.states)
        self.coordinator.active = True
        self.coordinator.listener = Mock()

    def test_primeiro_chamado_cumprimenta(self):
        with patch.object(self.coordinator, "_speak_async") as speak:
            self.coordinator.events.put(("wake_activated", ""))
            self.coordinator.poll()
            self.assertTrue(self.coordinator.activated_once)
            self.assertTrue(self.coordinator.busy)
            self.states.assert_called_with(AngelaState.SPEAKING)
            speak.assert_called_once()

    def test_segundo_chamado_silencioso_escuta(self):
        self.coordinator.activated_once = True
        with patch.object(self.coordinator, "_speak_async") as speak:
            self.coordinator.events.put(("wake_activated", ""))
            self.coordinator.poll()
            self.assertFalse(self.coordinator.busy)
            self.states.assert_called_with(AngelaState.LISTENING)
            self.coordinator.listener.resume.assert_called_once_with(follow_up=True)
            speak.assert_not_called()

    def test_microfone_iniciado_e_exibido_no_painel(self):
        status = Mock()
        self.coordinator.on_microphone_status = status
        self.coordinator.events.put(("wake_ready", ""))
        self.coordinator.poll()
        self.states.assert_called_with(AngelaState.READY)
        status.assert_called_once_with("Microfone ligado · diga Ângela")

    def test_falha_microfone_nao_declara_pronto(self):
        status = Mock()
        self.coordinator.on_microphone_status = status
        self.coordinator.events.put(("wake_error", "PortAudioError"))
        self.coordinator.poll()
        self.assertFalse(self.coordinator.active)
        self.states.assert_called_with(AngelaState.STARTING)
        status.assert_called_once()
        self.assertIn("indisponível", status.call_args.args[0])

    def test_timeout_volta_a_azul(self):
        self.coordinator.events.put(("wake_timeout", ""))
        self.coordinator.poll()
        self.states.assert_called_with(AngelaState.READY)

    def test_comando_muda_para_processando(self):
        with patch.object(self.coordinator, "_reply_async") as reply:
            self.coordinator.events.put(("wake_command", "abra calculadora"))
            self.coordinator.poll()
            self.states.assert_called_with(AngelaState.PROCESSING)
            reply.assert_called_once_with("abra calculadora")

    def test_stop_descarta_resposta_aguardando(self):
        self.coordinator.on_reply = Mock()
        self.coordinator.events.put(("reply", "resposta antiga"))
        with patch.object(self.coordinator, "_speak_async") as speak:
            self.coordinator.stop()
            self.coordinator.poll()
        self.coordinator.on_reply.assert_not_called()
        speak.assert_not_called()
        self.assertFalse(self.coordinator.busy)
        self.assertFalse(self.coordinator.active)

    def test_resposta_recebida_apos_stop_nao_inicia_voz(self):
        self.coordinator.on_reply = Mock()
        self.coordinator.stop()
        self.coordinator.events.put(("reply", "resposta atrasada"))
        with patch.object(self.coordinator, "_speak_async") as speak:
            self.coordinator.poll()
        speak.assert_not_called()
        self.coordinator.on_reply.assert_not_called()

    def test_worker_antigo_nao_contamina_nova_sessao(self):
        self.coordinator.active = False
        self.coordinator.start()
        previous_epoch = self.coordinator._session_epoch
        self.coordinator.stop()
        self.coordinator.start()
        self.coordinator._emit_if_current(previous_epoch, "reply", "resposta antiga")
        self.assertTrue(self.coordinator.events.empty())
        self.coordinator._emit_if_current(self.coordinator._session_epoch, "reply", "resposta atual")
        self.assertEqual(self.coordinator.events.get_nowait(), ("reply", "resposta atual"))

    def test_restart_descarta_eventos_pendentes(self):
        self.coordinator.active = False
        self.coordinator.events.put(("wake_command", "comando antigo"))
        self.coordinator.start()
        self.assertTrue(self.coordinator.events.empty())

    def test_comando_de_sessao_encerrada_nao_aciona_engine(self):
        fake_engine = Mock()
        self.coordinator.engine = fake_engine
        jobs = []
        def capture_thread(*args, **kwargs):
            job = Mock()
            job.start.side_effect = lambda: jobs.append(kwargs['target'])
            return job
        with patch('angela.voice_coordinator.threading.Thread', side_effect=capture_thread):
            self.coordinator._reply_async('abra calculadora')
        self.coordinator.stop()
        self.coordinator.start()
        jobs[0]()
        fake_engine.reply.assert_not_called()
        self.assertTrue(self.coordinator.events.empty())

    def test_voz_antiga_nao_inicia_apos_stop(self):
        jobs = []
        def capture_thread(*args, **kwargs):
            job = Mock()
            job.start.side_effect = lambda: jobs.append(kwargs['target'])
            return job
        with patch('angela.voice_coordinator.threading.Thread', side_effect=capture_thread):
            self.coordinator._speak_async('Olá', follow_up=False)
        self.coordinator.stop()
        with patch('angela.speech.speak') as speak:
            jobs[0]()
        speak.assert_not_called()


if __name__ == "__main__":
    unittest.main()
