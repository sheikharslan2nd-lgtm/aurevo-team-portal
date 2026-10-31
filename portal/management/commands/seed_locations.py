import csv
import html
import os
import re
from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils.text import slugify
from portal.models import Country, City, Niche, OutreachMethod
from portal.niche_data import generate_micro_niches, generate_sub_niches

try:
    import pycountry
except ImportError:
    pycountry = None

NICHE_NAMES = [
    "Restaurants & Cafes", "Real Estate", "Dental Clinics", "Medical Clinics",
    "Law Firms", "Accounting Firms", "Marketing Agencies", "Construction Companies",
    "Plumbers", "Electricians", "Roofing Contractors", "Landscaping Services",
    "Cleaning Services", "Auto Repair Shops", "Car Dealerships", "Gyms & Fitness",
    "Beauty Salons", "Spas", "Hotels", "Travel Agencies", "Schools",
    "Colleges & Universities", "Training Institutes", "E-commerce Stores",
    "Retail Stores", "Manufacturing Companies", "Logistics & Transport",
    "Recruitment Agencies", "IT Companies", "Consulting Firms", "Event Planners",
    "Photographers", "Catering Services", "Nonprofit Organizations", "Pet Services",
    "Home Renovation", "Interior Design", "Furniture Stores", "Pharmacies",
    "Clinics & Hospitals", "Insurance Agencies", "Banking & Finance",
    "SaaS Companies", "Agencies", "Freelancers", "Startup Founders",
    "Property Management", "Wedding Services", "Coaching Centers", "Language Schools",
    "Digital Agencies", "Business Consultants", "Architecture Firms",
    "HVAC Services", "Security Companies", "Packaging Companies", "Laundry Services",
    "Appliance Repair", "Solar Energy Companies", "Automotive Services",
    "Boats & Marine Services", "Health Clubs", "Bakery Shops", "Coffee Shops",
    "Grocery Stores", "Mobile Stores", "Electronics Stores", "Fashion Brands",
    "Franchises", "Property Developers", "Legal Services", "Tax Consultants",
    "Hospitality Businesses", "Cinemas", "Fitness Studios", "Home Services",
    "Commercial Cleaning", "Emergency Services", "Prototyping Firms",
    "Podcast Studios", "Business Coaches", "Vehicle Leasing", "Warehousing",
    "Industrial Suppliers", "Solar Installers", "Import & Export Businesses",
    "B2B Service Providers", "Private Clinics", "Dental Labs", "Orthopedic Clinics",
    "Daycare Centers", "Senior Care Homes", "Veterinary Clinics", "Farm Equipment",
    "Agriculture Businesses", "Food Processing", "Cold Storage", "Waste Management",
    "Construction Materials", "Packaging Suppliers", "Apparel Brands",
    "Textile Businesses", "Metal Fabrication", "Printing Presses", "Signage Companies",
    "Interior Contractors", "Glass & Aluminum", "Swimming Pool Services",
    "Water Treatment Companies", "Moving & Relocation", "Pest Control Services",
    "Security Guard Services", "Parking Management", "Corporate Training", "Call Centers",
    "IT Support Companies", "Cloud Service Providers", "CRM Consultants",
    "ERP Companies", "Automation Agencies", "Outsourcing Firms", "Research Firms",
    "Community Centers", "Sports Clubs", "Driving Schools", "Funeral Homes",
    "Luxury Goods Stores", "Jewelry Stores", "Mobile App Agencies", "Data Analytics Firms",
    "Corporate Wellness", "Private Schools", "Tutoring Centers", "Online Education",
    "Home Decor Stores", "Office Furniture", "Hostels", "Logistics Companies",
    "Transportation Companies", "Fleet Management", "Airlines", "Air Cargo"
]

METHOD_NAMES = [
    "Cold Email", "LinkedIn Outreach", "WhatsApp", "Instagram DM", "Facebook",
    "Phone Calls", "Google Maps Leads", "Contact Form", "Referral", "In-person",
    "SMS Outreach", "Telegram Outreach", "Cold Calling", "CRM Follow-up",
    "Email Follow-up", "Video Call", "Professional Network", "Local Community Outreach"
]

COUNTRY_CITY_MAP = {
    "Pakistan": ["Lahore", "Karachi", "Islamabad", "Rawalpindi", "Faisalabad", "Multan", "Peshawar", "Quetta", "Sialkot", "Gujranwala", "Sukkur", "Hyderabad", "Abbottabad", "Bahawalpur", "Mardan"],
    "United States": ["New York", "Los Angeles", "Chicago", "Houston", "Dallas", "Miami", "San Francisco", "Seattle", "Boston", "Atlanta", "Austin", "Phoenix", "Denver", "Las Vegas", "Philadelphia"],
    "United Arab Emirates": ["Dubai", "Abu Dhabi", "Sharjah", "Ajman", "Ras Al Khaimah", "Fujairah", "Al Ain"],
    "Saudi Arabia": ["Riyadh", "Jeddah", "Dammam", "Mecca", "Medina", "Khobar", "Tabuk", "Abha"],
    "United Kingdom": ["London", "Manchester", "Birmingham", "Leeds", "Glasgow", "Liverpool", "Edinburgh", "Bristol", "Cardiff", "Leicester"],
    "Canada": ["Toronto", "Vancouver", "Montreal", "Calgary", "Ottawa", "Edmonton", "Winnipeg", "Quebec City", "Halifax", "Victoria"],
    "Australia": ["Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide", "Gold Coast", "Canberra", "Hobart", "Darwin", "Newcastle"],
    "Germany": ["Berlin", "Hamburg", "Munich", "Frankfurt", "Cologne", "Stuttgart", "Dusseldorf", "Leipzig", "Bremen", "Nuremberg"],
    "France": ["Paris", "Lyon", "Marseille", "Nice", "Toulouse", "Bordeaux", "Strasbourg", "Lille", "Nantes", "Montpellier"],
    "Spain": ["Madrid", "Barcelona", "Valencia", "Seville", "Malaga", "Bilbao", "Zaragoza", "Alicante", "Granada", "Murcia"],
    "Italy": ["Rome", "Milan", "Naples", "Florence", "Turin", "Bologna", "Palermo", "Genoa", "Verona", "Bari"],
    "Netherlands": ["Amsterdam", "Rotterdam", "The Hague", "Utrecht", "Eindhoven", "Tilburg", "Groningen", "Almere", "Arnhem", "Nijmegen"],
    "Belgium": ["Brussels", "Antwerp", "Ghent", "Bruges", "Liège", "Charleroi", "Namur", "Leuven", "Mons", "Gent"],
    "Switzerland": ["Zurich", "Geneva", "Basel", "Bern", "Lausanne", "Lugano", "Winterthur", "Lucerne", "St. Gallen", "Fribourg"],
    "Sweden": ["Stockholm", "Gothenburg", "Malmo", "Uppsala", "Linkoping", "Norrkoping", "Vasteras", "Orebro", "Helsingborg", "Jönköping"],
    "Norway": ["Oslo", "Bergen", "Trondheim", "Stavanger", "Drammen", "Kristiansand", "Tromso", "Alesund", "Sandefjord", "Bodø"],
    "Denmark": ["Copenhagen", "Aarhus", "Odense", "Aalborg", "Esbjerg", "Roskilde", "Randers", "Helsingør", "Kolding", "Sønderborg"],
    "Finland": ["Helsinki", "Espoo", "Tampere", "Turku", "Oulu", "Vantaa", "Lahti", "Kuopio", "Jyvaskyla", "Porvoo"],
    "Poland": ["Warsaw", "Krakow", "Gdansk", "Wroclaw", "Poznan", "Lodz", "Katowice", "Bialystok", "Szczecin", "Gdynia"],
    "Romania": ["Bucharest", "Cluj-Napoca", "Timisoara", "Iasi", "Constanta", "Brasov", "Craiova", "Galati", "Oradea", "Ploiesti"],
    "Hungary": ["Budapest", "Debrecen", "Szeged", "Pecs", "Miskolc", "Gyor", "Nyiregyhaza", "Kecskemet", "Sopron", "Székesfehérvár"],
    "Czech Republic": ["Prague", "Brno", "Ostrava", "Plzen", "Liberec", "Olomouc", "Pardubice", "Hradec Kralove", "Ceske Budejovice", "Zlin"],
    "Portugal": ["Lisbon", "Porto", "Braga", "Faro", "Coimbra", "Amadora", "Setubal", "Aveiro", "Guimaraes", "Leiria"],
    "Greece": ["Athens", "Thessaloniki", "Patras", "Heraklion", "Larissa", "Piraeus", "Volos", "Crete", "Chania", "Ioannina"],
    "Turkey": ["Istanbul", "Ankara", "Izmir", "Antalya", "Bursa", "Adana", "Gaziantep", "Konya", "Mersin", "Trabzon"],
    "Russia": ["Moscow", "Saint Petersburg", "Novosibirsk", "Yekaterinburg", "Kazan", "Samara", "Nizhny Novgorod", "Rostov-on-Don", "Chelyabinsk", "Volgograd"],
    "Ukraine": ["Kyiv", "Kharkiv", "Lviv", "Odessa", "Dnipro", "Zaporizhzhia", "Donetsk", "Vinnytsia", "Mykolaiv", "Chernihiv"],
    "India": ["Delhi", "Mumbai", "Bengaluru", "Hyderabad", "Chennai", "Pune", "Kolkata", "Ahmedabad", "Jaipur", "Lucknow"],
    "Bangladesh": ["Dhaka", "Chittagong", "Khulna", "Rajshahi", "Sylhet", "Narshingdi", "Gazipur", "Comilla", "Barisal", "Mymensingh"],
    "Sri Lanka": ["Colombo", "Kandy", "Galle", "Negombo", "Jaffna", "Kurunegala", "Matara", "Anuradhapura", "Ratnapura", "Badulla"],
    "Nepal": ["Kathmandu", "Pokhara", "Biratnagar", "Lalitpur", "Bharatpur", "Janakpur", "Dharan", "Bhaktapur", "Butwal", "Hetauda"],
    "Afghanistan": ["Kabul", "Herat", "Kandahar", "Mazar-i-Sharif", "Jalalabad", "Gardez", "Kunduz", "Peshawar", "Balkh", "Maidan Wardak"],
    "Egypt": ["Cairo", "Alexandria", "Giza", "Luxor", "Sharm El Sheikh", "Aswan", "Hurghada", "Mansoura", "Port Said", "Suez"],
    "Morocco": ["Casablanca", "Rabat", "Marrakech", "Tangier", "Fez", "Agadir", "Oujda", "Meknes", "Kenitra", "Tetouan"],
    "South Africa": ["Johannesburg", "Cape Town", "Durban", "Pretoria", "Bloemfontein", "Gqeberha", "East London", "Polokwane", "Pietermaritzburg", "Benoni"],
    "Nigeria": ["Lagos", "Abuja", "Kano", "Ibadan", "Port Harcourt", "Kaduna", "Enugu", "Benin City", "Jos", "Abeokuta"],
    "Kenya": ["Nairobi", "Mombasa", "Kisumu", "Nakuru", "Eldoret", "Thika", "Machakos", "Meru", "Naivasha", "Nanyuki"],
    "Ghana": ["Accra", "Kumasi", "Tamale", "Takoradi", "Cape Coast", "Tema", "Ho", "Koforidua", "Wa", "Sunyani"],
    "Algeria": ["Algiers", "Oran", "Constantine", "Annaba", "Batna", "Setif", "Tlemcen", "Djelfa", "Sidi Bel Abbes", "Skikda"],
    "Tunisia": ["Tunis", "Sfax", "Sousse", "Kairouan", "Monastir", "Bizerte", "Gabes", "Nabeul", "Tozeur", "Djerba"],
    "Ethiopia": ["Addis Ababa", "Dire Dawa", "Mekelle", "Adama", "Gondar", "Hawassa", "Bahir Dar", "Jimma", "Awasa", "Jijiga"],
    "Tanzania": ["Dar es Salaam", "Dodoma", "Arusha", "Mwanza", "Mbeya", "Kigoma", "Morogoro", "Tabora", "Zanzibar City", "Tanga"],
    "Uganda": ["Kampala", "Gulu", "Jinja", "Mbarara", "Mbale", "Fort Portal", "Lira", "Masaka", "Arua", "Mukono"],
    "Indonesia": ["Jakarta", "Bandung", "Surabaya", "Medan", "Bali", "Semarang", "Makassar", "Palembang", "Yogyakarta", "Denpasar"],
    "Malaysia": ["Kuala Lumpur", "George Town", "Johor Bahru", "Kota Kinabalu", "Shah Alam", "Petaling Jaya", "Ipoh", "Kuching", "Melaka", "Seremban"],
    "Philippines": ["Manila", "Cebu City", "Davao City", "Quezon City", "Baguio", "Cagayan de Oro", "Iloilo City", "Zamboanga City", "General Santos", "Bacolod"],
    "Singapore": ["Singapore"],
    "Thailand": ["Bangkok", "Chiang Mai", "Phuket", "Pattaya", "Khon Kaen", "Nonthaburi", "Nakhon Ratchasima", "Samut Prakan", "Udon Thani", "Hat Yai"],
    "Vietnam": ["Ho Chi Minh City", "Hanoi", "Da Nang", "Hai Phong", "Can Tho", "Nha Trang", "Buon Ma Thuot", "Vinh", "Hue", "Quy Nhon"],
    "Japan": ["Tokyo", "Osaka", "Kyoto", "Yokohama", "Nagoya", "Sapporo", "Fukuoka", "Kobe", "Sendai", "Hiroshima"],
    "South Korea": ["Seoul", "Busan", "Incheon", "Daegu", "Daejeon", "Gwangju", "Jeju", "Ulsan", "Suwon", "Seongnam"],
    "China": ["Beijing", "Shanghai", "Guangzhou", "Shenzhen", "Hangzhou", "Chengdu", "Xi'an", "Nanjing", "Wuhan", "Dongguan"],
    "Taiwan": ["Taipei", "Kaohsiung", "Taichung", "Tainan", "Hsinchu", "Taoyuan", "Keelung", "Chiayi", "Taitung", "Hualien"],
    "Hong Kong": ["Hong Kong"],
    "Qatar": ["Doha", "Al Rayyan", "Al Wakrah", "Lusail", "Mesaieed", "Umm Salal", "Al Khor", "Al Daayen", "Al Shamal", "Al Ruwais"],
    "Oman": ["Muscat", "Salalah", "Sohar", "Nizwa", "Sur", "Buraimi", "Ibri", "Rustaq", "Samail", "Duqm"],
    "Kuwait": ["Kuwait City", "Hawalli", "Ahmadi", "Salmiya", "Fahaheel", "Jahra", "Sabah Al-Salem", "Farwaniya", "Al Ahmadi", "Al Fintas"],
    "Bahrain": ["Manama", "Muharraq", "Riffa", "Sitra", "Hamad Town", "A'ali", "Isa Town", "Jidd Haffs", "Budaiya", "Al-Malikiyah"],
    "Jordan": ["Amman", "Zarqa", "Irbid", "Aqaba", "Madaba", "Salt", "Balqa", "Al Karak", "Aqaba", "Mafraq"],
    "Lebanon": ["Beirut", "Tripoli", "Sidon", "Byblos", "Jounieh", "Tyre", "Baabda", "Zahle", "Baalbek", "Aley"],
    "Iraq": ["Baghdad", "Basra", "Erbil", "Najaf", "Kirkuk", "Mosul", "Sulaimaniya", "Nasiriyah", "Karbala", "Hilla"],
    "Iran": ["Tehran", "Mashhad", "Isfahan", "Shiraz", "Tabriz", "Karaj", "Qom", "Ahvaz", "Kermanshah", "Rasht"],
    "Israel": ["Jerusalem", "Tel Aviv", "Haifa", "Ramat Gan", "Netanya", "Beersheba", "Ashdod", "Herzliya", "Petah Tikva", "Holon"],
    "Kazakhstan": ["Astana", "Almaty", "Karaganda", "Shymkent", "Aktobe", "Atyrau", "Taraz", "Pavlodar", "Oral", "Semey"],
    "Uzbekistan": ["Tashkent", "Samarkand", "Bukhara", "Namangan", "Fergana", "Andijan", "Nukus", "Karshi", "Jizzakh", "Urgench"],
    "Azerbaijan": ["Baku", "Ganja", "Sumqayit", "Lankaran", "Nakhchivan", "Mingachevir", "Shaki", "Gabala", "Barda", "Quba"],
    "Georgia": ["Tbilisi", "Batumi", "Kutaisi", "Rustavi", "Sukhumi", "Zugdidi", "Poti", "Gori", "Kobuleti", "Telavi"],
    "Armenia": ["Yerevan", "Gyumri", "Vanadzor", "Ejmiatsin", "Abovyan", "Artashat", "Kapan", "Hrazdan", "Ijevan", "Vagharshapat"],
    "Mexico": ["Mexico City", "Guadalajara", "Monterrey", "Puebla", "Tijuana", "Leon", "Merida", "Cancun", "Queretaro", "Ciudad Juarez"],
    "Brazil": ["Sao Paulo", "Rio de Janeiro", "Brasilia", "Salvador", "Fortaleza", "Belo Horizonte", "Curitiba", "Recife", "Porto Alegre", "Manaus"],
    "Argentina": ["Buenos Aires", "Cordoba", "Rosario", "Mendoza", "La Plata", "San Miguel de Tucuman", "Salta", "Mar del Plata", "Santa Fe", "Neuquen"],
    "Chile": ["Santiago", "Valparaiso", "Concepcion", "Temuco", "Antofagasta", "La Serena", "Puerto Montt", "Rancagua", "Talca", "Arica"],
    "Colombia": ["Bogota", "Medellin", "Cali", "Barranquilla", "Cartagena", "Pereira", "Manizales", "Bucaramanga", "Villavicencio", "Pasto"],
    "Peru": ["Lima", "Arequipa", "Trujillo", "Cusco", "Piura", "Chiclayo", "Iquitos", "Huancayo", "Tacna", "Juliaca"],
    "Ecuador": ["Quito", "Guayaquil", "Cuenca", "Ambato", "Loja", "Machala", "Duran", "Manta", "Riobamba", "Esmeraldas"],
    "Bolivia": ["La Paz", "Santa Cruz", "Cochabamba", "Sucre", "Oruro", "Tarija", "Potosi", "Trinidad", "El Alto", "Montero"],
    "Uruguay": ["Montevideo", "Salto", "Paysandu", "Las Piedras", "Rivera", "Maldonado", "Mercedes", "Artigas", "Tacuarembo", "Rocha"],
    "Paraguay": ["Asuncion", "Ciudad del Este", "San Lorenzo", "Luque", "Capiata", "Pedro Juan Caballero", "Encarnacion", "Fernando de la Mora", "Villarrica", "Itaugua"],
    "Costa Rica": ["San Jose", "Alajuela", "Heredia", "Cartago", "Limon", "Liberia", "San Francisco", "Puntarenas", "Desamparados", "Curridabat"],
    "Guatemala": ["Guatemala City", "Mixco", "Villa Nueva", "Quetzaltenango", "Escuintla", "Antigua Guatemala", "Chimaltenango", "Petapa", "San Miguel Petapa", "Totonicapán"],
    "Dominican Republic": ["Santo Domingo", "Santiago", "Puerto Plata", "San Pedro de Macoris", "Samaná", "La Romana", "Bonao", "Higuey", "Duarte", "San Cristobal"],
    "Panama": ["Panama City", "David", "Colón", "San Miguelito", "La Chorrera", "Arraijan", "Tocumen", "Chepo", "Chitre", "Boquete"],
    "New Zealand": ["Auckland", "Wellington", "Christchurch", "Hamilton", "Dunedin", "Rotorua", "Tauranga", "Napier", "Nelson", "Palmerston North"],
    "Ireland": ["Dublin", "Cork", "Limerick", "Galway", "Waterford", "Kilkenny", "Athlone", "Sligo", "Wexford", "Drogheda"],
    "Austria": ["Vienna", "Graz", "Linz", "Salzburg", "Innsbruck", "Klosterneuburg", "Wels", "Villach", "Dornbirn", "Bregenz"],
    "Croatia": ["Zagreb", "Split", "Rijeka", "Osijek", "Zadar", "Dubrovnik", "Pula", "Karlovac", "Sisak", "Varaždin"],
    "Bulgaria": ["Sofia", "Plovdiv", "Varna", "Burgas", "Ruse", "Stara Zagora", "Pleven", "Sliven", "Dobrich", "Veliko Tarnovo"],
    "Serbia": ["Belgrade", "Novi Sad", "Niš", "Pristina", "Kragujevac", "Subotica", "Leskovac", "Zrenjanin", "Novi Pazar", "Čačak"],
    "Albania": ["Tirana", "Durres", "Vlore", "Shkoder", "Fier", "Korça", "Berat", "Elbasan", "Sarande", "Lushnje"],
    "Bosnia and Herzegovina": ["Sarajevo", "Banja Luka", "Mostar", "Tuzla", "Zenica", "Bijeljina", "Trebinje", "Brčko", "Visoko", "Doboj"],
    "Slovakia": ["Bratislava", "Košice", "Nitra", "Banská Bystrica", "Prešov", "Žilina", "Trnava", "Martin", "Poprad", "Piestany"],
    "Slovenia": ["Ljubljana", "Maribor", "Celje", "Kranj", "Koper", "Novo Mesto", "Velenje", "Ptuj", "Domžale", "Kamnik"],
    "Estonia": ["Tallinn", "Tartu", "Narva", "Pärnu", "Kohtla-Järve", "Viljandi", "Rakvere", "Maardu", "Haapsalu", "Sillamäe"],
    "Latvia": ["Riga", "Daugavpils", "Liepaja", "Jelgava", "Ventspils", "Jurmala", "Valmiera", "Rezekne", "Ogre", "Cesis"],
    "Lithuania": ["Vilnius", "Kaunas", "Klaipėda", "Šiauliai", "Panevėžys", "Alytus", "Marijampole", "Utena", "Taurage", "Druskininkai"],
    "Iceland": ["Reykjavik", "Akureyri", "Kopavogur", "Hafnarfjordur", "Selfoss", "Akranes", "Isafjordur", "Husavik", "Vestmannaeyjar", "Sauðárkrókur"],
    "Malta": ["Valletta", "Sliema", "St Julian's", "Birgu", "Birkirkara", "Mosta", "Qormi", "Paola", "Msida", "Naxxar"],
    "Cyprus": ["Nicosia", "Limassol", "Paphos", "Larnaca", "Famagusta", "Ayia Napa", "Kyrenia", "Polis", "Pera", "Morphou"],
    "Jordan": ["Amman", "Zarqa", "Irbid", "Aqaba", "Madaba", "Salt", "Al Karak", "Mafraq", "Ajloun", "Jerash"],
    "Lebanon": ["Beirut", "Tripoli", "Sidon", "Byblos", "Jounieh", "Tyre", "Zahlé", "Baalbek", "Aley", "Bourj Hammoud"],
    "Iraq": ["Baghdad", "Basra", "Erbil", "Najaf", "Kirkuk", "Mosul", "Sulaimaniya", "Nasiriyah", "Karbala", "Hilla"],
    "Iran": ["Tehran", "Mashhad", "Isfahan", "Shiraz", "Tabriz", "Karaj", "Qom", "Ahvaz", "Kermanshah", "Rasht"],
    "Kazakhstan": ["Astana", "Almaty", "Karaganda", "Shymkent", "Aktobe", "Atyrau", "Taraz", "Pavlodar", "Oral", "Semey"],
    "Uzbekistan": ["Tashkent", "Samarkand", "Bukhara", "Namangan", "Fergana", "Andijan", "Nukus", "Karshi", "Jizzakh", "Urgench"],
    "Azerbaijan": ["Baku", "Ganja", "Sumqayit", "Lankaran", "Nakhchivan", "Mingachevir", "Shaki", "Gabala", "Barda", "Quba"],
    "Georgia": ["Tbilisi", "Batumi", "Kutaisi", "Rustavi", "Sukhumi", "Zugdidi", "Poti", "Gori", "Kobuleti", "Telavi"],
    "Armenia": ["Yerevan", "Gyumri", "Vanadzor", "Ejmiatsin", "Abovyan", "Artashat", "Kapan", "Hrazdan", "Ijevan", "Vagharshapat"],
    "Thailand": ["Bangkok", "Chiang Mai", "Phuket", "Pattaya", "Khon Kaen", "Nonthaburi", "Nakhon Ratchasima", "Samut Prakan", "Udon Thani", "Hat Yai"],
    "Vietnam": ["Ho Chi Minh City", "Hanoi", "Da Nang", "Hai Phong", "Can Tho", "Nha Trang", "Buon Ma Thuot", "Vinh", "Hue", "Quy Nhon"],
    "Singapore": ["Singapore"],
    "Malaysia": ["Kuala Lumpur", "George Town", "Johor Bahru", "Kota Kinabalu", "Shah Alam", "Petaling Jaya", "Ipoh", "Kuching", "Melaka", "Seremban"],
    "Indonesia": ["Jakarta", "Bandung", "Surabaya", "Medan", "Bali", "Semarang", "Makassar", "Palembang", "Yogyakarta", "Denpasar"],
    "Japan": ["Tokyo", "Osaka", "Kyoto", "Yokohama", "Nagoya", "Sapporo", "Fukuoka", "Kobe", "Sendai", "Hiroshima"],
    "South Korea": ["Seoul", "Busan", "Incheon", "Daegu", "Daejeon", "Gwangju", "Jeju", "Ulsan", "Suwon", "Seongnam"],
    "China": ["Beijing", "Shanghai", "Guangzhou", "Shenzhen", "Hangzhou", "Chengdu", "Xi'an", "Nanjing", "Wuhan", "Dongguan"],
    "Taiwan": ["Taipei", "Kaohsiung", "Taichung", "Tainan", "Hsinchu", "Taoyuan", "Keelung", "Chiayi", "Taitung", "Hualien"],
    "Hong Kong": ["Hong Kong"],
    "Saudi Arabia": ["Riyadh", "Jeddah", "Dammam", "Mecca", "Medina", "Khobar", "Tabuk", "Abha"],
    "United Arab Emirates": ["Dubai", "Abu Dhabi", "Sharjah", "Ajman", "Ras Al Khaimah", "Fujairah", "Al Ain"],
    "Qatar": ["Doha", "Al Rayyan", "Al Wakrah", "Lusail", "Mesaieed", "Umm Salal", "Al Khor", "Al Daayen", "Al Shamal", "Al Ruwais"],
    "Bahrain": ["Manama", "Muharraq", "Riffa", "Sitra", "Hamad Town", "A'ali", "Isa Town", "Jidd Haffs", "Budaiya", "Al-Malikiyah"],
    "Kuwait": ["Kuwait City", "Hawalli", "Ahmadi", "Salmiya", "Fahaheel", "Jahra", "Sabah Al-Salem", "Farwaniya", "Al Ahmadi", "Al Fintas"],
    "Oman": ["Muscat", "Salalah", "Sohar", "Nizwa", "Sur", "Buraimi", "Ibri", "Rustaq", "Samail", "Duqm"],
    "Jordan": ["Amman", "Zarqa", "Irbid", "Aqaba", "Madaba", "Salt", "Al Karak", "Mafraq", "Ajloun", "Jerash"],
    "Iraq": ["Baghdad", "Basra", "Erbil", "Najaf", "Kirkuk", "Mosul", "Sulaimaniya", "Nasiriyah", "Karbala", "Hilla"],
    "Iran": ["Tehran", "Mashhad", "Isfahan", "Shiraz", "Tabriz", "Karaj", "Qom", "Ahvaz", "Kermanshah", "Rasht"],
    "Turkey": ["Istanbul", "Ankara", "Izmir", "Antalya", "Bursa", "Adana", "Gaziantep", "Konya", "Mersin", "Trabzon"],
    "Egypt": ["Cairo", "Alexandria", "Giza", "Luxor", "Sharm El Sheikh", "Aswan", "Hurghada", "Mansoura", "Port Said", "Suez"],
    "Morocco": ["Casablanca", "Rabat", "Marrakech", "Tangier", "Fez", "Agadir", "Oujda", "Meknes", "Kenitra", "Tetouan"],
    "Tunisia": ["Tunis", "Sfax", "Sousse", "Kairouan", "Monastir", "Bizerte", "Gabes", "Nabeul", "Tozeur", "Djerba"],
    "Algeria": ["Algiers", "Oran", "Constantine", "Annaba", "Batna", "Setif", "Tlemcen", "Djelfa", "Sidi Bel Abbes", "Skikda"],
    "Libya": ["Tripoli", "Benghazi", "Misrata", "Bayda", "Sabha", "Sirte", "Zawiya", "Gharyan", "Al Khums", "Ajdabiya"],
    "Sudan": ["Khartoum", "Omdurman", "Port Sudan", "Kadugli", "Kassala", "Nyala", "El Obeid", "Juba", "Atbara", "Wad Madani"],
    "South Sudan": ["Juba", "Wau", "Malakal", "Bor", "Aweil", "Rumbek", "Yei", "Bentiu", "Kajo Keji", "Yambio"],
    "Kenya": ["Nairobi", "Mombasa", "Kisumu", "Nakuru", "Eldoret", "Thika", "Machakos", "Meru", "Naivasha", "Nanyuki"],
    "Uganda": ["Kampala", "Gulu", "Jinja", "Mbarara", "Mbale", "Fort Portal", "Lira", "Masaka", "Arua", "Mukono"],
    "Tanzania": ["Dar es Salaam", "Dodoma", "Arusha", "Mwanza", "Mbeya", "Kigoma", "Morogoro", "Tabora", "Zanzibar City", "Tanga"],
    "Rwanda": ["Kigali", "Butare", "Gisenyi", "Muhanga", "Rwamagana", "Huye", "Rubavu", "Nyagatare", "Rusizi", "Musanze"],
    "Burundi": ["Bujumbura", "Gitega", "Ngozi", "Muyinga", "Ruyigi", "Rumonge", "Makamba", "Kayanza", "Muramvya", "Bururi"],
    "Gabon": ["Libreville", "Port-Gentil", "Franceville", "Oyem", "Moanda", "Lambarene", "Tchibanga", "Mouila", "Koulamoutou", "Bitam"],
    "Cameroon": ["Yaounde", "Douala", "Bamenda", "Garoua", "Maroua", "Yaounde", "Kousséri", "Nkongsamba", "Bafoussam", "Bertoua"],
    "Senegal": ["Dakar", "Thiès", "Saint-Louis", "Kaolack", "Ziguinchor", "Tambacounda", "Mbour", "Diourbel", "Tivaouane", "Louga"],
    "Mali": ["Bamako", "Sikasso", "Mopti", "Kayes", "Koutiala", "Gao", "Segou", "Kidal", "Tombouctou", "Bougouni"],
    "Ivory Coast": ["Abidjan", "Bouaké", "Daloa", "Yamoussoukro", "San Pedro", "Korhogo", "Man", "Gagnoa", "Divo", "Daoukro"],
    "Benin": ["Cotonou", "Porto-Novo", "Parakou", "Abomey", "Bohicon", "Lokossa", "Natitingou", "Djougou", "Ouidah", "Kandi"],
    "Togo": ["Lome", "Sokode", "Kara", "Atakpame", "Dapaong", "Aného", "Tsévié", "Bassar", "Bafilo", "Tchamba"],
    "Ghana": ["Accra", "Kumasi", "Tamale", "Takoradi", "Cape Coast", "Tema", "Ho", "Koforidua", "Wa", "Sunyani"],
    "Botswana": ["Gaborone", "Francistown", "Maun", "Kasane", "Serowe", "Palapye", "Selebi-Phikwe", "Kanye", "Mahalapye", "Lobatse"],
    "Namibia": ["Windhoek", "Swakopmund", "Walvis Bay", "Rundu", "Katima Mulilo", "Otjiwarongo", "Tsumeb", "Keetmanshoop", "Ongwediva", "Gobabis"],
    "Zimbabwe": ["Harare", "Bulawayo", "Chitungwiza", "Mutare", "Gweru", "Kadoma", "Masvingo", "Kwekwe", "Bindura", "Marondera"],
    "Zambia": ["Lusaka", "Ndola", "Kitwe", "Kabwe", "Chingola", "Livingstone", "Kasama", "Mansa", "Chipata", "Mazabuka"],
    "Mozambique": ["Maputo", "Beira", "Nampula", "Quelimane", "Matola", "Chimoio", "Tete", "Xai-Xai", "Pemba", "Gaza"],
    "Angola": ["Luanda", "Huambo", "Lobito", "Benguela", "Lubango", "Namibe", "Soyo", "Uige", "Malanje", "Kuito"],
    "Brazil": ["Sao Paulo", "Rio de Janeiro", "Brasilia", "Salvador", "Fortaleza", "Belo Horizonte", "Curitiba", "Recife", "Porto Alegre", "Manaus"],
    "Chile": ["Santiago", "Valparaiso", "Concepcion", "Temuco", "Antofagasta", "La Serena", "Puerto Montt", "Rancagua", "Talca", "Arica"],
    "Argentina": ["Buenos Aires", "Cordoba", "Rosario", "Mendoza", "La Plata", "San Miguel de Tucuman", "Salta", "Mar del Plata", "Santa Fe", "Neuquen"],
    "Peru": ["Lima", "Arequipa", "Trujillo", "Cusco", "Piura", "Chiclayo", "Iquitos", "Huancayo", "Tacna", "Juliaca"],
    "Colombia": ["Bogota", "Medellin", "Cali", "Barranquilla", "Cartagena", "Pereira", "Manizales", "Bucaramanga", "Villavicencio", "Pasto"],
    "Venezuela": ["Caracas", "Maracaibo", "Valencia", "Barquisimeto", "Maracay", "Ciudad Guayana", "Maturin", "San Cristobal", "Barcelona", "Cumana"],
    "Bolivia": ["La Paz", "Santa Cruz", "Cochabamba", "Sucre", "Oruro", "Tarija", "Potosi", "Trinidad", "El Alto", "Montero"],
    "Uruguay": ["Montevideo", "Salto", "Paysandu", "Las Piedras", "Rivera", "Maldonado", "Mercedes", "Artigas", "Tacuarembo", "Rocha"],
    "Paraguay": ["Asuncion", "Ciudad del Este", "San Lorenzo", "Luque", "Capiata", "Pedro Juan Caballero", "Encarnacion", "Fernando de la Mora", "Villarrica", "Itaugua"],
    "Mexico": ["Mexico City", "Guadalajara", "Monterrey", "Puebla", "Tijuana", "Leon", "Merida", "Cancun", "Queretaro", "Ciudad Juarez"],
    "Guatemala": ["Guatemala City", "Mixco", "Villa Nueva", "Quetzaltenango", "Escuintla", "Antigua Guatemala", "Chimaltenango", "Petapa", "San Miguel Petapa", "Totonicapán"],
    "El Salvador": ["San Salvador", "Santa Ana", "San Miguel", "Soyapango", "Mejicanos", "Apopa", "La Libertad", "Usulutan", "San Vicente", "Cojutepeque"],
    "Honduras": ["Tegucigalpa", "San Pedro Sula", "La Ceiba", "Choloma", "Comayagua", "El Progreso", "Juticalpa", "Siguatepeque", "Roatan", "Tela"],
    "Nicaragua": ["Managua", "Leon", "Masaya", "Matagalpa", "Chinandega", "Esteli", "Granada", "Juigalpa", "Bluefields", "Tipitapa"],
    "Costa Rica": ["San Jose", "Alajuela", "Heredia", "Cartago", "Limon", "Liberia", "San Francisco", "Puntarenas", "Desamparados", "Curridabat"],
    "Panama": ["Panama City", "David", "Colón", "San Miguelito", "La Chorrera", "Arraijan", "Tocumen", "Chepo", "Chitre", "Boquete"],
    "Dominican Republic": ["Santo Domingo", "Santiago", "Puerto Plata", "San Pedro de Macoris", "Samaná", "La Romana", "Bonao", "Higuey", "Duarte", "San Cristobal"],
    "Cuba": ["Havana", "Santiago de Cuba", "Camaguey", "Holguin", "Santa Clara", "Guantanamo", "Las Tunas", "Matanzas", "Cienfuegos", "Pinar del Rio"],
    "Puerto Rico": ["San Juan", "Bayamon", "Carolina", "Ponce", "Caguas", "Mayaguez", "Trujillo Alto", "Arecibo", "Guaynabo", "Humacao"],
    "Jamaica": ["Kingston", "Montego Bay", "Spanish Town", "Portmore", "Mandeville", "Ocho Rios", "May Pen", "Savanna-la-Mar", "Falmouth", "Linstead"],
    "Thailand": ["Bangkok", "Chiang Mai", "Phuket", "Pattaya", "Khon Kaen", "Nonthaburi", "Nakhon Ratchasima", "Samut Prakan", "Udon Thani", "Hat Yai"],
    "Vietnam": ["Ho Chi Minh City", "Hanoi", "Da Nang", "Hai Phong", "Can Tho", "Nha Trang", "Buon Ma Thuot", "Vinh", "Hue", "Quy Nhon"],
    "Singapore": ["Singapore"],
    "Malaysia": ["Kuala Lumpur", "George Town", "Johor Bahru", "Kota Kinabalu", "Shah Alam", "Petaling Jaya", "Ipoh", "Kuching", "Melaka", "Seremban"],
    "Indonesia": ["Jakarta", "Bandung", "Surabaya", "Medan", "Bali", "Semarang", "Makassar", "Palembang", "Yogyakarta", "Denpasar"],
    "Philippines": ["Manila", "Cebu City", "Davao City", "Quezon City", "Baguio", "Cagayan de Oro", "Iloilo City", "Zamboanga City", "General Santos", "Bacolod"],
    "Japan": ["Tokyo", "Osaka", "Kyoto", "Yokohama", "Nagoya", "Sapporo", "Fukuoka", "Kobe", "Sendai", "Hiroshima"],
    "South Korea": ["Seoul", "Busan", "Incheon", "Daegu", "Daejeon", "Gwangju", "Jeju", "Ulsan", "Suwon", "Seongnam"],
    "China": ["Beijing", "Shanghai", "Guangzhou", "Shenzhen", "Hangzhou", "Chengdu", "Xi'an", "Nanjing", "Wuhan", "Dongguan"],
    "Taiwan": ["Taipei", "Kaohsiung", "Taichung", "Tainan", "Hsinchu", "Taoyuan", "Keelung", "Chiayi", "Taitung", "Hualien"],
    "Hong Kong": ["Hong Kong"],
    "Mongolia": ["Ulaanbaatar", "Darkhan", "Erdenet", "Choibalsan", "Moron", "Bayankhongor", "Khovd", "Ulaangom", "Sukhbaatar", "Dalanzadgad"],
    "Myanmar": ["Yangon", "Mandalay", "Naypyidaw", "Bago", "Mawlamyine", "Pathein", "Taunggyi", "Meiktila", "Sagaing", "Kalay"],
    "Laos": ["Vientiane", "Savannakhet", "Paksan", "Luang Prabang", "Pakse", "Thakhek", "Khammouane", "Champasak", "Xieng Khouang", "Vang Vieng"],
    "Cambodia": ["Phnom Penh", "Siem Reap", "Battambang", "Sihanoukville", "Kampong Cham", "Poipet", "Kampot", "Takeo", "Bavet", "Pursat"],
    "Brunei": ["Bandar Seri Begawan", "Kuala Belait", "Seria", "Tutong", "Bangar"],
    "Macao": ["Macau"],
}


def _normalize_city_name(value):
    return (value or "").strip()


def _merge_country_city_map(raw_map):
    merged = {}
    for country_name, city_names in raw_map.items():
        normalized_country = (country_name or "").strip()
        if not normalized_country:
            continue

        city_list = merged.setdefault(normalized_country, [])
        seen_cities = {(_normalize_city_name(city) or "").lower() for city in city_list}

        for city_name in city_names or []:
            normalized_city = _normalize_city_name(city_name)
            if not normalized_city:
                continue
            if normalized_city.lower() in seen_cities:
                continue
            city_list.append(normalized_city)
            seen_cities.add(normalized_city.lower())

    return merged


_COUNTRY_ISO2_ALIASES = {
    "Turkey": "TR",
    "Russia": "RU",
    "Ivory Coast": "CI",
    "Brunei": "BN",
}


def _lookup_iso2(country_name):
    """Best-effort ISO-3166 alpha-2 lookup for a country name."""
    country_name = (country_name or "").strip()
    if not country_name or not pycountry:
        return ""
    for candidate in (country_name, _normalize_country_name(country_name)):
        try:
            return pycountry.countries.lookup(candidate).alpha_2
        except LookupError:
            continue
    return _COUNTRY_ISO2_ALIASES.get(country_name, "")


def _get_or_create_country(country_name, iso2="", rename=False):
    """Resolve a country by ISO code first, then by name.

    The world-cities CSV, the curated city map and pycountry all use slightly
    different country names.  Keying on ``iso2`` keeps them from producing
    duplicate rows such as "Pakistan" and "Islamic Republic of Pakistan".
    """
    country_name = (country_name or "").strip()
    iso2 = (iso2 or "").strip().upper()[:2]

    if iso2:
        country = Country.objects.filter(iso2=iso2).order_by("id").first()
        if country:
            if (
                rename
                and country.name != country_name
                and not Country.objects.filter(name__iexact=country_name).exclude(pk=country.pk).exists()
            ):
                country.name = country_name
                country.save(update_fields=["name"])
            return country

    country = Country.objects.filter(name__iexact=country_name).first()
    if country:
        if iso2 and country.iso2 != iso2:
            country.iso2 = iso2
            country.save(update_fields=["iso2"])
        return country

    return Country.objects.create(name=country_name, iso2=iso2)


def _normalize_country_name(value):
    country = (value or "").strip()
    if not country:
        return ""
    country = country.replace("\u00a0", " ")
    aliases = {
        "Korea, South": "South Korea",
        "Republic of Korea": "South Korea",
        "United States of America": "United States",
        "USA": "United States",
        "U.S.A.": "United States",
        "UAE": "United Arab Emirates",
        "The Bahamas": "Bahamas",
        "Czechia": "Czech Republic",
        "Russia": "Russian Federation",
        "The Gambia": "Gambia",
        "Bosnia And Herzegovina": "Bosnia and Herzegovina",
        "Congo (Kinshasa)": "Democratic Republic of the Congo",
        "Congo (Brazzaville)": "Republic of the Congo",
        "North Macedonia": "Macedonia",
        "Macedonia": "Macedonia",
        "Eswatini": "Swaziland",
        "Timor-Leste": "East Timor",
    }
    return aliases.get(country, country)


def _read_worldcities_csv(csv_path):
    if not csv_path or not csv_path.exists():
        return []

    rows = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            country_name = _normalize_country_name((row.get("country") or "").strip())
            city_name = (row.get("city") or "").strip()
            iso2 = (row.get("iso2") or "").strip()
            if not country_name or not city_name:
                continue
            rows.append({"country": country_name, "city": city_name, "iso2": iso2})
    return rows


def _strip_html_tags(value):
    text = re.sub(r"<[^>]+>", " ", value or "")
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _read_niche_hierarchy(html_path):
    if not html_path or not html_path.exists():
        return []

    content = html_path.read_text(encoding="utf-8-sig", errors="ignore")
    topics = []
    for match in re.finditer(
        r"<h3[^>]*class=\"wp-block-heading\"[^>]*>(.*?)</h3>(.*?)(?=<h3[^>]*class=\"wp-block-heading\"|$)",
        content,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        title = _strip_html_tags(match.group(1))
        if not title:
            continue
        body = match.group(2)
        item_matches = re.findall(r"<li[^>]*>(.*?)</li>", body, flags=re.IGNORECASE | re.DOTALL)
        items = []
        for item in item_matches:
            clean = _strip_html_tags(item)
            if clean:
                items.append(clean)
        if not items:
            continue
        topics.append({"title": title, "items": items})
    return topics


class Command(BaseCommand):
    help = "Seed countries, cities, niches (main, sub and micro), and outreach methods."

    def add_arguments(self, parser):
        parser.add_argument("--skip-locations", action="store_true", help="Skip countries and cities.")
        parser.add_argument("--skip-niches", action="store_true", help="Skip niches and outreach methods.")

    def handle(self, *args, **options):
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        data_folder = project_root / "data"
        legacy_data_folder = project_root / "date"
        csv_candidates = [
            Path(os.environ.get("WORLD_CITIES_CSV", "")) if os.environ.get("WORLD_CITIES_CSV") else None,
            data_folder / "worldcities.csv",
            legacy_data_folder / "worldcities.csv",
            Path.home() / "Downloads" / "worldcities.csv",
        ]
        html_candidates = [
            data_folder / "nichess.html",
            legacy_data_folder / "nichess.html",
            project_root / "date" / "nichess.html",
        ]

        csv_path = next((p for p in csv_candidates if p and p.exists()), None)
        niche_html_path = next((p for p in html_candidates if p.exists()), None)

        if not options["skip_locations"]:
            self._seed_locations(csv_path)

        if not options["skip_niches"]:
            self._seed_niches(niche_html_path)

        main_count = Niche.objects.filter(parent__isnull=True).count()
        sub_count = Niche.objects.filter(parent__isnull=False, parent__parent__isnull=True).count()
        micro_count = Niche.objects.filter(parent__parent__isnull=False).count()
        self.stdout.write(self.style.SUCCESS(
            f"Seeded {Country.objects.count()} countries, {City.objects.count()} cities, "
            f"{Niche.objects.count()} niches ({main_count} main, {sub_count} sub, {micro_count} micro) "
            f"and {OutreachMethod.objects.count()} methods."
        ))

    def _seed_locations(self, csv_path):
        csv_rows = _read_worldcities_csv(csv_path) if csv_path else []

        if csv_rows:
            country_map = {}
            for row in csv_rows:
                country_name = _normalize_country_name(row["country"])
                if not country_name:
                    continue
                country = country_map.setdefault(country_name, {"iso2": row["iso2"] or "", "cities": set()})
                city_name = _normalize_city_name(row["city"])
                if city_name:
                    country["cities"].add(city_name)

            for country_name, payload in country_map.items():
                country = _get_or_create_country(country_name, payload["iso2"], rename=True)
                existing = set(City.objects.filter(country=country).values_list("name", flat=True))
                new_cities = [
                    City(country=country, name=city_name[:120])
                    for city_name in sorted(payload["cities"])
                    if city_name and city_name not in existing
                ]
                if new_cities:
                    City.objects.bulk_create(new_cities, batch_size=1000, ignore_conflicts=True)

        if pycountry:
            for item in pycountry.countries:
                if Country.objects.filter(iso2=item.alpha_2).exists():
                    continue
                existing = Country.objects.filter(name__iexact=item.name).first()
                if existing:
                    if not existing.iso2:
                        existing.iso2 = item.alpha_2
                        existing.save(update_fields=["iso2"])
                    continue
                Country.objects.create(name=item.name, iso2=item.alpha_2)

        country_city_map = _merge_country_city_map(COUNTRY_CITY_MAP)
        for country_name, city_names in country_city_map.items():
            country = _get_or_create_country(country_name, _lookup_iso2(country_name), rename=True)
            existing = set(City.objects.filter(country=country).values_list("name", flat=True))
            seen_cities = set()
            new_cities = []
            for city_name in city_names:
                normalized = _normalize_city_name(city_name)
                key = normalized.casefold()
                if not normalized or key in seen_cities or normalized in existing:
                    continue
                seen_cities.add(key)
                new_cities.append(City(country=country, name=normalized[:120]))
            if new_cities:
                City.objects.bulk_create(new_cities, batch_size=500, ignore_conflicts=True)

    def _seed_niches(self, niche_html_path):
        topics = _read_niche_hierarchy(niche_html_path) if niche_html_path else []

        # Keep every scraped topic AND every curated business niche, so the
        # explorer lists the full universe of niches rather than one source.
        merged = {}
        for topic in topics:
            key = (topic.get("title") or "").strip().casefold()
            if key:
                merged[key] = topic
        for name in NICHE_NAMES:
            key = name.strip().casefold()
            if key and key not in merged:
                merged[key] = {"title": name, "items": []}
        topics = list(merged.values())

        # Level 1 + level 2 from the scraped niche list.
        for topic in topics:
            parent, _ = Niche.objects.get_or_create(
                parent=None,
                name=topic["title"],
                defaults={"slug": slugify(topic["title"])},
            )
            existing = set(parent.children.values_list("name", flat=True))
            seen = {name.casefold() for name in existing}
            new_children = []
            for item in topic["items"]:
                name = (item or "").strip()
                if not name:
                    continue
                key = name.casefold()
                if key in seen:
                    continue
                seen.add(key)
                new_children.append(Niche(parent=parent, name=name[:180], slug=slugify(name)[:220]))
            if new_children:
                Niche.objects.bulk_create(new_children, batch_size=500, ignore_conflicts=True)

        # Level 2 for main niches that have no sub-niches yet.
        mains = list(Niche.objects.filter(parent__isnull=True))
        have_children = set(
            Niche.objects.filter(parent_id__in=[main.id for main in mains]).values_list("parent_id", flat=True)
        )
        new_subs = []
        for main in mains:
            if main.id in have_children:
                continue
            for sub_name in generate_sub_niches(main.name):
                new_subs.append(Niche(parent=main, name=sub_name[:180], slug=slugify(sub_name)[:220]))
        if new_subs:
            Niche.objects.bulk_create(new_subs, batch_size=500, ignore_conflicts=True)

        # Level 3 (micro-niches) for every sub-niche that has no children yet.
        level_two = list(
            Niche.objects.filter(parent__isnull=False, parent__parent__isnull=True).values_list("id", "name")
        )
        filled = set(
            Niche.objects.filter(parent_id__in=[sub_id for sub_id, _ in level_two]).values_list("parent_id", flat=True)
        )
        new_micros = []
        for sub_id, sub_name in level_two:
            if sub_id in filled:
                continue
            for micro_name in generate_micro_niches(sub_name):
                new_micros.append(Niche(parent_id=sub_id, name=micro_name[:180], slug=slugify(micro_name)[:220]))
        if new_micros:
            Niche.objects.bulk_create(new_micros, batch_size=1000, ignore_conflicts=True)

        for name in METHOD_NAMES:
            OutreachMethod.objects.get_or_create(name=name)
