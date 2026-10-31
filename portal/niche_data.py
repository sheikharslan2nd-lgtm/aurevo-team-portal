"""Niche hierarchy data and deterministic generators.

The dashboard exposes a four step drill-down:

    country -> city -> main niche -> sub-niche -> micro-niche

The scraped ``nichess.html`` file only contains two levels (category -> niche),
so sub-niches for business categories and the third (micro-niche) level are
generated here in a deterministic, idempotent way.  Everything is plain data so
it can be edited/curated later without touching the seeding logic.
"""

import hashlib
import re

# ---------------------------------------------------------------------------
# Curated sub-niches for the business categories that the team targets most.
# Any category not listed here falls back to the generated templates below.
# ---------------------------------------------------------------------------
CURATED_SUB_NICHES = {
    "Restaurants & Cafes": [
        "Fine Dining Restaurants", "Fast Casual Restaurants", "Coffee Shops",
        "Bakeries & Cafes", "Food Trucks", "Pizza Restaurants",
        "Family Restaurants", "Catering & Banquets",
    ],
    "Real Estate": [
        "Residential Real Estate", "Commercial Real Estate", "Real Estate Agents",
        "Property Listings", "Rental & Letting", "Luxury Real Estate",
        "Real Estate Investors", "Relocation Services",
    ],
    "Dental Clinics": [
        "General Dentistry", "Cosmetic Dentistry", "Orthodontics",
        "Pediatric Dentistry", "Dental Implants", "Emergency Dentistry",
        "Teeth Whitening", "Oral Surgery",
    ],
    "Medical Clinics": [
        "Family Medicine", "Urgent Care Clinics", "Women's Health Clinics",
        "Skin Clinics", "Physiotherapy Clinics", "Cardiology Clinics",
        "Diagnostic Labs", "Vaccination Clinics",
    ],
    "Law Firms": [
        "Corporate Law", "Family Law", "Immigration Law", "Criminal Defense",
        "Real Estate Law", "Employment Law", "Intellectual Property Law",
        "Personal Injury Law",
    ],
    "Accounting Firms": [
        "Bookkeeping Services", "Tax Preparation", "Payroll Services",
        "Audit & Assurance", "Virtual CFO Services", "Financial Reporting",
        "Tax Consulting", "Payroll & Compliance",
    ],
    "Marketing Agencies": [
        "SEO Agencies", "PPC & Paid Media", "Social Media Agencies",
        "Content Marketing", "Email Marketing", "Brand Strategy",
        "Influencer Marketing", "Marketing Automation",
    ],
    "Digital Agencies": [
        "Web Design Agencies", "Digital Marketing Agencies",
        "Social Media Agencies", "App Development Agencies",
        "Branding Agencies", "CRO Agencies", "Video Production Agencies",
        "Full-Funnel Agencies",
    ],
    "Agencies": [
        "Creative Agencies", "Advertising Agencies", "PR Agencies",
        "Media Buying Agencies", "Talent Agencies", "Growth Agencies",
        "Web Design Agencies", "Full-Service Agencies",
    ],
    "Construction Companies": [
        "Residential Construction", "Commercial Construction", "Civil Contractors",
        "Renovation Contractors", "Interior Fit-Out", "Infrastructure Contractors",
        "General Contractors", "Turnkey Contractors",
    ],
    "Plumbers": [
        "Residential Plumbing", "Commercial Plumbing", "Emergency Plumbers",
        "Drain Cleaning", "Pipe Repair", "Water Heater Services",
        "Bathroom Plumbing", "Kitchen Plumbing",
    ],
    "Electricians": [
        "Residential Electricians", "Commercial Electricians",
        "Emergency Electricians", "Wiring & Rewiring", "Panel Upgrades",
        "EV Charger Installation", "Lighting Installation",
        "Generator Installation",
    ],
    "Roofing Contractors": [
        "Residential Roofing", "Commercial Roofing", "Roof Repair",
        "Roof Replacement", "Metal Roofing", "Tile Roofing",
        "Roof Inspection", "Gutter Services",
    ],
    "Landscaping Services": [
        "Lawn Care Services", "Garden Design", "Irrigation Services",
        "Tree Care & Trimming", "Hardscaping", "Landscaping Maintenance",
        "Outdoor Lighting", "Pest & Weed Control",
    ],
    "Cleaning Services": [
        "Residential Cleaning", "Commercial Cleaning", "Move-In/Move-Out Cleaning",
        "Deep Cleaning", "Carpet Cleaning", "Window Cleaning",
        "Post-Construction Cleaning", "Janitorial Services",
    ],
    "Commercial Cleaning": [
        "Office Cleaning", "Retail Cleaning", "Industrial Cleaning",
        "Hospital Cleaning", "School Cleaning", "Warehouse Cleaning",
        "Facade Cleaning", "Disinfection Services",
    ],
    "Auto Repair Shops": [
        "General Auto Repair", "Transmission Repair", "Brake Services",
        "Auto Electrical Services", "Denting & Painting", "Tire & Wheel Services",
        "Oil Change Services", "Diagnostic Services",
    ],
    "Car Dealerships": [
        "New Car Dealerships", "Used Car Dealerships", "Certified Pre-Owned",
        "Luxury Car Dealers", "Motorcycle Dealers", "Truck Dealers",
        "Auto Financing", "Fleet Sales",
    ],
    "Gyms & Fitness": [
        "Fitness Centers", "CrossFit Boxes", "Yoga Studios", "Personal Training",
        "Strength & Conditioning", "Martial Arts Gyms", "Women-Only Gyms",
        "24/7 Gyms",
    ],
    "Fitness Studios": [
        "Boutique Fitness Studios", "Pilates Studios", "Spin Studios",
        "Zumba Studios", "Boxing Studios", "Dance Fitness Studios",
        "Barre Studios", "HIIT Studios",
    ],
    "Beauty Salons": [
        "Hair Salons", "Nail Salons", "Barbershops", "Eyebrow & Threading Studios",
        "Makeup Studios", "Bridal Salons", "Unisex Salons", "Hair Loss Studios",
    ],
    "Spas": [
        "Day Spas", "Massage Spas", "Medical Spas", "Body Treatment Spas",
        "Ayurvedic Spas", "Couples Spas", "Foot Spas", "Wellness Spas",
    ],
    "Hotels": [
        "Luxury Hotels", "Boutique Hotels", "Budget Hotels", "Business Hotels",
        "Resort Hotels", "Serviced Apartments", "Hostels", "Hotel Booking Services",
    ],
    "Travel Agencies": [
        "Leisure Travel Agencies", "Corporate Travel", "Honeymoon Packages",
        "Umrah & Hajj Travel", "Adventure Travel", "Visa Consultancy",
        "Flight Booking", "Tour Operators",
    ],
    "Schools": [
        "Private Schools", "Primary Schools", "Secondary Schools",
        "International Schools", "Montessori Schools", "Special Needs Schools",
        "Home Schooling", "Online Schools",
    ],
    "Colleges & Universities": [
        "Engineering Colleges", "Medical Colleges", "Business Schools",
        "Law Schools", "Arts & Science Colleges", "Community Colleges",
        "Online Universities", "Technical Institutes",
    ],
    "Training Institutes": [
        "IT Training Institutes", "Vocational Training", "Skill Development Centers",
        "Corporate Training", "Certification Courses", "Language Training",
        "Job Placement Training", "Professional Courses",
    ],
    "E-commerce Stores": [
        "Fashion E-commerce", "Electronics E-commerce", "Beauty E-commerce",
        "Grocery Delivery", "Marketplaces", "D2C Brands", "Subscription Stores",
        "B2B E-commerce",
    ],
    "Retail Stores": [
        "Clothing Stores", "Supermarkets", "Convenience Stores", "Shoe Stores",
        "Sportswear Stores", "Toy Stores", "Gift Shops", "Electronics Retailers",
    ],
    "Manufacturing Companies": [
        "Textile Manufacturing", "Food Manufacturing", "Plastic Manufacturing",
        "Metal Manufacturing", "Pharmaceutical Manufacturing",
        "Packaging Manufacturing", "Electronics Manufacturing",
        "Chemical Manufacturing",
    ],
    "Logistics & Transport": [
        "Freight Forwarding", "Courier Services", "Last-Mile Delivery",
        "Cold Chain Logistics", "Moving Services", "Trucking Services",
        "Warehousing & Fulfillment", "Shipping Lines",
    ],
    "Recruitment Agencies": [
        "Permanent Staffing", "Temporary Staffing", "Executive Search",
        "IT Recruitment", "Healthcare Recruitment", "Overseas Recruitment",
        "RPO Services", "Campus Hiring",
    ],
    "IT Companies": [
        "Software Development", "Web Development", "Mobile App Development",
        "IT Support & Maintenance", "Managed IT Services", "Cybersecurity Firms",
        "DevOps Services", "QA & Testing",
    ],
    "Consulting Firms": [
        "Management Consulting", "Strategy Consulting", "Financial Consulting",
        "HR Consulting", "Operations Consulting", "Digital Transformation",
        "Startup Consulting", "Compliance Consulting",
    ],
    "Event Planners": [
        "Wedding Planners", "Corporate Event Planners", "Conference Organizers",
        "Exhibition Planners", "Birthday Party Planners", "Concert Organizers",
        "Event Rental Services", "Destination Weddings",
    ],
    "Photographers": [
        "Wedding Photographers", "Portrait Photographers", "Product Photographers",
        "Real Estate Photographers", "Event Photographers", "Newborn Photographers",
        "Commercial Photographers", "Drone Photography",
    ],
    "Catering Services": [
        "Wedding Catering", "Corporate Catering", "Buffet Catering",
        "Live Food Stalls", "Boxed Meal Catering", "Party Catering",
        "Religious Events Catering", "Concession Services",
    ],
    "Pet Services": [
        "Pet Grooming", "Veterinary Clinics", "Pet Boarding", "Dog Walking",
        "Pet Training", "Pet Sitting", "Pet Food Stores", "Pet Adoption",
    ],
    "Home Renovation": [
        "Kitchen Remodeling", "Bathroom Remodeling", "Basement Finishing",
        "Room Additions", "Flooring Contractors", "Painting Contractors",
        "Home Extensions", "Waterproofing",
    ],
    "Interior Design": [
        "Residential Interior Design", "Commercial Interior Design",
        "Office Interior Design", "Hospitality Interior Design",
        "Turnkey Interiors", "Modular Kitchens", "3D Visualization",
        "Space Planning",
    ],
    "Furniture Stores": [
        "Office Furniture", "Home Furniture", "Sofa & Couch Stores",
        "Bed & Mattress Stores", "Kitchen Furniture", "Outdoor Furniture",
        "Custom Furniture", "Second-Hand Furniture",
    ],
    "Pharmacies": [
        "Retail Pharmacies", "Online Pharmacies", "Compounding Pharmacies",
        "Hospital Pharmacies", "24/7 Pharmacies", "Medical Supply Stores",
        "Prescription Delivery", "Ayurvedic Pharmacies",
    ],
    "Insurance Agencies": [
        "Life Insurance", "Health Insurance", "Auto Insurance",
        "Property Insurance", "Business Insurance", "Travel Insurance",
        "Marine Insurance", "Crop Insurance",
    ],
    "Banking & Finance": [
        "Retail Banking", "Corporate Banking", "Investment Banking",
        "Wealth Management", "Microfinance", "Consumer Loans",
        "Mortgage Lending", "Financial Planning",
    ],
    "SaaS Companies": [
        "CRM Software", "HR Software", "Accounting Software",
        "Project Management Software", "E-commerce Software", "Cybersecurity SaaS",
        "Marketing Software", "Vertical SaaS",
    ],
    "Freelancers": [
        "Web Developers", "Graphic Designers", "Content Writers", "Video Editors",
        "Virtual Assistants", "UI/UX Designers", "Translators",
        "Marketing Consultants",
    ],
    "Startup Founders": [
        "SaaS Founders", "E-commerce Founders", "Fintech Startups",
        "Healthtech Startups", "Edtech Startups", "Marketplace Founders",
        "Solo Founders", "First-Time Founders",
    ],
    "Property Management": [
        "Residential Property Management", "Commercial Property Management",
        "Rental Management", "HOA Management", "Facility Management",
        "Vacation Rental Management", "Property Inspection", "Tenant Screening",
    ],
    "Property Developers": [
        "Residential Developers", "Commercial Developers", "Industrial Developers",
        "Mixed-Use Developers", "Land Developers", "Luxury Developers",
        "Affordable Housing Developers", "Hospitality Developers",
    ],
    "Wedding Services": [
        "Bridal Wear", "Wedding Venues", "Wedding Decorators",
        "Wedding Videographers", "Wedding Musicians", "Henna Artists",
        "Wedding Cakes", "Wedding Invitations",
    ],
    "Coaching Centers": [
        "Academic Coaching", "Test Prep Coaching", "Competitive Exam Coaching",
        "Career Coaching", "Online Coaching Centers", "Tutoring Centers",
        "Sports Coaching", "Music Coaching",
    ],
    "Language Schools": [
        "English Language Schools", "IELTS & TOEFL", "Arabic Language",
        "French Language", "German Language", "Corporate Language Training",
        "Online Language Courses", "Kids Language Schools",
    ],
    "Business Consultants": [
        "Startup Consultants", "SME Consultants", "HR Consultants",
        "Finance Consultants", "Operations Consultants", "Sales Consultants",
        "International Business Consultants", "Legal Consultants",
    ],
    "Architecture Firms": [
        "Residential Architecture", "Commercial Architecture", "Urban Planning",
        "Landscape Architecture", "Interior Architecture", "Sustainable Architecture",
        "3D Visualization", "MEP Consultants",
    ],
    "HVAC Services": [
        "AC Installation", "AC Repair", "Heating Services", "Ventilation Services",
        "Duct Cleaning", "Chiller Services", "HVAC Maintenance", "Commercial HVAC",
    ],
    "Security Companies": [
        "Manned Guarding", "CCTV Installation", "Alarm Systems", "Access Control",
        "Executive Protection", "Event Security", "Cybersecurity Services",
        "Security Consulting",
    ],
    "Packaging Companies": [
        "Flexible Packaging", "Corrugated Packaging", "Food Packaging",
        "Retail Packaging", "Label Printing", "Sustainable Packaging",
        "Custom Packaging", "Industrial Packaging",
    ],
    "Laundry Services": [
        "Wash & Fold", "Dry Cleaning", "Commercial Laundry", "Ironing Services",
        "Laundry Pickup & Delivery", "Wedding Dress Cleaning",
        "Shoe & Leather Care", "Self-Service Laundromats",
    ],
    "Appliance Repair": [
        "AC Repair Services", "Refrigerator Repair", "Washing Machine Repair",
        "Microwave Repair", "Water Purifier Repair", "TV Repair",
        "Small Appliance Repair", "Same-Day Appliance Repair",
    ],
    "Solar Energy Companies": [
        "Solar Panel Installation", "Solar Maintenance", "Solar Consulting",
        "Off-Grid Solar", "Commercial Solar", "Solar Water Heaters",
        "Battery Storage", "Solar Financing",
    ],
    "Automotive Services": [
        "Car Wash & Detailing", "Towing Services", "Roadside Assistance",
        "Tire Services", "Auto Glass Repair", "Vehicle Inspection",
        "Used Car Valuation", "Fleet Services",
    ],
    "Home Services": [
        "Handyman Services", "Home Cleaning", "Pest Control", "Plumbing Services",
        "Electrical Services", "Appliance Repair", "Home Security",
        "Garage Door Services",
    ],
    "Legal Services": [
        "Contract Drafting", "Legal Consulting", "Notary Services",
        "Litigation Support", "Compliance Services", "Trademark Registration",
        "Debt Recovery", "Legal Documentation",
    ],
    "Tax Consultants": [
        "Personal Tax Filing", "Business Tax Filing", "Tax Planning",
        "GST & VAT Consulting", "Tax Audit Support", "International Taxation",
        "Payroll Tax", "Tax Dispute Resolution",
    ],
    "Hospitality Businesses": [
        "Hotels", "Resorts", "Guest Houses", "Restaurants", "Cafes",
        "Banquet Halls", "Event Venues", "Vacation Rentals",
    ],
    "Cinemas": [
        "Multiplex Cinemas", "Single-Screen Cinemas", "Drive-In Cinemas",
        "Boutique Cinemas", "Open-Air Cinemas", "IMAX Theatres",
        "Cinema Equipment", "Movie Ticketing",
    ],
    "Health Clubs": [
        "Gyms", "Fitness Studios", "Swimming Clubs", "Yoga Centers",
        "Wellness Clubs", "Sports Academies", "Spa & Wellness", "Nutrition Clubs",
    ],
    "Bakery Shops": [
        "Artisan Bakeries", "Cake Shops", "Cupcake Stores", "Patisseries",
        "Bread Bakeries", "Gluten-Free Bakeries", "Wedding Cake Studios",
        "Bakery Supplies",
    ],
    "Coffee Shops": [
        "Specialty Coffee Shops", "Drive-Thru Coffee", "Coffee Roasters",
        "Cafe Chains", "Mobile Coffee Carts", "Coffee Equipment",
        "Coffee Subscription", "Barista Training",
    ],
    "Grocery Stores": [
        "Supermarkets", "Convenience Stores", "Organic Grocery Stores",
        "Online Grocery Delivery", "Specialty Food Stores", "Farmers Markets",
        "Wholesale Grocers", "Ethnic Grocery Stores",
    ],
    "Mobile Stores": [
        "Mobile Phone Shops", "Mobile Accessories", "Mobile Repair Services",
        "Refurbished Phones", "Mobile Wholesale", "Phone Insurance",
        "SIM & Plans", "Mobile Trade-In",
    ],
    "Electronics Stores": [
        "Consumer Electronics", "Computer Stores", "Home Appliance Stores",
        "Audio & Video Stores", "Gaming Stores", "Electronics Repair",
        "Electronics Wholesale", "Smart Home Devices",
    ],
    "Fashion Brands": [
        "Streetwear Brands", "Activewear Brands", "Formalwear Brands",
        "Kidswear Brands", "Lingerie Brands", "Ethnic Wear Brands",
        "Denim Brands", "Sustainable Fashion",
    ],
    "Franchises": [
        "Food Franchises", "Retail Franchises", "Service Franchises",
        "Fitness Franchises", "Education Franchises", "Cleaning Franchises",
        "Automotive Franchises", "Home-Based Franchises",
    ],
    "Hostels": [
        "Student Hostels", "Backpacker Hostels", "Working Women Hostels",
        "Budget Hotels & Hostels", "Hostel Management", "Co-Living Spaces",
        "Paying Guest Services", "Hostel Booking Platforms",
    ],
    "Logistics Companies": [
        "Freight Forwarders", "Courier Companies", "3PL Providers",
        "Last-Mile Delivery", "Cold Chain Logistics", "Warehousing Companies",
        "Container Shipping", "Customs Brokers",
    ],
    "Transportation Companies": [
        "Bus Operators", "Taxi & Ride-Hailing", "School Transport",
        "Corporate Transport", "Trucking Companies", "Car Rental",
        "Chauffeur Services", "Airport Transfers",
    ],
    "Fleet Management": [
        "Fleet Leasing", "Fleet Telematics", "Fleet Maintenance",
        "Fuel Management", "Driver Management", "Fleet Insurance",
        "GPS Tracking", "Fleet Consulting",
    ],
    "Airlines": [
        "Commercial Airlines", "Low-Cost Carriers", "Private Jets",
        "Charter Flights", "Cargo Airlines", "Regional Airlines",
        "Airline Catering", "Aviation Training",
    ],
    "Air Cargo": [
        "Freight Airlines", "Air Freight Forwarding", "Express Air Cargo",
        "Charter Cargo", "Cold Chain Air Cargo", "Dangerous Goods Handling",
        "Air Cargo Warehousing", "Customs Clearance",
    ],
    "Prototyping Firms": [
        "3D Printing Services", "CNC Machining", "Rapid Prototyping",
        "Product Design", "Injection Molding", "Model Making",
        "Sheet Metal Prototyping", "Engineering Prototyping",
    ],
    "Podcast Studios": [
        "Podcast Recording", "Podcast Editing", "Podcast Production",
        "Live Streaming Studios", "Voiceover Studios", "Audiobook Recording",
        "Music Recording Studios", "Video Podcast Studios",
    ],
    "Business Coaches": [
        "Executive Coaching", "Leadership Coaching", "Startup Coaching",
        "Sales Coaching", "Life Coaching", "Career Coaching",
        "Confidence Coaching", "Online Business Coaching",
    ],
    "Vehicle Leasing": [
        "Car Leasing", "Commercial Vehicle Leasing", "Equipment Leasing",
        "Long-Term Rental", "Lease-to-Own", "Fleet Leasing", "Truck Leasing",
        "Bike Leasing",
    ],
    "Warehousing": [
        "Cold Storage", "Fulfillment Centers", "Bonded Warehousing",
        "Distribution Centers", "Self-Storage", "Inventory Management",
        "3PL Warehousing", "Hazardous Storage",
    ],
    "Industrial Suppliers": [
        "Safety Equipment", "Electrical Supplies", "Hydraulic Supplies",
        "Industrial Tools", "Bearings & Belts", "Chemical Supplies",
        "MRO Supplies", "Packaging Supplies",
    ],
    "Import & Export Businesses": [
        "General Trading", "Import Agents", "Export Agents", "Customs Clearing",
        "Freight Forwarding", "Commodity Trading", "Sourcing Agents",
        "Trade Consulting",
    ],
    "B2B Service Providers": [
        "Lead Generation", "Outsourced Sales", "Managed Services",
        "Staffing Providers", "Payment Providers", "Fulfillment Providers",
        "Data Providers", "Channel Partners",
    ],
    "Private Clinics": [
        "General Practice Clinics", "Specialist Clinics", "Multi-Specialty Clinics",
        "Home Visit Clinics", "Executive Health Checkups", "Telemedicine Clinics",
        "Wellness Clinics", "Polyclinics",
    ],
    "Dental Labs": [
        "Dental Crowns", "Dentures", "Dental Implants Lab",
        "Orthodontic Appliances", "Retainers", "Night Guards",
        "Dental Prosthetics", "Lab Supplies",
    ],
    "Orthopedic Clinics": [
        "Joint Replacement", "Sports Injury Clinics", "Spine Clinics",
        "Fracture Care", "Arthroscopy", "Physiotherapy", "Pain Management",
        "Prosthetics & Orthotics",
    ],
    "Daycare Centers": [
        "Infant Care", "Toddler Programs", "Preschool Programs",
        "After-School Care", "Creche Services", "Early Learning Centers",
        "Montessori Daycare", "Part-Time Daycare",
    ],
    "Senior Care Homes": [
        "Assisted Living", "Nursing Homes", "Independent Living", "Memory Care",
        "Home Care Services", "Respite Care", "Retirement Communities",
        "Palliative Care",
    ],
    "Veterinary Clinics": [
        "Small Animal Clinics", "Large Animal Clinics", "Pet Vaccination",
        "Animal Surgery", "Pet Dentistry", "Exotic Pet Care",
        "Veterinary Emergency", "Mobile Vet Clinics",
    ],
    "Farm Equipment": [
        "Tractors", "Harvesting Equipment", "Irrigation Equipment",
        "Tillage Equipment", "Farm Machinery Rental", "Seeding Equipment",
        "Spraying Equipment", "Equipment Repair",
    ],
    "Agriculture Businesses": [
        "Crop Farming", "Dairy Farming", "Poultry Farming", "Aquaculture",
        "Organic Farming", "Horticulture", "Agro-Processing", "Agri-Export",
    ],
    "Food Processing": [
        "Beverage Processing", "Dairy Processing", "Meat Processing",
        "Grain Milling", "Bakery Manufacturing", "Frozen Foods",
        "Snack Foods", "Food Packaging",
    ],
    "Cold Storage": [
        "Cold Storage Warehouses", "Reefer Transport", "Blast Freezing",
        "Chilled Storage", "Cold Room Installation", "Ice Plants",
        "Cold Chain Consulting", "Agri Cold Storage",
    ],
    "Waste Management": [
        "Recycling Services", "Hazardous Waste", "E-Waste Management",
        "Waste Collection", "Landfill Services", "Composting",
        "Waste Consultancy", "Skip Hire",
    ],
    "Construction Materials": [
        "Cement & Concrete", "Steel & Rebar", "Aggregates", "Bricks & Blocks",
        "Insulation Materials", "Waterproofing Chemicals", "Tiles & Marble",
        "Scaffolding",
    ],
    "Apparel Brands": [
        "Streetwear Brands", "Activewear Brands", "Formalwear Brands",
        "Kidswear Brands", "Lingerie Brands", "Ethnic Wear Brands",
        "Denim Brands", "Sustainable Apparel",
    ],
    "Textile Businesses": [
        "Fabric Manufacturing", "Yarn Spinning", "Textile Printing",
        "Knitting Units", "Home Textiles", "Technical Textiles",
        "Textile Trading", "Dyeing & Finishing",
    ],
    "Metal Fabrication": [
        "Sheet Metal Fabrication", "CNC Cutting", "Welding Services",
        "Precision Machining", "Steel Structures", "Metal Casting",
        "Surface Treatment", "Custom Fabrication",
    ],
    "Printing Presses": [
        "Offset Printing", "Digital Printing", "Screen Printing",
        "Flexo Printing", "Large Format Printing", "Book Printing",
        "Packaging Printing", "Print Finishing",
    ],
    "Signage Companies": [
        "Shop Signs", "LED Displays", "Vehicle Graphics", "Wayfinding Signage",
        "Neon Signs", "Digital Signage", "Banner Printing", "Sign Maintenance",
    ],
    "Interior Contractors": [
        "Office Fit-Out", "Retail Fit-Out", "Turnkey Interiors",
        "Partition & Ceilings", "Flooring Contractors", "Painting Contractors",
        "MEP Contractors", "Shop Fitting",
    ],
    "Glass & Aluminum": [
        "Glass Partitions", "Aluminum Windows", "Curtain Walls",
        "Glass Railings", "Shower Enclosures", "Shopfronts", "Glass Repair",
        "Skylights",
    ],
    "Swimming Pool Services": [
        "Pool Construction", "Pool Cleaning", "Pool Maintenance", "Pool Repair",
        "Pool Landscaping", "Pool Equipment", "Spa Services", "Pool Safety Covers",
    ],
    "Water Treatment Companies": [
        "RO Plants", "Sewage Treatment", "Water Testing", "Water Softening",
        "Industrial ETP", "Pool Water Treatment", "Bottled Water Plants",
        "Water Tank Cleaning",
    ],
    "Moving & Relocation": [
        "Local Moving", "International Relocation", "Office Moving",
        "Packing Services", "Vehicle Moving", "Storage Services",
        "Corporate Relocation", "Student Moving",
    ],
    "Pest Control Services": [
        "Termite Control", "Rodent Control", "Cockroach Control",
        "Bed Bug Treatment", "Mosquito Control", "Bird Control", "Fumigation",
        "Wildlife Removal",
    ],
    "Security Guard Services": [
        "Residential Security", "Commercial Security", "Event Security",
        "Industrial Security", "VIP Protection", "Traffic Marshals",
        "Night Patrol", "Security Audits",
    ],
    "Parking Management": [
        "Valet Parking", "Car Park Operations", "Parking Guidance Systems",
        "Tower Parking", "EV Charging Parking", "Parking Consulting",
        "Tow-away Services", "Season Parking",
    ],
    "Corporate Training": [
        "Leadership Training", "Soft Skills Training", "Sales Training",
        "Technical Training", "Compliance Training", "Team Building",
        "Corporate Workshops", "Training Consulting",
    ],
    "Call Centers": [
        "Inbound Support", "Outbound Sales", "BPO Services", "Telemarketing",
        "Customer Service", "Collections Calls", "Multilingual Support",
        "Virtual Call Centers",
    ],
    "IT Support Companies": [
        "Helpdesk Services", "On-Site Support", "Network Support",
        "Remote Support", "IT Asset Management", "Backup & Recovery",
        "Server Maintenance", "IT Consultancy",
    ],
    "Cloud Service Providers": [
        "IaaS Providers", "PaaS Providers", "SaaS Hosting", "Cloud Migration",
        "Cloud Security", "CDN Providers", "Cloud Backup", "Hybrid Cloud",
    ],
    "CRM Consultants": [
        "Salesforce Consultants", "HubSpot Consultants", "Zoho Consultants",
        "CRM Implementation", "CRM Migration", "CRM Training",
        "CRM Integration", "CRM Optimization",
    ],
    "ERP Companies": [
        "ERP Implementation", "SAP Partners", "Odoo Partners", "Custom ERP",
        "ERP Migration", "ERP Support", "Industry ERP Solutions", "Cloud ERP",
    ],
    "Automation Agencies": [
        "Marketing Automation", "RPA Services", "Workflow Automation",
        "Home Automation", "Industrial Automation", "Sales Automation",
        "HR Automation", "Automation Consulting",
    ],
    "Outsourcing Firms": [
        "BPO Firms", "KPO Firms", "Finance Outsourcing", "HR Outsourcing",
        "IT Outsourcing", "Customer Support Outsourcing", "Payroll Outsourcing",
        "Legal Process Outsourcing",
    ],
    "Research Firms": [
        "Market Research", "Consumer Research", "Industry Reports",
        "Custom Research", "Competitor Research", "Brand Research",
        "Social Research", "Survey Services",
    ],
    "Community Centers": [
        "Event Halls", "Co-working Centers", "Youth Centers", "Senior Centers",
        "Cultural Centers", "Sports Facilities", "Meeting Rooms", "Art Galleries",
    ],
    "Sports Clubs": [
        "Cricket Clubs", "Football Clubs", "Tennis Clubs", "Golf Clubs",
        "Swimming Clubs", "Athletics Clubs", "Cycling Clubs", "Esports Clubs",
    ],
    "Driving Schools": [
        "Beginner Driving Lessons", "Defensive Driving",
        "Commercial Driving Licenses", "Teen Driver Training",
        "Motorcycle Training", "Refresher Courses", "Driving Test Prep",
        "Corporate Driver Training",
    ],
    "Funeral Homes": [
        "Funeral Planning", "Cremation Services", "Burial Services",
        "Memorial Services", "Funeral Transport", "Gravestones & Markers",
        "Grief Support", "Funeral Insurance",
    ],
    "Luxury Goods Stores": [
        "Designer Fashion", "Luxury Watches", "Luxury Jewelry", "Designer Bags",
        "Premium Footwear", "Luxury Cars", "Art & Collectibles",
        "Luxury Accessories",
    ],
    "Jewelry Stores": [
        "Gold Jewelry", "Diamond Jewelry", "Wedding Jewelry", "Fashion Jewelry",
        "Silver Jewelry", "Gemstone Jewelry", "Jewelry Repair",
        "Custom Jewelry Design",
    ],
    "Mobile App Agencies": [
        "iOS Development", "Android Development", "Cross-Platform Apps",
        "App UI/UX", "App Maintenance", "App Marketing", "Flutter Development",
        "React Native Development",
    ],
    "Data Analytics Firms": [
        "Business Intelligence", "Data Engineering", "Predictive Analytics",
        "Dashboard & Reporting", "Data Visualization", "Big Data Services",
        "Analytics Consulting", "Data Governance",
    ],
    "Corporate Wellness": [
        "Employee Wellness Programs", "Stress Management", "Fitness Challenges",
        "Mental Health Support", "Nutrition Programs", "Health Screenings",
        "Wellness Workshops", "EAP Services",
    ],
    "Home Decor Stores": [
        "Wall Decor", "Rugs & Carpets", "Lighting Stores", "Curtains & Blinds",
        "Home Accessories", "Mirrors & Frames", "Decorative Plants",
        "Seasonal Decor",
    ],
    "Office Furniture": [
        "Desks & Workstations", "Office Chairs", "Conference Tables",
        "Storage & Filing", "Reception Furniture", "Ergonomic Furniture",
        "Office Fit-Out Furniture", "Furniture Rental",
    ],
    "Online Education": [
        "Online Courses", "E-learning Platforms", "Test Prep Online",
        "Skill Development", "Coding Bootcamps", "Language Learning Apps",
        "Corporate E-learning", "Tutoring Platforms",
    ],
    "Tutoring Centers": [
        "Math Tutoring", "Science Tutoring", "English Tutoring",
        "Test Prep Tutoring", "Online Tutoring", "Homework Help",
        "Special Needs Tutoring", "Group Tutoring",
    ],
    "Private Schools": [
        "Primary Private Schools", "Secondary Private Schools",
        "International Schools", "Montessori Schools", "Boarding Schools",
        "Special Needs Schools", "STEM Schools", "Faith-Based Schools",
    ],
}

# ---------------------------------------------------------------------------
# Generated fallbacks
# ---------------------------------------------------------------------------
_SUB_TEMPLATES_SERVICE = [
    "Commercial {n}", "Residential {n}", "Local {n}", "Mobile {n}",
    "Emergency {n}", "Premium {n}", "Affordable {n}", "24/7 {n}",
]
_SUB_TEMPLATES_CONTENT = [
    "{n} for Beginners", "{n} Courses", "{n} Tips", "{n} Guides",
    "{n} Communities", "{n} Books", "{n} Kits", "{n} Workshops",
]

_MICRO_TEMPLATES_BUSINESS = [
    "Best {n}", "Affordable {n}", "Premium {n}", "Local {n}",
    "{n} Near Me", "Top-Rated {n}", "{n} for Small Business", "{n} Reviews",
]
_MICRO_TEMPLATES_GENERIC = [
    "Best {n}", "Affordable {n}", "Premium {n}", "Local {n}",
    "{n} Near Me", "Top-Rated {n}", "{n} Reviews", "{n} Online",
]
_MICRO_TEMPLATES_PRODUCT = [
    "Best {n}", "Affordable {n}", "Premium {n}", "{n} Reviews", "{n} Online",
    "{n} Deals", "Top-Rated {n}", "{n} Near Me",
]
_MICRO_TEMPLATES_CONTENT = [
    "{n} for Beginners", "{n} Tips", "{n} Guide", "{n} Strategies",
    "{n} Ideas", "{n} Examples", "{n} Checklist", "{n} Course",
]

_SERVICE_WORDS = re.compile(
    r"\b(clinic|clinics|agency|agencies|firm|firms|company|companies|"
    r"contractor|contractors|service|services|consultant|consultants|"
    r"center|centers|centre|institute|institutes|academy|academies|"
    r"salon|salons|spa|spas|hotel|hotels|restaurant|restaurants|"
    r"store|stores|shop|shops|dealer|dealers|provider|providers|"
    r"supplier|suppliers|installer|installers|school|schools|college|"
    r"university|gym|gyms|studio|studios|photographer|photographers|"
    r"planner|planners|designer|designers|developer|developers|builder|"
    r"builders|manufacturer|manufacturers|distributor|distributors|"
    r"wholesaler|wholesalers|lawyer|lawyers|attorney|attorneys|dentist|"
    r"dentists|doctor|doctors|therapist|therapists|trainer|trainers|"
    r"coach|coaches|agent|agents|broker|brokers)\b",
    re.IGNORECASE,
)

_CONTENT_START = re.compile(
    r"^(how\s+to|learn(ing)?|make\s|making\s|start(ing)?\s|run(ning)?\s|"
    r"choose|choosing|buy\s|buying\s|sell(ing)?\s|find\s|finding\s|get\s|"
    r"getting\s|track(ing)?\s|write|writing|draw|drawing|create|creating|"
    r"build(ing)?\s|turn\s|improve|quit|stop\s|lose\s|losing\s|gain\s|"
    r"try\s|become|becoming|teach|teaching|plan\s|planning\s)",
    re.IGNORECASE,
)
_PRODUCT_WORDS = re.compile(
    r"\b(cream|lotion|serum|product|products|supplies|supply|equipment|"
    r"store|stores|shop|shops|toy|toys|book|books|device|devices|gadget|"
    r"gadgets|machine|machines|tool|tools|furniture|apparel|jewelry|"
    r"bakery|grocery|pharmacy|decor|mattress|sofa|chair|desk)\b",
    re.IGNORECASE,
)


def _stable_index(value, modulus):
    digest = hashlib.md5(value.encode("utf-8")).hexdigest()
    return int(digest, 16) % modulus


def is_content_style(name):
    return bool(_CONTENT_START.match(name.strip()))


def is_product_style(name):
    return bool(_PRODUCT_WORDS.search(name))


def _pick(templates, name, count, blocked):
    """Deterministically pick ``count`` rendered templates for ``name``."""
    picked = []
    seen = {name.casefold(), *blocked}
    start = _stable_index(name, len(templates))
    for offset in range(len(templates)):
        candidate = templates[(start + offset) % len(templates)].format(n=name)
        candidate = re.sub(r"\s+", " ", candidate).strip()
        key = candidate.casefold()
        if key in seen or len(candidate) > 180:
            continue
        seen.add(key)
        picked.append(candidate)
        if len(picked) >= count:
            break
    return picked


def generate_sub_niches(top_name, count=6):
    """Return sub-niche names for a main niche that has no curated/scraped data."""
    curated = CURATED_SUB_NICHES.get(top_name)
    if curated:
        return list(curated)
    templates = _SUB_TEMPLATES_CONTENT if is_content_style(top_name) else _SUB_TEMPLATES_SERVICE
    return _pick(templates, top_name, count, set())


def generate_micro_niches(sub_name, count=5):
    """Return micro-niche names for a sub-niche."""
    if is_content_style(sub_name):
        templates = _MICRO_TEMPLATES_CONTENT
    elif is_product_style(sub_name):
        templates = _MICRO_TEMPLATES_PRODUCT
    elif _SERVICE_WORDS.search(sub_name):
        templates = _MICRO_TEMPLATES_BUSINESS
    else:
        templates = _MICRO_TEMPLATES_GENERIC
    return _pick(templates, sub_name, count, set())


def generate_micro_for_subs(sub_names, count=5):
    """Yield ``(sub_name, [micro names])`` pairs."""
    for sub_name in sub_names:
        yield sub_name, generate_micro_niches(sub_name, count)
