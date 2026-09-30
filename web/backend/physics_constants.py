"""Physical constants and common formulas (SI)."""
from __future__ import annotations
import math


CONSTANTS = {
    # Universal
    "c":        299792458.0,
    "G":        6.67430e-11,
    "h":        6.62607015e-34,
    "hbar":     1.054571817e-34,
    "k_B":      1.380649e-23,
    "N_A":      6.02214076e23,
    "R":        8.314462618,
    "e":        1.602176634e-19,
    "mu_0":     1.25663706212e-6,
    "eps_0":    8.8541878128e-12,

    # Particle masses
    "m_e":      9.1093837015e-31,
    "m_p":      1.67262192369e-27,
    "m_n":      1.67492749804e-27,
    "u":        1.66053906660e-27,

    # Earth
    "R_earth":  6.371e6,
    "M_earth":  5.9722e24,
    "g":        9.80665,

    # Sun
    "R_sun":    6.957e8,
    "M_sun":    1.98892e30,
    "L_sun":    3.828e26,

    # Astronomy
    "AU":       1.495978707e11,
    "ly":       9.4607304725808e15,
    "pc":       3.0856775814913673e16,
    "H0":       2.184e-18,
    "sigma_sb": 5.670374419e-8,
    "M_jup":    1.898e27,
    "M_moon":   7.342e22,
    "R_moon":   1.7374e6,

    # Math
    "pi":       math.pi,
    "euler":    math.e,
    "tau":      2 * math.pi,
    "phi":      (1 + math.sqrt(5)) / 2,
}


def _step(note, expr, value, unit=""):
    return {"note": note, "expr": expr, "value": value, "unit": unit}


def kinetic_energy(mass, velocity):
    """E = ½mv²"""
    energy = 0.5 * mass * velocity ** 2
    return {
        "result": energy, "unit": "J", "formula": "E = ½mv²",
        "steps": [
            _step("Square the velocity", f"v² = {velocity}²", velocity ** 2, "m²/s²"),
            _step("Multiply by mass", f"m · v² = {mass} × {velocity**2}", mass * velocity ** 2, "J"),
            _step("Halve the result", f"E = ½ · {mass * velocity**2}", energy, "J"),
        ],
    }


def potential_energy(mass, height, g=9.80665):
    """E = mgh"""
    energy = mass * g * height
    return {
        "result": energy, "unit": "J", "formula": "E = mgh",
        "steps": [
            _step("Apply standard gravity", f"g = {g}", g, "m/s²"),
            _step("Multiply", f"E = {mass} × {g} × {height}", energy, "J"),
        ],
    }


def force(mass, acceleration):
    """F = ma"""
    f = mass * acceleration
    return {
        "result": f, "unit": "N", "formula": "F = ma",
        "steps": [_step("Newton's second law", f"F = {mass} × {acceleration}", f, "N")],
    }


def escape_velocity(mass, radius):
    """v_esc = √(2GM/r)"""
    GM = CONSTANTS["G"] * mass
    v = math.sqrt(2 * GM / radius)
    return {
        "result": v, "unit": "m/s", "formula": "v_esc = √(2GM/r)",
        "steps": [
            _step("GM", f"G · M = {CONSTANTS['G']} × {mass}", GM, "m³/s²"),
            _step("2GM/r", f"2 · {GM} / {radius}", 2 * GM / radius, "m²/s²"),
            _step("Square root", f"v = √({2*GM/radius})", v, "m/s"),
        ],
    }


def orbital_velocity(mass, radius):
    """v_orb = √(GM/r)"""
    GM = CONSTANTS["G"] * mass
    v = math.sqrt(GM / radius)
    return {
        "result": v, "unit": "m/s", "formula": "v_orb = √(GM/r)",
        "steps": [
            _step("GM", f"G · M = {CONSTANTS['G']} × {mass}", GM, "m³/s²"),
            _step("Square root", f"v = √({GM}/{radius})", v, "m/s"),
        ],
    }


def schwarzschild_radius(mass):
    """r_s = 2GM/c²"""
    c = CONSTANTS["c"]
    r_s = 2 * CONSTANTS["G"] * mass / c**2
    return {
        "result": r_s, "unit": "m", "formula": "r_s = 2GM/c²",
        "steps": [
            _step("c²", f"c² = ({c})²", c**2, "m²/s²"),
            _step("2GM", f"2 · G · M", 2 * CONSTANTS["G"] * mass, "m³/s²"),
            _step("Divide", f"r_s = {2*CONSTANTS['G']*mass} / {c**2}", r_s, "m"),
        ],
    }


def photon_energy(wavelength):
    """E = hc/λ"""
    h, c = CONSTANTS["h"], CONSTANTS["c"]
    E = h * c / wavelength
    return {
        "result": E, "unit": "J", "formula": "E = hc/λ",
        "steps": [
            _step("hc", f"h · c", h * c, "J·m"),
            _step("Divide by λ", f"E = {h*c} / {wavelength}", E, "J"),
        ],
    }


def relativistic_mass(rest_mass, velocity):
    """m = γm₀"""
    c = CONSTANTS["c"]
    if velocity >= c:
        raise ValueError("velocity must be less than c")
    beta2 = (velocity / c) ** 2
    gamma = 1 / math.sqrt(1 - beta2)
    m = rest_mass * gamma
    return {
        "result": m, "unit": "kg", "formula": "m = γm₀",
        "steps": [
            _step("β²", f"(v/c)²", beta2, ""),
            _step("Lorentz factor", f"γ = 1/√(1 − {beta2})", gamma, ""),
            _step("Relativistic mass", f"m = γ · m₀", m, "kg"),
        ],
    }


def hubble_law(distance):
    """v = H₀ · d"""
    H0 = CONSTANTS["H0"]
    v = H0 * distance
    return {
        "result": v, "unit": "m/s", "formula": "v = H₀ · d",
        "steps": [
            _step("H₀", f"H₀ = {H0}", H0, "1/s"),
            _step("Multiply by distance", f"v = {H0} × {distance}", v, "m/s"),
        ],
    }


def stefan_boltzmann(radius, temperature):
    """L = 4πR²σT⁴"""
    sigma = CONSTANTS["sigma_sb"]
    L = 4 * math.pi * radius ** 2 * sigma * temperature ** 4
    return {
        "result": L, "unit": "W", "formula": "L = 4πR²σT⁴",
        "steps": [
            _step("T⁴", f"T⁴", temperature ** 4, "K⁴"),
            _step("Surface area", f"4πR²", 4 * math.pi * radius ** 2, "m²"),
            _step("Luminosity", f"L = 4πR²σT⁴", L, "W"),
        ],
    }


def de_broglie(mass, velocity):
    """λ = h/(mv)"""
    h = CONSTANTS["h"]
    lam = h / (mass * velocity)
    return {
        "result": lam, "unit": "m", "formula": "λ = h/(mv)",
        "steps": [
            _step("Momentum", f"p = m·v", mass * velocity, "kg·m/s"),
            _step("Wavelength", f"λ = h / p", lam, "m"),
        ],
    }


FORMULAS = {
    "kinetic_energy":       kinetic_energy,
    "potential_energy":     potential_energy,
    "force":                force,
    "escape_velocity":      escape_velocity,
    "orbital_velocity":     orbital_velocity,
    "schwarzschild_radius": schwarzschild_radius,
    "photon_energy":        photon_energy,
    "relativistic_mass":    relativistic_mass,
    "hubble_law":           hubble_law,
    "stefan_boltzmann":     stefan_boltzmann,
    "de_broglie":           de_broglie,
}


UNITS = {
    # Length
    "m": 1.0, "km": 1000.0, "cm": 0.01, "mm": 0.001,
    "um": 1e-6, "nm": 1e-9, "angstrom": 1e-10,
    "mi": 1609.344, "ft": 0.3048, "in": 0.0254, "yd": 0.9144,
    "ly": CONSTANTS["ly"], "au": CONSTANTS["AU"], "pc": CONSTANTS["pc"],
    # Time
    "s": 1.0, "ms": 1e-3, "us": 1e-6, "ns": 1e-9,
    "min": 60.0, "h": 3600.0, "day": 86400.0, "yr": 365.25 * 86400.0,
    # Mass
    "kg": 1.0, "g": 1e-3, "mg": 1e-6, "t": 1000.0,
    "lb": 0.45359237, "oz": 0.028349523125,
    # Energy
    "J": 1.0, "kJ": 1000.0, "MJ": 1e6, "cal": 4.184,
    "kcal": 4184.0, "eV": 1.602176634e-19, "keV": 1.602e-16,
    "MeV": 1.602e-13, "GeV": 1.602e-10,
    # Power
    "W": 1.0, "kW": 1000.0, "MW": 1e6, "GW": 1e9,
    # Temperature
    "K": 1.0, "C": None, "F": None,
    # Pressure
    "Pa": 1.0, "kPa": 1000.0, "MPa": 1e6, "bar": 1e5, "atm": 101325.0,
}
