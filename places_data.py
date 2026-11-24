# Saudi Weekend Planner: the starting catalogue of places
# Coordinates are approximate (taken from public maps). Costs are typical prices per person in SAR.

# the centre of each city, used as the home point and for hotels
CITIES = {
    'Riyadh':  {'lat': 24.7136, 'lng': 46.6753, 'hotel': 450},
    'Jeddah':  {'lat': 21.5433, 'lng': 39.1728, 'hotel': 420},
    'Makkah':  {'lat': 21.3891, 'lng': 39.8579, 'hotel': 550},
    'Madinah': {'lat': 24.4672, 'lng': 39.6112, 'hotel': 400},
    'Khobar':  {'lat': 26.2172, 'lng': 50.1971, 'hotel': 380},
    'AlUla':   {'lat': 26.6170, 'lng': 37.9150, 'hotel': 900},
    'Abha':    {'lat': 18.2164, 'lng': 42.5053, 'hotel': 350},
    'Taif':    {'lat': 21.2703, 'lng': 40.4158, 'hotel': 300},
}

CATEGORIES = ['Heritage', 'Nature', 'Food', 'Shopping', 'Entertainment', 'Beach', 'Religious', 'Cafe']

# (name, city, category, lat, lng, cost per person, minutes, opens, closes, description)
PLACES = [
    ('At-Turaif, Diriyah', 'Riyadh', 'Heritage', 24.7336, 46.5753, 100, 150, '16:00', '23:59', 'UNESCO mud-brick district of the first Saudi state'),
    ('Bujairi Terrace', 'Riyadh', 'Food', 24.7350, 46.5730, 180, 90, '16:00', '23:59', 'Restaurants facing At-Turaif'),
    ('Boulevard City', 'Riyadh', 'Entertainment', 24.7697, 46.6050, 150, 180, '16:00', '23:59', 'Riyadh Season zone with shows and rides'),
    ('Kingdom Centre Sky Bridge', 'Riyadh', 'Entertainment', 24.7114, 46.6744, 70, 60, '10:00', '23:00', 'Bridge at the top of Kingdom Tower'),
    ('National Museum', 'Riyadh', 'Heritage', 24.6476, 46.7106, 10, 120, '09:00', '20:00', 'Saudi history from prehistory to today'),
    ('Masmak Fortress', 'Riyadh', 'Heritage', 24.6312, 46.7134, 0, 60, '08:00', '21:00', 'Clay fort from the unification story'),
    ('Edge of the World', 'Riyadh', 'Nature', 24.9475, 45.9900, 50, 240, '06:00', '18:00', 'Cliffs of the Tuwaiq escarpment, 4x4 needed'),
    ('Riyadh Park Mall', 'Riyadh', 'Shopping', 24.7552, 46.6295, 120, 120, '10:00', '23:59', 'Large mall with cinema'),
    ('Al Balad (Historic Jeddah)', 'Jeddah', 'Heritage', 21.4858, 39.1925, 0, 150, '16:00', '23:59', 'Coral-stone houses, UNESCO site'),
    ('Jeddah Waterfront', 'Jeddah', 'Beach', 21.5937, 39.1090, 0, 90, '06:00', '23:59', 'Seaside walk, best at sunset'),
    ('King Fahd Fountain', 'Jeddah', 'Entertainment', 21.5146, 39.1460, 0, 30, '18:00', '23:59', 'The tallest fountain in the world'),
    ('Fakieh Aquarium', 'Jeddah', 'Entertainment', 21.6040, 39.1060, 90, 120, '10:00', '22:00', 'Aquarium with dolphin show'),
    ('Red Sea Mall', 'Jeddah', 'Shopping', 21.6278, 39.1110, 120, 120, '10:00', '23:59', 'Mall in north Jeddah'),
    ('Obhur Beach', 'Jeddah', 'Beach', 21.7300, 39.1000, 60, 180, '08:00', '23:00', 'Swimming and boat trips'),
    ('Fish market dinner', 'Jeddah', 'Food', 21.4930, 39.1780, 120, 75, '12:00', '23:59', 'Fresh Red Sea fish'),
    ('Masjid al-Haram', 'Makkah', 'Religious', 21.4225, 39.8262, 0, 180, '00:00', '23:59', 'Umrah and prayer'),
    ('Jabal al-Nour', 'Makkah', 'Religious', 21.4579, 39.8616, 0, 120, '05:00', '18:00', 'Mountain of the Hira cave'),
    ('Clock Tower Museum', 'Makkah', 'Heritage', 21.4189, 39.8253, 50, 60, '09:00', '22:00', 'Museum in Abraj Al Bait'),
    ('Al-Masjid an-Nabawi', 'Madinah', 'Religious', 24.4672, 39.6112, 0, 120, '00:00', '23:59', 'The Prophet’s Mosque'),
    ('Quba Mosque', 'Madinah', 'Religious', 24.4393, 39.6173, 0, 60, '00:00', '23:59', 'The first mosque in Islam'),
    ('Mount Uhud', 'Madinah', 'Heritage', 24.5050, 39.6150, 0, 90, '06:00', '20:00', 'Site of the Battle of Uhud'),
    ('Dates market', 'Madinah', 'Food', 24.4700, 39.6050, 80, 60, '08:00', '23:00', 'Ajwa and other dates'),
    ('Khobar Corniche', 'Khobar', 'Beach', 26.3000, 50.2200, 0, 90, '06:00', '23:59', 'Waterfront walk'),
    ('Half Moon Bay', 'Khobar', 'Beach', 26.0400, 50.0400, 40, 180, '08:00', '22:00', 'Calm shallow beach'),
    ('Ithra', 'Khobar', 'Heritage', 26.3327, 50.1100, 35, 150, '10:00', '22:00', 'King Abdulaziz Center for World Culture'),
    ('Al Rashid Mall', 'Khobar', 'Shopping', 26.2880, 50.1980, 100, 120, '10:00', '23:59', 'Mall in Khobar'),
    ('Hegra', 'AlUla', 'Heritage', 26.7914, 37.9533, 300, 180, '08:00', '18:00', 'Nabataean tombs, the first Saudi UNESCO site'),
    ('Elephant Rock', 'AlUla', 'Nature', 26.6660, 37.9500, 0, 90, '15:00', '23:59', 'Rock arch, best at sunset'),
    ('AlUla Old Town', 'AlUla', 'Heritage', 26.6260, 37.9150, 0, 90, '09:00', '23:00', 'Old mud-brick town'),
    ('Maraya', 'AlUla', 'Entertainment', 26.5990, 37.8790, 120, 60, '10:00', '22:00', 'Mirrored concert hall in the desert'),
    ('Al Soudah Park', 'Abha', 'Nature', 18.2700, 42.3700, 0, 150, '06:00', '22:00', 'The highest peak area, cool weather'),
    ('Rijal Almaa village', 'Abha', 'Heritage', 18.2090, 42.2740, 20, 120, '09:00', '19:00', 'Colourful stone village'),
    ('Al Muftaha Art Village', 'Abha', 'Heritage', 18.2160, 42.5050, 0, 60, '10:00', '22:00', 'Asiri art and crafts'),
    ('Green Mountain cafe', 'Abha', 'Cafe', 18.2300, 42.5070, 60, 75, '15:00', '23:59', 'View over Abha at night'),
    ('Al Shafa mountains', 'Taif', 'Nature', 21.0700, 40.3400, 0, 150, '06:00', '20:00', 'Mountain road and farms'),
    ('Rose farms', 'Taif', 'Nature', 21.1500, 40.3700, 30, 90, '07:00', '17:00', 'Taif roses, best in April'),
    ('Al Rudaf Park', 'Taif', 'Nature', 21.2470, 40.4000, 0, 90, '08:00', '23:00', 'Granite rocks park'),
    ('Taif Central Market', 'Taif', 'Food', 21.2720, 40.4150, 60, 60, '09:00', '23:00', 'Honey, fruit and sweets'),
]
