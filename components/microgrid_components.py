#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
Multi-Energy Microgrid (MEMG) Component Models - Section 1.1
================================================================================

TITLE: بخش ۱.۱ - طراحی ریزشبکه چندانرژی
Section 1.1: Multi-Energy Microgrid Design

DESCRIPTION:
    Comprehensive implementation of electrical and thermal bus components for
    a multi-energy microgrid system. This module provides physics-based models
    for:
    
    ELECTRICAL BUS:
    - Photovoltaic (PV) system with temperature dependency
    - Wind turbine (WT) with power curve modeling
    - Battery Energy Storage System (BESS) with state-of-charge dynamics
    - Grid interface with buy/sell capabilities
    
    THERMAL BUS:
    - Combined Heat and Power (CHP) unit with efficiency coupling
    - Thermal Energy Storage (TES) with heat loss dynamics
    - Auxiliary boiler for peak thermal demand
    - Thermal load satisfaction

AUTHOR: Research Support System
DATE: December 31, 2025
VERSION: 1.0
COMPATIBILITY: Python 3.8+, NumPy 1.20+

REFERENCE:
    [1] Mocanu et al., "Deep learning for multi-energy systems," 2021
    [2] Structural design based on Section 1.1-1.3 of comprehensive framework
    
================================================================================
"""

import numpy as np
from typing import Tuple, Dict, Optional
from dataclasses import dataclass, field
from enum import Enum
import warnings


# ============================================================================
# 1. DATACLASS DEFINITIONS FOR PARAMETERS
# ============================================================================

@dataclass
class BatteryParameters:
    """
    Battery Energy Storage System (BESS) Parameters
    
    متغیرهای باتری (BESS):
    - مدل دینامیکی: SOC_{t+1} = SOC_t + (η_c × P_charge - P_discharge/η_d) × Δt / E_cap
    """
    energy_capacity: float = 50.0  # kWh - اندازه ظرفیت انرژی
    power_max: float = 20.0  # kW - حداکثر قدرت شارژ/دشارژ
    soc_min: float = 0.20  # - حد پایین SOC (20%)
    soc_max: float = 1.00  # - حد بالای SOC (100%)
    eta_charge: float = 0.95  # - بازده شارژ
    eta_discharge: float = 0.95  # - بازده دشارژ
    eta_roundtrip: float = 0.90  # - بازده رفت‌برگشت
    lifecycle_cycles: int = 3000  # - چرخه‌های عمر
    
    def __post_init__(self):
        """Validate parameters"""
        assert self.energy_capacity > 0, "Energy capacity must be positive"
        assert self.power_max > 0, "Power limit must be positive"
        assert 0 < self.soc_min < self.soc_max < 1, "SOC limits invalid"
        assert 0 < self.eta_charge <= 1 and 0 < self.eta_discharge <= 1, "Efficiency invalid"


@dataclass
class CHPParameters:
    """
    Combined Heat and Power (CHP) Unit Parameters
    
    متغیرهای CHP:
    - خروجی الکتریکی: P_elec (کنترل‌شده)
    - خروجی حرارتی: Q = η_thermal × P_elec
    """
    power_elec_max: float = 15.0  # kW - حداکثر توان الکتریکی
    eta_elec: float = 0.40  # - کارایی الکتریکی
    eta_thermal: float = 0.50  # - کارایی حرارتی
    ramp_rate_up: float = 5.0  # kW/min - سرعت افزایش
    ramp_rate_down: float = 5.0  # kW/min - سرعت کاهش
    startup_time: float = 5.0  # min - زمان راه‌اندازی
    min_load: float = 3.0  # kW - حداقل بار
    fuel_cost: float = 0.05  # €/kWh - هزینه سوخت
    
    def __post_init__(self):
        assert self.power_elec_max > 0 and self.min_load > 0
        assert 0 < self.eta_elec < 1 and 0 < self.eta_thermal < 1


@dataclass
class TESParameters:
    """
    Thermal Energy Storage (TES) Parameters
    
    متغیرهای ذخیره حرارتی:
    - دینامیک: T_{t+1} = T_t + (Q_in - Q_loss - Q_out) × Δt / C_thermal
    - تلفات: Q_loss = U_loss × (T_t - T_ambient)
    """
    energy_capacity: float = 100.0  # kWh - ظرفیت حرارتی
    temp_min: float = 45.0  # °C - حد پایین دما
    temp_max: float = 65.0  # °C - حد بالای دما
    temp_ambient: float = 20.0  # °C - دمای محیط
    u_loss: float = 0.5  # kW/°C - ضریب تلفات
    power_charge_max: float = 25.0  # kW - حداکثر قدرت شارژ
    power_discharge_max: float = 25.0  # kW - حداکثر قدرت دشارژ
    
    def __post_init__(self):
        assert self.temp_min < self.temp_max
        assert self.energy_capacity > 0
        assert 0 < self.u_loss <= 2.0


@dataclass
class BoilerParameters:
    """
    Auxiliary Boiler Parameters
    
    متغیرهای بویلر کمکی:
    - استفاده در شرایط بحرانی
    - کارایی پایین‌تر اما شامل (85%)
    """
    power_max: float = 20.0  # kW - حداکثر توان حرارتی
    eta: float = 0.85  # - کارایی حرارتی
    fuel_cost: float = 0.08  # €/kWh - هزینه سوخت مستقیم
    
    def __post_init__(self):
        assert self.power_max > 0 and 0 < self.eta <= 1


@dataclass
class RESParameters:
    """
    Renewable Energy Sources (PV & Wind) Parameters
    
    متغیرهای منابع تجدیدپذیر:
    - غیرقابل کنترل، نیاز به پیش‌بینی
    """
    pv_area: float = 50.0  # m² - مساحت پنل
    pv_efficiency: float = 0.20  # - بازده پنل (20%)
    pv_temp_coeff: float = -0.004  # /°C - ضریب دمایی
    pv_ref_temp: float = 25.0  # °C - دمای مرجع
    
    wt_rotor_area: float = 150.0  # m² - مساحت روتور
    wt_cp: float = 0.35  # - ضریب توان
    air_density: float = 1.225  # kg/m³ - چگالی هوا


@dataclass
class GridParameters:
    """
    Grid Interface Parameters
    
    متغیرهای رابط شبکه:
    - خرید و فروش انرژی
    - محدود‌های قدرت
    """
    power_import_max: float = 50.0  # kW - حداکثر خرید
    power_export_max: float = 50.0  # kW - حداکثر فروش
    price_buy: float = 0.15  # €/kWh - قیمت خرید
    price_sell: float = 0.08  # €/kWh - قیمت فروش
    price_dynamic: bool = False  # - قیمت پویا
    
    def __post_init__(self):
        assert self.price_buy > self.price_sell, "Buy price must exceed sell price"


@dataclass
class MicrogridConfig:
    """
    Complete Microgrid Configuration Container
    
    تجمیع کامل تمام پارامترهای سیستم
    """
    battery: BatteryParameters = field(default_factory=BatteryParameters)
    chp: CHPParameters = field(default_factory=CHPParameters)
    tes: TESParameters = field(default_factory=TESParameters)
    boiler: BoilerParameters = field(default_factory=BoilerParameters)
    res: RESParameters = field(default_factory=RESParameters)
    grid: GridParameters = field(default_factory=GridParameters)
    
    # Simulation parameters
    timestep_minutes: float = 60  # دقیقه - طول پله زمانی
    
    @property
    def timestep_hours(self) -> float:
        """Convert timestep to hours"""
        return self.timestep_minutes / 60.0


# ============================================================================
# 2. ELECTRICAL BUS COMPONENTS
# ============================================================================

class PhotovoltaicSystem:
    """
    Photovoltaic (PV) System Model
    
    فتوولتائیک - تولید انرژی الکتریکی از تابش خورشید
    
    MODEL EQUATION:
        P_PV(t) = G(t) × A × η₀ × [1 - α(T_cell - T_ref)]
        
    Where:
        G(t): Solar irradiance [W/m²]
        A: Panel area [m²]
        η₀: Nominal efficiency
        α: Temperature coefficient [/°C]
        T_cell: Cell temperature [°C]
        T_ref: Reference temperature [°C]
    """
    
    def __init__(self, config: RESParameters):
        """
        Initialize PV system
        
        Args:
            config: RESParameters containing PV specifications
        """
        self.area = config.pv_area
        self.eta_0 = config.pv_efficiency
        self.alpha = config.pv_temp_coeff
        self.t_ref = config.pv_ref_temp
        
    def compute_output(
        self,
        irradiance: float,
        ambient_temp: float = 20.0
    ) -> float:
        """
        Compute PV output power with temperature effect
        
        محاسبه تولید خورشیدی با اثر دما
        
        Args:
            irradiance: Solar irradiance [W/m²]
            ambient_temp: Ambient temperature [°C]
            
        Returns:
            Power output [kW]
        """
        # Simple cell temperature estimation (NOCT model approximation)
        t_cell = ambient_temp + (irradiance / 1000) * 20  # Rough estimate
        
        # Efficiency with temperature derating
        eta_actual = self.eta_0 * (1 + self.alpha * (t_cell - self.t_ref))
        eta_actual = max(0, eta_actual)  # Efficiency cannot be negative
        
        # Power output
        p_pv = (irradiance * self.area * eta_actual) / 1000  # Convert to kW
        
        return p_pv


class WindTurbine:
    """
    Wind Turbine Model
    
    توربین بادی - تولید انرژی الکتریکی از باد
    
    MODEL EQUATION:
        P_WT(t) = 0.5 × ρ × A × v³(t) × C_p(v)
        
    Where:
        ρ: Air density [kg/m³]
        A: Rotor swept area [m²]
        v(t): Wind speed [m/s]
        C_p: Power coefficient (non-linear function of v)
    """
    
    def __init__(self, config: RESParameters):
        """Initialize wind turbine"""
        self.rotor_area = config.wt_rotor_area
        self.cp = config.wt_cp  # Approximate average
        self.air_density = config.air_density
        self.v_cutout = 25.0  # m/s - Cut-out speed
        self.v_cutin = 3.0  # m/s - Cut-in speed
        
    def compute_output(self, wind_speed: float) -> float:
        """
        Compute wind turbine output
        
        محاسبه تولید باد
        
        Args:
            wind_speed: Wind speed [m/s]
            
        Returns:
            Power output [kW]
        """
        if wind_speed < self.v_cutin or wind_speed > self.v_cutout:
            return 0.0
        
        # Power output
        p_wt = (0.5 * self.air_density * self.rotor_area * 
                (wind_speed ** 3) * self.cp) / 1000  # Convert to kW
        
        return p_wt


class BatteryEnergyStorageSystem:
    """
    Battery Energy Storage System (BESS) with State-of-Charge Dynamics
    
    سیستم ذخیره‌سازی انرژی - باتری
    
    STATE EQUATION:
        SOC(t+1) = SOC(t) + [η_c × P_charge(t) - P_discharge(t)/η_d] × Δt / E_capacity
        
    CONSTRAINTS:
        SOC_min ≤ SOC(t) ≤ SOC_max
        -P_max ≤ P_battery(t) ≤ +P_max  (negative = discharge, positive = charge)
        
    POWER BALANCE:
        P_charge = max(0, P)  when P > 0
        P_discharge = max(0, -P)  when P < 0
    """
    
    def __init__(self, config: BatteryParameters, dt_hours: float = 1.0):
        """
        Initialize BESS
        
        Args:
            config: BatteryParameters
            dt_hours: Timestep in hours
        """
        self.e_capacity = config.energy_capacity  # kWh
        self.p_max = config.power_max  # kW
        self.soc_min = config.soc_min
        self.soc_max = config.soc_max
        self.eta_c = config.eta_charge
        self.eta_d = config.eta_discharge
        self.dt = dt_hours
        
        # Initialize state
        self.soc = 0.5  # Start at 50%
        self.p_battery = 0.0  # Current power
        
    def update_soc(self, power: float) -> Tuple[float, float]:
        """
        Update SOC based on battery power command
        
        به‌روزرسانی حالت شارژ براساس فرمان قدرت
        
        Args:
            power: Power command [kW] 
                  (positive = charge, negative = discharge)
                  
        Returns:
            (new_soc, actual_power_delivered)
        """
        # Clip power to maximum
        power_clipped = np.clip(power, -self.p_max, self.p_max)
        
        if power_clipped >= 0:  # Charging
            # Energy to add (accounting for efficiency loss)
            energy_add = power_clipped * self.eta_c * self.dt
            max_energy = (self.soc_max - self.soc) * self.e_capacity
            energy_add = min(energy_add, max_energy)
            self.soc += energy_add / self.e_capacity
            
        else:  # Discharging
            # Energy to remove
            power_discharge = abs(power_clipped)
            energy_remove = power_discharge * self.dt / self.eta_d
            max_energy = (self.soc - self.soc_min) * self.e_capacity
            energy_remove = min(energy_remove, max_energy)
            self.soc -= energy_remove / self.e_capacity
        
        # Enforce hard limits
        self.soc = np.clip(self.soc, self.soc_min, self.soc_max)
        self.p_battery = power_clipped
        
        return self.soc, power_clipped
    
    def get_available_charge_power(self) -> float:
        """Maximum charge power available without exceeding SOC_max"""
        available_energy = (self.soc_max - self.soc) * self.e_capacity
        available_power = available_energy / (self.eta_c * self.dt)
        return min(available_power, self.p_max)
    
    def get_available_discharge_power(self) -> float:
        """Maximum discharge power available without exceeding SOC_min"""
        available_energy = (self.soc - self.soc_min) * self.e_capacity
        available_power = available_energy * self.eta_d / self.dt
        return min(available_power, self.p_max)


class GridInterface:
    """
    Grid Interface for Energy Exchange
    
    رابط شبکه - خرید و فروش انرژی
    
    CONSTRAINTS:
        -P_import_max ≤ P_grid ≤ P_export_max
        (negative = buy, positive = sell)
    """
    
    def __init__(self, config: GridParameters):
        """Initialize grid interface"""
        self.p_import_max = config.power_import_max
        self.p_export_max = config.power_export_max
        self.price_buy = config.price_buy
        self.price_sell = config.price_sell
        self.price_dynamic = config.price_dynamic
        
    def compute_cost(self, power: float, price_buy: Optional[float] = None,
                    price_sell: Optional[float] = None) -> float:
        """
        Compute grid exchange cost
        
        محاسبه هزینه تبادل با شبکه
        
        Args:
            power: Power [kW] (negative = buy, positive = sell)
            price_buy: Buy price override [€/kWh]
            price_sell: Sell price override [€/kWh]
            
        Returns:
            Cost [€] (positive = expense, negative = revenue)
        """
        if price_buy is None:
            price_buy = self.price_buy
        if price_sell is None:
            price_sell = self.price_sell
        
        if power < 0:  # Buying
            cost = abs(power) * price_buy
        else:  # Selling
            cost = -power * price_sell
        
        return cost


# ============================================================================
# 3. THERMAL BUS COMPONENTS
# ============================================================================

class CombinedHeatPower:
    """
    Combined Heat and Power (CHP) Unit
    
    نیروگاه حرارت-برق ترکیبی (CHP)
    
    CHARACTERISTICS:
    - Coupled electrical and thermal outputs
    - Electrical output is controlled, thermal follows
    - Ramping constraints
    
    MODEL EQUATIONS:
        Q_thermal(t) = η_thermal × P_elec(t)
        P_elec(t): controlled input [0, P_max]
        
    RAMP CONSTRAINTS:
        |ΔP_elec| ≤ ramp_rate × Δt
    """
    
    def __init__(self, config: CHPParameters, dt_hours: float = 1.0):
        """
        Initialize CHP unit
        
        Args:
            config: CHPParameters
            dt_hours: Timestep in hours
        """
        self.p_elec_max = config.power_elec_max
        self.eta_elec = config.eta_elec
        self.eta_thermal = config.eta_thermal
        self.ramp_up = config.ramp_rate_up * dt_hours  # kW per timestep
        self.ramp_down = config.ramp_rate_down * dt_hours
        self.startup_time = config.startup_time
        self.min_load = config.min_load
        self.fuel_cost = config.fuel_cost
        
        # State variables
        self.p_elec = 0.0
        self.q_thermal = 0.0
        self.on = False
        self.startup_counter = 0
        
    def set_power(self, power_cmd: float) -> Tuple[float, float]:
        """
        Set CHP electrical power with constraints
        
        تعیین توان الکتریکی CHP با در نظر گرفتن قیود رمپ
        
        Args:
            power_cmd: Desired electrical power [kW]
            
        Returns:
            (p_elec_actual, q_thermal)
        """
        # Apply ramp constraints
        power_cmd_limited = power_cmd
        if self.p_elec > 0:
            max_increase = self.p_elec + self.ramp_up
            max_decrease = self.p_elec - self.ramp_down
            power_cmd_limited = np.clip(power_cmd_limited, max_decrease, max_increase)
        
        # Apply power limits
        power_cmd_limited = np.clip(power_cmd_limited, 0, self.p_elec_max)
        
        # Check minimum load constraint
        if 0 < power_cmd_limited < self.min_load:
            if power_cmd_limited < self.min_load / 2:
                power_cmd_limited = 0
            else:
                power_cmd_limited = self.min_load
        
        self.p_elec = power_cmd_limited
        self.q_thermal = self.eta_thermal * self.p_elec
        
        return self.p_elec, self.q_thermal
    
    def get_fuel_cost(self) -> float:
        """Get hourly fuel cost"""
        return self.p_elec * self.fuel_cost


class ThermalEnergyStorage:
    """
    Thermal Energy Storage (TES) System
    
    سیستم ذخیره‌سازی انرژی حرارتی
    
    STATE EQUATION:
        T(t+1) = T(t) + [Q_in(t) - Q_loss(t) - Q_out(t)] × Δt / C_thermal
        
    LOSS MODEL:
        Q_loss(t) = U_loss × [T(t) - T_ambient]
        
    CONSTRAINTS:
        T_min ≤ T(t) ≤ T_max
    """
    
    def __init__(self, config: TESParameters, dt_hours: float = 1.0):
        """
        Initialize TES
        
        Args:
            config: TESParameters
            dt_hours: Timestep in hours
        """
        self.e_capacity = config.energy_capacity  # kWh
        self.t_min = config.temp_min
        self.t_max = config.temp_max
        self.t_ambient = config.temp_ambient
        self.u_loss = config.u_loss  # kW/°C
        self.p_charge_max = config.power_charge_max
        self.p_discharge_max = config.power_discharge_max
        self.dt = dt_hours
        
        # Derived parameters
        # C_thermal: thermal capacity [kWh/°C]
        # Assuming T_max - T_min = 20°C spans full capacity
        self.c_thermal = self.e_capacity / (self.t_max - self.t_min)
        
        # Initialize state to middle temperature
        self.temp = (self.t_min + self.t_max) / 2
        
    def update_temperature(
        self,
        q_in: float,
        q_out: float
    ) -> float:
        """
        Update TES temperature
        
        به‌روزرسانی دمای ذخیره حرارتی
        
        Args:
            q_in: Heat input [kW]
            q_out: Heat output [kW]
            
        Returns:
            New temperature [°C]
        """
        # Clip inputs to maximum power
        q_in = np.clip(q_in, 0, self.p_charge_max)
        q_out = np.clip(q_out, 0, self.p_discharge_max)
        
        # Calculate heat loss
        q_loss = self.u_loss * (self.temp - self.t_ambient)
        q_loss = max(0, q_loss)  # Loss only when T > T_ambient
        
        # Temperature dynamics
        dT = (q_in - q_out - q_loss) * self.dt / self.c_thermal
        self.temp += dT
        
        # Hard constraints on temperature
        self.temp = np.clip(self.temp, self.t_min, self.t_max)
        
        return self.temp
    
    def get_available_charge(self) -> float:
        """Maximum charge power without exceeding T_max"""
        temp_margin = self.t_max - self.temp
        available_power = temp_margin * self.c_thermal / self.dt
        return min(available_power, self.p_charge_max)
    
    def get_available_discharge(self) -> float:
        """Maximum discharge power without exceeding T_min"""
        temp_margin = self.temp - self.t_min
        available_power = temp_margin * self.c_thermal / self.dt
        return min(available_power, self.p_discharge_max)


class AuxiliaryBoiler:
    """
    Auxiliary Boiler for Peak Thermal Demand
    
    بویلر کمکی برای تقاضای حرارتی پیک
    
    CHARACTERISTICS:
    - Lower efficiency than CHP
    - Higher fuel cost
    - Used only when necessary (peak/emergency)
    """
    
    def __init__(self, config: BoilerParameters, dt_hours: float = 1.0):
        """Initialize boiler"""
        self.p_max = config.power_max
        self.eta = config.eta
        self.fuel_cost = config.fuel_cost
        self.dt = dt_hours
        self.q_thermal = 0.0
        
    def set_power(self, power_cmd: float) -> float:
        """
        Set boiler thermal power
        
        تعیین توان حرارتی بویلر
        
        Args:
            power_cmd: Desired thermal power [kW]
            
        Returns:
            Actual thermal power [kW]
        """
        self.q_thermal = np.clip(power_cmd, 0, self.p_max)
        return self.q_thermal
    
    def get_fuel_cost(self) -> float:
        """Get hourly fuel cost"""
        return self.q_thermal / self.eta * self.fuel_cost


# ============================================================================
# 4. INTEGRATED MICROGRID SYSTEM
# ============================================================================

class MultiEnergyMicrogridSystem:
    """
    Complete Multi-Energy Microgrid (MEMG) System
    
    سیستم یکپارچه ریزشبکه چندانرژی
    
    STRUCTURE:
        Electrical Bus:
        ├─ PV System (non-dispatchable)
        ├─ Wind Turbine (non-dispatchable)
        ├─ Battery Storage (dispatchable)
        ├─ CHP (dispatchable)
        └─ Grid Interface
        
        Thermal Bus:
        ├─ CHP Heat Output (from electrical)
        ├─ Thermal Storage (TES)
        ├─ Boiler (emergency)
        └─ Thermal Load
    
    POWER BALANCE EQUATIONS:
        ELECTRICAL:
            P_PV + P_WT + P_CHP + P_battery_out + P_grid_buy = 
            P_load_elec + P_battery_in + P_grid_sell
        
        THERMAL:
            Q_CHP + Q_boiler + Q_TES_out = Q_load_thermal + Q_TES_in + Q_loss
    """
    
    def __init__(self, config: MicrogridConfig):
        """
        Initialize complete MEMG system
        
        Args:
            config: MicrogridConfig containing all parameters
        """
        self.config = config
        self.dt_hours = config.timestep_hours
        
        # Electrical components
        self.pv = PhotovoltaicSystem(config.res)
        self.wt = WindTurbine(config.res)
        self.battery = BatteryEnergyStorageSystem(config.battery, self.dt_hours)
        self.grid = GridInterface(config.grid)
        
        # Thermal components
        self.chp = CombinedHeatPower(config.chp, self.dt_hours)
        self.tes = ThermalEnergyStorage(config.tes, self.dt_hours)
        self.boiler = AuxiliaryBoiler(config.boiler, self.dt_hours)
        
        # Operating point tracking
        self.p_pv = 0.0
        self.p_wt = 0.0
        self.p_load_elec = 0.0
        self.q_load_thermal = 0.0
        
        # Cost tracking
        self.cost_grid = 0.0
        self.cost_fuel_chp = 0.0
        self.cost_fuel_boiler = 0.0
        self.cost_total = 0.0
    
    def step(
        self,
        p_load_elec: float,
        q_load_thermal: float,
        solar_irradiance: float,
        wind_speed: float,
        ambient_temp: float,
        p_battery_cmd: float,
        p_chp_cmd: float,
        q_boiler_cmd: float,
        price_buy: Optional[float] = None,
        price_sell: Optional[float] = None,
    ) -> Dict:
        """
        Execute one simulation timestep
        
        اجرای یک گام شبیه‌سازی کامل
        
        Args:
            p_load_elec: Electrical load demand [kW]
            q_load_thermal: Thermal load demand [kW]
            solar_irradiance: Solar irradiance [W/m²]
            wind_speed: Wind speed [m/s]
            ambient_temp: Ambient temperature [°C]
            p_battery_cmd: Battery power command [kW]
            p_chp_cmd: CHP electrical power command [kW]
            q_boiler_cmd: Boiler thermal power command [kW]
            price_buy: Optional dynamic buy price [€/kWh]
            price_sell: Optional dynamic sell price [€/kWh]
            
        Returns:
            Dictionary with complete system state
        """
        # ===== ELECTRICAL BUS =====
        
        # 1. RES generation (non-controllable)
        self.p_pv = self.pv.compute_output(solar_irradiance, ambient_temp)
        self.p_wt = self.wt.compute_output(wind_speed)
        self.p_load_elec = max(0, p_load_elec)  # Ensure non-negative load
        
        # 2. CHP electrical output
        p_chp, q_chp = self.chp.set_power(p_chp_cmd)
        
        # 3. Battery operation
        soc_new, p_bat_actual = self.battery.update_soc(p_battery_cmd)
        
        # 4. Power balance and grid exchange
        # P_grid = Load - RES - CHP - Battery_out + Battery_in
        p_available = self.p_pv + self.p_wt + p_chp
        p_net_load = self.p_load_elec - p_available
        
        # Grid power (positive = buy, negative = sell)
        if p_battery_cmd >= 0:  # Battery charging
            p_grid = p_net_load + p_battery_cmd
        else:  # Battery discharging
            p_grid = p_net_load + abs(p_bat_actual)
        
        # Apply grid limits
        if p_grid > 0:  # Buying
            p_grid = min(p_grid, self.grid.p_import_max)
        else:  # Selling
            p_grid = max(p_grid, -self.grid.p_export_max)
        
        # ===== THERMAL BUS =====
        
        # 1. Boiler operation
        q_boiler = self.boiler.set_power(q_boiler_cmd)
        
        # 2. Thermal load and storage
        self.q_load_thermal = max(0, q_load_thermal)
        
        # 3. TES charge/discharge to balance thermal load
        q_available = q_chp + q_boiler
        q_net_load = self.q_load_thermal - q_available
        
        if q_net_load > 0:  # Thermal deficit - discharge TES
            q_tes_out = min(q_net_load, self.tes.get_available_discharge())
            q_tes_in = 0.0
        else:  # Thermal surplus - charge TES
            q_tes_out = 0.0
            q_tes_in = min(abs(q_net_load), self.tes.get_available_charge())
        
        # 4. Update TES temperature
        temp_tes = self.tes.update_temperature(q_tes_in, q_tes_out)
        
        # ===== COST CALCULATION =====
        
        self.cost_grid = self.grid.compute_cost(p_grid, price_buy, price_sell)
        self.cost_fuel_chp = self.chp.get_fuel_cost()
        self.cost_fuel_boiler = self.boiler.get_fuel_cost()
        self.cost_total = self.cost_grid + self.cost_fuel_chp + self.cost_fuel_boiler
        
        # ===== CONSTRAINT CHECKING =====
        
        violations = {
            'soc_high': 1 if soc_new > self.config.battery.soc_max else 0,
            'soc_low': 1 if soc_new < self.config.battery.soc_min else 0,
            'temp_high': 1 if temp_tes > self.config.tes.temp_max else 0,
            'temp_low': 1 if temp_tes < self.config.tes.temp_min else 0,
            'load_unmet_elec': 1 if (self.p_pv + self.p_wt + p_chp + self.grid.p_import_max) < self.p_load_elec else 0,
            'load_unmet_thermal': 1 if (q_chp + q_boiler + self.tes.p_discharge_max) < self.q_load_thermal else 0,
        }
        
        # ===== RETURN STATE AND INFO =====
        
        state = {
            # Electrical state
            'soc': soc_new,
            'p_pv': self.p_pv,
            'p_wt': self.p_wt,
            'p_load_elec': self.p_load_elec,
            'p_battery': p_bat_actual,
            'p_chp': p_chp,
            'p_grid': p_grid,
            
            # Thermal state
            'temp_tes': temp_tes,
            'q_load_thermal': self.q_load_thermal,
            'q_chp': q_chp,
            'q_boiler': q_boiler,
            'q_tes_in': q_tes_in,
            'q_tes_out': q_tes_out,
            
            # Environmental
            'solar_irradiance': solar_irradiance,
            'wind_speed': wind_speed,
            'ambient_temp': ambient_temp,
            
            # Economic
            'cost_grid': self.cost_grid,
            'cost_fuel_chp': self.cost_fuel_chp,
            'cost_fuel_boiler': self.cost_fuel_boiler,
            'cost_total': self.cost_total,
            
            # Constraints
            'violations': violations,
            'violation_count': sum(violations.values()),
        }
        
        return state
    
    def get_system_info(self) -> Dict:
        """Get comprehensive system information"""
        return {
            'battery_capacity': self.config.battery.energy_capacity,
            'tes_capacity': self.config.tes.energy_capacity,
            'chp_power_max': self.config.chp.power_elec_max,
            'boiler_power_max': self.config.boiler.power_max,
            'grid_import_max': self.config.grid.power_import_max,
            'grid_export_max': self.config.grid.power_export_max,
            'timestep_hours': self.dt_hours,
        }


# ============================================================================
# 5. EXAMPLE USAGE & VALIDATION
# ============================================================================

if __name__ == "__main__":
    """
    Example usage and validation of MEMG system
    
    مثال استفاده و اعتبارسنجی سیستم
    """
    
    # Create configuration with default parameters (Table 1.3)
    config = MicrogridConfig()
    
    # Initialize system
    memg = MultiEnergyMicrogridSystem(config)
    
    print("=" * 80)
    print("MULTI-ENERGY MICROGRID SYSTEM - SECTION 1.1 VALIDATION")
    print("=" * 80)
    print(f"\nSystem Configuration:")
    print(f"  Battery Capacity: {config.battery.energy_capacity} kWh")
    print(f"  Battery Power Max: {config.battery.power_max} kW")
    print(f"  TES Capacity: {config.tes.energy_capacity} kWh")
    print(f"  CHP Power Max: {config.chp.power_elec_max} kW")
    print(f"  Grid Import/Export Max: {config.grid.power_import_max}/{config.grid.power_export_max} kW")
    print()
    
    # Simulation parameters (example: sunny day with moderate wind)
    solar_irradiance = 800.0  # W/m²
    wind_speed = 8.0  # m/s
    ambient_temp = 20.0  # °C
    p_load_elec = 15.0  # kW
    q_load_thermal = 10.0  # kW
    
    # Control actions
    p_battery_cmd = 5.0  # Charging battery
    p_chp_cmd = 10.0  # Running CHP
    q_boiler_cmd = 2.0  # Running boiler
    
    # Execute one step
    state = memg.step(
        p_load_elec=p_load_elec,
        q_load_thermal=q_load_thermal,
        solar_irradiance=solar_irradiance,
        wind_speed=wind_speed,
        ambient_temp=ambient_temp,
        p_battery_cmd=p_battery_cmd,
        p_chp_cmd=p_chp_cmd,
        q_boiler_cmd=q_boiler_cmd,
    )
    
    print("\nSimulation Step Output:")
    print(f"  ELECTRICAL:")
    print(f"    PV Generation: {state['p_pv']:.2f} kW")
    print(f"    Wind Generation: {state['p_wt']:.2f} kW")
    print(f"    CHP Output: {state['p_chp']:.2f} kW")
    print(f"    Battery Power: {state['p_battery']:.2f} kW")
    print(f"    Battery SOC: {state['soc']:.1%}")
    print(f"    Grid Exchange: {state['p_grid']:+.2f} kW ({'buy' if state['p_grid'] > 0 else 'sell'})")
    print()
    print(f"  THERMAL:")
    print(f"    CHP Heat Output: {state['q_chp']:.2f} kW")
    print(f"    Boiler Output: {state['q_boiler']:.2f} kW")
    print(f"    TES Temperature: {state['temp_tes']:.1f} °C")
    print(f"    TES Charge: {state['q_tes_in']:.2f} kW")
    print(f"    TES Discharge: {state['q_tes_out']:.2f} kW")
    print()
    print(f"  COST:")
    print(f"    Grid Cost: {state['cost_grid']:+.2f} €")
    print(f"    CHP Fuel Cost: {state['cost_fuel_chp']:.2f} €")
    print(f"    Boiler Fuel Cost: {state['cost_fuel_boiler']:.2f} €")
    print(f"    Total Cost: {state['cost_total']:.2f} €")
    print()
    print(f"  CONSTRAINTS:")
    print(f"    Violations: {state['violation_count']}")
    if state['violation_count'] > 0:
        for vkey, vval in state['violations'].items():
            if vval:
                print(f"      - {vkey}: VIOLATED")
    print()
    print("=" * 80)
    print("Validation completed successfully!")
    print("=" * 80)
