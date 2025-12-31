#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
Example: 24-Hour Daily Simulation of Multi-Energy Microgrid (Section 1.1)
================================================================================

This example demonstrates:
1. Running a complete 24-hour simulation
2. Realistic daily load and renewable profiles
3. Control strategies (load-following, battery optimization)
4. Results analysis and export

AUTHOR: Research Support System
DATE: December 31, 2025

================================================================================
"""

import sys
import numpy as np
from pathlib import Path
from typing import List, Dict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from components.microgrid_components import (
    MicrogridConfig, MultiEnergyMicrogridSystem
)


class DailySimulation:
    """
    24-Hour simulation with realistic profiles and control
    """
    
    def __init__(self, config: MicrogridConfig = None):
        """
        Initialize simulation
        
        Args:
            config: MicrogridConfig (uses defaults if None)
        """
        if config is None:
            config = MicrogridConfig()
        
        self.memg = MultiEnergyMicrogridSystem(config)
        self.timesteps = []  # List to store results
        self.hourly_results = []
    
    def generate_solar_profile(self, day_type: str = "clear") -> np.ndarray:
        """
        Generate realistic daily solar irradiance profile
        
        برنامه گذاری ربود روزانه
        
        Args:
            day_type: 'clear', 'cloudy', or 'mixed'
            
        Returns:
            Array of irradiance values [W/m²] for 24 hours
        """
        time_hours = np.arange(24)
        
        # Clear day model (Erbs et al.)
        base_irr = 1000 * np.maximum(0, np.sin(
            np.pi * (time_hours - 6) / 12
        ))  # Peak at noon
        
        if day_type == "clear":
            irradiance = base_irr
        elif day_type == "cloudy":
            # 30-50% reduction with variations
            irradiance = base_irr * (0.3 + 0.2 * np.random.rand(24))
        else:  # mixed
            # Morning clear, afternoon cloudy
            irradiance = base_irr * np.where(
                time_hours < 14,
                0.9,  # Morning: 90%
                0.5   # Afternoon: 50%
            )
        
        return irradiance
    
    def generate_wind_profile(self, scenario: str = "moderate") -> np.ndarray:
        """
        Generate realistic daily wind speed profile
        
        برنامه گذاری باد
        
        Args:
            scenario: 'low', 'moderate', 'high'
            
        Returns:
            Array of wind speeds [m/s] for 24 hours
        """
        time_hours = np.arange(24)
        
        # Base profile: higher at day, lower at night
        base_wind = 3 + 4 * np.sin(np.pi * (time_hours - 6) / 12)
        
        if scenario == "low":
            wind = base_wind * 0.5
        elif scenario == "high":
            wind = base_wind * 1.5
        else:  # moderate
            wind = base_wind
        
        # Add stochasticity
        wind += np.random.normal(0, 0.5, 24)
        wind = np.maximum(0, wind)
        
        return wind
    
    def generate_load_profile(
        self,
        scenario: str = "residential"
    ) -> tuple:
        """
        Generate realistic daily load profiles
        
        برنامه گذاری بار
        
        Args:
            scenario: 'residential', 'commercial', 'mixed'
            
        Returns:
            (electrical_load, thermal_load) arrays [kW]
        """
        time_hours = np.arange(24)
        
        if scenario == "residential":
            # Morning peak, evening peak
            elec_load = (
                8 +  # Base load
                4 * np.exp(-((time_hours - 7) ** 2) / 5) +  # Morning
                6 * np.exp(-((time_hours - 18) ** 2) / 8)  # Evening
            )
            # Thermal: heating need decreases with time
            thermal_load = 12 - 2 * np.sin(np.pi * time_hours / 24)
        
        elif scenario == "commercial":
            # High during business hours, low at night
            elec_load = np.where(
                (time_hours >= 8) & (time_hours <= 18),
                18,  # Business hours: 18 kW
                6    # Off-hours: 6 kW
            )
            thermal_load = np.where(
                (time_hours >= 8) & (time_hours <= 18),
                12,  # Business hours
                4    # Off-hours
            )
        
        else:  # mixed
            elec_load = (
                10 +
                3 * np.exp(-((time_hours - 7) ** 2) / 5) +
                5 * np.exp(-((time_hours - 19) ** 2) / 8)
            )
            thermal_load = 10 - 1.5 * np.sin(np.pi * time_hours / 24)
        
        return np.maximum(0, elec_load), np.maximum(0, thermal_load)
    
    def generate_temperature_profile(self) -> np.ndarray:
        """
        Generate realistic daily temperature profile
        
        برنامه گذاری دما
        
        Returns:
            Array of temperatures [°C] for 24 hours
        """
        time_hours = np.arange(24)
        # Minimum at 5:00, maximum at 15:00
        temperature = 15 + 8 * np.sin(np.pi * (time_hours - 5) / 12)
        return temperature
    
    def simple_control_strategy(
        self,
        state_before: Dict,
        p_load_elec: float,
        q_load_thermal: float,
        hour: int,
        config: MicrogridConfig,
    ) -> tuple:
        """
        Simple control strategy for battery and CHP
        
        ستراتژی کنترل ساده: 
        - شارژ باتری هنگام افت جوی (قیمت پایین)
        - CHP برای بار حرارتی
        - بویلر فقط اگر لازم
        
        Args:
            state_before: Previous system state
            p_load_elec: Current electrical load
            q_load_thermal: Current thermal load
            hour: Current hour (0-23)
            config: Microgrid configuration
            
        Returns:
            (p_battery_cmd, p_chp_cmd, q_boiler_cmd)
        """
        # Battery control: charge during off-peak, discharge during peak
        if 9 <= hour <= 17:  # Peak hours
            # Discharge if SOC is above minimum
            if state_before['soc'] > 0.4:
                p_battery_cmd = -config.battery.power_max * 0.7
            else:
                p_battery_cmd = 0.0
        else:  # Off-peak
            # Charge if SOC is below maximum
            if state_before['soc'] < 0.8:
                p_battery_cmd = config.battery.power_max * 0.8
            else:
                p_battery_cmd = 0.0
        
        # CHP follows thermal load (with hysteresis)
        p_chp_cmd = min(q_load_thermal / config.chp.eta_thermal * 1.1,
                       config.chp.power_elec_max)
        p_chp_cmd = max(config.chp.min_load, p_chp_cmd)  # Minimum load
        
        # Boiler only for supplementary heat if needed
        q_chp = p_chp_cmd * config.chp.eta_thermal
        q_deficit = max(0, q_load_thermal - q_chp)
        q_boiler_cmd = min(q_deficit * 1.2, config.boiler.power_max)
        
        return p_battery_cmd, p_chp_cmd, q_boiler_cmd
    
    def run_24h_simulation(
        self,
        solar_scenario: str = "clear",
        wind_scenario: str = "moderate",
        load_scenario: str = "residential",
        use_control: bool = True,
    ):
        """
        Run complete 24-hour simulation
        
        اجرای شبيه سازی ۲۴ ساعته
        
        Args:
            solar_scenario: Weather scenario for solar
            wind_scenario: Weather scenario for wind
            load_scenario: Load type
            use_control: Use control strategy or open-loop
        """
        # Generate profiles
        solar_irr = self.generate_solar_profile(solar_scenario)
        wind_speed = self.generate_wind_profile(wind_scenario)
        p_load, q_load = self.generate_load_profile(load_scenario)
        temperature = self.generate_temperature_profile()
        
        print(f"\n{'='*80}")
        print(f"24-HOUR SIMULATION: {solar_scenario.upper()} DAY, {load_scenario.upper()} LOAD")
        print(f"{'='*80}")
        print(f"\n{'Hour':>4} {'Time':>6} {'P_PV':>6} {'P_WT':>6} {'Load':>6} | "
              f"{'SOC':>6} {'P_Bat':>7} {'T_TES':>6} | {'Cost':>7} {'Violations':>10}")
        print("-" * 95)
        
        # Simulation loop
        self.hourly_results = []
        state = None
        
        for hour in range(24):
            # Initial state for control (first hour: assume ~50% SOC)
            if state is None:
                state = {
                    'soc': 0.50,
                    'temp_tes': 55.0,
                    'cost_total': 0.0,
                }
            
            # Determine control actions
            if use_control:
                p_bat_cmd, p_chp_cmd, q_boil_cmd = self.simple_control_strategy(
                    state, p_load[hour], q_load[hour], hour, self.memg.config
                )
            else:
                # Open-loop: fixed operation
                p_bat_cmd = 5.0 if hour < 12 else -3.0
                p_chp_cmd = 7.0
                q_boil_cmd = 2.0
            
            # Execute simulation step
            state = self.memg.step(
                p_load_elec=p_load[hour],
                q_load_thermal=q_load[hour],
                solar_irradiance=solar_irr[hour],
                wind_speed=wind_speed[hour],
                ambient_temp=temperature[hour],
                p_battery_cmd=p_bat_cmd,
                p_chp_cmd=p_chp_cmd,
                q_boiler_cmd=q_boil_cmd,
            )
            
            # Store results
            state['hour'] = hour
            state['time'] = f"{hour:02d}:00"
            state['p_load_cmd'] = p_load[hour]
            state['q_load_cmd'] = q_load[hour]
            self.hourly_results.append(state)
            
            # Print summary
            time_str = f"{hour:02d}:00"
            print(f"{hour:4d} {time_str:>6} "
                  f"{state['p_pv']:6.2f} {state['p_wt']:6.2f} {state['p_load_elec']:6.2f} | "
                  f"{state['soc']:6.1%} {state['p_battery']:7.2f} {state['temp_tes']:6.1f} | "
                  f"{state['cost_total']:7.2f} € {state['violation_count']:10d}")
        
        print("-" * 95)
    
    def print_daily_summary(self):
        """
        Print summary statistics for 24-hour period
        
        چاپ خلاصه روزانه
        """
        if not self.hourly_results:
            return
        
        print(f"\n{'='*80}")
        print("DAILY SUMMARY STATISTICS")
        print(f"{'='*80}")
        
        # Energy generation
        total_pv = sum([h['p_pv'] for h in self.hourly_results])
        total_wt = sum([h['p_wt'] for h in self.hourly_results])
        total_chp = sum([h['p_chp'] for h in self.hourly_results])
        total_load = sum([h['p_load_elec'] for h in self.hourly_results])
        
        print(f"\nELECTRICAL ENERGY (kWh):")
        print(f"  PV Generation:       {total_pv:8.2f} kWh")
        print(f"  Wind Generation:     {total_wt:8.2f} kWh")
        print(f"  CHP Generation:      {total_chp:8.2f} kWh")
        print(f"  Total Generation:    {total_pv + total_wt + total_chp:8.2f} kWh")
        print(f"  Total Load:          {total_load:8.2f} kWh")
        
        # Battery statistics
        soc_min = min([h['soc'] for h in self.hourly_results])
        soc_max = max([h['soc'] for h in self.hourly_results])
        soc_mean = np.mean([h['soc'] for h in self.hourly_results])
        
        print(f"\nBATTERY STATE:")
        print(f"  Min SOC:             {soc_min:8.1%}")
        print(f"  Max SOC:             {soc_max:8.1%}")
        print(f"  Mean SOC:            {soc_mean:8.1%}")
        
        # Thermal statistics
        temp_min = min([h['temp_tes'] for h in self.hourly_results])
        temp_max = max([h['temp_tes'] for h in self.hourly_results])
        temp_mean = np.mean([h['temp_tes'] for h in self.hourly_results])
        
        print(f"\nTHERMAL STORAGE:")
        print(f"  Min Temperature:     {temp_min:8.1f} °C")
        print(f"  Max Temperature:     {temp_max:8.1f} °C")
        print(f"  Mean Temperature:    {temp_mean:8.1f} °C")
        
        # Cost analysis
        total_cost_grid = sum([h['cost_grid'] for h in self.hourly_results])
        total_cost_chp = sum([h['cost_fuel_chp'] for h in self.hourly_results])
        total_cost_boiler = sum([h['cost_fuel_boiler'] for h in self.hourly_results])
        total_cost = total_cost_grid + total_cost_chp + total_cost_boiler
        
        print(f"\nDOWNSTREAM COST (€):")
        print(f"  Grid Exchange:       {total_cost_grid:8.2f} €")
        print(f"  CHP Fuel:            {total_cost_chp:8.2f} €")
        print(f"  Boiler Fuel:         {total_cost_boiler:8.2f} €")
        print(f"  TOTAL COST:          {total_cost:8.2f} €")
        print(f"  Per Hour:            {total_cost/24:8.2f} €/h")
        print(f"  Per kWh:             {total_cost/total_load:8.2f} €/kWh")
        
        # Constraint violations
        total_violations = sum([h['violation_count'] for h in self.hourly_results])
        violation_hours = len([h for h in self.hourly_results if h['violation_count'] > 0])
        
        print(f"\nCONSTRAINT STATUS:")
        print(f"  Total Violations:    {total_violations:8d}")
        print(f"  Violation Hours:     {violation_hours:8d}/24")
        if total_violations == 0:
            print(f"  Status:              ✓ NO VIOLATIONS")
        else:
            print(f"  Status:              ⚠️  VIOLATIONS DETECTED")
        
        print(f"{'='*80}\n")
    
    def export_results_csv(self, filename: str = "results_24h.csv"):
        """
        Export results to CSV file
        
        صدور نتائج CSV
        
        Args:
            filename: Output filename
        """
        import csv
        
        with open(filename, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'hour', 'time', 'p_pv', 'p_wt', 'p_load_elec', 'p_battery',
                'p_chp', 'p_grid', 'soc', 'q_chp', 'q_boiler', 'temp_tes',
                'cost_grid', 'cost_fuel_chp', 'cost_fuel_boiler', 'cost_total',
                'violations'
            ])
            writer.writeheader()
            
            for result in self.hourly_results:
                writer.writerow({
                    'hour': result['hour'],
                    'time': result['time'],
                    'p_pv': f"{result['p_pv']:.2f}",
                    'p_wt': f"{result['p_wt']:.2f}",
                    'p_load_elec': f"{result['p_load_elec']:.2f}",
                    'p_battery': f"{result['p_battery']:.2f}",
                    'p_chp': f"{result['p_chp']:.2f}",
                    'p_grid': f"{result['p_grid']:.2f}",
                    'soc': f"{result['soc']:.3f}",
                    'q_chp': f"{result['q_chp']:.2f}",
                    'q_boiler': f"{result['q_boiler']:.2f}",
                    'temp_tes': f"{result['temp_tes']:.1f}",
                    'cost_grid': f"{result['cost_grid']:.2f}",
                    'cost_fuel_chp': f"{result['cost_fuel_chp']:.2f}",
                    'cost_fuel_boiler': f"{result['cost_fuel_boiler']:.2f}",
                    'cost_total': f"{result['cost_total']:.2f}",
                    'violations': result['violation_count'],
                })
        
        print(f"Results exported to {filename}")


if __name__ == "__main__":
    print("\n" + "*" * 80)
    print("* EXAMPLE: 24-HOUR DAILY MICROGRID SIMULATION (SECTION 1.1)")
    print("*" * 80)
    
    # Create simulator
    sim = DailySimulation()
    
    # Run simulation with control strategy
    sim.run_24h_simulation(
        solar_scenario="clear",
        wind_scenario="moderate",
        load_scenario="residential",
        use_control=True,
    )
    
    # Print detailed summary
    sim.print_daily_summary()
    
    # Export results
    sim.export_results_csv("microgrid_24h_results.csv")
    
    print("\n✓ Simulation completed successfully!")
    print("\nNext steps:")
    print("  1. Review microgrid_24h_results.csv")
    print("  2. Analyze patterns in load and generation")
    print("  3. Experiment with different scenarios and control strategies")
    print("  4. Compare with baseline controllers")
    print()
