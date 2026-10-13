"""Vera tests."""

from unittest.mock import MagicMock

import pytest
import pyvera as pv

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_ON,
    PRESET_ECO,
    PRESET_NONE,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .common import ComponentFactory, new_simple_controller_config


async def test_climate(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test function."""
    vera_device: pv.VeraThermostat = MagicMock(spec=pv.VeraThermostat)
    vera_device.get_energy_mode.return_value = None
    vera_device.device_id = 1
    vera_device.vera_device_id = vera_device.device_id
    vera_device.comm_failure = False
    vera_device.name = "dev1"
    vera_device.category = pv.CATEGORY_THERMOSTAT
    vera_device.power = 10
    vera_device.get_current_temperature.return_value = 71
    vera_device.get_hvac_mode.return_value = "Off"
    vera_device.get_current_goal_temperature.return_value = 72
    vera_device.get_heat_setpoint.return_value = None
    vera_device.get_cool_setpoint.return_value = None
    entity_id = "climate.dev1_1"

    component_data = await vera_component_factory.configure_component(
        hass=hass,
        controller_config=new_simple_controller_config(devices=(vera_device,)),
    )
    update_callback = component_data.controller_data[0].update_callback

    assert hass.states.get(entity_id).state == HVACMode.OFF

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": entity_id, "hvac_mode": HVACMode.COOL},
    )
    await hass.async_block_till_done()
    vera_device.turn_cool_on.assert_called()
    vera_device.get_hvac_mode.return_value = "CoolOn"
    update_callback(vera_device)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == HVACMode.COOL

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": entity_id, "hvac_mode": HVACMode.HEAT},
    )
    await hass.async_block_till_done()
    vera_device.turn_heat_on.assert_called()
    vera_device.get_hvac_mode.return_value = "HeatOn"
    update_callback(vera_device)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == HVACMode.HEAT

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": entity_id, "hvac_mode": HVACMode.HEAT_COOL},
    )
    await hass.async_block_till_done()
    vera_device.turn_auto_on.assert_called()
    vera_device.get_hvac_mode.return_value = "AutoChangeOver"
    update_callback(vera_device)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == HVACMode.HEAT_COOL

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": entity_id, "hvac_mode": HVACMode.OFF},
    )
    await hass.async_block_till_done()
    vera_device.turn_auto_on.assert_called()
    vera_device.get_hvac_mode.return_value = "Off"
    update_callback(vera_device)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == HVACMode.OFF

    await hass.services.async_call(
        "climate",
        "set_fan_mode",
        {"entity_id": entity_id, "fan_mode": "on"},
    )
    await hass.async_block_till_done()
    vera_device.turn_auto_on.assert_called()
    vera_device.get_fan_mode.return_value = "ContinuousOn"
    update_callback(vera_device)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).attributes["fan_mode"] == FAN_ON

    await hass.services.async_call(
        "climate",
        "set_fan_mode",
        {"entity_id": entity_id, "fan_mode": "off"},
    )
    await hass.async_block_till_done()
    vera_device.turn_auto_on.assert_called()
    vera_device.get_fan_mode.return_value = "Auto"
    update_callback(vera_device)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).attributes["fan_mode"] == FAN_AUTO

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": entity_id, "temperature": 30},
    )
    await hass.async_block_till_done()
    vera_device.set_temperature.assert_called_with(30)
    vera_device.get_current_goal_temperature.return_value = 30
    vera_device.get_current_temperature.return_value = 25
    update_callback(vera_device)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).attributes["current_temperature"] == 25
    assert hass.states.get(entity_id).attributes["temperature"] == 30


@pytest.mark.parametrize(
    ("vera_hvac_state", "expected_hvac_action"),
    [
        pytest.param("Heating", HVACAction.HEATING, id="heating"),
        pytest.param("Cooling", HVACAction.COOLING, id="cooling"),
        pytest.param("PendingCool", HVACAction.IDLE, id="pending-cool"),
        pytest.param("PendingHeat", HVACAction.IDLE, id="pending-heat"),
        pytest.param("PendingIdle", HVACAction.IDLE, id="pending-idle"),
        pytest.param("Idle", HVACAction.IDLE, id="idle"),
        pytest.param("FanOnly", HVACAction.FAN, id="fan-only"),
        pytest.param("Vent", HVACAction.FAN, id="vent"),
        pytest.param("Off", HVACAction.OFF, id="off"),
        pytest.param("Unknown", None, id="unmapped"),
    ],
)
async def test_hvac_action(
    hass: HomeAssistant,
    vera_component_factory: ComponentFactory,
    vera_hvac_state: str,
    expected_hvac_action: HVACAction | None,
) -> None:
    """Test HVAC action."""
    vera_device: pv.VeraThermostat = MagicMock(spec=pv.VeraThermostat)
    vera_device.get_energy_mode.return_value = None
    vera_device.device_id = 1
    vera_device.vera_device_id = vera_device.device_id
    vera_device.comm_failure = False
    vera_device.name = "dev1"
    vera_device.category = pv.CATEGORY_THERMOSTAT
    vera_device.power = 10
    vera_device.get_current_temperature.return_value = 71
    vera_device.get_hvac_mode.return_value = "Off"
    vera_device.get_hvac_state.return_value = vera_hvac_state
    vera_device.get_current_goal_temperature.return_value = 72

    await vera_component_factory.configure_component(
        hass=hass,
        controller_config=new_simple_controller_config(devices=(vera_device,)),
    )

    state = hass.states.get("climate.dev1_1")
    assert state is not None
    assert state.attributes.get("hvac_action") == expected_hvac_action


async def test_climate_f(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test function."""
    vera_device: pv.VeraThermostat = MagicMock(spec=pv.VeraThermostat)
    vera_device.get_energy_mode.return_value = None
    vera_device.device_id = 1
    vera_device.vera_device_id = vera_device.device_id
    vera_device.comm_failure = False
    vera_device.name = "dev1"
    vera_device.category = pv.CATEGORY_THERMOSTAT
    vera_device.power = 10
    vera_device.get_current_temperature.return_value = 71
    vera_device.get_hvac_mode.return_value = "Off"
    vera_device.get_current_goal_temperature.return_value = 72
    entity_id = "climate.dev1_1"

    def setup_callback(controller: pv.VeraController) -> None:
        controller.temperature_units = "F"

    component_data = await vera_component_factory.configure_component(
        hass=hass,
        controller_config=new_simple_controller_config(
            devices=(vera_device,), setup_callback=setup_callback
        ),
    )
    update_callback = component_data.controller_data[0].update_callback

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": entity_id, "temperature": 30},
    )
    await hass.async_block_till_done()
    vera_device.set_temperature.assert_called_with(86)
    vera_device.get_current_goal_temperature.return_value = 30
    vera_device.get_current_temperature.return_value = 25
    update_callback(vera_device)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).attributes["current_temperature"] == -3.9
    assert hass.states.get(entity_id).attributes["temperature"] == -1.1


def _new_heat_cool_thermostat(vera_hvac_mode: str) -> pv.VeraThermostat:
    """Return a thermostat that reports separate heat and cool setpoints."""
    vera_device: pv.VeraThermostat = MagicMock(spec=pv.VeraThermostat)
    vera_device.get_energy_mode.return_value = None
    vera_device.device_id = 1
    vera_device.vera_device_id = vera_device.device_id
    vera_device.comm_failure = False
    vera_device.name = "dev1"
    vera_device.category = pv.CATEGORY_THERMOSTAT
    vera_device.power = 10
    vera_device.get_current_temperature.return_value = 20
    vera_device.get_hvac_mode.return_value = vera_hvac_mode
    # Some Vera firmware reports the midpoint here while in auto mode.
    vera_device.get_current_goal_temperature.return_value = 21.75
    vera_device.get_heat_setpoint.return_value = 19.5
    vera_device.get_cool_setpoint.return_value = 24
    return vera_device


@pytest.mark.parametrize(
    ("vera_hvac_mode", "expected_target", "setter"),
    [
        pytest.param("HeatOn", 19.5, "set_heat_setpoint", id="heat"),
        pytest.param("CoolOn", 24, "set_cool_setpoint", id="cool"),
    ],
)
async def test_heat_cool_setpoints_single_mode(
    hass: HomeAssistant,
    vera_component_factory: ComponentFactory,
    vera_hvac_mode: str,
    expected_target: float,
    setter: str,
) -> None:
    """Test heat and cool modes use the matching setpoint."""
    vera_device = _new_heat_cool_thermostat(vera_hvac_mode)
    entity_id = "climate.dev1_1"

    await vera_component_factory.configure_component(
        hass=hass,
        controller_config=new_simple_controller_config(devices=(vera_device,)),
    )
    vera_device.refresh_states.assert_called()

    state = hass.states.get(entity_id)
    assert state.attributes["temperature"] == expected_target
    assert "target_temp_low" not in state.attributes
    assert "target_temp_high" not in state.attributes

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": entity_id, "temperature": 21},
        blocking=True,
    )
    getattr(vera_device, setter).assert_called_once_with(21)
    vera_device.set_temperature.assert_not_called()


async def test_heat_cool_setpoints_auto_mode(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test auto mode exposes the heat and cool setpoints as a range."""
    vera_device = _new_heat_cool_thermostat("AutoChangeOver")
    entity_id = "climate.dev1_1"

    await vera_component_factory.configure_component(
        hass=hass,
        controller_config=new_simple_controller_config(devices=(vera_device,)),
    )

    state = hass.states.get(entity_id)
    assert state.state == HVACMode.HEAT_COOL
    assert "temperature" not in state.attributes
    assert state.attributes["target_temp_low"] == 19.5
    assert state.attributes["target_temp_high"] == 24
    features = state.attributes["supported_features"]
    assert features & ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
    assert not features & ClimateEntityFeature.TARGET_TEMPERATURE

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": entity_id, "target_temp_low": 18, "target_temp_high": 25},
        blocking=True,
    )
    vera_device.set_heat_setpoint.assert_called_once_with(18)
    vera_device.set_cool_setpoint.assert_called_once_with(25)
    vera_device.set_temperature.assert_not_called()

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "climate",
            "set_temperature",
            {"entity_id": entity_id, "temperature": 21},
            blocking=True,
        )
    vera_device.set_temperature.assert_not_called()


async def test_heat_cool_setpoints_set_temperature_with_hvac_mode(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test a mode change in set_temperature writes the new mode's setpoint."""
    vera_device = _new_heat_cool_thermostat("HeatOn")
    entity_id = "climate.dev1_1"

    def turn_cool_on() -> None:
        # pyvera caches the requested mode when it is set.
        vera_device.get_hvac_mode.return_value = "CoolOn"

    vera_device.turn_cool_on.side_effect = turn_cool_on

    await vera_component_factory.configure_component(
        hass=hass,
        controller_config=new_simple_controller_config(devices=(vera_device,)),
    )

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": entity_id, "temperature": 23, "hvac_mode": HVACMode.COOL},
        blocking=True,
    )
    vera_device.turn_cool_on.assert_called_once()
    vera_device.set_cool_setpoint.assert_called_once_with(23)
    vera_device.set_heat_setpoint.assert_not_called()


async def test_energy_mode_preset(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test the eco preset follows the thermostat's energy mode."""
    vera_device = _new_heat_cool_thermostat("HeatOn")
    vera_device.get_energy_mode.return_value = "Normal"
    entity_id = "climate.dev1_1"

    component_data = await vera_component_factory.configure_component(
        hass=hass,
        controller_config=new_simple_controller_config(devices=(vera_device,)),
    )
    update_callback = component_data.controller_data[0].update_callback

    state = hass.states.get(entity_id)
    assert state.attributes["preset_mode"] == PRESET_NONE
    assert state.attributes["preset_modes"] == [PRESET_NONE, PRESET_ECO]
    assert state.attributes["supported_features"] & ClimateEntityFeature.PRESET_MODE
    assert state.attributes["temperature"] == 19.5

    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": entity_id, "preset_mode": PRESET_ECO},
        blocking=True,
    )
    vera_device.set_energy_mode.assert_called_once_with("EnergySavingsMode")

    # In energy savings mode the Vera reports the economy variant of the mode.
    vera_device.get_energy_mode.return_value = "EnergySavingsMode"
    vera_device.get_hvac_mode.return_value = "EconomyHeatOn"
    update_callback(vera_device)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == HVACMode.HEAT
    assert state.attributes["preset_mode"] == PRESET_ECO
    # The setback setpoint is not reported, so no target is exposed.
    assert "temperature" not in state.attributes
    assert not state.attributes["supported_features"] & (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
    )

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "climate",
            "set_temperature",
            {"entity_id": entity_id, "temperature": 21},
            blocking=True,
        )
    vera_device.set_heat_setpoint.assert_not_called()

    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": entity_id, "preset_mode": PRESET_NONE},
        blocking=True,
    )
    vera_device.set_energy_mode.assert_called_with("Normal")


@pytest.mark.parametrize(
    ("vera_hvac_mode", "expected_mode"),
    [
        pytest.param("EconomyHeatOn", HVACMode.HEAT, id="heat"),
        pytest.param("EconomyCoolOn", HVACMode.COOL, id="cool"),
        pytest.param("EconomyAutoChangeOver", HVACMode.HEAT_COOL, id="auto"),
    ],
)
async def test_economy_hvac_modes(
    hass: HomeAssistant,
    vera_component_factory: ComponentFactory,
    vera_hvac_mode: str,
    expected_mode: HVACMode,
) -> None:
    """Test economy variants of the hvac mode map to the base mode."""
    vera_device = _new_heat_cool_thermostat(vera_hvac_mode)
    vera_device.get_energy_mode.return_value = "EnergySavingsMode"

    await vera_component_factory.configure_component(
        hass=hass,
        controller_config=new_simple_controller_config(devices=(vera_device,)),
    )

    assert hass.states.get("climate.dev1_1").state == expected_mode


async def test_no_energy_mode(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test thermostats without an energy mode do not offer presets."""
    vera_device = _new_heat_cool_thermostat("HeatOn")

    await vera_component_factory.configure_component(
        hass=hass,
        controller_config=new_simple_controller_config(devices=(vera_device,)),
    )

    state = hass.states.get("climate.dev1_1")
    assert "preset_mode" not in state.attributes
    assert not state.attributes["supported_features"] & ClimateEntityFeature.PRESET_MODE
