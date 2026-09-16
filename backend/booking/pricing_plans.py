"""Public Vremio plan catalog for the platform landing page."""

from django.utils.translation import gettext_lazy as _


def _price_display(amount):
    return f"{int(amount):,}"


# Prices are "starting from" MKD / month — not fixed enterprise quotes.
PRICING_PLANS = (
    {
        "id": "starter",
        "name": _("Starter"),
        "price_mkd": 990,
        "price_display": _price_display(990),
        "blurb": _(
            "For businesses that want to stop managing bookings through Instagram messages and Notes."
        ),
        "highlights": (
            _("Get an online booking page instead of endless chat threads"),
            _("See requests in one dashboard — approve or reject in seconds"),
            _("Set your services, hours, and booking rules once"),
        ),
        "details": (
            _("Business profile on Vremio"),
            _("Services and working schedule"),
            _("Booking requests with customer details"),
            _("Owner dashboard"),
            _("Email notifications"),
            _("Booking rules and policies"),
        ),
        "perfect_for": _(
            "Nail salons, beauty studios, barbershops, trainers, and small service businesses."
        ),
        "cta": _("Request Starter"),
    },
    {
        "id": "pro",
        "name": _("Pro"),
        "price_mkd": 1990,
        "price_display": _price_display(1990),
        "featured": True,
        "blurb": _("Your own brand. Your own domain. A professional online presence."),
        "highlights": (
            _("Look like a real brand with your own domain and booking page"),
            _("We help connect DNS so customers land on your site"),
            _("Priority support when you need setup help"),
        ),
        "details": (
            _("Everything in Starter"),
            _("Custom domain connection"),
            _("Branded salon landing page"),
            _("Location with Open in Maps"),
            _("DNS setup included"),
            _("Priority support"),
        ),
        "perfect_for": _(
            "Businesses ready to look professional online and move off Instagram-only booking."
        ),
        "cta": _("Request Pro"),
    },
    {
        "id": "premium",
        "name": _("Premium"),
        "price_mkd": 2990,
        "price_display": _price_display(2990),
        "blurb": _(
            "Spend less time managing appointments and more time running your business."
        ),
        "highlights": (
            _("Stronger protection against no-shows and abusive bookings"),
            _("Monthly consultation to tune your booking flow"),
            _("SMS reminders coming soon — included when available"),
        ),
        "details": (
            _("Everything in Pro"),
            _("SMS reminders (coming soon)"),
            _("Advanced booking rules"),
            _("Anti-abuse protection"),
            _("Customer blocklist"),
            _("Monthly consultation"),
            _("Priority feature requests"),
        ),
        "perfect_for": _(
            "Growing businesses that want less admin and more control every month."
        ),
        "cta": _("Request Premium"),
    },
)

PRICING_FAQ = (
    {
        "question": _("Do I need my own website?"),
        "answer": _(
            "No. Every business automatically receives its own booking page on Vremio."
        ),
    },
    {
        "question": _("Can I connect my own domain?"),
        "answer": _(
            "Yes. The Pro and Premium plans support connecting your own domain."
        ),
    },
    {
        "question": _("Can customers book appointments 24/7?"),
        "answer": _(
            "Yes. Customers can request appointments anytime while you stay in control of approvals and availability."
        ),
    },
    {
        "question": _("Can I cancel anytime?"),
        "answer": _("Yes. There are no long-term contracts."),
    },
    {
        "question": _("Can I upgrade later?"),
        "answer": _(
            "Absolutely. You can upgrade your plan whenever your business grows."
        ),
    },
)
