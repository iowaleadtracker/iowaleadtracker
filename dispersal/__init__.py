"""The Gaussian puff dispersion model behind puff_dispersal.py, one module per topic.

constants    physical constants and unit conversions
units        input parsing (masses, concentrations, size distributions, times)
source_term  explosion source term, material presets, release cases
particles    particle diameter, slip correction and settling velocity
deposition   dry deposition (Zhang et al. 2001) and drop collection (Slinn 1984)
dispersion   stability classes, Briggs sigma curves, puff growth, ground reflection
met          weather download, cache and the gridded met field
model        the puff model itself
grid         gridding puff records into hourly map fields
output       packed fields, HYSPLIT files and the HTML map
"""
