"""Physical constants and unit conversions shared by the model."""

from __future__ import annotations

R_EARTH = 6371000.0  # m, mean Earth radius


G = 9.81  # m/s2


RHO_AIR = 1.2  # kg/m3


MU_AIR = 1.81e-5  # Pa s, dynamic viscosity of air near 15-20 C


MFP_AIR = 0.068e-6  # m, mean free path of air molecules near room temperature


MU_WATER = 1.0e-3  # Pa s, dynamic viscosity of water (for Slinn's viscosity ratio)


RHO_WATER = 1000.0  # kg/m3


K_BOLTZ = 1.380649e-23  # J/K


VON_KARMAN = 0.4


T_REF = 288.15  # K, temperature used for particle diffusivity


CLASSES = "ABCDEF"


TNT_MJ_PER_KG = 4.184  # energy-equivalence definition of TNT


KG_PER_LB = 0.45359237


M2_PER_FT2 = 0.09290304
