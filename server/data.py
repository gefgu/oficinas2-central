from typing import List, Dict, Any

sample_trajectories = [
    {
        "id": "1",
        "mode": "bus",
        "color": "#FF5733",  # Orange
        "coordinates": [
            # Starting from North Curitiba (Santa Cândida)
            {"latitude": -25.3750, "longitude": -49.2320},  # Starting point (Santa Cândida terminal)
            {"latitude": -25.3830, "longitude": -49.2350},
            {"latitude": -25.3900, "longitude": -49.2370},
            {"latitude": -25.3980, "longitude": -49.2400},
            {"latitude": -25.4050, "longitude": -49.2450},
            {"latitude": -25.4120, "longitude": -49.2500},
            {"latitude": -25.4180, "longitude": -49.2550},
            {"latitude": -25.4240, "longitude": -49.2590},
            {"latitude": -25.4290, "longitude": -49.2640},
            {"latitude": -25.4350, "longitude": -49.2670},  # End at city center
        ]
    },
    {
        "id": "2",
        "mode": "car",
        "color": "#3498DB",  # Blue
        "coordinates": [
            # From city center to west Curitiba
            {"latitude": -25.4350, "longitude": -49.2670},  # Starting from city center
            {"latitude": -25.4380, "longitude": -49.2750},
            {"latitude": -25.4420, "longitude": -49.2830},
            {"latitude": -25.4460, "longitude": -49.2920},
            {"latitude": -25.4500, "longitude": -49.3000},
            {"latitude": -25.4540, "longitude": -49.3080},
            {"latitude": -25.4580, "longitude": -49.3150},
            {"latitude": -25.4620, "longitude": -49.3210},
            {"latitude": -25.4660, "longitude": -49.3270},
            {"latitude": -25.4700, "longitude": -49.3320},  # End at Campo Comprido
        ]
    },
    {
        "id": "3",
        "mode": "bicycle",
        "color": "#2ECC71",  # Green
        "coordinates": [
            # From Campo Comprido to South Curitiba through parks
            {"latitude": -25.4700, "longitude": -49.3320},  # Starting from Campo Comprido
            {"latitude": -25.4750, "longitude": -49.3270},
            {"latitude": -25.4800, "longitude": -49.3200},
            {"latitude": -25.4850, "longitude": -49.3120},
            {"latitude": -25.4900, "longitude": -49.3040},
            {"latitude": -25.4940, "longitude": -49.2950},
            {"latitude": -25.4980, "longitude": -49.2870},
            {"latitude": -25.5020, "longitude": -49.2800},
            {"latitude": -25.5060, "longitude": -49.2730},
            {"latitude": -25.5100, "longitude": -49.2680},  # End at Pinheirinho
        ]
    },
    {
        "id": "4",
        "mode": "walk",
        "color": "#9B59B6",  # Purple
        "coordinates": [
            # From Pinheirinho back towards east through a walking path
            {"latitude": -25.5100, "longitude": -49.2680},  # Starting from Pinheirinho
            {"latitude": -25.5050, "longitude": -49.2600},
            {"latitude": -25.5000, "longitude": -49.2520},
            {"latitude": -25.4940, "longitude": -49.2450},
            {"latitude": -25.4880, "longitude": -49.2380},
            {"latitude": -25.4820, "longitude": -49.2320},
            {"latitude": -25.4760, "longitude": -49.2260},
            {"latitude": -25.4700, "longitude": -49.2200},
            {"latitude": -25.4640, "longitude": -49.2150},
            {"latitude": -25.4580, "longitude": -49.2100},  # End at Jardim das Américas
        ]
    }
]