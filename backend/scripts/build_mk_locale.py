"""Build locale/mk/LC_MESSAGES/django.po and django.mo without GNU gettext tools."""
from pathlib import Path

import polib

BASE = Path(__file__).resolve().parent.parent
LOCALE_DIR = BASE / "locale" / "mk" / "LC_MESSAGES"

# English msgid -> Macedonian msgstr
TRANSLATIONS = {
    # base.html
    "Salon Scheduler": "Vremio",
    "Vremio": "Vremio",
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
    "There is not enough available time for the selected services together. Please choose another date or book the services separately.": "Нема доволно слободно време за избраните услуги заедно. Ве молиме изберете друг датум или закажете ги услугите одделно.",
    "Select one or more services to continue.": "Изберете една или повеќе услуги за да продолжите.",
    "Could not load times. Please try again.": "Не можеше да се вчитаат термините. Обидете се повторно.",
    "Only one service is allowed per booking. Your previous selection was replaced.": "Дозволена е само 1 услуга по резервација. Претходниот избор е заменет.",
    "Only images are allowed (JPG, PNG, WebP). Choose another format.": "Дозволени се само слики (JPG, PNG, WebP). Одбери друг формат.",
    "The image is too large. Maximum allowed size is %(max)s MB.": "Сликата е преголема. Максималната дозволена големина е %(max)s MB.",
    "(required)": "(задолжително)",
    "(recommended)": "(препорачано)",
    "(optional)": "(опционално)",
    "Via": "Преку",
    "min": "мин",
    "Total": "Вкупно",
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
    "Message to salon (optional)": "Порака до салонот (опционално)",
    "Customer note": "Порака од клиент",
    "Customer note:": "Порака од клиент:",
    "Any notes for the salon...": "Белешки за салонот...",
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
    "Photo attached": "Има прикачена слика",
    "View reference photo": "Погледни референтна слика",
    "Show photo": "Прикажи слика",
    "Delete photo": "Избриши слика",
    "Block customer": "Блокирај клиент",
    "Blocked customers": "Блокирани клиенти",
    "Customers who cannot submit new booking requests.": "Клиенти кои не можат да испратат нови барања за термин.",
    "Search by name, phone, or email…": "Пребарај по име, телефон или email…",
    "Date blocked": "Датум на блокирање",
    "Reason": "Причина",
    "Status": "Статус",
    "Unblock": "Одблокирај",
    "Blocked customer": "Блокиран клиент",
    "Booking reference": "Референца на термин",
    "Choose a reason…": "Изберете причина…",
    "Notes": "Белешки",
    "optional": "опционално",
    "Additional details for your records…": "Дополнителни детали за вашите записи…",
    "This customer will no longer be able to submit booking requests to your business until unblocked.": "Овој клиент повеќе нема да може да испраќа барања за термин додека не биде одблокиран.",
    "Customer actions": "Акции за клиент",
    "Call customer": "Повикај клиент",
    "Email customer": "Email до клиент",
    "Already blocked": "Веќе блокиран",
    "Customer unblocked.": "Клиентот е одблокиран.",
    "Block reason updated.": "Причината за блокирање е ажурирана.",
    "Unblock this customer? They will be able to book again.": "Дали да се одблокира овој клиент? Повторно ќе може да закажува.",
    "Edit block reason": "Уреди причина за блокирање",
    "Audit log": "Дневник на промени",
    "Unblocked": "Одблокиран",
    "No blocked customers.": "Нема блокирани клиенти.",
    "No blocked customers match your search.": "Нема блокирани клиенти што одговараат на пребарувањето.",
    "Edit reason": "Уреди причина",
    "Spam": "Спам",
    "Fake bookings": "Лажни резервации",
    "Repeated no-shows": "Повторени непojавувања",
    "Repeated cancellations": "Повторени откажувања",
    "Inappropriate photos": "Непримерни слики",
    "Harassment": "Вознемирување",
    "Other": "Друго",
    "Delete this reference photo?": "Дали да се избрише референтната слика?",
    "Block this customer from booking?": "Дали да се блокира овој клиент од закажување?",
    "Customer blocked.": "Клиентот е блокиран.",
    "No photo attached": "Нема прикачена слика",
    "No photo attached.": "Нема прикачена слика.",
    "Photo removed.": "Сликата е отстранета.",
    "Upload only a photo related to the service. Inappropriate images will be removed and the customer may be blocked.": "Прикачете само слика поврзана со услугата. Непримерни слики ќе бидат отстранети и клиентот може да биде блокиран.",
    "Check your email": "Проверете го вашиот email",
    "We sent you a verification link. Click it to complete your booking request.": "Ви испративме линк за потврда. Кликнете на него за да го завршите барањето за термин.",
    "If you do not see the email within a few minutes, check your spam or junk folder.": "Ако не ја гледате пораката во неколку минути, проверете ја папката за спам.",
    "Your appointment is not confirmed yet. The salon will review your request after you verify your email.": "Терминот сè уште не е потврден. Салонот ќе го прегледа барањето откако ќе ја потврдите email адресата.",
    "Resend verification email": "Испрати повторно email за потврда",
    "Please wait a minute before requesting another verification email.": "Почекајте една минута пред повторно да побарате email за потврда.",
    "We sent another verification email. Please check your inbox and spam folder.": "Испративме уште еден email за потврда. Проверете ја поштата и папката за спам.",
    "We could not send the verification email. Use the button below to try again, or contact the salon.": "Не можевме да го испратиме email-от за потврда. Користете го копчето подолу за повторен обид или контактирајте го салонот.",
    "Verification failed": "Потврдата не успеа",
    "The verification link has expired. Please submit a new booking request.": "Линкот за потврда е истечен. Ве молиме испратете ново барање за термин.",
    "The selected time slot is no longer available. Please choose another time.": "Избраниот термин повеќе не е достапен. Ве молиме изберете друг термин.",
    "This verification link is invalid or has already been used.": "Овој линк за потврда е неважечки или веќе е искористен.",
    "Something went wrong. Please submit a new booking request.": "Нешто тргна наопаку. Ве молиме испратете ново барање за термин.",
    "Confirm your email to complete your booking request": "Потврдете го вашиот email за да го завршите барањето за термин",
    "Require email verification for online bookings": "Задолжителна email потврда за онлајн резервации",
    "Email verification link expiry (minutes)": "Важност на линкот за потврда (минути)",
    "Require SMS verification for online bookings": "Задолжителна SMS потврда за онлајн резервации",
    "SMS verification code expiry (minutes)": "Важност на SMS кодот за потврда (минути)",
    "Send transactional SMS to customers": "Испраќај трансакциски SMS до клиентите",
    "Verify your phone": "Потврдете го телефонот",
    "Enter verification code": "Внесете код за потврда",
    "We could not send the verification SMS. Use the button below to try again, or contact the salon.": (
        "Не можевме да го испратиме SMS-от за потврда. Користете го копчето подолу за повторен обид или контактирајте го салонот."
    ),
    "We sent a 6-digit code to your phone. Enter it below to complete your booking request.": (
        "Испративме 6-цифрен код на вашиот телефон. Внесете го подолу за да го завршите барањето за термин."
    ),
    "Verification code": "Код за потврда",
    "Verify and submit request": "Потврди и испрати барање",
    "Your appointment is not confirmed yet. The salon will review your request after you verify your phone.": (
        "Терминот сè уште не е потврден. Салонот ќе го прегледа барањето откако ќе го потврдите телефонот."
    ),
    "Resend verification code": "Испрати повторно код за потврда",
    "Please wait a minute before requesting another verification code.": (
        "Почекајте една минута пред повторно да побарате код за потврда."
    ),
    "We sent a new verification code to your phone.": "Испративме нов код за потврда на вашиот телефон.",
    "We could not send the verification SMS right now. Please try again in a few minutes or contact the salon.": (
        "Не можевме да го испратиме SMS-от за потврда во моментов. Обидете се повторно за неколку минути или контактирајте го салонот."
    ),
    "The verification code has expired. Please submit a new booking request.": (
        "Кодот за потврда е истечен. Ве молиме испратете ново барање за термин."
    ),
    "The code is incorrect. Please try again.": "Кодот е неточен. Обидете се повторно.",
    "Your verification code for %(salon)s is %(code)s. Valid for %(minutes)s minutes. Do not share this code.": (
        "Вашиот код за потврда за %(salon)s е %(code)s. Важи %(minutes)s минути. Не го споделувајте овој код."
    ),
    "You already started a booking request. Please enter the SMS verification code we sent to your phone before submitting again.": (
        "Веќе започнавте барање за термин. Внесете го SMS кодот за потврда што го испративме на вашиот телефон пред повторно да испратите барање."
    ),
    "Phone verified": "Телефонот е потврден",
    "SMS sent": "SMS испратен",
    "Awaiting email verification": "Се чека email потврда",
    "Open full size": "Отвори целосна големина",
    "Welcome back — %(salon_name)s": "Добредојде — %(salon_name)s",
    "Pending requests": "Барања на чекање",
    "Approved bookings scheduled for today.": "Одобрени термини закажани за денес.",
    "Review new requests and approve or reject.": "Прегледај ги новите барања и одобри или одбиј.",
    "View": "Погледни",
    "Online booking, made simple.": "Онлајн резервации, едноставно.",
    "Footer navigation": "Подножје навигација",
    "Made by": "Направено од",
    # home.html — Vremio platform landing
    "Vremio — Bookings & Reservations": "Vremio — термини и резервации",
    "Menu": "Мени",
    "Browse businesses": "Пребарај бизниси",
    "For business owners": "За сопственици на бизниси",
    "Owner sign in": "Најава за сопственици",
    "Booking platform": "Платформа за закажување",
    "Vremio — appointments and reservations in one place": "Vremio — термини и резервации на едно место",
    "Find a service, choose an available time slot, and send a booking request. Vremio helps local businesses manage appointments quickly, clearly, and professionally.": (
        "Пронајдете услуга, изберете слободен термин и испратете барање за закажување. "
        "Vremio им помага на локалните бизниси да управуваат со термини брзо, јасно и професионално."
    ),
    "Book appointment": "Закажи термин",
    "I have a business": "Имам бизнис",
    "Directory": "Директориум",
    "Businesses on Vremio": "Бизниси на Vremio",
    "Search and book appointments at local businesses.": "Пребарајте и закажете термин кај локални бизниси.",
    "Search by business name or city…": "Пребарај по име на бизнис или град…",
    "Search": "Пребарај",
    "Category": "Категорија",
    "All": "Сите",
    "Salons": "Салони",
    "Barbershops": "Бербери",
    "Sports venues": "Спортски терени",
    "Fitness / gyms": "Фитнес/сали",
    "Services": "Услуги",
    "We couldn't find a business matching your search.": "Не најдовме бизнис според вашето пребарување.",
    "Does your business run on appointments?": "Дали вашиот бизнис работи со термини?",
    "Vremio helps you organize appointments, clients, and working hours in one place — with fewer messages and fewer mistakes.": (
        "Vremio ви помага да ги организирате термините, клиентите и работното време на едно место — "
        "со помалку пораки и помалку грешки."
    ),
    "Online booking requests": "Онлајн барања за термин",
    "Owner dashboard and calendar": "Контролна табла и календар",
    "Approve, reject, and edit bookings": "Одобрување, одбивање и уредување на термини",
    "Working hours and unavailable times": "Работно време и недостапни термини",
    "Customer details and reference photos": "Податоци за клиенти и референтни фотографии",
    "Email notifications and reminders": "Email известувања и потсетници",
    "I want Vremio for my business": "Сакам Vremio за мојот бизнис",
    "Still scheduling through messages?": "Дали вашиот бизнис сè уште закажува преку пораки?",
    "Instagram, Viber, and Messenger are hard to track. Vremio gives you a clear calendar and structured booking requests.": (
        "Instagram, Viber и Messenger се тешки за следење. Vremio ви дава јасен календар и структурирани барања за термин."
    ),
    "Request access": "Побарај пристап",
    "How it works": "Како функционира",
    "Simple for everyone": "Едноставно за сите",
    "For customers": "За клиенти",
    "Choose a business": "Изберете бизнис",
    "Choose a service and time slot": "Изберете услуга и термин",
    "Send a request and wait for confirmation": "Испратете барање и почекајте потврда",
    "For business owners": "За сопственици",
    "Set up services and working hours": "Поставете услуги и работно време",
    "Receive booking requests": "Примајте барања за термин",
    "Manage calendar and clients": "Управувајте со календар и клиенти",
    "Supported businesses": "Поддржани бизниси",
    "Vremio works for many types of local businesses": "Vremio работи за многу типови локални бизниси",
    "Beauty salons": "Салони за убавина",
    "Hair salons": "Фризерски салони",
    "Massage & physiotherapy": "Масажа и физиотерапија",
    "Sports halls": "Спортски сали",
    "School gyms": "Училишни спортски сали",
    "Courts & pitches": "Терени",
    "Car wash & detailing": "Авто услуги",
    "Private lessons": "Приватни часови",
    "Rentable rooms & spaces": "Простории за изнајмување",
    "Get started": "Започнете",
    "Want Vremio for your business?": "Сакате Vremio за вашиот бизнис?",
    "If your business works with appointments or reservations, contact us for access and profile setup.": (
        "Ако вашиот бизнис работи со термини или резервации, контактирајте нè за пристап и поставување на вашиот профил."
    ),
    "Send email": "Испрати email",
    "Contact email will be added soon.": "Контакт email ќе биде додаден наскоро.",
    "A modern booking platform for local businesses and services.": "Модерна платформа за закажување за локални бизниси и услуги.",
    "Beauty salon": "Салон за убавина",
    "Barbershop": "Берберница",
    "Sports venue": "Спортски терен",
    "Fitness / gym": "Фитнес / сала",
    "Other": "Друго",
    # legal / compliance pages
    "Privacy Policy": "Политика за приватност",
    "Terms of Use": "Услови за користење",
    "Booking Rules": "Правила за закажување",
    "Photo Policy": "Политика за фотографии",
    "Photo Upload Policy": "Политика за прикачување фотографии",
    "Contact": "Контакт",
    "Contact and data requests": "Контакт и барања за податоци",
    "Contact and Data Requests": "Контакт и барања за податоци",
    "Owner Pilot Terms": "Услови за пилот — сопственици",
    "Business owner pilot terms": "Услови за пилот за сопственици на бизнис",
    "Legal links": "Правни линкови",
    "Back to home": "Назад на почетна",
    "Last updated: %(date)s": "Последна измена: %(date)s",
    "This page is a draft for the Vremio private pilot. It is not legal advice and has not been reviewed by a lawyer.": (
        "Оваа страница е нацрт за приватниот Vremio пилот. Не претставува правен совет и не е прегледана од адвокат."
    ),
    "Who operates Vremio": "Кој управува со Vremio",
    "Vremio is a booking and reservation platform for local businesses. The platform is operated by the Vremio project team. The business listed on a booking page (for example a salon, barber, or sports venue) provides the actual service.": (
        "Vremio е платформа за закажување и резервации за локални бизниси. Платформата ја управува тимот на Vremio. "
        "Бизнисот наведен на страницата за резервација (на пр. салон, берберница или спортски терен) ја обезбедува вистинската услуга."
    ),
    "What data we may process": "Кои податоци може да ги обработуваме",
    "Customer name and surname": "Име и презиме на клиентот",
    "Instagram username or preferred contact method": "Instagram корисничко име или претпочитан начин на контакт",
    "Selected service, date, and time": "Избрана услуга, датум и време",
    "Booking status and history": "Статус и историја на резервацијата",
    "Uploaded reference photos (when required or provided)": "Прикачени референтни фотографии (кога се задолжителни или доставени)",
    "Email verification and manage-booking tokens": "Email верификација и токени за управување со резервација",
    "Technical and security logs (for example IP address for rate limiting and abuse prevention)": (
        "Технички и безбедносни записи (на пр. IP адреса за ограничување на барања и спречување злоупотреба)"
    ),
    "Business owner account data (username, email, password hash)": "Податоци за сметка на сопственик (корисничко име, email, хеш на лозинка)",
    "Why we process data": "Зошто ги обработуваме податоците",
    "Creating and managing booking requests": "Креирање и управување со барања за резервација",
    "Verifying customer email addresses": "Потврдување на email адреси на клиенти",
    "Sending notifications to customers and business owners": "Испраќање известувања до клиенти и сопственици",
    "Preventing abuse, spam, and duplicate bookings": "Спречување злоупотреба, спам и дупликат резервации",
    "Showing booking details to the correct business owner": "Приказ на детали за резервација на соодветниот сопственик",
    "Improving security and reliability of the platform": "Подобрување на безбедноста и доверливоста на платформата",
    "Reference photos": "Референтни фотографии",
    "Uploaded photos are used only for the booking or service request. They are not public. They should be visible only to the logged-in business owner and platform administrators who need access for support or security.": (
        "Прикачените фотографии се користат само за барањето за резервација/услуга. Не се јавни. "
        "Треба да бидат видливи само за најавениот сопственик и администратори на платформата кога е потребно за поддршка или безбедност."
    ),
    "Inappropriate or unrelated images may be deleted. Abusive customers may be blocked.": (
        "Непримерни или нерелевантни слики може да бидат избришани. Клиенти кои злоупотребуваат може да бидат блокирани."
    ),
    "Email messages": "Email пораки",
    "Vremio may send transactional emails related to your booking, such as:": "Vremio може да испраќа трансакциски email пораки поврзани со вашата резервација, како:",
    "Booking request received": "Примено барање за резервација",
    "Booking approved, rejected, edited, or cancelled": "Резервација одобрена, одбиена, изменета или откажана",
    "Password reset for business owners": "Ресетирање на лозинка за сопственици",
    "Owner notifications about new bookings": "Известувања до сопственик за нови резервации",
    "Vremio does not send marketing or newsletter emails unless a separate explicit opt-in is added in the future.": (
        "Vremio не испраќа маркетинг или newsletter email освен ако во иднина не се додаде посебна јасна согласност."
    ),
    "Your rights": "Вашите права",
    "You may request correction or deletion of your personal data by contacting Vremio or the business where you booked. We will handle reasonable requests manually during the pilot period.": (
        "Можете да побарате исправка или бришење на вашите лични податоци со контакт на Vremio или на бизнисот каде што резervиравте. "
        "Разумни барања ќе ги обработуваме рачно за време на пилотот."
    ),
    "Retention": "Задржување на податоци",
    "Booking data is kept as long as needed to operate the service, support the business owner, and meet reasonable record-keeping needs. Data may be deleted or anonymized when no longer required.": (
        "Податоците за резервации се чуваат колку што е потребно за работа на услугата, поддршка на сопственикот и разумни евиденциски потреби. "
        "Податоците може да се избришат или анонимизираат кога повеќе не се потребни."
    ),
    "About Vremio": "За Vremio",
    "Vremio is a booking and reservation platform. It helps customers send appointment requests and helps business owners manage them. The listed business provides the actual service — not Vremio.": (
        "Vremio е платформа за закажување и резервации. Им помага на клиентите да испратат барања за термин и на сопствениците да ги управуваат. "
        "Наведениот бизнис ја обезбедува вистинската услуга — не Vremio."
    ),
    "Bookings and approval": "Резервации и одобрување",
    "A booking submitted through Vremio is a request, not a confirmed appointment, unless the business has enabled automatic approval.": (
        "Резервација испратена преку Vremio е барање, не потврден термин, освен ако бизнисот не вклучил автоматско одобрување."
    ),
    "The business owner may approve or reject requests.": "Сопственикот може да ги одобри или одбие барањата.",
    "Availability shown online may change if another booking is accepted or the schedule is updated.": (
        "Достапноста прикажана онлајн може да се промени ако друга резервација биде прифатена или распоредот се ажурира."
    ),
    "Customer responsibilities": "Обврски на клиентот",
    "Provide accurate contact information.": "Да се внесат точни контакт податоци.",
    "Use the platform honestly and do not abuse booking limits.": "Да се користи платформата искрено и без злоупотреба на лимитите.",
    "Do not upload inappropriate, unrelated, or illegal images.": "Да не се прикачуваат непримерни, нерелевантни или незаконски слики.",
    "Follow the booking rules of the business you selected.": "Да се почитуваат правилата за закажување на избраниот бизнис.",
    "Business responsibilities": "Обврски на бизнисот",
    "Each business is responsible for service quality, prices, appointment handling, and communication with its customers. Vremio provides the software platform only.": (
        "Секој бизнис е одговорен за квалитет на услугата, цени, управување со термини и комуникација со клиентите. Vremio обезбедува само софтверската платформа."
    ),
    "Platform changes and availability": "Промени и достапност на платформата",
    "Vremio may be updated, improved, or temporarily unavailable during maintenance. During the private pilot, features may change as the system is tested with real bookings.": (
        "Vremio може да се ажурира, подобрува или привремено да не биде достапен за време на одржување. "
        "За време на приватниот пилот, функциите може да се менуваат додека системот се тестира со вистински резервации."
    ),
    "Abuse and blocking": "Злоупотреба и блокирање",
    "Vremio or the business owner may block users who submit fake bookings, abusive content, or repeated misuse of the system.": (
        "Vremio или сопственикот може да блокираат корисници кои испраќаат лажни резервации, непримерна содржина или повторена злоупотреба."
    ),
    "These are the default customer booking rules for Vremio. An individual business may add additional rules on its booking page.": (
        "Ова се стандардните правила за закажување на Vremio. Поединечен бизнис може да додаде дополнителни правила на својата страница."
    ),
    "The appointment is not confirmed until it is approved by the business.": "Терминот не е потврден додека не биде одобрен од бизнисот.",
    "Enter accurate contact details so the business can reach you.": "Внесете точни контакт податоци за да може бизнисот да ве контактира.",
    "If you cannot attend, cancel the appointment in time according to the business rules.": "Доколку не можете да дојдете, откажете го терминот навреме според правилата на бизнисот.",
    "Arriving late may result in cancellation of the appointment.": "Доцнење може да резултира со откажување на терминот.",
    "Inappropriate images or abuse of the system may lead to blocking.": "Непримерни слики или злоупотреба може да доведат до блокирање.",
    "Related policies": "Поврзани политики",
    "You may upload only images related to the requested service (for example nail design reference or medical pedicure context).": (
        "Можете да прикачите само слики поврзани со бараната услуга (на пр. референца за дизајн на нокти или медицински педикир)."
    ),
    "Inappropriate, unrelated, or 18+ images are not allowed.": "Непримерни, нерелевантни или 18+ слики не се дозволени.",
    "Uploaded images are used only for the booking request.": "Прикачените слики се користат само за барањето за резервација.",
    "Uploaded images are visible only to the logged-in business owner and platform administrators who need access for support or security.": (
        "Прикачените слики се видливи само за најавениот сопственик и администратори на платформата кога е потребно."
    ),
    "The business owner or administrator may delete inappropriate images.": "Сопственикот или администраторот може да избрише непримерни слики.",
    "Customers who upload abusive content may be blocked from future bookings.": "Клиенти кои прикачуваат непримерна содржина може да бидат блокирани.",
    "Allowed formats and size": "Дозволени формати и големина",
    "Allowed formats: JPG, JPEG, PNG, WEBP.": "Дозволени формати: JPG, JPEG, PNG, WEBP.",
    "Maximum file size: 5 MB per image (unless the business configures a different limit).": "Максимална големина: 5 MB по слика (освен ако бизнисот не постави друг лимит).",
    "For questions, correction, or deletion of personal data, contact us.": "За прашања, исправка или бришење на лични податоци, контактирајте нè.",
    "What you can request": "Што можете да побарате",
    "Correction of your contact details": "Исправка на вашите контакт податоци",
    "Deletion of a booking or uploaded photo where reasonable": "Бришење на резервација или прикачена слика кога е разумно",
    "Questions about how your data is used": "Прашања за тоа како се користат вашите податоци",
    "During the pilot, requests are handled manually. You may also contact the business where you booked directly.": (
        "За време на пилотот, барањата се обработуваат рачно. Можете и директно да го контактирате бизнисот каде што резервиравте."
    ),
    "These terms describe the private pilot period for the first business owners using Vremio. This is not a full commercial contract.": (
        "Овие услови го опишуваат приватниот пилот за првите сопственици кои го користат Vremio. Ова не е целосен комерцијален договор."
    ),
    "Pilot period": "Пилот период",
    "The first month may be free as a testing period.": "Првиот месец може да биде бесплатен како тест период.",
    "The system is being tested with real booking flows and real customer data.": "Системот се тестира со вистински резервации и вистински податоци од клиенти.",
    "Features may change or improve during the pilot.": "Функциите може да се менуваат или подобруваат за време на пилотот.",
    "Owner responsibilities": "Обврски на сопственикот",
    "You are responsible for the actual service delivery, prices, and customer communication.": "Вие сте одговорни за вистинската услуга, цените и комуникацијата со клиентите.",
    "Use customer data only for booking and service purposes.": "Користете ги податоците од клиенти само за резервации и услуга.",
    "Do not share customer photos or contact details outside what is necessary for the service.": (
        "Не споделувајте фотографии или контакт податоци надвор од она што е потребно за услугата."
    ),
    "Review important bookings manually during the pilot.": "Рачно проверувајте ги важните резервации за време на пилотот.",
    "Report bugs, incorrect bookings, or security concerns promptly.": "Пријавете грешки, неточни резервации или безбедносни проблеми навреме.",
    "After the pilot": "По пилотот",
    "Continued paid use, pricing, and formal terms should be agreed separately before wider commercial launch.": (
        "Понатамошна платена употреба, цени и формални услови треба да се договорат посебно пред пошироко комерцијално лансирање."
    ),
    "Powered by": "Овозможено од",
    "I have read and agree to the": "Ги прочитав и се согласувам со",
    "booking rules": "правилата за закажување",
    "privacy policy": "политиката за приватност",
    "photo policy": "политиката за фотографии",
    "and": "и",
    "I have read and agree to the booking rules and privacy policy.": (
        "Ги прочитав и се согласувам со правилата за закажување и политиката за приватност."
    ),
    "I have read, understood, and agree to all rules and policies.": (
        "Ги прочитав, разбирам и се согласувам со сите правила и политики."
    ),
    "I accept the salon rules and understand this is only a request.": (
        "Ги прочитав и се согласувам со правилата за закажување и политиката за приватност."
    ),
    # legacy home (kept for compatibility)
    "Salon Scheduler — Book Online": "Vremio — Резервирај онлајн",
    "Book your salon<br><em>appointment online</em>": "Резервирајте го вашиот<br><em>салонски термин онлајн</em>",
    "No messages. No waiting. Choose a service, pick a time, and send your request.": "Без пораки. Без чекање. Изберете услуга, термин и испратете барање.",
    "Choose your salon": "Изберете салон",
    "Available": "Достапни",
    "salons": "салони",
    "View & Book": "Погледни и резервирај",
    "No active salons available yet.": "Сè уште нема активни салони.",
    "Professional scheduling for beauty businesses": "Професионално закажување за beauty бизниси",
    # auth
    "Owner — Vremio": "Сопственик — Vremio",
    "Owner — Salon Scheduler": "Сопственик — Vremio",
    "Owner Login": "Најава за сопственик",
    "Sign in to your salon dashboard": "Најавете се на контролната табла на салонот",
    "Signing out…": "Одјавување…",
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
    "You requested a password reset for your Vremio owner account.": "Побаравте ресетирање на лозинката за вашата Vremio сметка.",
    "You requested a password reset for your Salon Scheduler owner account.": "Побаравте ресетирање на лозинката за вашата Vremio сметка.",
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
    "View today on calendar": "Погледни денес на календарот",
    "View pending bookings": "Погледни термини на чекање",
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
    "These hours control online booking availability and the owner calendar.": "Овие часови го одредуваат достапноста за онлајн резервации и календарот на сопственикот.",
    "Public salon page": "Јавна страница на салонот",
    "Optional display-only closing time for the customer-facing page. Does not affect booking slots or the owner calendar.": "Опционално време на затворање само за приказ на страницата за клиенти. Не влијае на слободните термини ниту на календарот на сопственикот.",
    "Public page closing time": "Време на затворање на јавната страница",
    "Leave empty to show the same end time as working hours. Booking availability is not affected.": "Оставете празно за да се прикаже истото време на затворање како работното време. Достапноста за резервации не се менува.",
    "Save public page hours": "Зачувај часови на јавната страница",
    "Public salon page hours saved.": "Часовите на јавната страница се зачувани.",
    "Could not save public salon page hours.": "Не можеше да се зачуваат часовите на јавната страница.",
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
    "— Occupied": "— Зафатено",
    "Service schedule": "Распоред на услуги",
    "%(count)s appointment": "%(count)s термин",
    "%(count)s appointments": "%(count)s термини",
    "Cannot add bookings in the past.": "Не може да се додаваат термини во минатото.",
    "Copy message": "Копирај порака",
    "Message copied.": "Пораката е копирана.",
    "Could not copy. Long-press the message to copy.": "Не можеше да се копира. Долго притиснете на пораката за да ја копирате.",
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
    "dd/mm/yyyy": "дд/мм/гггг",
    "Choose date": "Изберете датум",
    "Use dd/mm/yyyy": "Користете дд/мм/гггг",
    "Choose today or a future date.": "Изберете денес или иден датум.",
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
    "Hello %(name)s,": "Здраво %(name)s,",
    "We received your booking request": "Го примивме вашето барање за термин",
    "Hello %(name)s,\n\nWe received your booking request.": (
        "Здраво %(name)s,\n\n"
        "Го примивме вашето барање за термин."
    ),
    "You have a new booking request.\n\nCustomer: %(name)s\nPhone: %(phone)s": (
        "Имате ново барање за термин.\n\n"
        "Клиент: %(name)s\n"
        "Телефон: %(phone)s"
    ),
    "Service: %(service)s": "Услуга: %(service)s",
    "Date and time: %(date)s at %(time)s": "Датум и време: %(date)s во %(time)s",
    "Your appointment is not confirmed yet. The salon will review your request.": (
        "Терминот сè уште не е потврден. Салонот ќе го прегледа барањето."
    ),
    "You can track your appointment here:": "Вашиот термин можете да го следите тука:",
    "Hello %(name)s,\n\nYour appointment for %(date)s at %(time)s has been confirmed.": (
        "Здраво %(name)s,\n\n"
        "Вашиот термин за %(date)s во %(time)s е потврден."
    ),
    "We look forward to seeing you.": "Ве очекуваме.",
    "You requested an appointment at %(salon_name)s. To send your request to the salon, please confirm your email address:": (
        "Побаравте термин во %(salon_name)s. За да го испратите барањето до салонот, "
        "потврдете ја вашата email адреса:"
    ),
    "Hello %(name)s,\n\nYou requested an appointment at %(salon_name)s. To send your request to the salon, please confirm your email address:": (
        "Здраво %(name)s,\n\n"
        "Побаравте термин во %(salon_name)s. За да го испратите барањето до салонот, "
        "потврдете ја вашата email адреса:"
    ),
    "This link is valid for %(minutes)s minutes.": "Линкот е валиден %(minutes)s минути.",
    "If you did not make this request, you can ignore this email.": (
        "Ако не сте го направиле ова барање, можете да го игнорирате овој email."
    ),
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
    "Cancel appointment": "Откажи термин",
    "Are you sure you want to cancel this appointment?": "Дали сте сигурни дека сакате да го откажете терминот?",
    "Yes, cancel appointment": "Да, откажи термин",
    "No, go back": "Не, врати се назад",
    "Reference photo attached": "Прикачена е референтна фотографија",
    "Total duration: %(minutes)s min": "Вкупно време: %(minutes)s мин",
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
    "Vremio test email": "Тест email од Vremio",
    "This is a test email from Vremio.\n\nIf you received this message, outgoing email is configured correctly.": (
        "Ова е тест email од Vremio.\n\n"
        "Ако ја примивте пораката, испраќањето на email е правилно конфигурирано."
    ),
    "Salon Scheduler test email": "Тест email од Vremio",
    "This is a test email from Salon Scheduler.\n\nIf you received this message, outgoing email is configured correctly.": (
        "Ова е тест email од Vremio.\n\n"
        "Ако ја примивте пораката, испраќањето на email е правилно конфигурирано."
    ),
    "Review in dashboard:": "Преглед во контролна табла:",
    "Missed appointment": "Пропуштен термин",
    "Request received": "Барањето е примено",
    "Your appointment is confirmed": "Вашиот термин е потврден",
    "Reminder: your upcoming appointment": "Потсетник: вашиот претстоен термин",
    "This is a reminder that you have an appointment on %(date)s at %(time)s.": (
        "Ова е потсетник дека имате термин на %(date)s во %(time)s."
    ),
    "You can view or cancel your appointment here:": "Можете да го прегледате или откажете терминот тука:",
    "We look forward to seeing you.": "Ве очекуваме.",
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
    "Use fixed start times": "Фиксни почетни термини",
    "Fixed start times": "Почетни часови (HH:MM)",
    "Comma-separated HH:MM times (e.g. 08:00, 10:30, 13:00, 15:30). Used only when fixed start times mode is on; slot interval is ignored.": "Време одделено со запирка во формат HH:MM (на пр. 08:00, 10:30, 13:00, 15:30). Се користи само кога се вклучени фиксни термини; интервалот на термини се игнорира.",
    "Add at least one fixed start time.": "Додадете барем еден фиксен почетен термин.",
    "Slot interval minutes": "Интервал на термини (минути)",
    "Buffer minutes between bookings": "Бафер меѓу термини (минути)",
    "Gap between services in same booking (minutes)": "Пауза меѓу услуги во иста резервација (минути)",
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
    "You already started a booking request. Please check your email inbox (and spam folder) to confirm it before submitting again.": (
        "Веќе започнавте барање за термин. Проверете ја е-поштата (и спам папката) "
        "за да го потврдите, пред да испратите повторно."
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
    "Reopen cancelled slots inside notice window": "Автоматски отвори откажани термини за онлајн резервација",
    "This is a last-minute opening from a cancelled appointment.": "Ова е последен слободен термин од откажување.",
    "This cancelled opening is not available for your selected service.": "Овој термин од откажување не е достапен за избраната услуга.",
    "Could not cancel appointment.": "Терминот не можеше да се откаже.",
    # Legal pages (2026 update)
    "1. Introduction": "1. Вовед",
    "Welcome to Vremio.": "Добредојдовте на Vremio.",
    "Vremio is a platform for online appointment booking and reservation management for local businesses.": (
        "Vremio е платформа за онлајн закажување термини и управување со резервации за локални бизниси."
    ),
    "By using the platform, you entrust us with certain personal data necessary for successfully organizing and managing your appointments. We are committed to their secure processing and protection.": (
        "Со користење на платформата, ни доверувате одредени лични податоци неопходни за успешно организирање и управување со вашите термини. "
        "Ние сме посветени на нивна безбедна обработка и заштита."
    ),
    "2. What data we collect": "2. Кои податоци ги собираме",
    "Depending on the service you book, we may collect the following information:": (
        "Во зависност од услугата што ја резервирате, може да ги собираме следните информации:"
    ),
    "First and last name": "име и презиме",
    "Instagram username (if provided)": "Instagram корисничко име (доколку е внесено)",
    "Selected service": "избрана услуга",
    "Appointment date and time": "датум и време на термин",
    "Booking status": "статус на резервацијата",
    "Photos attached for the service": "прикачени фотографии поврзани со услугата",
    "IP address and technical data needed for security and abuse prevention": (
        "IP адреса и технички податоци потребни за безбедност и спречување злоупотреба"
    ),
    "3. Why we use your data": "3. Зошто ги користиме податоците",
    "Your data is used exclusively for:": "Вашите податоци се користат исклучиво за:",
    "Processing appointment requests": "обработка на барања за термин",
    "Communication between the customer and the business": "комуникација помеѓу клиентот и бизнисот",
    "Sending appointment-related notifications": "испраќање известувања поврзани со термини",
    "Preventing abuse of the platform": "спречување злоупотреба на платформата",
    "Improving the security and stability of the system": "подобрување на сигурноста и стабилноста на системот",
    "4. Attached photos": "4. Прикачени фотографии",
    "Photos are used solely as a reference for the selected service.": (
        "Фотографиите се користат исклучиво како референца за избраната услуга."
    ),
    "They are available only to the business owner and authorized Vremio administrators when needed for technical support.": (
        "Тие се достапни само за сопственикот на бизнисот и овластени администратори на Vremio доколку е потребно за техничка поддршка."
    ),
    "5. Data sharing": "5. Споделување на податоци",
    "Vremio does not sell or share your personal data with third parties, except when necessary for the platform to function or when required by law.": (
        "Vremio не ги продава ниту ги споделува вашите лични податоци со трети лица, освен кога тоа е неопходно за функционирањето на платформата или кога тоа го бара закон."
    ),
    "6. Your rights": "6. Вашите права",
    "You have the right to request:": "Имате право да побарате:",
    "Access to your data": "увид во вашите податоци",
    "Correction of inaccurate data": "исправка на неточни податоци",
    "Deletion of data when permitted": "бришење на податоци кога тоа е дозволено",
    "Restriction of processing": "ограничување на обработката",
    "For such requests, contact us via the contact email.": "За вакви барања контактирајте нè преку контакт е-поштата.",
    "7. Security": "7. Безбедност",
    "Vremio applies technical and organizational measures to protect personal data from unauthorized access, loss, or misuse.": (
        "Vremio применува технички и организациски мерки за заштита на личните податоци од неовластен пристап, губење или злоупотреба."
    ),
    "1. Acceptance": "1. Прифаќање",
    "By using the Vremio platform, you agree to these terms.": "Со користење на платформата Vremio се согласувате со овие услови.",
    "2. Role of Vremio": "2. Улога на Vremio",
    "Vremio provides a booking platform.": "Vremio обезбедува платформа за закажување.",
    "The service you book is provided by the business itself (salon, barber shop, sports facility, etc.), not by Vremio.": (
        "Услугата што ја резервирате ја обезбедува самиот бизнис (салон, берберница, спортски објект и сл.), а не Vremio."
    ),
    "3. Booking": "3. Закажување",
    "A submitted appointment request does not represent a confirmed appointment.": (
        "Испратеното барање за термин не претставува потврден термин."
    ),
    "The appointment becomes valid only after approval by the business.": (
        "Терминот станува важечки само по одобрување од страна на бизнисот."
    ),
    "4. User obligations": "4. Обврски на корисникот",
    "The user agrees to:": "Корисникот се согласува дека ќе:",
    "Provide accurate information": "внесува точни информации",
    "Not submit false requests": "нема да испраќа лажни барања",
    "Not misuse photos": "нема да злоупотребува фотографии",
    "Not disrupt the operation of the platform": "нема да ја попречува работата на платформата",
    "5. Limitation of liability": "5. Ограничување на одговорност",
    "Vremio is not responsible for:": "Vremio не е одговорен за:",
    "Quality of the service": "квалитетот на услугата",
    "Prices": "цените",
    "Delays": "доцнења",
    "Business working hours": "работното време на бизнисот",
    "The business itself is responsible for these matters.": "За овие прашања одговорен е самиот бизнис.",
    "6. Changes": "6. Измени",
    "Vremio may update these terms from time to time in order to improve the service.": (
        "Vremio може повремено да ги ажурира овие услови со цел подобрување на услугата."
    ),
    "By submitting an appointment request, you confirm that:": "Со испраќање барање за термин потврдувате дека:",
    "You understand that the request is not an automatically confirmed appointment": (
        "разбирате дека барањето не е автоматски потврден термин"
    ),
    "You will provide accurate contact information": "ќе обезбедите точни контакт информации",
    "You will respect the selected appointment time": "ќе го почитувате избраниот термин",
    "You will notify the business if you cannot attend": "ќе го известите бизнисот доколку не можете да присуствувате",
    "You accept that significant lateness may result in cancellation of the appointment": (
        "прифаќате дека значително доцнење може да резултира со откажување на терминот"
    ),
    "You accept that the business may decline a request if no appointment is available": (
        "прифаќате дека бизнисот може да одбие барање доколку нема достапен термин"
    ),
    "You will not abuse the platform with false or repeated requests": (
        "нема да ја злоупотребувате платформата со лажни или повторени барања"
    ),
    "If the selected service allows or requires a photo upload:": (
        "Доколку избраната услуга дозволува или бара прикачување фотографија:"
    ),
    "Allowed": "Дозволено е",
    "Photos related to the service": "фотографии поврзани со услугата",
    "Reference photos": "референтни фотографии",
    "Photos of the current condition (for example for medical pedicure)": (
        "фотографии од постоечката состојба (на пример за медицински педикир)"
    ),
    "Not allowed": "Не е дозволено",
    "Indecent or explicit photos": "непристојни или експлицитни фотографии",
    "Photos unrelated to the service": "фотографии што не се поврзани со услугата",
    "Photos that offend or harass others": "фотографии што ги навредуваат или вознемируваат другите",
    "Malicious content": "злонамерна содржина",
    "Formats": "Формати",
    "Supported formats:": "Поддржани формати:",
    "Photo review": "Преглед на фотографиите",
    "Uploaded photos are visible only to:": "Прикачените фотографии се видливи само за:",
    "The business where the request was submitted": "бизнисот кај кој е испратено барањето",
    "Authorized administrators when necessary for technical support": (
        "овластени администратори кога тоа е неопходно за техничка поддршка"
    ),
    "Abuse": "Злоупотреба",
    "Vremio reserves the right to:": "Vremio го задржува правото да:",
    "Delete inappropriate photos": "избрише несоодветна фотографија",
    "Block users who misuse the platform": "блокира корисник кој ја злоупотребува платформата",
    "Decline future requests if abuse is confirmed": "одбие идни барања доколку се утврди злоупотреба",
}


def main():
    for lang in ("mk", "en"):
        locale_dir = BASE / "locale" / lang / "LC_MESSAGES"
        locale_dir.mkdir(parents=True, exist_ok=True)
        po_path = locale_dir / "django.po"
        mo_path = locale_dir / "django.mo"

        po = polib.POFile()
        po.metadata = {
            "Project-Id-Version": "Vremio",
            "Report-Msgid-Bugs-To": "",
            "POT-Creation-Date": "2026-06-21 12:00+0000",
            "PO-Revision-Date": "2026-06-21 12:00+0000",
            "Last-Translator": "Vremio",
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
