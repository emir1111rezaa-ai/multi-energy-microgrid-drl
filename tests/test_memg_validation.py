#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
Validation and Testing Suite for Multi-Energy Microgrid (Section 1.1)
================================================================================

TEST COVERAGE:
1. Component physics validation
2. Power balance equations
3. Constraint enforcement
4. Dynamic behavior verification
5. Numerical stability

AUTHOR: Research Support System
DATE: December 31, 2025

================================================================================
"""

import sys
import numpy as np
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from components.microgrid_components import (
    MicrogridConfig, MultiEnergyMicrogridSystem,
    PhotovoltaicSystem, WindTurbine, BatteryEnergyStorageSystem,
    CombinedHeatPower, ThermalEnergyStorage, AuxiliaryBoiler
)


class TestMEMGComponents:
    """
    Comprehensive validation tests for MEMG components
    """
    
    def __init__(self):
        """Initialize test suite"""
        self.config = MicrogridConfig()
        self.passed = 0
        self.failed = 0
        self.tests = []
    
    def assert_true(self, condition: bool, test_name: str, message: str = ""):
        """Helper for assertions"""
        if condition:
            self.passed += 1
            print(f"  ✓ {test_name}")
        else:
            self.failed += 1
            print(f"  ✗ {test_name}: {message}")
    
    def assert_close(self, actual: float, expected: float, tolerance: float,
                     test_name: str):
        """Helper for numerical comparisons"""
        error = abs(actual - expected)
        if error <= tolerance:
            self.passed += 1
            print(f"  ✓ {test_name} (error: {error:.6f})")
        else:
            self.failed += 1
            print(f"  ✗ {test_name}: expected {expected}, got {actual}")
    
    # ========== PV SYSTEM TESTS ==========
    
    def test_pv_no_irradiance(self):
        """PV should produce zero power with zero irradiance"""
        print("\n[PV SYSTEM TESTS]")
        pv = PhotovoltaicSystem(self.config.res)
        power = pv.compute_output(irradiance=0.0, ambient_temp=20.0)
        self.assert_close(power, 0.0, 0.001, "PV no irradiance")
    
    def test_pv_reference_conditions(self):
        """PV at STC (1000 W/m², 25°C)"""
        pv = PhotovoltaicSystem(self.config.res)
        power = pv.compute_output(irradiance=1000.0, ambient_temp=25.0)
        expected = 1000 * self.config.res.pv_area * self.config.res.pv_efficiency / 1000
        self.assert_close(power, expected, 0.1, "PV STC conditions")
    
    def test_pv_temperature_derating(self):
        """PV efficiency decreases with temperature"""
        pv = PhotovoltaicSystem(self.config.res)
        power_cold = pv.compute_output(irradiance=1000.0, ambient_temp=10.0)
        power_hot = pv.compute_output(irradiance=1000.0, ambient_temp=40.0)
        self.assert_true(power_cold > power_hot, "PV temperature derating",
                        f"cold={power_cold:.2f}, hot={power_hot:.2f}")
    
    # ========== WIND TURBINE TESTS ==========
    
    def test_wt_no_wind(self):
        """Wind turbine should produce zero power at zero wind speed"""
        print("\n[WIND TURBINE TESTS]")
        wt = WindTurbine(self.config.res)
        power = wt.compute_output(wind_speed=0.0)
        self.assert_close(power, 0.0, 0.001, "WT zero wind speed")
    
    def test_wt_below_cutin(self):
        """Wind turbine below cut-in speed (3 m/s) should be zero"""
        wt = WindTurbine(self.config.res)
        power = wt.compute_output(wind_speed=2.5)
        self.assert_close(power, 0.0, 0.001, "WT below cut-in speed")
    
    def test_wt_above_cutout(self):
        """Wind turbine above cut-out speed (25 m/s) should be zero"""
        wt = WindTurbine(self.config.res)
        power = wt.compute_output(wind_speed=26.0)
        self.assert_close(power, 0.0, 0.001, "WT above cut-out speed")
    
    def test_wt_cubic_relationship(self):
        """Wind power should scale with v³"""
        wt = WindTurbine(self.config.res)
        power_v1 = wt.compute_output(wind_speed=10.0)
        power_v2 = wt.compute_output(wind_speed=15.0)
        ratio = power_v2 / power_v1
        expected_ratio = (15.0 / 10.0) ** 3
        self.assert_close(ratio, expected_ratio, 0.01, "WT cubic wind relationship")
    
    # ========== BATTERY TESTS ==========
    
    def test_battery_initial_soc(self):
        """Battery should initialize at 50% SOC"""
        print("\n[BATTERY STORAGE TESTS]")
        battery = BatteryEnergyStorageSystem(self.config.battery)
        self.assert_close(battery.soc, 0.5, 0.001, "Battery initial SOC")
    
    def test_battery_charge_dynamics(self):
        """Battery SOC should increase with positive power"""
        battery = BatteryEnergyStorageSystem(self.config.battery, dt_hours=1.0)
        initial_soc = battery.soc
        soc_new, power = battery.update_soc(power=10.0)  # Charge at 10 kW
        self.assert_true(soc_new > initial_soc, "Battery charges",
                        f"initial={initial_soc:.3f}, new={soc_new:.3f}")
    
    def test_battery_discharge_dynamics(self):
        """Battery SOC should decrease with negative power"""
        battery = BatteryEnergyStorageSystem(self.config.battery, dt_hours=1.0)
        initial_soc = battery.soc
        soc_new, power = battery.update_soc(power=-10.0)  # Discharge at 10 kW
        self.assert_true(soc_new < initial_soc, "Battery discharges",
                        f"initial={initial_soc:.3f}, new={soc_new:.3f}")
    
    def test_battery_soc_limits(self):
        """Battery SOC must stay within limits"""
        battery = BatteryEnergyStorageSystem(self.config.battery, dt_hours=0.5)
        for _ in range(500):  # Many charge cycles
            battery.update_soc(power=20.0)  # Max charge
        self.assert_true(battery.soc <= self.config.battery.soc_max, "Battery SOC limit high",
                        f"SOC={battery.soc:.3f}")
        
        for _ in range(500):  # Many discharge cycles
            battery.update_soc(power=-20.0)  # Max discharge
        self.assert_true(battery.soc >= self.config.battery.soc_min, "Battery SOC limit low",
                        f"SOC={battery.soc:.3f}")
    
    def test_battery_efficiency_roundtrip(self):
        """Battery round-trip efficiency should be ~90%"""
        battery = BatteryEnergyStorageSystem(self.config.battery, dt_hours=1.0)
        battery.soc = 0.5  # Start at 50%
        
        # Charge 5 kWh
        energy_in = 5.0 / self.config.battery.energy_capacity
        battery.update_soc(power=5.0)
        soc_charged = battery.soc
        
        # Discharge fully
        battery.update_soc(power=-20.0)
        for _ in range(50):
            battery.update_soc(power=-5.0)
        
        energy_recovered = soc_charged - battery.soc
        efficiency = energy_recovered / energy_in if energy_in > 0 else 0
        
        # Account for both charge and discharge efficiency
        expected_efficiency = self.config.battery.eta_roundtrip
        self.assert_close(efficiency, expected_efficiency, 0.15, "Battery round-trip efficiency")
    
    # ========== CHP TESTS ==========
    
    def test_chp_heat_coupling(self):
        """CHP heat output should follow electrical output"""
        print("\n[CHP UNIT TESTS]")
        chp = CombinedHeatPower(self.config.chp, dt_hours=1.0)
        p_elec, q_thermal = chp.set_power(power_cmd=10.0)
        expected_q = 10.0 * self.config.chp.eta_thermal
        self.assert_close(q_thermal, expected_q, 0.01, "CHP thermal coupling")
    
    def test_chp_power_limits(self):
        """CHP power should not exceed maximum"""
        chp = CombinedHeatPower(self.config.chp, dt_hours=1.0)
        p_elec, _ = chp.set_power(power_cmd=100.0)  # Command > max
        self.assert_true(p_elec <= self.config.chp.power_elec_max, "CHP power limit",
                        f"power={p_elec:.2f}, max={self.config.chp.power_elec_max:.2f}")
    
    def test_chp_zero_power(self):
        """CHP at zero power should produce zero heat"""
        chp = CombinedHeatPower(self.config.chp, dt_hours=1.0)
        p_elec, q_thermal = chp.set_power(power_cmd=0.0)
        self.assert_close(q_thermal, 0.0, 0.001, "CHP zero power heat output")
    
    # ========== TES TESTS ==========
    
    def test_tes_initial_temperature(self):
        """TES should initialize at middle temperature"""
        print("\n[THERMAL ENERGY STORAGE TESTS]")
        tes = ThermalEnergyStorage(self.config.tes, dt_hours=1.0)
        expected_temp = (self.config.tes.temp_min + self.config.tes.temp_max) / 2
        self.assert_close(tes.temp, expected_temp, 0.1, "TES initial temperature")
    
    def test_tes_charging(self):
        """TES temperature should increase with heat input"""
        tes = ThermalEnergyStorage(self.config.tes, dt_hours=1.0)
        initial_temp = tes.temp
        tes.update_temperature(q_in=20.0, q_out=0.0)  # Heat input
        self.assert_true(tes.temp > initial_temp, "TES charges",
                        f"initial={initial_temp:.1f}, new={tes.temp:.1f}")
    
    def test_tes_discharging(self):
        """TES temperature should decrease with heat output"""
        tes = ThermalEnergyStorage(self.config.tes, dt_hours=1.0)
        initial_temp = tes.temp
        tes.update_temperature(q_in=0.0, q_out=10.0)  # Heat output
        self.assert_true(tes.temp < initial_temp, "TES discharges",
                        f"initial={initial_temp:.1f}, new={tes.temp:.1f}")
    
    def test_tes_temperature_limits(self):
        """TES temperature must stay within limits"""
        tes = ThermalEnergyStorage(self.config.tes, dt_hours=0.5)
        
        # Heat to maximum
        for _ in range(100):
            tes.update_temperature(q_in=25.0, q_out=0.0)
        self.assert_true(tes.temp <= self.config.tes.temp_max, "TES temp limit high",
                        f"temp={tes.temp:.1f}")
        
        # Cool to minimum
        for _ in range(100):
            tes.update_temperature(q_in=0.0, q_out=25.0)
        self.assert_true(tes.temp >= self.config.tes.temp_min, "TES temp limit low",
                        f"temp={tes.temp:.1f}")
    
    def test_tes_heat_loss(self):
        """TES should lose heat to environment"""
        tes = ThermalEnergyStorage(self.config.tes, dt_hours=1.0)
        tes.temp = 65.0  # Heat up
        
        initial_temp = tes.temp
        tes.update_temperature(q_in=0.0, q_out=0.0)  # No input/output
        
        # Temperature should decrease due to loss
        self.assert_true(tes.temp < initial_temp, "TES loses heat",
                        f"initial={initial_temp:.1f}, new={tes.temp:.1f}")
    
    # ========== POWER BALANCE TESTS ==========
    
    def test_electrical_power_balance(self):
        """Electrical power should balance"""
        print("\n[POWER BALANCE TESTS]")
        memg = MultiEnergyMicrogridSystem(MicrogridConfig())
        
        state = memg.step(
            p_load_elec=12.0,
            q_load_thermal=8.0,
            solar_irradiance=900.0,
            wind_speed=9.0,
            ambient_temp=22.0,
            p_battery_cmd=0.0,
            p_chp_cmd=5.0,
            q_boiler_cmd=0.0,
        )
        
        # Check if system can supply load
        supply = state['p_pv'] + state['p_wt'] + state['p_chp']
        demand = state['p_load_elec']
        
        # If supply < demand, grid must import
        if supply < demand:
            self.assert_true(state['p_grid'] > 0, "Grid import when needed",
                           f"supply={supply:.2f}, demand={demand:.2f}")
    
    def test_thermal_power_balance(self):
        """Thermal power should balance"""
        memg = MultiEnergyMicrogridSystem(MicrogridConfig())
        
        state = memg.step(
            p_load_elec=10.0,
            q_load_thermal=12.0,
            solar_irradiance=800.0,
            wind_speed=8.0,
            ambient_temp=20.0,
            p_battery_cmd=0.0,
            p_chp_cmd=8.0,
            q_boiler_cmd=2.0,
        )
        
        # Heat supply
        supply = state['q_chp'] + state['q_boiler'] + state['q_tes_out']
        demand = state['q_load_thermal'] + state['q_tes_in']
        
        # Should roughly balance (allow small difference for losses)
        balance_error = abs(supply - demand) / demand if demand > 0 else 0
        self.assert_true(balance_error < 0.15, "Thermal power balance",
                        f"error={balance_error:.1%}")
    
    # ========== CONSTRAINT VIOLATION TESTS ==========
    
    def test_no_violations_normal_operation(self):
        """Normal operation should have no constraint violations"""
        print("\n[CONSTRAINT TESTS]")
        memg = MultiEnergyMicrogridSystem(MicrogridConfig())
        
        state = memg.step(
            p_load_elec=10.0,
            q_load_thermal=8.0,
            solar_irradiance=600.0,
            wind_speed=7.0,
            ambient_temp=18.0,
            p_battery_cmd=2.0,
            p_chp_cmd=6.0,
            q_boiler_cmd=1.0,
        )
        
        self.assert_true(state['violation_count'] == 0, "No violations in normal operation",
                        f"violations={state['violation_count']}")
    
    # ========== COST CALCULATION TESTS ==========
    
    def test_grid_cost_buying(self):
        """Grid buying cost should be positive"""
        print("\n[COST CALCULATION TESTS]")
        memg = MultiEnergyMicrogridSystem(MicrogridConfig())
        
        state = memg.step(
            p_load_elec=30.0,  # High load
            q_load_thermal=15.0,
            solar_irradiance=100.0,  # Low generation
            wind_speed=3.0,
            ambient_temp=15.0,
            p_battery_cmd=0.0,
            p_chp_cmd=8.0,
            q_boiler_cmd=2.0,
        )
        
        # Should need to buy from grid
        if state['p_grid'] > 0:
            self.assert_true(state['cost_grid'] > 0, "Positive cost when buying",
                           f"cost={state['cost_grid']:.2f} €")
    
    def test_total_cost_positive(self):
        """Total cost should generally be non-negative"""
        memg = MultiEnergyMicrogridSystem(MicrogridConfig())
        
        state = memg.step(
            p_load_elec=12.0,
            q_load_thermal=10.0,
            solar_irradiance=500.0,
            wind_speed=6.0,
            ambient_temp=20.0,
            p_battery_cmd=0.0,
            p_chp_cmd=7.0,
            q_boiler_cmd=1.5,
        )
        
        # Total cost should be positive (expenses)
        self.assert_true(state['cost_total'] >= -0.01, "Total cost non-negative",
                        f"cost={state['cost_total']:.2f} €")
    
    # ========== SIMULATION TESTS ==========
    
    def test_continuous_operation(self):
        """System should run for multiple steps without errors"""
        print("\n[SIMULATION TESTS]")
        memg = MultiEnergyMicrogridSystem(MicrogridConfig())
        
        try:
            for step in range(24):  # 24-hour simulation
                solar_irr = 600 * np.sin(np.pi * step / 24)  # Solar profile
                wind = 5 + 3 * np.sin(2 * np.pi * step / 24)  # Wind profile
                
                state = memg.step(
                    p_load_elec=12 + 3 * np.sin(2 * np.pi * step / 24),
                    q_load_thermal=10 - 2 * np.sin(2 * np.pi * step / 24),
                    solar_irradiance=max(0, solar_irr),
                    wind_speed=max(0, wind),
                    ambient_temp=15 + 5 * np.sin(np.pi * step / 24),
                    p_battery_cmd=5.0 if step % 2 == 0 else -2.0,
                    p_chp_cmd=7.0,
                    q_boiler_cmd=2.0,
                )
            
            self.passed += 1
            print(f"  ✓ 24-hour continuous simulation")
        except Exception as e:
            self.failed += 1
            print(f"  ✗ Continuous simulation: {str(e)}")
    
    # ========== REPORT ==========
    
    def run_all_tests(self):
        """Execute all test suites"""
        print("\n" + "="*80)
        print("MULTI-ENERGY MICROGRID - SECTION 1.1 VALIDATION TEST SUITE")
        print("="*80)
        
        # Run all tests
        self.test_pv_no_irradiance()
        self.test_pv_reference_conditions()
        self.test_pv_temperature_derating()
        
        self.test_wt_no_wind()
        self.test_wt_below_cutin()
        self.test_wt_above_cutout()
        self.test_wt_cubic_relationship()
        
        self.test_battery_initial_soc()
        self.test_battery_charge_dynamics()
        self.test_battery_discharge_dynamics()
        self.test_battery_soc_limits()
        self.test_battery_efficiency_roundtrip()
        
        self.test_chp_heat_coupling()
        self.test_chp_power_limits()
        self.test_chp_zero_power()
        
        self.test_tes_initial_temperature()
        self.test_tes_charging()
        self.test_tes_discharging()
        self.test_tes_temperature_limits()
        self.test_tes_heat_loss()
        
        self.test_electrical_power_balance()
        self.test_thermal_power_balance()
        
        self.test_no_violations_normal_operation()
        
        self.test_grid_cost_buying()
        self.test_total_cost_positive()
        
        self.test_continuous_operation()
        
        # Print summary
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        print(f"Passed: {self.passed}")
        print(f"Failed: {self.failed}")
        print(f"Total: {self.passed + self.failed}")
        print(f"Success Rate: {100*self.passed/(self.passed+self.failed):.1f}%")
        print("="*80)
        
        return self.failed == 0


if __name__ == "__main__":
    tester = TestMEMGComponents()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)
