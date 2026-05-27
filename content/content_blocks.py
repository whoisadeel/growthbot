"""
Reusable content blocks for the template-based draft and landing page generators.

These are intentionally generic, professional, and editable. They are NOT meant
to be published as-is — they're a strong first draft for a human to refine.
"""

INTRO_TEMPLATES = [
    ("If you're a {audience} looking for {topic} in {city}, you already know "
     "the stakes: it has to drive results, look professional, and fit your "
     "budget. In this guide we break down what good {topic} looks like, "
     "common pitfalls to avoid, and how to choose a partner you can trust."),
    ("{topic} can feel overwhelming for a {audience}. There are dozens of tools, "
     "vendors, and opinions — and most of them contradict each other. This "
     "article gives you a practical, no-fluff walkthrough so you can make a "
     "confident decision for your business in {city}."),
]

WHY_IT_MATTERS = [
    "Customers research online before they ever pick up the phone. Weak {topic} "
    "costs you leads every day, often silently.",
    "Search engines reward sites that solve real customer problems. Investing in "
    "{topic} compounds over time — every month you wait is lost momentum.",
    "Most competitors in {city} have generic, templated work. A focused {topic} "
    "strategy is one of the cheapest ways to stand out.",
]

COMMON_PROBLEMS = [
    "Treating {topic} as a one-time project instead of an ongoing program.",
    "Hiring on price alone and getting locked into a poor template.",
    "No clear conversion goal — pages look nice but don't generate inquiries.",
    "Skipping local SEO basics like NAP consistency and Google Business Profile.",
    "No measurement: no analytics, no call tracking, no monthly review.",
]

WHAT_TO_LOOK_FOR = [
    "A clear discovery process — the team should ask about your customers, not just your colors.",
    "Transparent pricing and a written scope of work.",
    "Examples of work for businesses like yours (ideally in {city} or nearby).",
    "Ownership of your domain, hosting, and analytics from day one.",
    "A maintenance / support plan so the site stays fast and secure.",
]

RECOMMENDED_SOLUTION = (
    "At {brand}, we help {audience} across {city} and {state} with {service}. "
    "Our process is built around your business goals: we start with a discovery "
    "call, audit your current setup, and propose a clear, fixed-scope plan. No "
    "lock-in contracts, no surprise fees, and every deliverable is reviewed "
    "with you before launch."
)

LOCAL_ANGLE = (
    "Working with a {city}-based partner means faster response times, in-person "
    "meetings when needed, and a team that understands the local market — from "
    "the small business community to the way local customers search."
)

CHECKLIST_TEMPLATES = {
    "default": [
        "Define one primary goal for the project (leads, sales, bookings).",
        "Map out your top 3 customer journeys.",
        "List the 5–10 keywords your customers actually search.",
        "Audit your current website performance and SEO baseline.",
        "Set a realistic budget and timeline (and a 10–15% buffer).",
        "Agree on success metrics in writing before kickoff.",
    ],
}

CTA_BLOCK = (
    "**Ready to take the next step?** {cta} with {brand} — we'll review your "
    "current setup, walk through what's working, and give you a clear plan "
    "you can act on (whether you hire us or not)."
)
