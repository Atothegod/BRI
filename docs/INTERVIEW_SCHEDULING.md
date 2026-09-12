# Appointment Scheduling

Open `/school-admin/appointments/` from the school overview as a superuser,
matching the existing school-admin authorization. Use the Interview or
Orientation tab, select up to 50 participants, enter a future date/time in
Asia/Bangkok, location, link and details, then confirm. The date is Gregorian
(CE). Interview candidates are in-progress applicants; orientation candidates
are passed students whose payment has been approved.

The list can be filtered by text, appointment state, LINE connection,
notification result and applicant confirmation. Filters can be combined.
The header checkbox selects every visible result on the current page, up to
the 50-person batch limit; individual checkboxes send only to those people.

Appointments are saved atomically before notifications start. Each selected
person receives a separate browser POST, avoiding one long bulk request.
Keep the page open until the summary finishes. If the page closes or a send
fails, reopen the scheduler and use the row's Send LINE button. Pending and
failed notification states persist in the database.

The LINE API accepting a message does not establish that the recipient read
or received it. Missing LINE identities, token issues or network failures do
not roll back the saved appointment. A timeout can have an ambiguous delivery
outcome; retrying such a request may deliver a duplicate.

The themed LINE Flex message changes its heading for interviews and
orientation, and includes a signed confirmation link. Opening the link only
previews the appointment; the participant must press the confirmation button
before the participant response is saved. The admin response column
polls every 15 seconds while the page is visible. Forwarding the signed link
would allow its holder to confirm, so it should be treated as private.

Each event is stored in `Appointment`, while each person's LINE and response
state is stored in `AppointmentParticipant`. The page keeps a 12-event history.
Legacy interview fields are updated temporarily for rollout compatibility, and
previous signed interview confirmation links continue to work. Notification
endpoints reject stale or expired appointments. Successful sends are guarded
by a participant row lock and are not repeated for the same saved appointment.
No student IDs are included. The old `/school-admin/interviews/` and
`/interviews/confirm/` URLs remain as compatibility routes, but new links use
`appointments`.

## Deployment

This feature adds migrations `0009`, `0010` and `0011`. From the production project directory,
build the new code, apply the migration, then recreate the backend:

```sh
docker compose -f docker-compose.prod.yml build backend
docker compose -f docker-compose.prod.yml run --rm backend python manage.py migrate
docker compose -f docker-compose.prod.yml up -d --no-deps backend
```

Configure the existing `LINE_MESSAGING_CHANNEL_ACCESS_TOKEN` in `.env`.
The migration must run before serving the new code to avoid missing-column
errors. The normal backend startup collects static assets.
