"""Mock claim descriptions for the A2 showcase. Free text, as a customer would actually type it —
deliberately messy, no fixed fields. One of these is picked at random or passed on the command line."""

CLAIMS = [
    # id, free-text description, what a human would call it (for the README table only, not used by the code)
    ("minor_no_injury",
     "My car was hit from behind at a signal in Hitech City yesterday evening. The bumper and boot "
     "are a bit damaged, nobody was hurt, and the other driver has admitted fault."),

    ("minor_scrape",
     "Someone scraped my car door in a parking lot. Small dent and some paint came off. No one else "
     "involved, I didn't see who did it. I'm fine, just annoyed."),

    ("major_injury",
     "There was a bad accident on the outer ring road. My car rolled over after swerving to avoid a "
     "truck. I have a fractured arm and my passenger has a head injury, we were both taken to the "
     "hospital. The car is badly damaged, probably a total loss."),

    ("major_no_injury_expensive",
     "My car caught fire in the parking garage at home, I think it was an electrical fault. Nobody "
     "was inside at the time so no injuries, but the engine bay and a lot of the interior is burnt. "
     "I think it's not drivable."),

    ("ambiguous_whiplash",
     "Got rear-ended at a traffic light, low speed. The car only has a small scratch on the bumper "
     "but my neck has been hurting since yesterday, I might go to a doctor to get it checked."),

    ("major_multi_vehicle",
     "Four-car pile-up on the highway during heavy rain. My car was in the middle, both the front and "
     "back are damaged. I have some bruising but nothing serious, didn't need a hospital. Still pretty "
     "shaken up though."),

    ("minor_glass_only",
     "A stone hit my windscreen on the highway and cracked it. That's the only damage, car drives "
     "fine, nobody hurt obviously."),

    ("fraud_flag_suspicious",
     "My car was 'stolen' from outside my house and then found three streets away with the whole "
     "front end smashed in. No witnesses. I want to file a claim for the damage."),
]

CLAIMS_BY_ID = {cid: text for cid, text in CLAIMS}
