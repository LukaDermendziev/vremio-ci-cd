# AGENTS.md

## Project Name

Salon Booking & Appointment Management System

## Project Goal

Build a real-world web application for beauty/service businesses, starting with a nail salon. The app should help salon owners manage bookings, reduce Instagram/Viber/Messenger scheduling chaos, reduce no-shows, and give customers a clean mobile-first booking experience.

The first real tester is a nail salon owner. Future testers may include a barber or other beauty/service businesses.

## Final Tech Direction

Use:

* Django for backend
* PostgreSQL for database
* Django Templates for first frontend
* Bootstrap or Tailwind for styling
* HTMX or small JavaScript for smooth interactions
* FullCalendar.js later for owner calendar UI

Do not start with React unless specifically requested later.

Do not use Spring Boot for this project unless the user explicitly changes the tech direction.

## Why Django

Django is chosen because this project needs:

* fast real-world MVP development
* authentication
* admin panel
* forms
* image uploads
* database models
* dashboard pages
* appointment CRUD
* owner management features

The goal is not only learning architecture. The goal is building a useful real-life product.

## Core Business Problem

The salon owner currently receives bookings through:

* Instagram
* Messenger
* Viber

Most customers book by message.

The owner currently tracks appointments in the Notes app on her phone.

She spends around 1-2 hours per day answering messages and arranging appointments.

Her biggest pain points:

* customers ask today for tomorrow
* customers ask for unavailable times
* customers do not respect given available slots
* customers think services take less time than they really do
* new clients sometimes waste time and do not show up
* customers are often late
* she wants clients to accept salon rules before booking
* she wants customers to send photos for certain services

## Owner Interview Findings

Current booking channels:

* Instagram
* Messenger
* Viber

Most common method:

* message

Time spent on scheduling:

* around 1-2 hours daily depending on the day

Current tracking method:

* Notes app on phone

Working days:

* Monday to Saturday

Working hours:

* 08:00 - 18:00

Closed:

* Sunday

Breaks:

* no fixed break

Weekend:

* works every Saturday

Services:

* Manicure
* Pedicure

Average service duration:

* around 2 hours, depending on case

Design impact:

* design can add 15-40 minutes

Photo upload:

* wanted for manicure/design
* required for medical pedicure

Average appointments:

* around 4 per day
* maximum usually 5 per day

Minimum booking notice:

* 2 weeks

Same-day booking:

* not allowed

Next-day booking:

* generally not allowed, except if someone cancels last minute

Maximum booking window:

* 60 days

Late arrival rule:

* 15 minutes without notice means appointment may be canceled

Rules:

* should be automatically shown
* customer must accept rules before booking

Approval:

* manual approval is preferred for this salon
* owner wants to know who is coming
* owner may reject clients with previous bad experience

Customer info:

* name and surname (required)
* phone number
* Instagram (optional)
* email (optional)

Note: Instagram is optional everywhere (public booking form, owner dashboard, and Django admin). The `Customer` model stores it as a blank-allowed field, so customers can be created and edited without an Instagram handle.

Customer history:

* useful

Notes about clients:

* not needed initially

Reminders:

* mandatory
* 24 hours before appointment

Owner would use the system:

* yes

Owner would use it instead of Instagram messages:

* yes

## Main MVP Goal

Build a web app where customers can request appointments and the owner can manage them from a dashboard/calendar.

The app should replace scheduling through random messages and phone notes.

## Customer Flow

1. Customer opens booking page from Instagram bio.
2. Customer chooses service.
3. Customer chooses available date.
4. Customer chooses available time.
5. Customer enters:

   * name and surname
   * phone number
   * Instagram (optional)
   * email (optional)
   * preferred contact method
6. Customer uploads photo if needed.
7. Customer accepts salon rules.
8. Customer submits booking request.
9. System shows:
   "Your appointment request has been sent. It is not confirmed yet. The salon will review it and contact you."

Never say the appointment is confirmed before owner approval.

## Owner Flow

1. Owner logs in.
2. Owner sees dashboard.
3. Owner sees pending requests.
4. Owner can approve or reject.
5. Owner can manually add bookings.
6. Owner can edit bookings.
7. Owner can block days or unavailable time periods.
8. Owner can view upcoming appointments.
9. Owner can view customer history.
10. Owner can send prepared messages or call customers.

## Booking Statuses

Use these appointment statuses:

* Pending
* Approved
* Rejected
* Cancelled
* Completed
* No Show

## Booking Rules for First Salon

Default settings:

* working days: Monday-Saturday
* working hours: 08:00-18:00
* closed day: Sunday
* minimum booking notice: 14 days
* maximum booking window: 60 days
* same-day booking: disabled
* next-day booking: disabled
* manual approval: enabled
* reminder time: 24 hours before appointment
* late arrival limit: 15 minutes

## Anti-Abuse Rules

Implement or plan for:

* one active pending booking per phone number
* rate limit booking attempts
* pending appointments may expire if not approved
* owner can block/blacklist customer phone numbers
* customers cannot book unavailable slots
* customers cannot book outside booking rules
* prevent double booking

## Notification System

Use multiple notification methods.

For owner:

* dashboard notification
* web push notification later
* email notification
* pending count in dashboard

For customer:

* confirmation page after request
* prepared message from owner after approve/reject
* email only if valid email was entered
* future web push if allowed
* future SMS if enabled

For owner actions, provide buttons:

* Call
* Send Viber message
* Send WhatsApp message
* Send SMS
* Copy message

Always include Copy Message as universal fallback.

If customer does not have Viber or WhatsApp, owner can use:

* SMS
* phone call
* Instagram DM
* email if provided
* copied prepared message

## Prepared Message Feature

When owner approves or rejects, generate a message in Macedonian.

Example approval:

"Здраво [име], вашиот термин за [датум] во [време] е потврден. Ве очекуваме."

Example rejection:

"Здраво [име], за жал терминот за [датум] во [време] не е достапен. Ве молиме изберете друг термин."

The owner can copy it or open it in Viber/WhatsApp/SMS.

## Important Inspired Features From Planfy

Use these as inspiration, not as exact copies:

* owner calendar
* manual add booking
* automatic/manual approval toggle
* unavailable time blocks
* custom working hours for chosen day
* booking management
* settings cards/modules
* edit booking
* toggle: inform customer about changes
* add to calendar for customer
* multiple services in one booking later

## MVP Features

Must have:

* customer booking page
* service selection
* date/time selection
* customer info form
* photo upload
* salon rules checkbox
* booking request creation
* owner login
* owner dashboard
* pending bookings
* approve/reject
* booking list
* manual add booking
* manage services
* working hours
* blocked days
* booking policy settings

Should have soon:

* unavailable time blocks
* custom working hours for specific date
* edit booking
* prepared messages
* call button
* copy message button
* add to calendar
* customer history

Later:

* web push notifications
* automatic email confirmations
* SMS reminders
* online deposits
* loyalty rewards
* multiple employees
* multiple salons
* React frontend if needed
* Django REST Framework if needed

## Database Direction

Design the database so it can grow.

Core models likely needed:

* Salon
* Service
* Customer
* Booking or Appointment
* BookingService
* WorkingHours
* BlockedDate
* UnavailableTimeBlock
* BookingPolicy
* NotificationPreference
* CustomerBlocklist

Appointment should support multiple services later, so avoid locking the design into one appointment = one service if possible.

## Frontend Style

Mobile-first.

The customer page should feel:

* clean
* elegant
* premium
* simple
* beauty/salon oriented
* smooth
* Instagram-friendly

Owner dashboard should feel:

* practical
* fast
* calendar-focused
* clean
* easy to use on laptop and phone

Smoothness should come from:

* good UI
* responsive design
* HTMX/small JavaScript
* modals
* dynamic slot loading
* no unnecessary full-page reloads

## Development Behavior

Before writing code:

1. Read this AGENTS.md.
2. Ask clarifying questions if something is unclear.
3. Do not overbuild.
4. Prefer small working increments.
5. Keep MVP focused.
6. Use Django best practices.
7. Do not introduce React unless requested.
8. Do not introduce Spring Boot unless requested.
9. Make code understandable for a student/developer learning from the project.

## First Development Milestone

Create a local Django project with:

* clean folder structure
* one Django app for booking/core logic
* base templates
* initial models proposal
* admin registration
* simple homepage
* simple owner dashboard placeholder

Do not implement complex notifications, payments, loyalty, or SMS in the first milestone.
