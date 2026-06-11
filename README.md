# Salon Scheduler System

Salon Scheduler System is a web-based appointment booking and management application for beauty and service businesses.

The first real-world use case is a nail salon owner who currently manages appointments through Instagram, Messenger, Viber, and phone notes. The goal of the system is to reduce manual messaging, prevent scheduling confusion, reduce no-shows, and give the owner a clean dashboard/calendar for managing appointments.

## Main Goal

Build a real-world booking system where customers can request appointments online and the salon owner can manage, approve, reject, edit, and track appointments from an owner dashboard.

## First Target Business

The first target business is a nail salon.

Future possible businesses:

* Barbers
* Hair salons
* Makeup artists
* Tattoo studios
* Massage studios
* Beauty salons

## Current Tech Decision

Initial stack:

* Backend: Django
* Database: PostgreSQL
* Frontend: Django Templates
* Styling: Bootstrap or Tailwind
* Smooth UI interactions: HTMX or small JavaScript
* Calendar UI later: FullCalendar.js

React and Django REST Framework are not part of the first MVP unless they become necessary later.

## Core Problems Being Solved

The salon owner currently:

* receives appointment requests through Instagram, Messenger, and Viber
* tracks appointments in phone notes
* spends around 1-2 hours daily arranging appointments
* deals with customers asking for unavailable times
* deals with customers asking today for tomorrow
* wants customers to send reference photos for certain services
* wants customers to accept salon rules before booking
* wants to manually approve bookings
* wants 24-hour appointment reminders

## Main MVP Features

Customer side:

* Select service
* Select date
* Select available time
* Enter name, phone number, Instagram, and optional email
* Choose preferred contact method
* Upload reference photo if needed
* Accept salon rules
* Submit booking request
* See pending confirmation message

Owner side:

* Login
* Dashboard
* View pending bookings
* Approve or reject bookings
* Manually add bookings
* Edit bookings
* View appointments
* Manage services
* Manage working hours
* Block days or unavailable times
* View customer history
* Use prepared messages to contact customers

## Important Booking Rules for First Salon

* Working days: Monday to Saturday
* Working hours: 08:00 - 18:00
* Closed: Sunday
* Same-day booking: not allowed
* Next-day booking: generally not allowed
* Minimum booking notice: 14 days
* Maximum booking window: 60 days
* Manual approval: enabled
* Reminder: 24 hours before appointment
* Late arrival limit: 15 minutes without notice

## Appointment Statuses

Appointments can have these statuses:

* Pending
* Approved
* Rejected
* Cancelled
* Completed
* No Show

## Documentation

Detailed project documents are stored in the `docs/` folder:

* `owner-interview-summary.md`
* `requirements-v1.md`
* `roadmap.md`

## Development Philosophy

Build the project in small steps.

Do not overbuild early.

First goal:

Create a working local MVP for one nail salon.

Later goals:

* Improve based on real owner feedback
* Test with a barber
* Add reminders
* Add customer history
* Add calendar improvements
* Add deposits/payments later
* Add loyalty features later
* Add multiple salons/employees later
