"""
Predefined waypoint routes for drone simulation.

Each waypoint: {"lat": float, "lon": float, "alt": float}
Altitudes form a natural climb-cruise-descent profile.
"""

# Route 1: Taipei Keelung River corridor
# Songshan Airport → along Keelung River → Dazhi → Yuanshan → return
TAIPEI_ROUTE = [
    {"lat": 25.0634, "lon": 121.5522, "alt": 0},     # Songshan Airport (takeoff)
    {"lat": 25.0634, "lon": 121.5522, "alt": 80},     # climbing
    {"lat": 25.0670, "lon": 121.5450, "alt": 120},    # over Keelung River
    {"lat": 25.0720, "lon": 121.5380, "alt": 120},    # river corridor
    {"lat": 25.0780, "lon": 121.5310, "alt": 120},    # near Dazhi Bridge
    {"lat": 25.0830, "lon": 121.5250, "alt": 120},    # near Yuanshan
    {"lat": 25.0800, "lon": 121.5200, "alt": 100},    # begin descent
    {"lat": 25.0750, "lon": 121.5150, "alt": 60},     # descending
    {"lat": 25.0700, "lon": 121.5250, "alt": 30},     # returning
    {"lat": 25.0634, "lon": 121.5522, "alt": 0},      # Songshan Airport (land)
]

# Route 2: Solar farm grid scan (Zhonghe area)
SOLAR_FARM_ROUTE = [
    {"lat": 24.9980, "lon": 121.4950, "alt": 0},
    {"lat": 24.9980, "lon": 121.4950, "alt": 60},
    {"lat": 24.9990, "lon": 121.4950, "alt": 60},
    {"lat": 24.9990, "lon": 121.4970, "alt": 60},
    {"lat": 25.0000, "lon": 121.4970, "alt": 60},
    {"lat": 25.0000, "lon": 121.4950, "alt": 60},
    {"lat": 25.0010, "lon": 121.4950, "alt": 60},
    {"lat": 25.0010, "lon": 121.4970, "alt": 60},
    {"lat": 24.9980, "lon": 121.4950, "alt": 0},
]

# Route 3: Bridge inspection (Xinbei Bridge)
BRIDGE_INSPECTION_ROUTE = [
    {"lat": 25.0570, "lon": 121.4650, "alt": 0},
    {"lat": 25.0570, "lon": 121.4650, "alt": 40},
    {"lat": 25.0580, "lon": 121.4680, "alt": 30},
    {"lat": 25.0590, "lon": 121.4710, "alt": 25},
    {"lat": 25.0600, "lon": 121.4740, "alt": 30},
    {"lat": 25.0610, "lon": 121.4770, "alt": 35},
    {"lat": 25.0570, "lon": 121.4650, "alt": 0},
]
