"""Tests for Philips quirks."""

import pytest

import zhaquirks
from zhaquirks.const import (
    BUTTON_1,
    BUTTON_2,
    BUTTON_3,
    BUTTON_4,
    CLUSTER_ID,
    COMMAND,
    ENDPOINT_ID,
    PARAMS,
)
import zhaquirks.philips
from zhaquirks.philips import PhilipsRemoteCluster
import zhaquirks.philips.rdm002
from zhaquirks.philips.rdm002 import PhilipsRDM002

zhaquirks.setup()

class _SimpleRemote(PhilipsRemoteCluster):
    BUTTONS = { 1: "turn_on", 2: "right" }
    PRESS_TYPES = { 0: "remote_button_long_release" }
    SIMULATE_SHORT_EVENTS = None
    TRIGGER_OVERRIDES = {}
    COMMAND_OVERRIDES = {}

class _RemoteWithTriggerOverrides(_SimpleRemote):
    TRIGGER_OVERRIDES = { "turn_on": "left"}

class _RemoteWithSimulatedRelease(_SimpleRemote):
    SIMULATE_SHORT_EVENTS = ["remote_button_short_press", "remote_button_short_release"]

class _RemoteWithSimulatedReleaseAndCommandOverride(_SimpleRemote):
    SIMULATE_SHORT_EVENTS = ["remote_button_short_press", "remote_button_short_release"]
    COMMAND_OVERRIDES = { "remote_button_short_press": "short_press" }

class _RemoteWithCommandOverrides(_SimpleRemote):
    COMMAND_OVERRIDES = { "remote_button_long_release": "release" }

@pytest.mark.parametrize(
    "cls, expected_value",
    (
        (
            _SimpleRemote,
            {
                ("remote_button_long_release", "turn_on"): {COMMAND: "turn_on_remote_button_long_release"},
                ("remote_button_long_release", "right"): {COMMAND: "right_remote_button_long_release"},
            },
        ),
        (
            _RemoteWithTriggerOverrides,
            {
                ("remote_button_long_release", "left"): {COMMAND: "turn_on_remote_button_long_release"},
                ("remote_button_long_release", "right"): {COMMAND: "right_remote_button_long_release"},
            },
        ),
        (
            _RemoteWithSimulatedRelease,
            {
                ("remote_button_long_release", "turn_on"): {COMMAND: "turn_on_remote_button_long_release"},
                ("remote_button_long_release", "right"): {COMMAND: "right_remote_button_long_release"},
                ("remote_button_short_press", "turn_on"): {COMMAND: "turn_on_remote_button_short_press"},
                ("remote_button_short_press", "right"): {COMMAND: "right_remote_button_short_press"},
                ("remote_button_short_release", "turn_on"): {COMMAND: "turn_on_remote_button_short_release"},
                ("remote_button_short_release", "right"): {COMMAND: "right_remote_button_short_release"},
            },
        ),
        (
            _RemoteWithCommandOverrides,
            {
                ("remote_button_long_release", "turn_on"): {COMMAND: "turn_on_release"},
                ("remote_button_long_release", "right"): {COMMAND: "right_release"},
            },
        ),
        (
            _RemoteWithSimulatedReleaseAndCommandOverride,
            {
                ("remote_button_long_release", "turn_on"): {COMMAND: "turn_on_remote_button_long_release"},
                ("remote_button_long_release", "right"): {COMMAND: "right_remote_button_long_release"},
                ("remote_button_short_press", "turn_on"): {COMMAND: "turn_on_short_press"},
                ("remote_button_short_press", "right"): {COMMAND: "right_short_press"},
                ("remote_button_short_release", "turn_on"): {COMMAND: "turn_on_remote_button_short_release"},
                ("remote_button_short_release", "right"): {COMMAND: "right_remote_button_short_release"},
            },
        ),
    ),
)
def test_generate_device_automation_triggers(cls, expected_value):
    """Test trigger generation and button overrides."""

    assert cls.generate_device_automation_triggers() == expected_value

def test_rdm002_triggers():
    """Ensure RDM002 triggers won't break."""

    buttons = [BUTTON_1, BUTTON_2, BUTTON_3, BUTTON_4]
    actions = {
        "remote_button_short_press": "press",
        "remote_button_long_press": "hold",
        "remote_button_short_release": "short_release",
        "remote_button_long_release": "long_release",
        "remote_button_double_press": "double_press",
        "remote_button_triple_press": "triple_press",
        "remote_button_quadruple_press": "quadruple_press",
        "remote_button_quintuple_press": "quintuple_press"
    }
    expected_triggers = {}
    for button in buttons:
        for action, command in actions.items():
            expected_triggers[(action, button)] = {
                COMMAND: f"{button}_{command}"
            }
    expected_triggers.update({
        ("remote_button_short_press", "dim_up"): {
            COMMAND: "step_with_on_off",
            CLUSTER_ID: 8,
            ENDPOINT_ID: 1,
            PARAMS: {"step_mode": 0},
        },
        ("remote_button_short_press", "dim_down"): {
            COMMAND: "step_with_on_off",
            CLUSTER_ID: 8,
            ENDPOINT_ID: 1,
            PARAMS: {"step_mode": 1},
        },
    })
    actual_triggers = PhilipsRDM002.device_automation_triggers

    assert actual_triggers == expected_triggers
