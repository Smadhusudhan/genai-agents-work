"""Support ticket texts for the Session 11 temperature sweep.
A mix of clear-cut and genuinely borderline cases — the borderline ones are the
point: they are where temperature actually changes the answer."""

CLEAR_TICKETS = [
    ("billing_clear", "I was charged twice for my subscription this month. Please refund the duplicate charge."),
    ("technical_clear", "The app crashes every time I try to upload a photo larger than 5MB."),
    ("general_clear", "What are your customer support hours on weekends?"),
]

BORDERLINE_TICKETS = [
    ("borderline_1", "I upgraded my plan but I'm still being charged the old price and the new features aren't showing up either."),
    ("borderline_2", "Your app keeps logging me out and now I can't tell if I'm still being billed for the plan I signed up for."),
    ("borderline_3", "I'm not sure who to ask, but something seems wrong with my account since the last update."),
]

ALL_TICKETS = CLEAR_TICKETS + BORDERLINE_TICKETS
TICKETS_BY_ID = {tid: text for tid, text in ALL_TICKETS}
