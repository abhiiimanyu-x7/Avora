"""
Campus Map Service - Avora
Provides verified topographical and building data based on the official
Topographical Survey of Khwaja Moinuddin Chishti Language University (KMCLU).
"""

CAMPUS_BUILDINGS = [
    {
        'id': 'academic-building',
        'name': 'Academic Building',
        'type': 'academic',
        'zone': 'Southern Sector',
        'coords': {'top': 73, 'left': 41},
        'description': 'Main multi-wing academic complex housing faculties of Engineering & Technology, Science, Arts & Humanities, and Commerce, departmental lecture halls, and laboratories.'
    },
    {
        'id': 'admin-building',
        'name': 'Administrative Building',
        'type': 'admin',
        'zone': 'South-West Sector',
        'coords': {'top': 55, 'left': 19},
        'description': 'Acharya Narendra Deva Building: Central offices of the Vice Chancellor, Registrar, Finance Officer, Controller of Examinations, and administrative clearance cells.'
    },
    {
        'id': 'library',
        'name': 'Central Library',
        'type': 'library',
        'zone': 'Central Sector',
        'coords': {'top': 49, 'left': 27},
        'description': 'Pt. Ram Prasad Bismil Central Library: Multi-story reading halls, 28,700+ print volumes, Wi-Fi terminals, and digital Knimbus e-library access.'
    },
    {
        'id': 'sfc',
        'name': "Students' Facility Center (SFC)",
        'type': 'amenity',
        'zone': 'Central East Sector',
        'coords': {'top': 54, 'left': 38},
        'description': 'Campus amenity center: University canteen, ICICI Bank branch with 24x7 ATM, stationery shop, print bureau, girls common room, and NCC / NSS unit offices.'
    },
    {
        'id': 'sports-ground',
        'name': 'Basketball Court & Play Ground',
        'type': 'sports',
        'zone': 'Central Sector',
        'coords': {'top': 59, 'left': 27},
        'description': 'Outdoor sports grounds, basketball court, athletic track, and campus recreational fields.'
    },
    {
        'id': 'gymnasium',
        'name': 'Gymnasium',
        'type': 'sports',
        'zone': 'Central Sector',
        'coords': {'top': 36, 'left': 30},
        'description': 'Chandrashekhar Azad Gymnasium: Indoor fitness facility, cardio and weight equipment, badminton courts, and Yoga Vatika.'
    },
    {
        'id': 'study-centre',
        'name': 'Study Centre',
        'type': 'academic',
        'zone': 'Central North Sector',
        'coords': {'top': 29, 'left': 30},
        'description': 'Ganesh Shankar Vidyarthi Study Centre: Department of Journalism & Mass Communication, Media Studio, and specialized language peeths.'
    },
    {
        'id': 'auditorium',
        'name': 'University Auditorium',
        'type': 'amenity',
        'zone': 'Central West Sector',
        'coords': {'top': 34, 'left': 23},
        'description': 'Large 1,200-seat university auditorium facility for convocations, seminars, foundation day events, and youth festivals.'
    },
    {
        'id': 'guest-house',
        'name': 'University Guest House',
        'type': 'amenity',
        'zone': 'Eastern Sector',
        'coords': {'top': 51, 'left': 49},
        'description': 'Campus VIP guest house surrounded by landscaped gardens, offering accommodation for visiting scholars, examiners, and delegates.'
    },
    {
        'id': 'girls-hostel',
        'name': "Girls' Hostel",
        'type': 'hostel',
        'zone': 'West Sector',
        'coords': {'top': 39, 'left': 14},
        'description': 'Rani Laxmi Bai Girls Hostel: Multi-wing residential hall, dining facilities, common room, and 24x7 security for ~300 students.'
    },
    {
        'id': 'boys-hostel',
        'name': "Boys' Hostel",
        'type': 'hostel',
        'zone': 'North-West Sector',
        'coords': {'top': 21, 'left': 16},
        'description': 'Boys residential quarters with dining hall, recreational rooms, outdoor courts, and accommodation for ~400 students.'
    },
    {
        'id': 'residences',
        'name': 'Faculty & Staff Residences',
        'type': 'residential',
        'zone': 'Northern Sector',
        'coords': {'top': 14, 'left': 25},
        'description': 'Residential enclave with Type I, Type II, Type III, and Type IV staff quarters for university faculty and administrative personnel.'
    },
    {
        'id': 'police-chauki',
        'name': 'Police Chauki & Main Entrance',
        'type': 'gate',
        'zone': 'Southern Sector',
        'coords': {'top': 80, 'left': 35},
        'description': 'Main campus entrance gate along Sitapur-Hardoi Bypass Road, security inspection checkpoint, and Police Chauki.'
    },
    {
        'id': 'parking',
        'name': 'Campus Parking Bay',
        'type': 'amenity',
        'zone': 'South-West Sector',
        'coords': {'top': 64, 'left': 20},
        'description': 'Organized two-wheeler and four-wheeler parking lots adjacent to the Administrative Building.'
    },
    {
        'id': 'utilities',
        'name': 'AC Plant & Substation',
        'type': 'utility',
        'zone': 'West Sector',
        'coords': {'top': 47, 'left': 14},
        'description': 'Central campus air-conditioning plant, high-tension electrical substation, and power transformers.'
    },
    {
        'id': 'stp',
        'name': 'Sewage Treatment Plant',
        'type': 'utility',
        'zone': 'North-West Sector',
        'coords': {'top': 11, 'left': 14},
        'description': 'Ecological wastewater management and water recycling plant on the northwestern boundary.'
    },
]

BUILDING_TYPES = {
    'academic': {'label': 'Academic', 'color': '#2563eb'},
    'admin': {'label': 'Administration', 'color': '#4f46e5'},
    'library': {'label': 'Library', 'color': '#7c3aed'},
    'hostel': {'label': 'Hostels', 'color': '#0891b2'},
    'amenity': {'label': 'Amenities & Facilities', 'color': '#059669'},
    'sports': {'label': 'Sports & Gym', 'color': '#d97706'},
    'residential': {'label': 'Residences', 'color': '#6366f1'},
    'gate': {'label': 'Entry & Security', 'color': '#64748b'},
    'utility': {'label': 'Utilities', 'color': '#78716c'},
}


def get_all_buildings():
    """Return the verified list of campus buildings."""
    return CAMPUS_BUILDINGS


def get_building_types():
    """Return building category metadata."""
    return BUILDING_TYPES


def get_building_by_id(building_id):
    """Look up a single building by its ID."""
    for b in CAMPUS_BUILDINGS:
        if b['id'] == building_id:
            return b
    return None
