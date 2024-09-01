"""Module for Philips quirks implementations."""

import asyncio
import logging
import time
from typing import Any, Optional, Union

from zigpy.quirks import CustomCluster
import zigpy.types as t
from zigpy.zcl import foundation
from zigpy.zcl.clusters.general import Basic
from zigpy.zcl.clusters.measurement import OccupancySensing

from zhaquirks.const import (
    ARGS,
    BUTTON,
    COMMAND,
    COMMAND_HOLD,
    COMMAND_ID,
    COMMAND_M_LONG_RELEASE,
    COMMAND_M_SHORT_RELEASE,
    COMMAND_PRESS,
    DIM_DOWN,
    DIM_UP,
    DOUBLE_PRESS,
    LONG_PRESS,
    LONG_RELEASE,
    PRESS_TYPE,
    QUADRUPLE_PRESS,
    QUINTUPLE_PRESS,
    SHORT_PRESS,
    SHORT_RELEASE,
    TRIPLE_PRESS,
    TURN_OFF,
    TURN_ON,
    ZHA_SEND_EVENT,
)

PHILIPS = "Philips"
SIGNIFY = "Signify Netherlands B.V."
_LOGGER = logging.getLogger(__name__)


class PhilipsOccupancySensing(CustomCluster):
    """Philips occupancy cluster."""

    cluster_id = OccupancySensing.cluster_id
    ep_attribute = "philips_occupancy"

    attributes = OccupancySensing.attributes.copy()
    attributes[0x0030] = ("sensitivity", t.uint8_t, True)
    attributes[0x0031] = ("sensitivity_max", t.uint8_t, True)

    server_commands = OccupancySensing.server_commands.copy()
    client_commands = OccupancySensing.client_commands.copy()


class PhilipsBasicCluster(CustomCluster, Basic):
    """Philips Basic cluster."""

    attributes = Basic.attributes.copy()
    attributes[0x0031] = ("philips", t.bitmap16, True)

    attr_config = {0x0031: 0x000B}

    async def bind(self):
        """Bind cluster."""
        result = await super().bind()
        await self.write_attributes(self.attr_config, manufacturer=0x100B)
        return result


class ButtonPressQueue:
    """Philips button queue to derive multiple press events."""

    def __init__(self):
        """Init."""
        self._ms_threshold = 300
        self._ms_last_click = 0
        self._click_counter = 1
        self._button = None
        self._callback = lambda x: None
        self._task = None

    async def _job(self):
        await asyncio.sleep(self._ms_threshold / 1000)
        self._callback(self._click_counter)

    def _reset(self, button):
        if self._task:
            self._task.cancel()
        self._click_counter = 1
        self._button = button

    def press(self, callback, button):
        """Process a button press."""
        self._callback = callback
        now_ms = time.time() * 1000
        if self._button != button:
            self._reset(button)
        elif now_ms - self._ms_last_click > self._ms_threshold:
            self._click_counter = 1
        else:
            self._task.cancel()
            self._click_counter += 1
        self._ms_last_click = now_ms
        self._task = asyncio.ensure_future(self._job())


class PhilipsRemoteCluster(CustomCluster):
    """Philips remote cluster."""

    cluster_id = 0xFC00
    name = "PhilipsRemoteCluster"
    ep_attribute = "philips_remote_cluster"
    client_commands = {
        0x0000: foundation.ZCLCommandDef(
            "notification",
            {
                "button": t.uint8_t,
                "param2": t.uint24_t,
                "press_type": t.uint8_t,
                "param4": t.uint8_t,
                "param5": t.uint16_t,
            },
            False,
            is_manufacturer_specific=True,
        )
    }

    # In classes inheriting from PhilipsRemoteCluster, define BUTTONS
    # with the respective remote's buttons.
    # BUTTONS = {1: TURN_ON, 2: DIM_UP, 3: DIM_DOWN, 4: TURN_OFF}

    # In case we need to use a different button name in the command than
    # used in the trigger tuple, we can override button names here. This
    # is only needed for backwards compatibility. See
    # PhilipsRdm001RemoteCluster for an example.
    TRIGGER_OVERRIDES = {}

    COMMAND_OVERRIDES = {
        SHORT_PRESS: COMMAND_PRESS,
        LONG_PRESS: COMMAND_HOLD,
        SHORT_RELEASE: COMMAND_M_SHORT_RELEASE,
        LONG_RELEASE: COMMAND_M_LONG_RELEASE,
        DOUBLE_PRESS: "double_press",
        TRIPLE_PRESS: "triple_press",
        QUADRUPLE_PRESS: "quadruple_press",
        QUINTUPLE_PRESS: "quintuple_press"
    }

    PRESS_TYPES = {
        # We omit "short_press" and "short_release" on purpose, so it
        # won't interfere with simulated multi-press events. We emit
        # them in the multi-press code later on.
        # 0: SHORT_PRESS,
        1: LONG_PRESS,
        # 2: SHORT_RELEASE,
        3: LONG_RELEASE,
        4: DOUBLE_PRESS,
        5: TRIPLE_PRESS,
        6: QUADRUPLE_PRESS,
        7: QUINTUPLE_PRESS,
    }
    SIMULATE_SHORT_EVENTS = [SHORT_PRESS, SHORT_RELEASE]

    button_press_queue = ButtonPressQueue()

    def handle_cluster_request(
        self,
        hdr: foundation.ZCLHeader,
        args: list[Any],
        *,
        dst_addressing: Optional[
            Union[t.Addressing.Group, t.Addressing.IEEE, t.Addressing.NWK]
        ] = None,
    ):
        """Handle the cluster command."""
        self.debug(
            "%s - handle_cluster_request tsn: [%s] command id: %s - args: [%s]",
            self.__class__.__name__,
            hdr.tsn,
            hdr.command_id,
            args,
        )

        button = self.BUTTONS.get(args[0])
        _LOGGER.debug(
            "%s - handle_cluster_request button id: [%s], button name: [%s]",
            self.__class__.__name__,
            args[0],
            button,
        )
        # Bail on unknown buttons. (This gets rid of dial button "presses")
        if button is None:
            return

        press_type = self.PRESS_TYPES.get(args[2])
        if press_type is None and self.SIMULATE_SHORT_EVENTS is not None and args[2] == 2:
            press_type = SHORT_RELEASE
        if press_type is None:
            return

        duration = args[4]
        _LOGGER.debug(
            "%s - handle_cluster_request button press type: [%s], duration: [%s]",
            self.__class__.__name__,
            press_type,
            duration,
        )

        event_args = {
            BUTTON: button,
            PRESS_TYPE: press_type,
            COMMAND_ID: hdr.command_id,
            "duration": duration,
            ARGS: args,
        }

        def send_press_event(click_count):
            _LOGGER.debug(
                "%s - send_press_event click_count: [%s]",
                self.__class__.__name__,
                click_count,
            )
            press_type = None
            if click_count == 1:
                press_type = SHORT_PRESS
            elif click_count == 2:
                press_type = DOUBLE_PRESS
            elif click_count == 3:
                press_type = TRIPLE_PRESS
            elif click_count == 4:
                press_type = QUADRUPLE_PRESS
            elif click_count > 4:
                press_type = QUINTUPLE_PRESS

            if press_type:
                # Override PRESS_TYPE
                event_args[PRESS_TYPE] = press_type
                command_press_type = self.COMMAND_OVERRIDES.get(press_type, press_type)
                action = f"{button}_{command_press_type}"
                _LOGGER.debug(
                    "%s - send_press_event emitting action: [%s]",
                    self.__class__.__name__,
                    action,
                )
                self.listener_event(ZHA_SEND_EVENT, action, event_args)

            # simulate short release event, if needed for this device type
            if press_type == SHORT_PRESS and self.SIMULATE_SHORT_EVENTS is not None:
                event_args[PRESS_TYPE] = SHORT_RELEASE
                command_press_type = self.COMMAND_OVERRIDES.get(SHORT_RELEASE, SHORT_RELEASE)
                action = f"{button}_{command_press_type}"
                _LOGGER.debug(
                    "%s - send_press_event emitting simulated action: [%s]",
                    self.__class__.__name__,
                    action,
                )
                self.listener_event(ZHA_SEND_EVENT, action, event_args)

        # Derive Multiple Presses
        if press_type == SHORT_RELEASE:
            self.button_press_queue.press(send_press_event, button)
        else:
            command_press_type = self.COMMAND_OVERRIDES.get(press_type, press_type)
            action = f"{button}_{command_press_type}"
            self.listener_event(ZHA_SEND_EVENT, action, event_args)

    @classmethod
    def generate_device_automation_triggers(cls, additional=None):
        """Generate automation triggers based on device buttons and press-types."""
        triggers = {}
        for button in cls.BUTTONS.values():
            trigger_button = cls.TRIGGER_OVERRIDES.get(button, button)
            for press_type in cls.PRESS_TYPES.values():
                # command_press_type = press_type
                command_press_type = cls.COMMAND_OVERRIDES.get(press_type, press_type)
                triggers[(press_type, trigger_button)] = {COMMAND: f"{button}_{command_press_type}"}

            if cls.SIMULATE_SHORT_EVENTS is not None:
                for press_type in cls.SIMULATE_SHORT_EVENTS:
                    command_press_type = cls.COMMAND_OVERRIDES.get(press_type, press_type)
                    triggers[(press_type, trigger_button)] = {
                        COMMAND: f"{button}_{command_press_type}"
                    }

        if additional:
            triggers.update(additional)

        return triggers


class PhilipsRwlRemoteCluster(PhilipsRemoteCluster):
    """Philips remote cluster for RWL devices."""

    BUTTONS = {1: TURN_ON, 2: DIM_UP, 3: DIM_DOWN, 4: TURN_OFF}

    SIMULATE_SHORT_RELEASE = SHORT_RELEASE
