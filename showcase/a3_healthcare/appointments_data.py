"""Mock data for the A3 showcase. Everything here is invented - no real doctors, no real patients."""

SPECIALTIES = ["cardiology", "dermatology", "general_physician", "orthopedics"]
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday"]
TIMES_OF_DAY = ["morning", "afternoon", "evening"]

# (doctor, specialty, day, time_of_day, clock time)
AVAILABILITY = [
    ("Dr. Rao",    "cardiology",        "monday",    "morning",   "10:30"),
    ("Dr. Rao",    "cardiology",        "wednesday", "afternoon", "15:00"),
    ("Dr. Iyer",   "dermatology",       "tuesday",   "morning",   "09:30"),
    ("Dr. Iyer",   "dermatology",       "thursday",  "evening",   "17:30"),
    ("Dr. Khan",   "general_physician", "monday",    "afternoon", "14:00"),
    ("Dr. Khan",   "general_physician", "tuesday",   "morning",   "11:00"),
    ("Dr. Khan",   "general_physician", "friday",    "evening",   "18:00"),
    ("Dr. Sharma", "orthopedics",       "wednesday", "morning",   "10:00"),
    ("Dr. Sharma", "orthopedics",       "friday",    "afternoon", "16:00"),
]

# Rule owned by CODE, checked before any model is called.
EMERGENCY_KEYWORDS = ["chest pain", "can't breathe", "cannot breathe", "difficulty breathing", "unconscious",
                      "severe bleeding", "stroke", "heart attack", "suicidal", "overdose"]

# Scripted conversations: each list is what the "patient" types, turn by turn.
SCENARIOS = {
    "happy_path": ["Hi, I want to book an appointment", "A skin doctor please", "Tuesday", "Morning works", "Priya Menon"],
    "all_in_one": ["I'm Arjun Das and I need a general physician on Monday afternoon"],
    "vague_then_filled": ["I need to see someone about my knee", "orthopedics I guess", "Friday afternoon", "Sneha Reddy"],
    "no_matching_slot": ["Book me a cardiologist on Friday evening, name is Vikram Nair"],
    "cancel_request": ["I need to cancel my appointment for tomorrow"],
    "emergency": ["I have chest pain and I want an appointment"],
    "off_topic": ["What is the weather in Hyderabad today?"],
}
