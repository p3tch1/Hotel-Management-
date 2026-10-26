# Lumen House Hotel Management System

Responsive hotel app with separate guest, staff, and manager portals. The frontend is React/Vite. The API is Django REST Framework with validation, role permissions, bearer-token authentication, pagination, throttling, and Swagger documentation. Hotel data and user accounts are stored in MongoDB through a small PyMongo data-access module. The project does not store hotel business records in its local SQLite framework file.

## Install

- Node.js 20.19+ (LTS is recommended) and npm
- Python 3.10+
- MongoDB Community Server running locally, or a MongoDB Atlas database
- VS Code (optional) and MongoDB Compass (optional, for browsing collections)

## Run on Windows

1. Start MongoDB Community Server. Open Compass and connect to `mongodb://127.0.0.1:27017` to confirm the server is available.
2. Copy `backend/.env.example` to `backend/.env`. Replace the Django and JWT secrets with private random strings. Generate a Fernet key with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` and replace the `FIELD_ENCRYPTION_KEY` placeholder with that output. Keep this key private and backed up: losing it prevents decrypting guest addresses and ID-proof numbers. Keep the local MongoDB URI unless you are using Atlas; for Atlas, put its connection string in `MONGODB_URI`.
3. Open this project folder in VS Code. Open a terminal in the folder containing the root `package.json`.
4. Install Python and JavaScript packages:

   ```powershell
   npm run install:all
   ```

5. Load demo records and demo accounts:

   ```powershell
   npm run seed
   ```

   The seed command intentionally replaces the project's demo collections. It requires an explicit `--yes` confirmation (the npm shortcut supplies it).

6. Start the Django API and React app:

   ```powershell
   npm run dev
   ```

7. Open `http://localhost:5173`. Swagger/OpenAPI is at `http://localhost:4000/api/docs`; the schema is at `/api/schema`.

If PowerShell blocks the `npm` script, use `npm.cmd` in the same commands. If `python` is not found, install Python and select the installer option that adds it to PATH, then restart VS Code.

## Demo sign-ins

| Portal | Email | Password |
|---|---|---|
| Manager | `manager@lumenhotel.example` | `ManagerDemo123!` |
| Staff | `staff1@lumenhotel.example` | `StaffDemo123!` |
| Guest | `guest1@example.com` | `GuestDemo123!` |

All demo accounts are for local development. Change the seed passwords before any shared or deployed use. Guest self-registration is available from the sign-in page. Login requests are rate limited. Passwords are hashed and the API uses expiring signed bearer tokens with logout revocation.

Guest addresses and ID-proof numbers are encrypted in MongoDB using Fernet authenticated encryption. API responses decrypt these fields for authorized hotel staff and the guest profile. Email and phone remain plaintext so the application can enforce uniqueness and search the guest directory. To encrypt guest fields already stored as plaintext, set `FIELD_ENCRYPTION_KEY` first, then run `python backend/manage.py encrypt_guest_fields`. The command skips fields it has already encrypted. Passwords are one-way hashed and are not reversibly encrypted.

## MongoDB data

The seed command writes 30 records each to `guests`, `room_types`, `rooms`, `services`, `bookings`, `booking_services`, and `payments`; it also creates staff/manager/guest accounts, operational service requests, and activity records. Six demo bookings are currently checked in to demonstrate guest service requests and staff check-out. In Compass, refresh the connection and open the `hotel_management` database.

## Main API groups

- `/api/auth/`: guest registration, login, logout, token refresh, and account profile
- `/api/rooms/`, `/api/room-types/`: public-to-authenticated room search and manager inventory/rate changes
- `/api/bookings/`, `/api/payments/`: booking lifecycle, server-side availability/pricing, billing, and payment metadata
- `/api/guests/`: guests see their own profile; staff/manager can search the full directory
- `/api/service-requests/`, `/api/staff/`: guest requests and staff task assignment/status workflow
- `/api/admin/`: staff management and audit-log access for managers
- `/api/dashboard`, `/api/reports`: role-protected operations metrics and date-filterable reporting

## Rules implemented

- Booking dates, room capacity, room status, and date overlaps are validated server-side.
- Guests can only view their own bookings and can cancel only their confirmed reservations before check-in. Cancellation does not automatically refund recorded payments; refunds require a separate manager process.
- Room rate is read from MongoDB on the server. The demo pricing adds a 5% fee; no external tax configuration is assumed.
- Payment method and transaction metadata are stored, never card numbers. Online gateway callbacks are not implemented.
- Check-out finalizes the bill and moves the room to Cleaning. Staff can mark it Inspected or Available. Room and service-request changes append histories; sensitive operations are recorded in the manager audit log.
- Outbound email/SMS, password reset, deployment HTTPS, automated backups, external payment processing, and production monitoring need environment-specific services and are not configured in this local demo.

For a manual MongoDB backup/restore, install MongoDB Database Tools, stop writes to the app, then use `mongodump --uri="mongodb://127.0.0.1:27017/hotel_management" --out="./backup"`. Restore that database with `mongorestore --uri="mongodb://127.0.0.1:27017" --nsInclude="hotel_management.*" --drop "./backup"`. Test backup and restore steps on a separate copy before relying on them for important data.

## Development notes

The MongoDB adapter is isolated in `backend/hotel/db.py`; serializers validate input, service modules hold business rules, API modules handle endpoints and permissions, and `config/settings.py` reads environment configuration. Tests live in `backend/hotel/tests.py`; run them with `python backend/manage.py test hotel` after installing dependencies.

For Vercel deployment, follow [VERCEL_DEPLOYMENT.md](VERCEL_DEPLOYMENT.md). The frontend and Django API deploy as separate Vercel projects, with MongoDB Atlas used for the hosted database. The deployment guide includes a manager bootstrap command so public deployments do not need the seeded demo credentials.
