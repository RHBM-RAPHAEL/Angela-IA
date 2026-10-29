"""Testes da máquina de estados do núcleo holográfico."""
import unittest
from datetime import datetime
from unittest.mock import patch

from angela.states import AngelaState, AngelaStateMachine, STATE_COLORS
from angela.voice_coordinator import greeting


class StateTests(unittest.TestCase):
    def test_initially_starting(self):
        self.assertEqual(AngelaStateMachine().state, AngelaState.STARTING)

    def test_all_states_have_colors(self):
        self.assertEqual(set(AngelaState), set(STATE_COLORS))

    def test_transitions(self):
        machine = AngelaStateMachine()
        for state in AngelaState:
            self.assertEqual(machine.transition(state.value), state)

    def test_invalid_state(self):
        with self.assertRaises(ValueError):
            AngelaStateMachine().transition("undefined")

    def test_greeting_by_daypart(self):
        with patch("angela.voice_coordinator._RANDOM.choice", side_effect=lambda options: options[0]):
            self.assertIn("Bom dia", greeting(datetime(2026, 10, 26, 9, 0)))
            self.assertIn("Boa tarde", greeting(datetime(2026, 10, 26, 15, 0)))
            self.assertIn("Boa noite", greeting(datetime(2026, 10, 26, 21, 0)))


if __name__ == "__main__":
    unittest.main()
