"""Support for RFXtrx covers."""

from __future__ import annotations

import logging
from typing import Any

import RFXtrx as rfxtrxmod

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverEntity,
    CoverEntityFeature,
    CoverState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DeviceTuple, async_setup_platform_entry
from .const import (
    COMMAND_OFF_LIST,
    COMMAND_ON_LIST,
    CONF_VENETIAN_BLIND_MODE,
    CONST_VENETIAN_BLIND_MODE_EU,
    CONST_VENETIAN_BLIND_MODE_US,
    CONST_VENTIAN_BLIND_MODE_DDXXXX,
)
from .entity import RfxtrxCommandEntity

_LOGGER = logging.getLogger(__name__)


def supported(event: rfxtrxmod.RFXtrxEvent) -> bool:
    """Return whether an event supports cover."""
    return bool(event.device.known_to_be_rollershutter)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up config entry."""

    def _constructor(
        event: rfxtrxmod.RFXtrxEvent,
        auto: rfxtrxmod.RFXtrxEvent | None,
        device_id: DeviceTuple,
        entity_info: dict[str, Any],
    ) -> list[Entity]:
        return [
            RfxtrxCover(
                event.device,
                device_id,
                venetian_blind_mode=entity_info.get(CONF_VENETIAN_BLIND_MODE),
                event=event if auto else None,
            )
        ]

    await async_setup_platform_entry(
        hass, config_entry, async_add_entities, supported, _constructor
    )


class RfxtrxCover(RfxtrxCommandEntity, CoverEntity):
    """Representation of a RFXtrx cover."""

    _device: (
        rfxtrxmod.RollerTrolDevice
        | rfxtrxmod.DDxxxxDevice
        | rfxtrxmod.RfyDevice
        | rfxtrxmod.LightingDevice
    )

    def __init__(
        self,
        device: rfxtrxmod.RFXtrxDevice,
        device_id: DeviceTuple,
        event: rfxtrxmod.RFXtrxEvent = None,
        venetian_blind_mode: str | None = None,
    ) -> None:
        """Initialize the RFXtrx cover device."""
        super().__init__(device, device_id, event)
        self._venetian_blind_mode = venetian_blind_mode
        self._attr_is_closed: bool | None = True

        self._attr_supported_features = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
        )

        if isinstance(device, rfxtrxmod.DDxxxxDevice):
            self._attr_supported_features |= CoverEntityFeature.SET_POSITION

        if venetian_blind_mode in (
            CONST_VENETIAN_BLIND_MODE_US,
            CONST_VENETIAN_BLIND_MODE_EU,
        ):
            self._attr_supported_features |= (
                CoverEntityFeature.OPEN_TILT
                | CoverEntityFeature.CLOSE_TILT
                | CoverEntityFeature.STOP_TILT
            )

        if (
            isinstance(device, rfxtrxmod.DDxxxxDevice)
            and venetian_blind_mode == CONST_VENTIAN_BLIND_MODE_DDXXXX
        ):
            self._attr_supported_features |= (
                CoverEntityFeature.OPEN_TILT
                | CoverEntityFeature.CLOSE_TILT
                | CoverEntityFeature.STOP_TILT
                | CoverEntityFeature.SET_TILT_POSITION
            )

    async def async_added_to_hass(self) -> None:
        """Restore device state."""
        await super().async_added_to_hass()

        if self._event is None:
            old_state = await self.async_get_last_state()
            if old_state is not None:
                self._attr_is_closed = old_state.state != CoverState.OPEN
                self._attr_current_cover_position = old_state.attributes.get(
                    ATTR_POSITION, 0 if self._attr_is_closed else 100
                )
                self._attr_current_cover_tilt_position = old_state.attributes.get(
                    ATTR_TILT_POSITION, 0
                )

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Move the cover up."""
        if self._venetian_blind_mode == CONST_VENETIAN_BLIND_MODE_US:
            await self._async_send(self._device.send_up05sec)
        elif self._venetian_blind_mode == CONST_VENETIAN_BLIND_MODE_EU:
            await self._async_send(self._device.send_up2sec)
        elif self._device.send_up:
            await self._async_send(self._device.send_up)
        else:
            await self._async_send(self._device.send_open)
        self._attr_is_closed = False
        self._attr_current_cover_position = 100
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Move the cover down."""
        if self._venetian_blind_mode == CONST_VENETIAN_BLIND_MODE_US:
            await self._async_send(self._device.send_down05sec)
        elif self._venetian_blind_mode == CONST_VENETIAN_BLIND_MODE_EU:
            await self._async_send(self._device.send_down2sec)
        elif self._device.send_down:
            await self._async_send(self._device.send_down)
        else:
            await self._async_send(self._device.send_close)
        self._attr_is_closed = True
        self._attr_current_cover_position = 0
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self._async_send(self._device.send_stop)
        self._attr_is_closed = False
        self._attr_current_cover_position = 50
        self.async_write_ha_state()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position = kwargs[ATTR_POSITION]
        await self._async_send(self._device.send_percent, 100 - position)
        self._attr_current_cover_position = position
        self.async_write_ha_state()

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Tilt the cover up."""
        if self._venetian_blind_mode == CONST_VENETIAN_BLIND_MODE_US:
            await self._async_send(self._device.send_up2sec)
        elif self._venetian_blind_mode == CONST_VENETIAN_BLIND_MODE_EU:
            await self._async_send(self._device.send_up05sec)
        elif self._venetian_blind_mode == CONST_VENTIAN_BLIND_MODE_DDXXXX:
            await self._async_send(self._device.send_angle, 180)
            self._attr_current_cover_tilt_position = 100
            self.async_write_ha_state()

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Tilt the cover down."""
        if self._venetian_blind_mode == CONST_VENETIAN_BLIND_MODE_US:
            await self._async_send(self._device.send_down2sec)
        elif self._venetian_blind_mode == CONST_VENETIAN_BLIND_MODE_EU:
            await self._async_send(self._device.send_down05sec)
        elif self._venetian_blind_mode == CONST_VENTIAN_BLIND_MODE_DDXXXX:
            await self._async_send(self._device.send_angle, 0)
            self._attr_current_cover_tilt_position = 0
            self.async_write_ha_state()

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        angle = kwargs[ATTR_TILT_POSITION] * 180 / 100
        await self.hass.async_add_executor_job(self._device.send_angle, angle)
        self._attr_current_cover_tilt_position = kwargs[ATTR_TILT_POSITION]
        self.async_write_ha_state()

    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop the cover tilt."""
        await self._async_send(self._device.send_stop)
        self._attr_is_closed = False
        self._attr_current_cover_tilt_position = 50
        self.async_write_ha_state()

    def _apply_event(self, event: rfxtrxmod.RFXtrxEvent) -> None:
        """Apply command from rfxtrx."""
        assert isinstance(event, rfxtrxmod.ControlEvent)
        super()._apply_event(event)
        if event.values["Command"] in COMMAND_ON_LIST:
            self._attr_is_closed = False
        elif event.values["Command"] in COMMAND_OFF_LIST:
            self._attr_is_closed = True

    @callback
    def _handle_event(
        self, event: rfxtrxmod.RFXtrxEvent, device_id: DeviceTuple
    ) -> None:
        """Check if event applies to me and update."""
        if device_id != self._device_id:
            return

        self._apply_event(event)

        self.async_write_ha_state()
