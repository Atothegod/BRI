# Interview Scheduling

Open `/school-admin/interviews/` from the school overview as a superuser,
matching the existing school-admin authorization. Select up to 50 pending
applicants, enter a future date/time in Asia/Bangkok and optional details,
then confirm. The date is Gregorian (CE).

Appointments are saved atomically before notifications start. Each selected
person receives a separate browser POST, avoiding one long bulk request.
Keep the page open until the summary finishes. If the page closes or a send
fails, reopen the scheduler and use the row's Send LINE button. Pending and
failed notification states persist in the database.

The LINE API accepting a message does not establish that the recipient read
or received it. Missing LINE identities, token issues or network failures do
not roll back the saved appointment. A timeout can have an ambiguous delivery
outcome; retrying such a request may deliver a duplicate.

The LINE Flex message includes a signed confirmation link. Opening the link
only previews the appointment; the applicant must press the confirmation
button before `interview_confirmed_at` is saved. The admin response column
polls every 15 seconds while the page is visible. Forwarding the signed link
would allow its holder to confirm, so it should be treated as private.

The current appointment replaces the previous one when rescheduling. This is
not a historical calendar or an automatic reminder service. Notification
endpoints reject stale appointment timestamps, expired appointments and
applicants whose selection result has already been decided. Successful sends
are guarded by a per-person row lock and are not repeated for the same saved
appointment. No student IDs are included.

## Deployment

This feature adds migrations `0009` and `0010`. From the production project directory,
build the new code, apply the migration, then recreate the backend:

```sh
docker compose -f docker-compose.prod.yml build backend
docker compose -f docker-compose.prod.yml run --rm backend python manage.py migrate
docker compose -f docker-compose.prod.yml up -d --no-deps backend
```

Configure the existing `LINE_MESSAGING_CHANNEL_ACCESS_TOKEN` in `.env`.
The migration must run before serving the new code to avoid missing-column
errors. The normal backend startup collects static assets.
