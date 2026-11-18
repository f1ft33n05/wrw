# Werwines mobile POS

Flutter cashier client for the Werwines FastAPI backend.

## Run on a device

From this directory, fetch packages and run the Android app:

```powershell
flutter pub get
flutter run --dart-define=API_BASE_URL=http://<computer-lan-ip>:8000 --dart-define=CURRENCY_CODE=MWK
```

The device and backend computer must be reachable on the same network. The
development URL defaults to the current LAN address in `lib/config/api_config.dart`.
Use an HTTPS backend URL for production builds.

The app signs in with the backend's `/auth/token` endpoint, then loads
`/items/catalogue` and `/contacts/`. Sale totals are quoted by `/sales/quote`
and submitted to `/sales/create`; checkout sends an `Idempotency-Key` to prevent
duplicate sales when a request is retried. Sales history is paginated through
`/sales/history`, and native receipt details come from
`/sales/{invoice_id}/receipt/data`.

The cashier workspace has Home, Items, POS, Receipts, and Settings tabs.
Home reads its daily totals and recent sales from `/sales/dashboard`. Active
locations come from `/events/active`; selecting an event scopes both the POS
catalogue (`/items/catalogue?event_id=...`) and sale quote/checkout to that
event. Profile details use `/profile/data`. Receipt text size and display
options are stored locally on the device.

## Checks

```powershell
flutter analyze
flutter test
```
