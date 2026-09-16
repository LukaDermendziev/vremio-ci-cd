# Owner Interview Summary

## Purpose

This document summarizes the first interview with the nail salon owner and turns her answers into product requirements for the Salon Booking & Appointment Management System.

The goal of this interview was to understand the real scheduling problems before starting implementation.

---

## 1. Current Booking Workflow

### Q1. How do customers currently book appointments?

**Answer:** Instagram, Messenger, Viber.

### Q2. Which method do customers use the most?

**Answer:** Through messages.

### Q3. How much time per day do you spend answering messages and arranging appointments?

**Answer:** Around 1–2 hours per day, depending on the day. Sometimes more time is spent when multiple customers accumulate and the owner needs to negotiate appointment times with them.

### Q4. Do you use a notebook, calendar, or app to track appointments?

**Answer:** Notes app on the phone.

### Q5. What is the most annoying part of appointment scheduling?

**Answer:** Customers write today asking for tomorrow, or the owner offers available times such as 10:00 and 12:00, and the customer replies that they will come at 15:00 even though that time was not offered.

### Product interpretation

The current workflow is message-based and manual. The owner loses 1–2 hours daily on scheduling. The app should reduce message negotiation and force customers to choose only real available times.

---

## 2. Working Hours

### Q6. Which days do you work?

**Answer:** Monday to Saturday.

### Q7. What are your working hours?

**Answer:** 08:00–18:00.

### Q8. Do you have a break during the day?

**Answer:** No fixed break.

### Q9. Do you sometimes work weekends?

**Answer:** Yes, every Saturday.

### Q10. Are there days when you do not accept clients at all?

**Answer:** Sunday is a non-working day.

### Q11. Do you have vacations or periods when you know in advance that you will not work?

**Answer:** When she knows in time, she announces it on Instagram story around one month in advance.

### Product interpretation

Default working schedule should be Monday–Saturday, 08:00–18:00, with Sunday closed. The system must allow the owner to block days or periods manually for vacation, personal obligations, or other unavailable time.

---

## 3. Services

### Q12. Which services do you offer?

**Answer:** Manicure and pedicure.

### Q13. How long does each service take?

**Answer:** Approximately 2 hours for both, depending on the case.

### Q14. Does duration depend on the design?

**Answer:** Yes. Design can add around 15–40 minutes.

### Q15. Would you like customers to send a photo of the design beforehand?

**Answer:** Yes.

### Q16. For which services is a photo required?

**Answer:** For manicure, clients can send what they want to do. For medical pedicure, the photo should be required so the owner can see what kind of case it is.

### Q17. Are there services that require more time than customers think?

**Answer:** Yes. Customers often think something can be done in 1 hour, but it takes longer.

### Product interpretation

Services should have editable duration, price, description, and photo requirement settings. Some services should require photo upload. The system should communicate estimated duration clearly so customers understand that services cannot always be completed in 1 hour.

Possible initial services:

- Manicure
- Manicure with design
- Pedicure
- Medical pedicure

---

## 4. Appointment Volume and Booking Rules

### Q18. How many appointments do you have on average per week?

**Answer:** She has never counted exactly, but most often around 4 appointments daily.

### Q19. How many appointments do you have on average per day?

**Answer:** Most often 4, maximum usually 5.

### Q20. Does it often happen that two customers want the same appointment time?

**Answer:** She has not noticed this much because she usually offers the first available slot.

### Q21. How far in advance do you want customers to book?

**Answer:** 2–3 weeks in advance, or during their current appointment.

### Q22. Do you allow next-day appointments?

**Answer:** Usually only when someone cancels last minute.

### Q23. Do you allow same-day appointments?

**Answer:** No, not at all.

### Q24. What is the shortest acceptable time in advance for booking?

**Answer:** 2 weeks.

### Q25. How far into the future should booking be allowed?

**Answer:** 60 days.

### Product interpretation

The app should strongly enforce booking rules:

- Same-day booking disabled.
- Next-day booking disabled by default.
- Minimum booking notice: 14 days.
- Maximum booking window: 60 days.
- Average daily capacity: 4 appointments.
- Maximum daily capacity: 5 appointments.

The owner can still manually add next-day appointments if a cancellation appears.

---

## 5. Cancellations, No-Shows, and Lateness

### Q26. How often do customers not show up?

**Answer:** Regular clients rarely do this and usually announce if they cannot come. New clients are the bigger issue: sometimes they take a lot of time and then do not show up.

### Q27. How often do customers cancel at the last minute?

**Answer:** Rarely.

### Q28. How often do customers arrive late?

**Answer:** Often.

### Q29. After how many minutes of being late is the appointment considered cancelled?

**Answer:** 15 minutes of unannounced lateness.

### Q30. Would you like the system to automatically display these rules?

**Answer:** Yes.

### Q31. Would you like customers to be required to accept the rules before booking?

**Answer:** Yes.

### Product interpretation

The booking flow must show salon rules and require customer agreement before submission. The 15-minute late policy should be clearly visible.

Possible rule text:

- Same-day appointments are not accepted.
- Appointments must be requested at least 2 weeks in advance.
- If you are more than 15 minutes late without notice, the appointment may be cancelled.
- The appointment is not confirmed until approved by the salon.

---

## 6. Appointment Approval and Owner Control

### Q32–Q36. Manual approval, automatic confirmation, notifications, and checking requests

**Answer summary:** The owner checks requests daily. She wants advice on the most practical workflow. She wants to know who is coming and may not want to accept a client if she previously had a bad experience with that person. She is also concerned about abuse, for example someone clicking many appointments and blocking all available times without actually showing up.

### Product interpretation

For this salon, the best first workflow is manual approval.

Recommended mode:

- Customer sends booking request.
- Appointment status becomes Pending.
- Owner reviews request.
- Owner approves or rejects.
- Appointment is only confirmed after approval.

The system should later support an automatic approval toggle, but manual approval should be the default for this first salon.

Anti-abuse measures should include:

- One active pending booking per phone number.
- Rate limiting booking attempts.
- No double booking.
- Owner can block a customer by phone number.
- Pending slots can expire after a configured time if not approved.
- Customer must enter name, phone number, and Instagram.

---

## 7. Customer Information

### Q37. Which customer information do you want to collect?

**Answer:** Name and surname, phone number, Instagram, maybe email.

### Q38. Would you like to see previous visits of a customer?

**Answer:** Yes.

### Q39. Would you like to store photos of previous designs?

**Answer:** Not answered directly.

### Q40. Would you like notes about customers?

**Answer:** No, not initially.

### Product interpretation

Required customer fields:

- Name and surname
- Phone number
- Instagram username

Optional customer fields:

- Email

Customer history should be included or planned early. Detailed private notes are not required in the first version.

---

## 8. Reminders

### Q41. Would you like customers to receive reminders before appointments?

**Answer:** Yes, mandatory.

### Q42. How long before the appointment?

**Answer:** 24 hours before.

### Product interpretation

The app should support 24-hour reminders.

MVP approach:

- Owner dashboard shows tomorrow's appointments.
- Owner can send prepared reminder messages manually.

Later approach:

- Automatic email reminder if customer provided email.
- SMS reminder if paid SMS integration is added.
- Web push notification if customer allowed notifications.

---

## 9. Business Perspective

### Q44. If this system existed today, would you use it?

**Answer:** Yes, definitely.

### Q45. Would you use it instead of Instagram messages?

**Answer:** Yes.

### Q46–Q50. Extra business questions

**Answer:** Not fully answered yet.

### Product interpretation

The owner confirmed that the product solves a real problem and that she would use it. This validates moving forward with an MVP.

---

## Main Conclusions

The strongest confirmed problems are:

1. Too much time spent arranging appointments by message.
2. Customers request unavailable times.
3. Customers try to book too late, including today for tomorrow.
4. Customers underestimate service duration.
5. The owner needs photo previews for some services.
6. New clients can be unreliable.
7. Customers are often late.
8. The owner wants control over who gets accepted.
9. The current appointment tracking system is only phone Notes.
10. The owner would use this system instead of Instagram messages.

---

## Recommended First Salon Defaults

- Booking mode: Manual approval.
- Working days: Monday–Saturday.
- Working hours: 08:00–18:00.
- Closed day: Sunday.
- Minimum booking notice: 14 days.
- Maximum booking window: 60 days.
- Same-day booking: Disabled.
- Next-day booking: Disabled by default.
- Average service duration: 120 minutes.
- Design extra duration: 15–40 minutes.
- Reminder: 24 hours before appointment.
- Lateness rule: 15 minutes without notice.
- Customer data: name, phone, Instagram, optional email.
- Photo upload: required for medical pedicure, recommended for manicure/design.

