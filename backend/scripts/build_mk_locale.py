"""Build locale/mk/LC_MESSAGES/django.po and django.mo without GNU gettext tools."""
from pathlib import Path

import polib

BASE = Path(__file__).resolve().parent.parent
LOCALE_DIR = BASE / "locale" / "mk" / "LC_MESSAGES"

# English msgid -> Macedonian msgstr
TRANSLATIONS = {
    # base.html
    "Salon Scheduler": "Salon Scheduler",
    # booking_form.html
    "Book": "Резервирај",
    "Something went wrong. Please check your details and choose an available time.": "Нешто тргна наопаку. Проверете ги податоците и изберете слободен термин.",
    "Service": "Услуга",
    "Date & Time": "Датум и време",
    "Your Details": "Ваши податоци",
    "Review": "Преглед",
    "Back": "Назад",
    "Back to salon": "Назад кон салонот",
    "Please enter your full name.": "Внесете го вашето име и презиме.",
    "Please enter your phone number.": "Внесете го вашиот телефонски број.",
    "Please enter your email address.": "Внесете ја вашата email адреса.",
    "Please enter a valid email address.": "Внесете валидна email адреса.",
    "Please enter your Instagram username.": "Внесете го вашето Instagram корисничко име.",
    "Please upload a reference photo for this service.": "Прикачете референтна фотографија за оваа услуга.",
    "Please complete all required fields before continuing.": "Пополнете ги сите задолжителни полиња пред да продолжите.",
    "Upload your logo here": "Поставете го вашиот лого тука",
    "Request an appointment": "Побарајте термин",
    "Choose service": "Изберете услуга",
    "%(minutes)s min": "%(minutes)s мин",
    "from %(price)s den": "од %(price)s ден",
    "den": "ден",
    "Photo required": "Потребна е фотографија",
    "Photo recommended": "Препорачана е фотографија",
    "No active services available yet.": "Сè уште нема активни услуги.",
    "Continue": "Продолжи",
    "Previous month": "Претходен месец",
    "Next month": "Следен месец",
    "Mo": "По",
    "Tu": "Вт",
    "We": "Ср",
    "Th": "Че",
    "Fr": "Пе",
    "Sa": "Са",
    "Su": "Не",
    "Available times": "Слободни термини",
    "Select a date above to see available times.": "Изберете датум погоре за да ги видите слободните термини.",
    "Full name": "Име и презиме",
    "Phone number": "Телефонски број",
    "Instagram username": "Instagram корисничко име",
    "Email": "Е-пошта",
    "optional": "опционално",
    "Preferred contact method": "Претпочитан начин на контакт",
    "Reference photo": "Референтна фотографија",
    "Tap to upload a photo": "Допри за да прикачиш слика",
    "Review & Submit": "Преглед и испраќање",
    "Review request": "Преглед на барањето",
    "Appointment": "Термин",
    "Contact details": "Контакт податоци",
    "Salon rules": "Правила на салонот",
    "I understand:": "Разбирам дека:",
    "This is a request only — not confirmed until the salon approves it.": "Ова е само барање — не е потврдено додека салонот не одобри.",
    "Cancellations require at least 24–48 hours notice.": "Откажувањата бараат најмалку 24–48 часа однапред.",
    "Being more than 15 minutes late without notice may result in cancellation.": "Доцнење повеќе од 15 минути без најава може да резултира со откажување.",
    "I agree to the selected time and understand it cannot be changed without notice.": "Се согласувам со избраниот термин и разбирам дека не може да се промени без најава.",
    "Submit Request": "Испрати барање",
    "Loading times…": "Се вчитуваат термини…",
    "No available times on this date.": "Нема слободни термини на овој датум.",
    "Could not load times. Please try again.": "Не можеше да се вчитаат термините. Обидете се повторно.",
    "Only one service is allowed per booking. Your previous selection was replaced.": "Дозволена е само 1 услуга по резервација. Претходниот избор е заменет.",
    "Only images are allowed (JPG, PNG, WebP). Choose another format.": "Дозволени се само слики (JPG, PNG, WebP). Одбери друг формат.",
    "The image is too large. Maximum allowed size is %(max)s MB.": "Сликата е преголема. Максималната дозволена големина е %(max)s MB.",
    "(required)": "(задолжително)",
    "(recommended)": "(препорачано)",
    "(optional)": "(опционално)",
    "Via": "Преку",
    "min": "мин",
    "January": "Јануари",
    "February": "Февруари",
    "March": "Март",
    "April": "Април",
    "May": "Мај",
    "June": "Јуни",
    "July": "Јули",
    "August": "Август",
    "September": "Септември",
    "October": "Октомври",
    "November": "Ноември",
    "December": "Декември",
    "Sunday": "Недела",
    "Monday": "Понеделник",
    "Tuesday": "Вторник",
    "Wednesday": "Среда",
    "Thursday": "Четврток",
    "Friday": "Петок",
    "Saturday": "Сабота",
    "Jan": "Јан",
    "Feb": "Фев",
    "Mar": "Мар",
    "Apr": "Апр",
    "Jun": "Јун",
    "Jul": "Јул",
    "Aug": "Авг",
    "Sep": "Сеп",
    "Oct": "Окт",
    "Nov": "Ное",
    "Dec": "Дек",
    # booking_success.html
    "Request Sent": "Барањето е испратено",
    "Request sent!": "Барањето е испратено!",
    "Your booking request has been submitted.<br> The appointment is <strong>not confirmed yet</strong>.<br> %(salon_name)s will review your request and contact you.": (
        "Вашето барање за термин е испратено.<br> "
        "Терминот <strong>сè уште не е потврден</strong>.<br> "
        "%(salon_name)s ќе го прегледа вашето барање и ќе ве контактира."
    ),
    "Booking summary": "Резиме на барањето",
    "Pending approval": "Чека одобрување",
    "The salon will contact you to confirm via your preferred contact method.": "Салонот ќе ве контактира за потврда преку вашиот претпочитан начин на контакт.",
    "Back to %(salon_name)s": "Назад кон %(salon_name)s",
    # salon_page.html
    "Services": "Услуги",
    "Hours": "Работно време",
    "Book now": "Резервирај",
    "Professional nail care": "Професионална нега на нокти",
    "Beautiful nails,": "Убави нокти,",
    "made just for you.": "направени само за вас.",
    "Explore our services and book your next appointment online — in just a few minutes.": "Истражете ги нашите услуги и резервирајте го следниот термин онлајн — за само неколку минути.",
    "Book an appointment": "Резервирај термин",
    "View services": "Погледни услуги",
    "Schedule": "Распоред",
    "Online booking": "Онлајн резервации",
    "Approval": "Одобрување",
    "Manual review": "Рачен преглед",
    "Reminder": "Потсетник",
    "24 h before": "24 ч. однапред",
    "Working days": "Работни денови",
    "Mon – Sat": "Пон – Саб",
    "What we offer": "Што нудиме",
    "Our": "Нашите",
    "services": "услуги",
    "More": "Повеќе",
    "Price list": "Ценовник",
    "Reference photo required": "Потребна е референтна фотографија",
    "Book this service": "Резервирај ја оваа услуга",
    "Services will be listed here soon.": "Услугите наскоро ќе бидат објавени тука.",
    "Working": "Работно",
    "hours": "време",
    "Today": "Денес",
    "Closed": "Затворено",
    "Before you book": "Пред да резервирате",
    "Booking": "Правила за",
    "rules": "резервации",
    "Minimum booking notice: <strong>%(days)s days</strong>": "Минимално однапред: <strong>%(days)s дена</strong>",
    "Book up to <strong>%(days)s days</strong> in advance": "Резервирајте до <strong>%(days)s дена</strong> однапред",
    "All requests require <strong>salon approval</strong> before confirmation": "Сите барања бараат <strong>одобрување од салонот</strong> пред потврда",
    "Late arrival limit: <strong>%(minutes)s minutes</strong>": "Лимит за доцнење: <strong>%(minutes)s минути</strong>",
    "All requests require salon approval before confirmation.": "Сите барања бараат одобрување од салонот пред потврда.",
    "Open now": "Отворено сега",
    "Closed now": "Затворено сега",
    "Closed today": "Затворено денес",
    "Ready for": "Подготвени за",
    "your": "вашиот",
    "next appointment?": "следен термин?",
    "Send a request in minutes. We'll review it and contact you to confirm.": "Испратете барање за неколку минути. Ќе го прегледаме и ќе ве контактираме за потврда.",
    "Book appointment": "Закажи термин",
    "Care, style, and an appointment that suits you.": "Нега, стил и термин што ви одговара.",
    "Choose a service, date and available time. The salon will review your request.": "Избери услуга, датум и слободен термин. Барањето ќе биде прегледано од салонот.",
    "Choose a service, date and available time. Your request will be reviewed by the salon.": "Изберете услуга, датум и слободен термин. Барањето ќе биде прегледано од салонот.",
    "The appointment is not confirmed until the salon approves it.": "Терминот не е потврден додека не биде одобрен.",
    "The appointment is not confirmed until it is approved.": "Терминот не е потврден додека не биде одобрен.",
    "Photo uploaded": "Има слика",
    "View reference photo": "Погледни референтна слика",
    "No photo attached": "Нема прикачена слика",
    "Open full size": "Отвори целосна големина",
    "Welcome back — %(salon_name)s": "Добредојде — %(salon_name)s",
    "Pending requests": "Барања на чекање",
    "Approved bookings scheduled for today.": "Одобрени термини закажани за денес.",
    "Review new requests and approve or reject.": "Прегледај ги новите барања и одобри или одбиј.",
    "View": "Погледни",
    "Online booking, made simple.": "Онлајн резервации, едноставно.",
    "Footer navigation": "Подножје навигација",
    "Made by": "Направено од",
    # home.html
    "Salon Scheduler — Book Online": "Salon Scheduler — Резервирај онлајн",
    "Book your salon<br><em>appointment online</em>": "Резервирајте го вашиот<br><em>салонски термин онлајн</em>",
    "No messages. No waiting. Choose a service, pick a time, and send your request.": "Без пораки. Без чекање. Изберете услуга, термин и испратете барање.",
    "Choose your salon": "Изберете салон",
    "Available": "Достапни",
    "salons": "салони",
    "View & Book": "Погледни и резервирај",
    "No active salons available yet.": "Сè уште нема активни салони.",
    "Professional scheduling for beauty businesses": "Професионално закажување за beauty бизниси",
    # auth
    "Owner — Salon Scheduler": "Сопственик — Salon Scheduler",
    "Owner Login": "Најава за сопственик",
    "Sign in to your salon dashboard": "Најавете се на контролната табла на салонот",
    "Username": "Корисничко име",
    "Password": "Лозинка",
    "Sign in": "Најави се",
    "Forgot password?": "Заборавена лозинка?",
    "Reset Password": "Ресетирај лозинка",
    "Enter your email and we'll send a reset link.": "Внесете ја вашата е-пошта и ќе ви испратиме линк за ресетирање.",
    "Email address": "Е-пошта",
    "Send reset link": "Испрати линк за ресетирање",
    "Back to login": "Назад на најава",
    "Reset Link Sent": "Линкот е испратен",
    "Check your inbox": "Проверете ја вашата поштенска сандуче",
    "If an account with that email exists, a password reset link has been sent. Check your spam folder if you don't see it.": "Ако постои сметка со таа е-пошта, испратен е линк за ресетирање. Проверете ја папката за спам ако не го гледате.",
    "Set New Password": "Постави нова лозинка",
    "Set new password": "Постави нова лозинка",
    "Choose a strong password for your account.": "Изберете силна лозинка за вашата сметка.",
    "Set password": "Постави лозинка",
    "This reset link is invalid or has expired.": "Овој линк за ресетирање е неважечки или истечен.",
    "Request a new one.": "Побарајте нов.",
    "Password Reset Complete": "Лозинката е ресетирана",
    "Password updated": "Лозинката е ажурирана",
    "Your password has been set. You can now sign in.": "Вашата лозинка е поставена. Сега можете да се најавите.",
    "Go to login": "Оди на најава",
    "Change Password": "Промени лозинка",
    "Change password": "Промени лозинка",
    "Update your account password.": "Ажурирајте ја лозинката на вашата сметка.",
    "Update password": "Ажурирај лозинка",
    "Cancel": "Откажи",
    "Hello,": "Здраво,",
    "You requested a password reset for your Salon Scheduler owner account.": "Побаравте ресетирање на лозинката за вашата Salon Scheduler сметка.",
    "Click the link below to set a new password:": "Кликнете на линкот подолу за да поставите нова лозинка:",
    "This link expires in 24 hours.": "Овој линк истекува за 24 часа.",
    "If you did not request this, ignore this email — your password will not change.": "Ако не сте го побарале ова, игнорирајте ја пораката — вашата лозинка нема да се промени.",
    "Dashboard": "Контролна табла",
    "Overview": "Преглед",
    "Calendar": "Календар",
    "Bookings": "Термини",
    "Customers": "Клиенти",
    "Working hours": "Работно време",
    "Availability": "Достапност",
    "Booking policy": "Политика за резервации",
    "Owner panel": "Панел за сопственик",
    "Customer view": "Страница за клиенти",
    "Sign out": "Одјави се",
    "Close sidebar": "Затвори странична лента",
    "Close": "Затвори",
    "Expand sidebar": "Прошири странична лента",
    "Collapse sidebar": "Собери странична лента",
    "No active salon is assigned to your account yet.": "На вашата сметка сè уште не е доделен активен салон.",
    "Please contact the administrator.": "Ве молиме контактирајте го администраторот.",
    "Open booking page": "Отвори страница за резервации",
    "Pending": "На чекање",
    "Approved": "Одобрено",
    "Rejected": "Одбиено",
    "Cancelled": "Откажано",
    "Completed": "Завршено",
    "No Show": "Не се појави",
    "No-show": "Не се појави",
    "Upcoming": "Најавени",
    "No-shows": "Не се појавија",
    "Completed this week": "Завршени оваа недела",
    "Weekly revenue": "Неделен приход",
    "Total revenue": "Вкупен приход",
    "Revenue from completed appointments only. No online payments.": "Приход само од завршени термини. Без онлајн плаќања.",
    "Today's appointments": "Денешни термини",
    "No approved appointments for today.": "Нема одобрени термини за денес.",
    "Pending booking requests": "Барања на чекање",
    "View all": "Види ги сите",
    "All caught up — no pending requests.": "Сè е чисто — нема барања на чекање.",
    "View and manage your appointment schedule.": "Преглед и управување со термините.",
    "Week": "Недела",
    "Day": "Ден",
    "Add": "Додади",
    "Unavailable": "Недостапно",
    "Double-click (or double-tap on mobile) an empty slot to add a booking · Click an appointment to view details": "Дупло кликни (или двоен допир на мобилен) на празен термин за нова резервација · Кликни на термин за детали",
    "Add booking": "Додади термин",
    "No bookings yet.": "Сè уште нема термини.",
    "Add customer": "Додади клиент",
    "Name": "Име",
    "Phone": "Телефон",
    "Contact": "Контакт",
    "History": "Историја",
    "Edit": "Уреди",
    "No customers yet.": "Сè уште нема клиенти.",
    "Add service": "Додади услуга",
    "Inactive": "Неактивна",
    "Active": "Активна",
    "Delete": "Избриши",
    "Photo req.": "Фото?",
    "Actions": "Акции",
    "Drag to reorder": "Повлечи за преуредување",
    "Photo needed": "Потребна фотографија",
    "Add price item": "Додади ставка",
    "No price list items yet.": "Сè уште нема ставки во ценовникот.",
    "Working Hours": "Работно време",
    "Save working hours": "Зачувај работно време",
    "Blocked dates": "Блокирани датуми",
    "Add blocked date": "Додади блокиран датум",
    "No blocked dates.": "Нема блокирани датуми.",
    "Unavailable time blocks": "Недостапни блокови",
    "Add time block": "Додади блок",
    "No unavailable blocks.": "Нема недостапни блокови.",
    "Remove": "Отстрани",
    "Save policy": "Зачувај политика",
    "No bookings in this category.": "Нема термини во оваа категорија.",
    "No slots available": "Нема слободни термини",
    "The time %(time)s is no longer available. Please select another slot.": "Терминот %(time)s веќе не е достапен. Изберете друг.",
    "Edit booking": "Уреди термин",
    "Delete this booking permanently?": "Трајно избриши го терминот?",
    "Edit service": "Уреди услуга",
    "Delete this service?": "Избриши ја услугата?",
    "Reject this booking?": "Одбиј го терминот?",
    "Cancel this booking?": "Откажи го терминот?",
    "Mark as no-show?": "Означи како не се појави?",
    "Approve": "Одобри",
    "Reject": "Одбиј",
    "Mark completed": "Означи завршен",
    "Something went wrong. Please try again.": "Нешто тргна наопаку. Обидете се повторно.",
    "Add item": "Додади ставка",
    "Save changes": "Зачувај промени",
    "Edit customer": "Уреди клиент",
    "Delete this customer?": "Избриши го клиентот?",
    "Block time": "Блокирај време",
    "Edit blocked time": "Уреди блокирано време",
    "Remove this time block?": "Отстрани го блокот?",
    "Remove this blocked date?": "Отстрани го блокираниот датум?",
    "Blocked": "Блокирано",
    "Blocked %(start)s%(end)s": "Блокирано %(start)s%(end)s",
    "— Available": "— Достапно",
    "%(count)s appointment": "%(count)s термин",
    "%(count)s appointments": "%(count)s термини",
    "Cannot add bookings in the past.": "Не може да се додаваат термини во минатото.",
    "Copy message": "Копирај порака",
    "Call": "Повикај",
    "Save": "Зачувај",
    "Price": "Цена",
    "Duration": "Времетраење",
    "Status": "Статус",
    "Source": "Извор",
    "Owner note": "Белешка од сопственик",
    "Preferred contact": "Претпочитан контакт",
    "Start time": "Почеток",
    "Date": "Датум",
    "Online": "Онлајн",
    "Owner manual": "Рачно од сопственик",
    "Requested": "Побарано",
    "Email sent": "Е-пошта испратена",
    "Phone call": "Телефонски повик",
    "Only pending bookings can be approved or rejected here.": "Само термини на чекање може да се одобрат или одбијат тука.",
    "Booking approved. Email sent to customer.": "Терминот е одобрен. Е-пошта е испратена до клиентот.",
    "Booking approved. Customer has no email — use prepared message.": "Терминот е одобрен. Клиентот нема е-pошта — користете подготвена порака.",
    "Booking approved. Email could not be sent — use prepared message.": "Терминот е одобрен. Е-пошта не беше испратена — користете подготвена порака.",
    "Booking rejected. Email sent to customer.": "Терминот е одбиен. Е-пошта е испратена до клиентот.",
    "Booking rejected. Customer has no email — use prepared message.": "Терминот е одбиен. Клиентот нема е-pошта — користете подготвена порака.",
    "Booking rejected. Email could not be sent — use prepared message.": "Терминот е одбиен. Е-пошта не беше испратена — користете подготвена порака.",
    "Booking updated. Email sent.": "Терминот е ажуриран. Е-пошта е испратена.",
    " Use prepared message to notify customer.": " Користете подготвена порака за да го известите клиентот.",
    "Booking updated.": "Терминот е ажуриран.",
    "Booking updated successfully.": "Терминот е успешно ажуриран.",
    "Booking added successfully.": "Терминот е успешно додаден.",
    "Working hours saved.": "Работното време е зачувано.",
    "Could not save working hours. Check the times.": "Не можеше да се зачува работното време. Проверете ги времената.",
    "No booking policy found for this salon.": "Не е пронајдена политика за резервации.",
    "Booking policy saved.": "Политиката е зачувана.",
    "Could not save booking policy.": "Не можеше да се зачува политиката.",
    "Blocked date added.": "Блокираниот датум е додаден.",
    "Invalid blocked date.": "Невалиден блокиран датум.",
    "Blocked date removed.": "Блокираниот датум е отстранет.",
    "Unavailable time block added.": "Недостапниот блок е додаден.",
    "Could not add unavailable time block.": "Не можеше да се додаде блокот.",
    "Unavailable time block removed.": "Блокот е отстранет.",
    "Booking marked as completed.": "Терминот е означен како завршен.",
    "Booking marked as no-show.": "Терминот е означен како не се појави.",
    "Cannot cancel a completed or no-show booking.": "Не може да се откаже завршен термин или не се појави.",
    "Booking cancelled. Email sent to customer.": "Терминот е откажан. Е-пошта е испратена.",
    "Booking cancelled. Customer has no email — use prepared message.": "Терминот е откажан. Клиентот нема е-pошта — користете подготвена порака.",
    "Booking cancelled.": "Терминот е откажан.",
    "Booking deleted.": "Терминот е избришан.",
    "New booking request": "Ново барање за термин",
    "Appointment approved. Email sent to customer.": "Терминот е одобрен. Испратен е email до клиентот.",
    "Appointment approved. Customer did not provide an email.": "Терминот е одобрен. Клиентот нема внесено email.",
    "Appointment approved.": "Терминот е одобрен.",
    "Email could not be sent. Prepared message is available.": "Email не можеше да се испрати. Подготвената порака е достапна.",
    "Request declined. Email sent to customer.": "Барањето е одбиено. Испратен е email до клиентот.",
    "Request declined. Customer did not provide an email.": "Барањето е одбиено. Клиентот нема внесено email.",
    "Request declined.": "Барањето е одбиено.",
    "Appointment updated. Email sent to customer.": "Терминот е променет. Испратен е email до клиентот.",
    "Appointment updated. Customer did not provide an email.": "Терминот е променет. Клиентот нема внесено email.",
    "Appointment updated.": "Терминот е променет.",
    "Appointment cancelled. Email sent to customer.": "Терминот е откажан. Испратен е email до клиентот.",
    "Appointment cancelled. Customer did not provide an email.": "Терминот е откажан. Клиентот нема внесено email.",
    "Appointment cancelled.": "Терминот е откажан.",
    "Cancelled by customer": "Откажано од клиент",
    "Customer cancellation notice (hours)": "Одредба за откажување од клиент (часови)",
    "We received your booking request": "Го примивме вашето барање за термин",
    "Customer cancelled appointment": "Клиент откажа термин",
    "We sent a confirmation email with a link to view and manage your booking.": "Испративме email за потврда со линк за преглед и управување со вашиот термин.",
    "View / manage booking": "Преглед / управување со термин",
    "Your appointment": "Вашиот термин",
    "Your request is not confirmed yet. The salon will review it and contact you.": "Вашето барање сè уште не е потврдено. Салонот ќе го прегледа и ќе ве контактира.",
    "Your appointment is confirmed.": "Вашиот термин е потврден.",
    "Your booking request was declined.": "Вашето барање за термин е одбиено.",
    "This appointment was cancelled.": "Овој термин е откажан.",
    "This appointment was completed.": "Овој термин е завршен.",
    "This appointment was marked as a no-show.": "Овој термин е означен како не се појави.",
    "Appointment cancelled.": "Терминот е откажан.",
    "Thank you for letting us know. The salon has been notified.": "Ви благодариме што нè известивте. Салонот е известен.",
    "Cancel appointment?": "Откажи термин?",
    "Are you sure you want to cancel this appointment?": "Дали сте сигурни дека сакате да го откажете терминот?",
    "Yes, cancel appointment": "Да, откажи термин",
    "No, go back": "Не, врати се назад",
    "Reference photo attached": "Прикачена е референтна фотографија",
    "Salon rules": "Правила на салонот",
    "I understand:": "Разбирам дека:",
    "Cancellation": "Откажување",
    "You can cancel this appointment online.": "Можете да го откажете терминот онлајн.",
    "This appointment is too close for automatic cancellation (less than %(hours)s hours). Please contact the salon.": "Овој термин е премногу блиску за автоматско откажување (помалку од %(hours)s часа). Ве молиме контактирајте го салонот.",
    "This appointment is too close for automatic cancellation. Please contact the salon.": "Овој термин е премногу блиску за автоматско откажување. Ве молиме контактирајте го салонот.",
    "This appointment has already passed.": "Овој термин веќе помина.",
    "This appointment is already cancelled.": "Овој термин е веќе откажан.",
    "This booking request was declined by the salon.": "Ова барање е одбиено од салонот.",
    "This appointment was completed.": "Овој термин е завршен.",
    "This appointment was marked as a no-show.": "Овој термин е означен како не се појави.",
    "Cancellation is not available for this appointment.": "Откажувањето не е достапно за овој термин.",
    "This appointment cannot be cancelled.": "Овој термин не може да се откаже.",
    "Need help? Contact %(salon_name)s directly if you have questions about your appointment.": "Потребна ви е помош? Контактирајте го %(salon_name)s директно ако имате прашања за вашиот термин.",
    "Hello %(name)s,\n\nWe received your booking request.\n\nService: %(service)s\nDate and time: %(date)s at %(time)s\n\nYour appointment is not confirmed yet. The salon will review your request.\n\nYou can track your appointment here:\n%(manage_url)s": (
        "Здраво %(name)s,\n\n"
        "Го примивме вашето барање за термин.\n\n"
        "Услуга: %(service)s\n"
        "Датум и време: %(date)s во %(time)s\n\n"
        "Терминот сè уште не е потврден. Салонот ќе го прегледа барањето.\n\n"
        "Вашиот термин можете да го следите тука:\n"
        "%(manage_url)s"
    ),
    "Hello %(name)s,\n\nYour appointment on %(date)s at %(time)s has been cancelled.\n\nThank you for letting us know in time.": (
        "Здраво %(name)s,\n\n"
        "Вашиот термин за %(date)s во %(time)s е откажан.\n\n"
        "Ви благодариме што нè известивте навреме."
    ),
    "The customer %(name)s cancelled their appointment.\n\nService: %(service)s\nDate and time: %(date)s at %(time)s\nPhone: %(phone)s": (
        "Клиентот %(name)s го откажа терминот.\n\n"
        "Услуга: %(service)s\n"
        "Датум и време: %(date)s во %(time)s\n"
        "Телефон: %(phone)s"
    ),
    "Salon Scheduler test email": "Тест email од Salon Scheduler",
    "This is a test email from Salon Scheduler.\n\nIf you received this message, outgoing email is configured correctly.": (
        "Ова е тест email од Salon Scheduler.\n\n"
        "Ако ја примивте пораката, испраќањето на email е правилно конфигурирано."
    ),
    "Review in dashboard:": "Преглед во контролна табла:",
    "Missed appointment": "Пропуштен термин",
    "Request received": "Барањето е примено",
    "Your appointment is confirmed": "Вашиот термин е потврден",
    "Your appointment request was declined": "Вашето барање за термин е одбиено",
    "Your appointment was changed": "Вашиот термин е променет",
    "Your appointment was cancelled": "Вашиот термин е откажан",
    "Hello %(name)s,\n\nYour appointment for %(date)s at %(time)s has been confirmed.\n\nService: %(service)s\n\nWe look forward to seeing you.": (
        "Здраво %(name)s,\n\n"
        "Вашиот термин за %(date)s во %(time)s е потврден.\n\n"
        "Услуга: %(service)s\n\n"
        "Ве очекуваме."
    ),
    "Hello %(name)s,\n\nUnfortunately, the requested appointment for %(date)s at %(time)s is not available.\n\nPlease choose another time.": (
        "Здраво %(name)s,\n\n"
        "За жал, бараниот термин за %(date)s во %(time)s не е достапен.\n\n"
        "Ве молиме изберете друг термин."
    ),
    "Hello %(name)s,\n\nYour appointment has been changed to %(date)s at %(time)s.\n\nService: %(service)s\n\nWe look forward to seeing you.": (
        "Здраво %(name)s,\n\n"
        "Вашиот термин е променет на %(date)s во %(time)s.\n\n"
        "Услуга: %(service)s\n\n"
        "Ве очекуваме."
    ),
    "Hello %(name)s,\n\nYour appointment on %(date)s at %(time)s has been cancelled.\n\nThank you for your understanding.": (
        "Здраво %(name)s,\n\n"
        "Вашиот термин за %(date)s во %(time)s е откажан.\n\n"
        "Ви благодариме на разбирањето."
    ),
    "You have a new booking request.\n\nCustomer: %(name)s\nPhone: %(phone)s\nService: %(service)s\nDate and time: %(date)s at %(time)s": (
        "Имате ново барање за термин.\n\n"
        "Клиент: %(name)s\n"
        "Телефон: %(phone)s\n"
        "Услуга: %(service)s\n"
        "Датум и време: %(date)s во %(time)s"
    ),
    "Hello %(name)s,\n\nYou did not attend your appointment on %(date)s at %(time)s.\n\nIf you would like to book again, please contact us. — %(salon)s": (
        "Здраво %(name)s,\n\n"
        "Не се појавивте на терминот за %(date)s во %(time)s.\n\n"
        "Ако сакате повторно да закажете, контактирајте нè. — %(salon)s"
    ),
    "Hello %(name)s,\n\nYour appointment request for %(date)s at %(time)s has been received.\n\nWe will contact you soon. — %(salon)s": (
        "Здраво %(name)s,\n\n"
        "Вашето барање за %(date)s во %(time)s е примено.\n\n"
        "Ќе ве контактираме наскоро. — %(salon)s"
    ),
    "Invalid username or password.": "Невалидно корисничко име или лозинка.",
    # dynamic view messages
    "%(field)s: %(error)s": "%(field)s: %(error)s",
    "Service updated successfully.": "Услугата е успешно ажурирана.",
    "Service added successfully.": "Услугата е успешно додадена.",
    "Could not save service. Check the form.": "Не можеше да се зачува услугата. Проверете го формуларот.",
    "Service deleted.": "Услугата е избришана.",
    "Price item saved.": "Ставката е зачувана.",
    "Name and price are required.": "Името и цената се задолжителни.",
    "Price item deleted.": "Ставката е избришана.",
    "Customer updated successfully.": "Клиентот е успешно ажуриран.",
    "Customer added successfully.": "Клиентот е успешно додаден.",
    "Could not save customer.": "Не можеше да се зачува клиентот.",
    "Cannot delete a customer with existing bookings. Remove bookings first.": "Не може да се избрише клиент со постоечки термини. Прво отстранете ги термините.",
    "Customer deleted.": "Клиентот е избришан.",
    "Blocked date saved.": "Блокираниот датум е зачуван.",
    "Time block updated.": "Временскиот блок е ажуриран.",
    "Time block added.": "Временскиот блок е додаден.",
    "Could not save unavailable time block.": "Не можеше да се зачува недостапниот блок.",
    "Unknown action.": "Непозната акција.",
    "SMS": "SMS",
    "Viber": "Viber",
    "WhatsApp": "WhatsApp",
    "Instagram": "Instagram",
    "Messenger": "Messenger",
    "Phone": "Телефон",
    "In person": "Лично",
    "Edited": "Уредено",
    "Open": "Отворено",
    "Block": "Блокирај",
    "Block day": "Блокирај ден",
    "No price items yet. Add the first one below.": "Сè уште нема ставки. Додадете ја првата подолу.",
    "No time blocks.": "Нема блокирани термини.",
    "Scheduling rules": "Правила за закажување",
    "Booking settings": "Поставки за резервации",
    "Salon rules shown to customers": "Правила на салонот за клиентите",
    "Shown on the booking form. Each line is a separate rule.": "Се прикажуваат на формата за резервација. Секој ред е посебно правило.",
    "Each line is a separate rule. Customers see the Macedonian or English version based on their language.": "Секој ред е посебно правило. Клиентите ја гледаат македонската или англиската верзија според јазикот.",
    "Salon rules (Macedonian)": "Правила на салонот (македонски)",
    "Salon rules (English)": "Правила на салонот (англиски)",
    "Available variables:": "Достапни променливи:",
    "customer first name": "име на клиент",
    "date": "датум",
    "time": "време",
    "salon name": "име на салон",
    "Save all policy settings": "Зачувај ги сите поставки",
    "Save booking": "Зачувај термин",
    "Save service": "Зачувај услуга",
    "Save customer": "Зачувај клиент",
    "Save block": "Зачувај блок",
    "Save blocked date": "Зачувај блокиран датум",
    "Block full day": "Блокирај цел ден",
    "Prepared message": "Подготвена порака",
    "Minimum notice days": "Минимален рок однапред (дена)",
    "Maximum booking window days": "Максимален прозорец (дена)",
    "Allow same day booking": "Дозволи резервација ист ден",
    "Allow next day booking": "Дозволи резервација следен ден",
    "Auto approve bookings": "Автоматско одобрување",
    "Late arrival limit minutes": "Лимит за доцнење (минути)",
    "Reminder hours before": "Потсетник (часови однапред)",
    "Pending holds slot": "На чекање го држи терминот",
    "Max appointments per day": "Макс. термини дневно",
    "Slot interval minutes": "Интервал на термини (минути)",
    "Buffer minutes between bookings": "Бафер меѓу термини (минути)",
    "Salon rules": "Правила на салонот",
    "I understand:": "Разбирам дека:",
    "Approved message": "Порака за одобрување",
    "Rejected message": "Порака за одбивање",
    "Cancelled message": "Порака за откажување",
    "Edited/rescheduled message": "Порака за промена",
    "No-show message": "Порака за не се појави",
    "Pending/received message": "Порака за примено барање",
    "Reminder message": "Порака за потсетник",
    "Duration (min)": "Времетраење (мин)",
    "Sort order": "Редослед",
    "Description": "Опис",
    "Extra duration note": "Белешка за дополнително време",
    "Start": "Почеток",
    "End": "Крај",
    "Reason (optional)": "Причина (опционално)",
    "Clear form": "Исчисти формулар",
    "Sub-service name": "Име на под-услуга",
    "Section / Group": "Секција / група",
    "Leave blank if not in a group": "Остави празно ако не е во група",
    "Customer must upload a reference photo when booking this sub-service": "Клиентот мора да прикачи референтна фотографија при резервација",
    "Price item —": "Ставка —",
    "Delete service": "Избриши услуга",
    "Delete this service? This cannot be undone.": "Избриши ја услугата? Ова не може да се врати.",
    " Email sent.": " Е-пошта е испратена.",
    # email subjects & prepared messages
    "Your appointment is confirmed — %(salon)s": "Вашиот термин е потврден — %(salon)s",
    "Unfortunately the appointment is unavailable — %(salon)s": "За жал терминот не е достапен — %(salon)s",
    "Your appointment was cancelled — %(salon)s": "Вашиот термин е откажан — %(salon)s",
    "Your appointment was changed — %(salon)s": "Вашиот термин е променет — %(salon)s",
    "Missed appointment — %(salon)s": "Пропуштен термин — %(salon)s",
    "Request received — %(salon)s": "Барањето е примено — %(salon)s",
    "Appointment information — %(salon)s": "Информација за термин — %(salon)s",
    "New booking request — %(salon)s": "Ново барање за термин — %(salon)s",
    "Hello %(name)s, your appointment on %(date)s at %(time)s has been confirmed. We look forward to seeing you! — %(salon)s": (
        "Здраво %(name)s, вашиот термин за %(date)s во %(time)s е потврден. Ве очекуваме. — %(salon)s"
    ),
    "Hello %(name)s, unfortunately the appointment on %(date)s at %(time)s is not available. Please choose another time. — %(salon)s": (
        "Здраво %(name)s, за жал терминот за %(date)s во %(time)s не е достапен. Ве молиме изберете друг термин. — %(salon)s"
    ),
    "Hello %(name)s, your appointment on %(date)s at %(time)s has been cancelled. Thank you for your understanding. — %(salon)s": (
        "Здраво %(name)s, вашиот термин за %(date)s во %(time)s е откажан. Ви благодариме на разбирањето. — %(salon)s"
    ),
    "Hello %(name)s, your appointment has been changed to %(date)s at %(time)s. We look forward to seeing you! — %(salon)s": (
        "Здраво %(name)s, вашиот термин е променет на %(date)s во %(time)s. Ве очекуваме. — %(salon)s"
    ),
    "Hello %(name)s, you did not attend your appointment on %(date)s at %(time)s. If you would like to book again, please contact us. — %(salon)s": (
        "Здраво %(name)s, не се појавивте на терминот за %(date)s во %(time)s. Ако сакате повторно да закажете, контактирајте нè. — %(salon)s"
    ),
    "Hello %(name)s, your appointment request for %(date)s at %(time)s has been received. We will contact you soon. — %(salon)s": (
        "Здраво %(name)s, вашето барање за %(date)s во %(time)s е примено. Ќе ве контактираме наскоро. — %(salon)s"
    ),
    "Hello %(name)s, this is a reminder that you have an appointment on %(date)s at %(time)s. We look forward to seeing you! — %(salon)s": (
        "Здраво %(name)s, потсетник: имате термин на %(date)s во %(time)s. Ве очекуваме! — %(salon)s"
    ),
    "A new booking request was submitted.\n\nCustomer: %(customer)s\nPhone: %(phone)s\nInstagram: %(instagram)s\nService: %(service)s\nDate: %(date)s\nTime: %(time)s\nStatus: Pending (awaiting your approval)\n\nReview in dashboard: %(dashboard)s\n": (
        "Ново барање за термин.\n\n"
        "Клиент: %(customer)s\n"
        "Телефон: %(phone)s\n"
        "Instagram: %(instagram)s\n"
        "Услуга: %(service)s\n"
        "Датум: %(date)s\n"
        "Време: %(time)s\n"
        "Статус: На чекање (чека ваше одобрување)\n\n"
        "Преглед во контролна табла: %(dashboard)s\n"
    ),
    "You already have a booking request waiting for approval. Please wait for the salon to respond or cancel your existing request.": (
        "Веќе имате барање за термин кое чека одобрување. "
        "Ве молиме почекајте одговор од салонот или откажете го постоечкото барање."
    ),
    "You already have the maximum number of active appointments. To book a new one, please cancel or complete an existing appointment.": (
        "Веќе го имате максималниот број активни термини. "
        "За нов термин, ве молиме откажете или завршете постоечки термин."
    ),
    "You have sent too many requests in a short time. Please try again later.": (
        "Испративте премногу барања за кратко време. Ве молиме обидете се повторно подоцна."
    ),
    "Your request could not be sent. Please contact the salon.": (
        "Вашето барање не може да биде испратено. Ве молиме контактирајте го салонот."
    ),
    "Something went wrong. Please check your details and choose an available time.": (
        "Нешто тргна наопаку. Проверете ги податоците и изберете слободен термин."
    ),
    "This customer already has active appointment(s).": (
        "Клиентот веќе има активен/и термин/и."
    ),
    "The image is too large. Please upload an image up to %(size)s MB.": (
        "Сликата е преголема. Ве молиме прикачете слика до %(size)s MB."
    ),
    "Invalid image format. Allowed formats are JPG, PNG, and WEBP.": (
        "Невалиден формат на слика. Дозволени се JPG, PNG и WEBP."
    ),
    "A reference photo is required for this service.": (
        "Потребна е референтна фотографија за оваа услуга."
    ),
    "Max pending bookings per customer": "Макс. барања на чекање по клиент",
    "Max active future bookings per customer": "Макс. активни идни термини по клиент",
    "Booking rate limit per IP per hour": "Лимит на барања по IP на час",
    "Booking rate limit per email per day": "Лимит на барања по email на ден",
    "Booking rate limit per phone per day": "Лимит на барања по телефон на ден",
    "Enable honeypot protection": "Honeypot заштита",
    "Max reference photo size (MB)": "Макс. големина на фотографија (MB)",
    "Anti-abuse": "Anti-abuse",
    "The image is too large. Please upload an image up to %(max)s MB.": (
        "Сликата е преголема. Ве молиме прикачете слика до %(max)s MB."
    ),
}


def main():
    for lang in ("mk", "en"):
        locale_dir = BASE / "locale" / lang / "LC_MESSAGES"
        locale_dir.mkdir(parents=True, exist_ok=True)
        po_path = locale_dir / "django.po"
        mo_path = locale_dir / "django.mo"

        po = polib.POFile()
        po.metadata = {
            "Project-Id-Version": "Salon Scheduler",
            "Report-Msgid-Bugs-To": "",
            "POT-Creation-Date": "2026-06-21 12:00+0000",
            "PO-Revision-Date": "2026-06-21 12:00+0000",
            "Last-Translator": "Salon Scheduler",
            "Language-Team": "Macedonian" if lang == "mk" else "English",
            "Language": lang,
            "MIME-Version": "1.0",
            "Content-Type": "text/plain; charset=UTF-8",
            "Content-Transfer-Encoding": "8bit",
            "Plural-Forms": "nplurals=2; plural=(n % 10 == 1 && n % 100 != 11) ? 0 : 1;",
        }

        for msgid, mk_text in sorted(TRANSLATIONS.items()):
            msgstr = mk_text if lang == "mk" else msgid
            po.append(polib.POEntry(msgid=msgid, msgstr=msgstr))

        po.save(str(po_path))
        po.save_as_mofile(str(mo_path))
        print(f"Wrote {po_path} ({len(po)} entries)")
        print(f"Wrote {mo_path}")


if __name__ == "__main__":
    main()
