#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Simulation of a Plasma Spark Pumped YAG Laser Beam with Button, Temperature Metrics, Frequency Knob, and Current Calculation"""

import numpy as np
import pkg_resources

# Check if KrakenOS is installed; if not, adjust the path
required = {'KrakenOS'}
installed = {pkg.key for pkg in pkg_resources.working_set}
missing = required - installed

if missing:
    print("KrakenOS not installed; assuming local folder")
    import sys
    sys.path.append("../..")

import KrakenOS as Kos

# --- Constants and Variables (Declared at the Top) ---
# Optical System Parameters
OBJ_THICKNESS = 10.0  # Distance to YAG crystal entrance (mm)
YAG_THICKNESS = 5.0  # YAG crystal length (mm)
YAG_TO_LENS = 20.0  # Distance from YAG exit to lens (mm)
L1A_RADIUS = 92.84706570002484  # Radius of curvature for lens 1a (mm)
L1A_THICKNESS = 6.0  # Thickness of first lens element (mm)
L1B_RADIUS = -30.71608670000159  # Radius of curvature for lens 1b (mm)
L1B_THICKNESS = 3.0  # Thickness of second lens element (mm)
L1C_RADIUS = -78.19730726078505  # Radius of curvature for lens 1c (mm)
L1C_THICKNESS = 97.37604742910693  # Distance to image plane (mm)
DIAMETER_OBJ = 30.0  # Object plane diameter (mm)
DIAMETER_YAG = 10.0  # YAG crystal diameter (mm)
DIAMETER_LENS = 30.0  # Lens diameter (mm)
DIAMETER_IMA = 100.0  # Image plane diameter (mm)
WAVELENGTH = 1.064  # Wavelength in microns (1064 nm)

# Ray Tracing Parameters
GRID_SIZE = 5  # Grid size for ray starting points
BEAM_RADIUS = 10.0  # Beam radius (mm, 20 mm diameter)

# Laser and Thermal Parameters
INITIAL_FREQ = 250.0  # Plasma spark frequency (Hz, set to 250 Hz as specified)
PULSE_DURATION = 0.001  # Pulse duration (s, 1 ms)
THERMAL_CONDUCTIVITY = 50.0  # Thermal conductivity of steel (W/m·K)
PLATE_THICKNESS = 0.001  # Plate thickness (m)
PLATE_RADIUS = 0.1  # Effective plate radius (m)
AMBIENT_TEMP = 25.0  # Ambient temperature (°C)
TARGET_TEMP = 280.0  # Target surface temperature (°C, as specified)

# Heat-to-Electricity Conversion Parameters
HEAT_ABSORPTION_EFF = 0.8  # 80% of laser energy absorbed as heat
ORC_EFFICIENCY = 0.12  # 12% efficiency for ORC at 280°C (from Web ID 1)
VOLTAGES = [12, 120, 240]  # Common voltages for current calculation (V)

# --- Object Plane ---
P_Obj = Kos.surf()
P_Obj.Rc = 0.0
P_Obj.Thickness = OBJ_THICKNESS
P_Obj.Glass = "AIR"
P_Obj.Diameter = DIAMETER_OBJ

# --- YAG Crystal Entrance ---
YAG_entrance = Kos.surf()
YAG_entrance.Rc = 0.0
YAG_entrance.Thickness = YAG_THICKNESS
YAG_entrance.Glass = "AIR"  # Placeholder (YAG material not supported)
YAG_entrance.Diameter = DIAMETER_YAG

# --- YAG Crystal Exit ---
YAG_exit = Kos.surf()
YAG_exit.Rc = 0.0
YAG_exit.Thickness = YAG_TO_LENS
YAG_exit.Glass = "AIR"
YAG_exit.Diameter = DIAMETER_YAG

# --- Doublet Lens First Surface ---
L1a = Kos.surf()
L1a.Rc = L1A_RADIUS
L1a.Thickness = L1A_THICKNESS
L1a.Glass = "BK7"
L1a.Diameter = DIAMETER_LENS
L1a.Color = [0.8, 0.7, 0.4]

# --- Doublet Lens Second Surface ---
L1b = Kos.surf()
L1b.Rc = L1B_RADIUS
L1b.Thickness = L1B_THICKNESS
L1b.Glass = "F2"
L1b.Diameter = DIAMETER_LENS
L1b.Color = [0.7, 0.4, 0.4]

# --- Doublet Lens Third Surface ---
L1c = Kos.surf()
L1c.Rc = L1C_RADIUS
L1c.Thickness = L1C_THICKNESS
L1c.Glass = "AIR"
L1c.Diameter = DIAMETER_LENS

# --- Image Plane ---
P_Ima = Kos.surf()
P_Ima.Rc = 0.0
P_Ima.Thickness = 0.0
P_Ima.Glass = "AIR"
P_Ima.Diameter = DIAMETER_IMA
P_Ima.Name = "Image Plane"

# --- System Setup ---
A = [P_Obj, YAG_entrance, YAG_exit, L1a, L1b, L1c, P_Ima]
config = Kos.Setup()
OpticalSystem = Kos.system(A, config)
Rays = Kos.raykeeper(OpticalSystem)

# --- Function to Perform Ray Tracing ---
def trace_rays():
    Rays.clean()  # Clear previous rays
    for i in range(-GRID_SIZE, GRID_SIZE + 1):
        for j in range(-GRID_SIZE, GRID_SIZE + 1):
            x_0 = (i / GRID_SIZE) * BEAM_RADIUS
            y_0 = (j / GRID_SIZE) * BEAM_RADIUS
            r = np.sqrt(x_0**2 + y_0**2)
            if r < BEAM_RADIUS:
                tet = 0.0
                pSource_0 = [x_0, y_0, 0.0]
                dCos = [0.0, 0.0, 1.0]
                OpticalSystem.Trace(pSource_0, dCos, WAVELENGTH)
                Rays.push()

# --- Calculate Spot Size and Required Peak Power for Target Temperature ---
def calculate_peak_power_for_temp(freq, target_temp):
    # Estimate spot size using ray tracing data
    try:
        ray_paths = Rays.raylist  # Access ray paths (adjust based on KrakenOS API)
        x = [path[-1][0] for path in ray_paths]
        y = [path[-1][1] for path in ray_paths]
        r = np.sqrt(np.array(x)**2 + np.array(y)**2)
        w = np.sqrt(np.mean(r**2)) / 1000  # RMS radius in meters
    except AttributeError:
        print("Warning: Unable to access ray positions; estimating spot size analytically.")
        f = 100.0  # Approximate focal length (mm)
        lambda_m = WAVELENGTH * 1e-3  # Microns to mm
        D = BEAM_RADIUS * 2  # Beam diameter (mm)
        w_mm = (4 * lambda_m * f) / (np.pi * D)  # Spot radius in mm
        w = w_mm / 1000  # Convert to meters
    
    # Duty cycle
    duty_cycle = freq * PULSE_DURATION
    duty_cycle = min(duty_cycle, 1.0)  # Clamp to 100%
    
    # Required temperature rise
    Delta_T = target_temp - AMBIENT_TEMP
    
    # Solve for average power: Delta_T = (P_avg / (4 * pi * k * t)) * ln(4 * R / w)
    # Rearrange: P_avg = Delta_T / [ln(4 * R / w) / (4 * pi * k * t)]
    denominator = np.log(4 * PLATE_RADIUS / w) / (4 * np.pi * THERMAL_CONDUCTIVITY * PLATE_THICKNESS)
    P_avg = Delta_T / denominator
    
    # Peak power: P_avg = P_peak * duty_cycle
    P_peak = P_avg / duty_cycle if duty_cycle > 0 else P_avg
    
    # Recalculate final temperature to confirm
    Delta_T_calc = (P_avg / (4 * np.pi * THERMAL_CONDUCTIVITY * PLATE_THICKNESS)) * np.log(4 * PLATE_RADIUS / w)
    final_T = AMBIENT_TEMP + Delta_T_calc
    
    return w * 1000, P_peak, P_avg, final_T  # Spot radius (mm), peak power (W), average power (W), final temp (°C)

# --- Calculate Electrical Current from Heat ---
def calculate_current(average_power):
    # Heat power absorbed
    heat_power = average_power * HEAT_ABSORPTION_EFF
    
    # Electrical power generated via ORC
    electrical_power = heat_power * ORC_EFFICIENCY
    
    # Calculate current for each voltage
    currents = {}
    for voltage in VOLTAGES:
        current = electrical_power / voltage  # I = P / V
        currents[voltage] = current
    
    return electrical_power, currents

# --- Main Simulation Loop ---
frequency = INITIAL_FREQ  # Set to 250 Hz
print("Laser Simulation: Frequency set to 250 Hz. Press 'b' to run simulation.")

while True:
    print("\nCurrent spark frequency:", frequency, "Hz")
    print("Options: 'b' to press button (run simulation), 'exit' to quit")
    user_input = input("> ").lower()
    
    if user_input == 'exit':
        break
    elif user_input == 'b':
        print("Button pressed: Activating laser and tracing rays...")
        trace_rays()
        
        # Calculate required peak power to reach 280°C
        spot_radius, peak_power, avg_power, final_temp = calculate_peak_power_for_temp(frequency, TARGET_TEMP)
        print(f"\nSpot radius at image plane: {spot_radius:.6f} mm")
        print(f"Required peak power to reach {TARGET_TEMP}°C: {peak_power:.2f} W")
        print(f"Average power: {avg_power:.2f} W")
        print(f"Calculated surface temperature: {final_temp:.2f} °C")
        
        # Calculate electrical current
        electrical_power, currents = calculate_current(avg_power)
        print(f"\nElectrical power generated (at {ORC_EFFICIENCY*100}% ORC efficiency): {electrical_power:.2f} W")
        print("Current generated at different voltages:")
        for voltage, current in currents.items():
            print(f"  At {voltage} V: {current:.2f} amperes")
        
        # Display optical system
        Kos.display3d(OpticalSystem, Rays, 1)

print("Simulation ended.")