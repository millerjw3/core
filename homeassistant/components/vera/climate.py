"""Support for Vera thermostats."""

from typing import Any, override

import pyvera as veraApi

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ENTITY_ID_FORMAT,
    FAN_AUTO,
    FAN_ON,
    PRESET_ECO,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .common import ControllerData, VeraConfigEntry
from .entity import VeraEntity

FAN_OPERATION_LIST = [FAN_ON, FAN_AUTO]

SUPPORT_HVAC = [HVACMode.COOL, HVACMode.HEAT, HVACMode.HEAT_COOL, HVACMode.OFF]

ENERGY_MODE_NORMAL = "Normal"
ENERGY_MODE_SAVINGS = "EnergySavingsMode"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VeraConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor config entry."""
    controller_data = entry.runtime_data
    async_add_entities(
        [
            VeraThermostat(device, controller_data)
            for device in controller_data.devices[Platform.CLIMATE]
        ],
        True,
    )


class VeraThermostat(VeraEntity[veraApi.VeraThermostat], ClimateEntity):
    """Representation of a Vera Thermostat."""

    _attr_hvac_modes = SUPPORT_HVAC
    _attr_fan_modes = FAN_OPERATION_LIST
    _attr_preset_modes = [PRESET_NONE, PRESET_ECO]

    def __init__(
        self, vera_device: veraApi.VeraThermostat, controller_data: ControllerData
    ) -> None:
        """Initialize the Vera device."""
        VeraEntity.__init__(self, vera_device, controller_data)
        self.entity_id = ENTITY_ID_FORMAT.format(self.vera_id)

    @override
    def update(self) -> None:
        """Refresh the device, including its heat and cool setpoints.

        The heat and cool setpoint variables are not part of the Vera's
        summary data, so they are refreshed on every update.
        """
        super().update()
        self.vera_device.refresh_states()

    @property
    def _heat_setpoint(self) -> float | None:
        return self.vera_device.get_heat_setpoint()

    @property
    def _cool_setpoint(self) -> float | None:
        return self.vera_device.get_cool_setpoint()

    @property
    def _energy_mode(self) -> str | None:
        return self.vera_device.get_energy_mode()

    @property
    def _is_eco(self) -> bool:
        """Return True while the thermostat runs on its energy savings setback.

        The setback setpoint is not reported by the Vera, so no target
        temperature is exposed in this mode.
        """
        return self._energy_mode == ENERGY_MODE_SAVINGS

    @property
    def _has_heat_cool_range(self) -> bool:
        """Return True when the thermostat reports both heat and cool setpoints."""
        return self._heat_setpoint is not None and self._cool_setpoint is not None

    @property
    @override
    def supported_features(self) -> ClimateEntityFeature:
        """Return a setpoint range in auto mode when both setpoints exist."""
        features = (
            ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TURN_ON
        )
        if self._energy_mode is not None:
            features |= ClimateEntityFeature.PRESET_MODE
        if self._is_eco:
            return features
        if self.hvac_mode == HVACMode.HEAT_COOL and self._has_heat_cool_range:
            return features | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        return features | ClimateEntityFeature.TARGET_TEMPERATURE

    @property
    @override
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode.

        Need to be one of HVAC_MODE_*.
        """
        mode = self.vera_device.get_hvac_mode() or ""
        # In energy savings mode the Vera reports e.g. "EconomyHeatOn".
        mode = mode.removeprefix("Economy")
        if mode == "HeatOn":
            return HVACMode.HEAT
        if mode == "CoolOn":
            return HVACMode.COOL
        if mode == "AutoChangeOver":
            return HVACMode.HEAT_COOL
        return HVACMode.OFF

    @property
    @override
    def preset_mode(self) -> str | None:
        """Return eco while the thermostat is in energy savings mode."""
        return PRESET_ECO if self._is_eco else PRESET_NONE

    @override
    def set_preset_mode(self, preset_mode: str) -> None:
        """Set the energy mode."""
        if preset_mode == PRESET_ECO:
            self.vera_device.set_energy_mode(ENERGY_MODE_SAVINGS)
        else:
            self.vera_device.set_energy_mode(ENERGY_MODE_NORMAL)

        self.schedule_update_ha_state()

    @property
    @override
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        if self.vera_device.get_fan_mode() == "ContinuousOn":
            return FAN_ON
        return FAN_AUTO

    @override
    def set_fan_mode(self, fan_mode: str) -> None:
        """Set new target temperature."""
        if fan_mode == FAN_ON:
            self.vera_device.fan_on()
        else:
            self.vera_device.fan_auto()

        self.schedule_update_ha_state()

    @property
    @override
    def native_temperature_unit(self) -> str:
        """Return the unit of measurement."""
        vera_temp_units = self.vera_device.vera_controller.temperature_units

        if vera_temp_units == "F":
            return UnitOfTemperature.FAHRENHEIT

        return UnitOfTemperature.CELSIUS

    @property
    @override
    def native_current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self.vera_device.get_current_temperature()

    @property
    def operation(self) -> str:
        """Return current operation ie. heat, cool, idle."""
        return self.vera_device.get_hvac_mode()

    @property
    @override
    def native_target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        mode = self.hvac_mode
        if mode == HVACMode.HEAT and self._heat_setpoint is not None:
            return self._heat_setpoint
        if mode == HVACMode.COOL and self._cool_setpoint is not None:
            return self._cool_setpoint
        return self.vera_device.get_current_goal_temperature()

    @property
    @override
    def native_target_temperature_low(self) -> float | None:
        """Return the lower bound of the auto range (the heat setpoint)."""
        return self._heat_setpoint

    @property
    @override
    def native_target_temperature_high(self) -> float | None:
        """Return the upper bound of the auto range (the cool setpoint)."""
        return self._cool_setpoint

    @override
    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperatures."""
        if (hvac_mode := kwargs.get(ATTR_HVAC_MODE)) is not None:
            self.set_hvac_mode(hvac_mode)

        mode = self.hvac_mode
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            if mode == HVACMode.HEAT and self._heat_setpoint is not None:
                self.vera_device.set_heat_setpoint(temperature)
            elif mode == HVACMode.COOL and self._cool_setpoint is not None:
                self.vera_device.set_cool_setpoint(temperature)
            else:
                self.vera_device.set_temperature(temperature)

        if (target_low := kwargs.get(ATTR_TARGET_TEMP_LOW)) is not None:
            self.vera_device.set_heat_setpoint(target_low)
        if (target_high := kwargs.get(ATTR_TARGET_TEMP_HIGH)) is not None:
            self.vera_device.set_cool_setpoint(target_high)

        self.schedule_update_ha_state()

    @property
    @override
    def hvac_action(self) -> HVACAction | None:
        mode = self.vera_device.get_hvac_state()
        if mode == "Heating":
            result = HVACAction.HEATING
        elif mode == "Cooling":
            result = HVACAction.COOLING
        elif mode in {"Idle", "PendingCool", "PendingHeat", "PendingIdle"}:
            result = HVACAction.IDLE
        elif mode in {"FanOnly", "Vent"}:
            result = HVACAction.FAN
        elif mode == "Off":
            result = HVACAction.OFF
        else:
            result = None

        return result

    @override
    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.OFF:
            self.vera_device.turn_off()
        elif hvac_mode == HVACMode.HEAT_COOL:
            self.vera_device.turn_auto_on()
        elif hvac_mode == HVACMode.COOL:
            self.vera_device.turn_cool_on()
        elif hvac_mode == HVACMode.HEAT:
            self.vera_device.turn_heat_on()

        self.schedule_update_ha_state()
