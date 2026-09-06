"""What every Hosekeeper entity shares: the field's device and the coordinator."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HosekeeperCoordinator


class HosekeeperEntity(CoordinatorEntity[HosekeeperCoordinator]):
    """An entity that belongs to one field."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HosekeeperCoordinator, key: str) -> None:
        """Bind to one zone and name the entity after `key`."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        assert entry is not None
        self._attr_translation_key = key
        self._attr_unique_id = f"{coordinator.zone_id}_{key}"
        # The device is the zone, hanging beneath the lawn it belongs to, so a lawn with
        # four of them reads as one lawn in four parts, not four unrelated integrations.
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.zone_id)},
            name=coordinator.field.name,
            manufacturer="Hosekeeper",
            model=coordinator.field.grass_type.replace("_", " ").title(),
            via_device=(DOMAIN, entry.entry_id),
        )
