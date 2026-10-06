"""Tests for the permission-tier wiring in AgentState.

`permission_level` existed as a field that nothing ever wrote to. These assert
it now tracks the mode, and that an explicit override still wins.
"""
import unittest

from lc.core.state import (
    AgentMode,
    AgentState,
    MODE_PERMISSION,
    PermissionLevel,
)


class TestPermissionLevel(unittest.TestCase):
    def test_idle_starts_at_observe(self):
        self.assertEqual(AgentState().permission_level, PermissionLevel.OBSERVE)

    def test_transition_tracks_the_mode(self):
        state = AgentState()
        state.transition(AgentMode.PLANNING)
        self.assertEqual(state.permission_level, PermissionLevel.READ)
        state.transition(AgentMode.EXECUTING)
        self.assertEqual(state.permission_level, PermissionLevel.WRITE)
        state.transition(AgentMode.COMPLETED)
        self.assertEqual(state.permission_level, PermissionLevel.OBSERVE)

    def test_explicit_permission_level_overrides_the_mode(self):
        state = AgentState()
        state.transition(AgentMode.EXECUTING, permission_level=PermissionLevel.DESTRUCTIVE)
        self.assertEqual(state.permission_level, PermissionLevel.DESTRUCTIVE)

    def test_only_executing_and_verifying_reach_write(self):
        writers = {
            mode for mode, level in MODE_PERMISSION.items()
            if level >= PermissionLevel.WRITE
        }
        self.assertEqual(writers, {AgentMode.EXECUTING, AgentMode.VERIFYING})

    def test_no_mode_reaches_destructive_implicitly(self):
        # Destructive work has to be opted into explicitly; no lifecycle mode
        # should hand out that tier on its own.
        for mode, level in MODE_PERMISSION.items():
            with self.subTest(mode=mode):
                self.assertLess(level, PermissionLevel.DESTRUCTIVE)

    def test_can_perform_respects_the_current_tier(self):
        state = AgentState()
        state.transition(AgentMode.PLANNING)
        self.assertTrue(state.can_perform(PermissionLevel.READ))
        self.assertFalse(state.can_perform(PermissionLevel.WRITE))

        state.transition(AgentMode.EXECUTING)
        self.assertTrue(state.can_perform(PermissionLevel.WRITE))
        self.assertFalse(state.can_perform(PermissionLevel.DESTRUCTIVE))

    def test_every_mode_has_a_tier(self):
        for mode in AgentMode:
            with self.subTest(mode=mode):
                self.assertIn(mode, MODE_PERMISSION)


if __name__ == "__main__":
    unittest.main()