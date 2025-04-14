#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Simulation of a Plasma Spark Pumped YAG Laser Beam with Temperature Metrics, Current, Lumens, Solar Cell Power, and With/Without YAG Crystal"""

import numpy as np
import pkg_resources
from scipy.integrate import quad

# Check if KrakenOS is installed; if not, adjust the path
required = {'KrakenOS'}
installed = {pkg.key for pkg in pkg_resources.working_set}
missing = required - installed

if missing:
    print("KrakenOS not installed; assuming local folder")
    import sys
    sys.path.append("../..")

import KrakenOS as Kos

# --- Constants and Variables ---
# Optical System Parameters
OBJ_THICKNESS = 10.0
YAG_THICKNESS = 5.0
YAG_TO_LENS = 20.0
L1A_RADIUS = 92.84706570002484
L1A_THICKNESS = 6.0
L1B_RADIUS = -30.71608670000159
L1B_THICKNESS = 3.0
L1C_RADIUS = -78.19730726078505
L1C_THICKNESS = 97.37604742910693
DIAMETER_OBJ = 30.0
DIAMETER_YAG = 10.0
DIAMETER_LENS = 30.0
DIAMETER_IMA = 100.0
WAVELENGTH = 1.064  # microns (1064 nm)

# Ray Tracing Parameters
GRID_SIZE = 5
BEAM_RADIUS = 10.0

# Laser and Thermal Parameters
INITIAL_FREQ = 250.0  # Hz
PULSE_DURATION = 0.001  # s
THERMAL_CONDUCTIVITY = 50.0  # W/m·K
PLATE_THICKNESS = 0.001  # m
PLATE_RADIUS = 0.1  # m
AMBIENT_TEMP = 25.0  # °C
TARGET_TEMP = 280.0  # °C

# Heat-to-Electricity Conversion Parameters
HEAT_ABSORPTION_EFF = 0.8
ORC_EFFICIENCY = 0.12
VOLTAGES = [12, 120, 240]

# Lumens Calculation Parameters
WAVELENGTH_NM = WAVELENGTH * 1000  # 1064 nm
LUMINOUS_EFFICACY_MAX = 683  # lm/W at 555 nm

# Solar Cell Parameters
SOLAR_CELL_EFF_1064 = 0.60  # Efficiency at 1064 nm for InGaAs
SOLAR_CELL_VOLTAGE = 1.0  # V
PLASMA_TEMP = 4000  # K for blackbody spectrum without YAG

# Physical Constants for Blackbody Calculation
h = 6.626e-34  # J·s
c = 3e8  # m/s
k = 1.381e-23  # J/K

# --- Calculate Blackbody Fraction ---
def planck(lambda_m, T):
    x = h * c / (lambda_m * k * T)
    if x > 700:  # Avoid overflow
        return 0
    return (1 / lambda_m**5) / (np.exp(x) - 1)

int_sensitive, _ = quad(planck, 900e-9, 1700e-9, args=(PLASMA_TEMP,))
int_total, _ = quad(planck, 100e-9, 100e-6, args=(PLASMA_TEMP,))
FRACTION_SENSITIVE = int_sensitive / int_total  # ~0.255
SOLAR_CELL_EFF_BROADBAND = SOLAR_CELL_EFF_1064 * FRACTION_SENSITIVE  # ~0.153

# --- Function to Setup Optical System ---
def setup_optical_system(include_yag=True):
    P_Obj = Kos.surf()
    P_Obj.Rc = 0.0
    P_Obj.Thickness = OBJ_THICKNESS if include_yag else OBJ_THICKNESS + YAG_THICKNESS + YAG_TO_LENS
    P_Obj.Glass = "AIR"
    P_Obj.Diameter = DIAMETER_OBJ

    if include_yag:
        YAG_entrance = Kos.surf()
        YAG_entrance.Rc = 0.0
        YAG_entrance.Thickness = YAG_THICKNESS
        YAG_entrance.Glass = "AIR"
        YAG_entrance.Diameter = DIAMETER_YAG

        YAG_exit = Kos.surf()
        YAG_exit.Rc = 0.0
        YAG_exit.Thickness = YAG_TO_LENS
        YAG_exit.Glass = "AIR"
        YAG_exit.Diameter = DIAMETER_YAG
    else:
        YAG_entrance = Kos.surf()
        YAG_entrance.Rc = 0.0
        YAG_entrance.Thickness = 0.0
        YAG_entrance.Glass = "AIR"
        YAG_entrance.Diameter = DIAMETER_YAG

        YAG_exit = Kos.surf()
        YAG_exit.Rc = 0.0
        YAG_exit.Thickness = 0.0
        YAG_exit.Glass = "AIR"
        YAG_exit.Diameter = DIAMETER_YAG

    L1a = Kos.surf()
    L1a.Rc = L1A_RADIUS
    L1a.Thickness = L1A_THICKNESS
    L1a.Glass = "BK7"
    L1a.Diameter = DIAMETER_LENS
    L1a.Color = [0.8, 0.7, 0.4]

    L1b = Kos.surf()
    L1b.Rc = L1B_RADIUS
    L1b.Thickness = L1B_THICKNESS
    L1b.Glass = "F2"
    L1b.Diameter = DIAMETER_LENS
    L1b.Color = [0.7, 0.4, 0.4]

    L1c = Kos.surf()
    L1c.Rc = L1C_RADIUS
    L1c.Thickness = L1C_THICKNESS
    L1c.Glass = "AIR"
    L1c.Diameter = DIAMETER_LENS

    P_Ima = Kos.surf()
    P_Ima.Rc = 0.0
    P_Ima.Thickness = 0.0
    P_Ima.Glass = "AIR"
    P_Ima.Diameter = DIAMETER_IMA
    P_Ima.Name = "Image Plane"

    A = [P_Obj, YAG_entrance, YAG_exit, L1a, L1b, L1c, P_Ima]
    config = Kos.Setup()
    optical_system = Kos.system(A, config)
    rays = Kos.raykeeper(optical_system)
    return optical_system, rays

# --- Function to Perform Ray Tracing ---
def trace_rays(optical_system, rays):
    rays.clean()
    for i in range(-GRID_SIZE, GRID_SIZE + 1):
        for j in range(-GRID_SIZE, GRID_SIZE + 1):
            x_0 = (i / GRID_SIZE) * BEAM_RADIUS
            y_0 = (j / GRID_SIZE) * BEAM_RADIUS
            r = np.sqrt(x_0**2 + y_0**2)
            if r < BEAM_RADIUS:
                tet = 0.0
                pSource_0 = [x_0, y_0, 0.0]
                dCos = [0.0, 0.0, 1.0]
                optical_system.Trace(pSource_0, dCos, WAVELENGTH)
                rays.push()

# --- Calculate Peak Power for Target Temperature ---
def calculate_peak_power_for_temp(freq, target_temp, rays):
    try:
        ray_paths = rays.raylist
        x = [path[-1][0] for path in ray_paths]
        y = [path[-1][1] for path in ray_paths]
        r = np.sqrt(np.array(x)**2 + np.array(y)**2)
        w = np.sqrt(np.mean(r**2)) / 1000  # RMS radius in meters
    except AttributeError:
        print("Warning: Estimating spot size analytically.")
        f = 100.0  # mm
        lambda_m = WAVELENGTH * 1e-3  # microns to mm
        D = BEAM_RADIUS * 2
        w_mm = (4 * lambda_m * f) / (np.pi * D)
        w = w_mm / 1000

    duty_cycle = min(freq * PULSE_DURATION, 1.0)
    Delta_T = target_temp - AMBIENT_TEMP
    denominator = np.log(4 * PLATE_RADIUS / w) / (4 * np.pi * THERMAL_CONDUCTIVITY * PLATE_THICKNESS)
    P_avg = Delta_T / denominator
    P_peak = P_avg / duty_cycle if duty_cycle > 0 else P_avg
    Delta_T_calc = (P_avg / (4 * np.pi * THERMAL_CONDUCTIVITY * PLATE_THICKNESS)) * np.log(4 * PLATE_RADIUS / w)
    final_T = AMBIENT_TEMP + Delta_T_calc
    return w * 1000, P_peak, P_avg, final_T

# --- Calculate Luminous Flux ---
def calculate_lumens(average_power, wavelength_nm):
    lambda_peak = 555
    sigma = 100
    efficacy = LUMINOUS_EFFICACY_MAX * np.exp(-((wavelength_nm - lambda_peak)**2) / (2 * sigma**2))
    luminous_flux = average_power * efficacy
    return luminous_flux, efficacy

# --- Calculate Solar Cell Power and Current ---
def calculate_solar_cell_power(average_power, spot_radius_mm, is_with_yag):
    spot_radius_m = spot_radius_mm * 1e-3
    spot_area = np.pi * spot_radius_m**2
    power_density = average_power / spot_area if spot_area > 0 else 0
    efficiency = SOLAR_CELL_EFF_1064 if is_with_yag else SOLAR_CELL_EFF_BROADBAND
    solar_power = average_power * efficiency
    solar_current = solar_power / SOLAR_CELL_VOLTAGE if SOLAR_CELL_VOLTAGE > 0 else 0
    return solar_power, solar_current, power_density, efficiency

# --- Calculate Electrical Current from Heat ---
def calculate_current(average_power):
    heat_power = average_power * HEAT_ABSORPTION_EFF
    electrical_power = heat_power * ORC_EFFICIENCY
    currents = {voltage: electrical_power / voltage for voltage in VOLTAGES}
    return electrical_power, currents

# --- Main Simulation Loop ---
frequency = INITIAL_FREQ
print("Laser Simulation: Frequency set to 250 Hz. Press 'b' to run simulation.")

while True:
    print("\nCurrent spark frequency:", frequency, "Hz")
    print("Options: 'b' to run simulation, 'exit' to quit")
    user_input = input("> ").lower()

    if user_input == 'exit':
        break
    elif user_input == 'b':
        print("Button pressed: Activating laser and tracing rays...")

        # With YAG Crystal
        print("\n=== Simulation WITH YAG Crystal ===")
        optical_system_with_yag, rays_with_yag = setup_optical_system(include_yag=True)
        trace_rays(optical_system_with_yag, rays_with_yag)
        spot_radius, peak_power, avg_power, final_temp = calculate_peak_power_for_temp(frequency, TARGET_TEMP, rays_with_yag)
        print(f"Spot radius at image plane: {spot_radius:.6f} mm")
        print(f"Required peak power to reach {TARGET_TEMP}°C: {peak_power:.2f} W")
        print(f"Average power: {avg_power:.2f} W")
        print(f"Calculated surface temperature: {final_temp:.2f} °C")

        lumens, efficacy = calculate_lumens(avg_power, WAVELENGTH_NM)
        print(f"\nLuminous flux: {lumens:.2e} lumens")
        print(f"(Luminous efficacy at {WAVELENGTH_NM} nm: {efficacy:.2e} lm/W)")

        solar_power, solar_current, power_density, eff_used = calculate_solar_cell_power(avg_power, spot_radius, is_with_yag=True)
        print(f"\nSolar Cell Power Generation (at {eff_used*100:.1f}% efficiency for 1064 nm):")
        print(f"  Incident power density: {power_density:.2e} W/m²")
        print(f"  Electrical power: {solar_power:.2f} W")
        print(f"  Current at {SOLAR_CELL_VOLTAGE} V: {solar_current:.2f} A")

        electrical_power, currents = calculate_current(avg_power)
        print(f"\nElectrical power from heat (ORC efficiency {ORC_EFFICIENCY*100}%): {electrical_power:.2f} W")
        print("Current from heat at different voltages:")
        for voltage, current in currents.items():
            print(f"  At {voltage} V: {current:.2f} A ({current*1000:.2f} mA)")

        Kos.display3d(optical_system_with_yag, rays_with_yag, 1)

        # Without YAG Crystal
        print("\n=== Simulation WITHOUT YAG Crystal ===")
        optical_system_no_yag, rays_no_yag = setup_optical_system(include_yag=False)
        trace_rays(optical_system_no_yag, rays_no_yag)
        spot_radius_no_yag, peak_power_no_yag, avg_power_no_yag, final_temp_no_yag = calculate_peak_power_for_temp(frequency, TARGET_TEMP, rays_no_yag)
        print(f"Spot radius at image plane: {spot_radius_no_yag:.6f} mm")
        print(f"Required peak power to reach {TARGET_TEMP}°C: {peak_power_no_yag:.2f} W")
        print(f"Average power: {avg_power_no_yag:.2f} W")
        print(f"Calculated surface temperature: {final_temp_no_yag:.2f} °C")

        lumens_no_yag, efficacy_no_yag = calculate_lumens(avg_power_no_yag, WAVELENGTH_NM)
        print(f"\nLuminous flux: {lumens_no_yag:.2e} lumens")
        print(f"(Luminous efficacy at {WAVELENGTH_NM} nm: {efficacy_no_yag:.2e} lm/W)")

        solar_power_no_yag, solar_current_no_yag, power_density_no_yag, eff_used_no_yag = calculate_solar_cell_power(avg_power_no_yag, spot_radius_no_yag, is_with_yag=False)
        print(f"\nSolar Cell Power Generation (at {eff_used_no_yag*100:.1f}% effective efficiency for broadband light):")
        print(f"  Incident power density: {power_density_no_yag:.2e} W/m²")
        print(f"  Electrical power: {solar_power_no_yag:.2f} W")
        print(f"  Current at {SOLAR_CELL_VOLTAGE} V: {solar_current_no_yag:.2f} A")

        electrical_power_no_yag, currents_no_yag = calculate_current(avg_power_no_yag)
        print(f"\nElectrical power from heat (ORC efficiency {ORC_EFFICIENCY*100}%): {electrical_power_no_yag:.2f} W")
        print("Current from heat at different voltages:")
        for voltage, current in currents_no_yag.items():
            print(f"  At {voltage} V: {current:.2f} A ({current*1000:.2f} mA)")

        Kos.display3d(optical_system_no_yag, rays_no_yag, 1)

        # Updated Assumptions
        print("\nAssumptions:")
        print(f"- Pulse duration: {PULSE_DURATION*1000} ms")
        print(f"- Heat absorption efficiency: {HEAT_ABSORPTION_EFF*100}%")
        print(f"- ORC efficiency: {ORC_EFFICIENCY*100}%")
        print(f"- With YAG: InGaAs solar cell efficiency at 1064 nm: {SOLAR_CELL_EFF_1064*100}%")
        print(f"- Without YAG: Effective efficiency: {SOLAR_CELL_EFF_BROADBAND*100:.1f}% (blackbody at {PLASMA_TEMP} K, 900-1700 nm range)")
        print(f"- Material: Steel (thermal conductivity {THERMAL_CONDUCTIVITY} W/m·K)")

print("Simulation ended.")