"""Signify RDM001 device."""

import logging

from zigpy.profiles import zha
from zigpy.quirks import CustomCluster, CustomDevice
import zigpy.types as t
from zigpy.zcl.clusters.general import (
    Basic,
    Groups,
    Identify,
    LevelControl,
    OnOff,
    Ota,
    PowerConfiguration,
)

from zhaquirks.const import (
    DEVICE_TYPE,
    ENDPOINTS,
    INPUT_CLUSTERS,
    MODELS_INFO,
    OUTPUT_CLUSTERS,
    PROFILE_ID,
    RIGHT,
    TURN_ON,
)
from zhaquirks.philips import PHILIPS, SIGNIFY, PhilipsRemoteCluster

DEVICE_SPECIFIC_UNKNOWN = 64512
_LOGGER = logging.getLogger(__name__)


class PhilipsBasicCluster(CustomCluster, Basic):
    """Philips Basic cluster."""

    attributes = Basic.attributes.copy()
    attributes.update(
        {
            0x0031: ("philips", t.bitmap16, True),
            0x0034: ("mode", t.enum8, True),
        }
    )

    attr_config = {0x0031: 0x000B, 0x0034: 0x02}

    async def bind(self):
        """Bind cluster."""
        result = await super().bind()
        await self.write_attributes(self.attr_config, manufacturer=0x100B)
        return result


class PhilipsRdm001RemoteCluster(PhilipsRemoteCluster):
    """Philips remote cluster for RDM001."""

    BUTTONS = {
        1: TURN_ON,
        2: RIGHT,
    }


class PhilipsROM001(CustomDevice):
    """Philips ROM001 device."""

    signature = {
        #  <SimpleDescriptor endpoint=1 profile=260 device_type=2080
        #  device_version=1
        #  input_clusters=[0, 1, 3, 64512]
        #  output_clusters=[3, 4, 6, 8, 25]>
        MODELS_INFO: [(PHILIPS, "RDM001"), (SIGNIFY, "RDM001")],
        ENDPOINTS: {
            1: {
                PROFILE_ID: zha.PROFILE_ID,
                DEVICE_TYPE: zha.DeviceType.NON_COLOR_CONTROLLER,
                INPUT_CLUSTERS: [
                    Basic.cluster_id,
                    PowerConfiguration.cluster_id,
                    Identify.cluster_id,
                    DEVICE_SPECIFIC_UNKNOWN,
                ],
                OUTPUT_CLUSTERS: [
                    Identify.cluster_id,
                    Groups.cluster_id,
                    OnOff.cluster_id,
                    LevelControl.cluster_id,
                    Ota.cluster_id,
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
                    PhilipsRdm001RemoteCluster,
                ],
                OUTPUT_CLUSTERS: [
                    Ota.cluster_id,
                    Identify.cluster_id,
                    Groups.cluster_id,
                    OnOff.cluster_id,
                    LevelControl.cluster_id,
                ],
            }
        }
    }

    device_automation_triggers = (
        PhilipsRdm001RemoteCluster.generate_device_automation_triggers()
    )
