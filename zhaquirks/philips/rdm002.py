"""Signify RDM002 device."""

import logging
from typing import Any, Optional, Union

from zigpy.profiles import zha
from zigpy.quirks import CustomDevice
import zigpy.types as t
from zigpy.zcl import foundation
from zigpy.zcl.clusters.general import (
    Basic,
    Groups,
    Identify,
    LevelControl,
    OnOff,
    Ota,
    PowerConfiguration,
    Scenes,
)
from zigpy.zcl.clusters.lightlink import LightLink

from zhaquirks.const import (
    ARGS,
    BUTTON_1,
    BUTTON_2,
    BUTTON_3,
    BUTTON_4,
    CLUSTER_ID,
    COMMAND,
    COMMAND_ID,
    COMMAND_STEP_ON_OFF,
    DEVICE_TYPE,
    DIM_DOWN,
    DIM_UP,
    ENDPOINT_ID,
    ENDPOINTS,
    INPUT_CLUSTERS,
    MODELS_INFO,
    OUTPUT_CLUSTERS,
    PARAMS,
    PROFILE_ID,
    SHORT_PRESS,
    ZHA_SEND_EVENT,
)
from zhaquirks.philips import (
    PHILIPS,
    SIGNIFY,
    Button,
    PhilipsBasicCluster,
    PhilipsRemoteCluster,
)

_LOGGER = logging.getLogger(__name__)


DIAL_TRIGGERS = {
    (SHORT_PRESS, DIM_UP): {
        COMMAND: COMMAND_STEP_ON_OFF,
        CLUSTER_ID: 0xFC00,
        ENDPOINT_ID: 1,
        PARAMS: {"step_mode": 0},
    },
    (SHORT_PRESS, DIM_DOWN): {
        COMMAND: COMMAND_STEP_ON_OFF,
        CLUSTER_ID: 0xFC00,
        ENDPOINT_ID: 1,
        PARAMS: {"step_mode": 1},
    },
}


class PhilipsRdm002RemoteCluster(PhilipsRemoteCluster):
    """Philips remote cluster for RDM002."""

    BUTTONS = {
        1: Button(BUTTON_1),
        2: Button(BUTTON_2),
        3: Button(BUTTON_3),
        4: Button(BUTTON_4),
    }

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
        buttonId = args[0]

        if buttonId != 20:
            return PhilipsRemoteCluster.handle_cluster_request(
                self, hdr, args, dst_addressing=dst_addressing
            )

        event_args = {
            COMMAND_ID: 0x06,
            "step_mode": 1 if args[4] < 0 else 0,
            "step_size": abs(args[4]),
            "transition_time": 4,
            ARGS: args,
            # ARGS: {
            #     "step_mode": 1 if args[4] < 0 else 0,
            #     "step_size": abs(args[4]),
            #     "transition_time": 4,
            # },
        }

        _LOGGER.debug(
            "%s - handle_cluster_request for dial; tsn: [%s] command id: %s - args: [%s]",
            self.__class__.__name__,
            hdr.tsn,
            0x06,
            args,
        )
        self.listener_event(ZHA_SEND_EVENT, COMMAND_STEP_ON_OFF, event_args)


class PhilipsRDM002(CustomDevice):
    """Philips RDM002 device."""

    signature = {
        #  <SimpleDescriptor endpoint=1 profile=260 device_type=2096
        #  device_version=1
        #  input_clusters=[0, 1, 3, 64512, 4096]
        #  output_clusters=[25, 0, 3, 4, 6, 8, 5, 4096]>
        MODELS_INFO: [(PHILIPS, "RDM002"), (SIGNIFY, "RDM002")],
        ENDPOINTS: {
            1: {
                PROFILE_ID: zha.PROFILE_ID,
                DEVICE_TYPE: zha.DeviceType.NON_COLOR_SCENE_CONTROLLER,
                INPUT_CLUSTERS: [
                    Basic.cluster_id,
                    PowerConfiguration.cluster_id,
                    Identify.cluster_id,
                    PhilipsRdm002RemoteCluster.cluster_id,
                    LightLink.cluster_id,
                ],
                OUTPUT_CLUSTERS: [
                    Ota.cluster_id,
                    Basic.cluster_id,
                    Identify.cluster_id,
                    Groups.cluster_id,
                    OnOff.cluster_id,
                    LevelControl.cluster_id,
                    Scenes.cluster_id,
                    LightLink.cluster_id,
                ],
            }
        },
    }

    replacement = {
        ENDPOINTS: {
            1: {
                PROFILE_ID: zha.PROFILE_ID,
                DEVICE_TYPE: zha.DeviceType.NON_COLOR_CONTROLLER,
                INPUT_CLUSTERS: [
                    PhilipsBasicCluster,
                    PowerConfiguration.cluster_id,
                    Identify.cluster_id,
                    PhilipsRdm002RemoteCluster,
                    LightLink.cluster_id,
                ],
                OUTPUT_CLUSTERS: [
                    Ota.cluster_id,
                    Basic.cluster_id,
                    Identify.cluster_id,
                    Groups.cluster_id,
                    OnOff.cluster_id,
                    0,
                    Scenes.cluster_id,
                    LightLink.cluster_id,
                ],
            }
        }
    }

    device_automation_triggers = (
        PhilipsRdm002RemoteCluster.generate_device_automation_triggers(DIAL_TRIGGERS)
    )
