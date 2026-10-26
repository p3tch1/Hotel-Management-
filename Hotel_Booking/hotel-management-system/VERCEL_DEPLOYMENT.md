# Deploy the hotel application on Vercel

The client and API are deployed as two Vercel projects from one Git repository. Deploy the API first, then give its URL to the client project. The Django root contains `manage.py`, `config/wsgi.py`, and `requirements.txt`, which Vercel uses to identify the Django application.

## 1. Prepare the source repository

Push the complete `hotel-management-system` folder to a private GitHub repository. Do not commit `backend/.env`, database credentials, encryption keys, `.venv`, `node_modules`, or `client/dist`. The root `.gitignore` excludes the local environment files and build folders.

## 2. Prepare MongoDB Atlas

Create an Atlas cluster and a dedicated database user with access only to the `hotel_management` database. Copy the Atlas connection URI and replace its username/password placeholders. Do not use your Atlas website login as the database credentials.

Vercel functions normally use changing outbound IP addresses. Atlas requires the Vercel deployment's outbound addresses to be allowed. Prefer Vercel Static IPs or a private network option where available. The Vercel/Atlas native integration can configure connectivity, but MongoDB documents that its setup may add `0.0.0.0/0`; that rule allows network attempts from any IP, so only use it knowingly with a restricted database user and a strong password. Never commit the URI.

## 3. Deploy the Django API

In Vercel, import the GitHub repository as a new project named, for example, `hotel-management-api`. Set **Root Directory** to `backend`. Vercel's Django support detects `manage.py` and the WSGI application; use the detected Python/Django framework settings.

Add these project environment variables for Production (and Preview only if you need preview deployments):

| Name | Value |
| --- | --- |
| `DEBUG` | `false` |
| `DJANGO_SECRET_KEY` | A long, random private value |
| `JWT_SECRET` | A different long, random private value |
| `FIELD_ENCRYPTION_KEY` | The existing Fernet key for the database, generated with `Fernet.generate_key()` |
| `MONGODB_URI` | Your Atlas `mongodb+srv://...` URI |
| `MONGODB_DATABASE` | `hotel_management` |
| `ALLOWED_HOSTS` | `.vercel.app,localhost,127.0.0.1` (add the API's custom hostname if used) |
| `CORS_ALLOWED_ORIGINS` | `https://YOUR-FRONTEND-PROJECT.vercel.app` |
| `JWT_LIFETIME_SECONDS` | `28800` |

Keep the same `FIELD_ENCRYPTION_KEY` for all deployments that read the same MongoDB data. Do not regenerate it during a redeploy.

Deploy the API and note its public project URL, such as `https://hotel-management-api.vercel.app`. Confirm `https://hotel-management-api.vercel.app/api/health` returns a connected MongoDB status before deploying the client.

### Create the first manager

Do not use `npm run seed` on the public database. It creates well-known demo accounts and clears the named demo collections. Instead, on a trusted local machine, configure `backend/.env` with the same Atlas URI/database and encryption key, install dependencies, and run:

```powershell
python backend/manage.py create_manager
```

Enter a manager name, email, and private password when prompted. This command creates only the manager account. Guest registrations are available from the website. Add room types, rooms, services and staff after signing in as the manager, or prepare non-demo data separately.

## 4. Deploy the React client

Import the same GitHub repository as a second Vercel project, for example `hotel-management-web`. Set **Root Directory** to `client`. Select the Vite framework preset; use `npm run build` as the build command and `dist` as the output directory if Vercel does not detect them automatically.

Set this build environment variable before deploying:

| Name | Value |
| --- | --- |
| `VITE_API_URL` | `https://YOUR-API-PROJECT.vercel.app/api` |

The value must include `/api` and must not end with a slash. Use the API's actual URL. Deploy the client, then update the API project's `CORS_ALLOWED_ORIGINS` to the exact client origin shown by Vercel and redeploy the API.

## 5. Verify the live site

1. Open the frontend Vercel URL and register a guest account.
2. Sign in with the manager account created above.
3. Check `/api/health`, room search, booking creation and service request pages.
4. Review Vercel function logs if the API returns an error; never paste secrets into logs or support messages.

## Important notes

- Local MongoDB at `127.0.0.1` cannot be reached by Vercel. Use Atlas or another reachable managed MongoDB deployment.
- Vercel deployments are serverless. Do not start `runserver` as the hosted process and do not seed the database at application startup.
- The database's encrypted guest fields require the matching `FIELD_ENCRYPTION_KEY` at runtime. A wrong key makes those fields unreadable.
- The frontend calls `localhost` by default for local development. Production must set `VITE_API_URL` in Vercel.
- Vercel's current Python/Django support and Atlas network requirements can change; see [Vercel's Django deployment documentation](https://vercel.com/docs/frameworks/backend/django) and [Vercel Python runtime documentation](https://vercel.com/docs/functions/runtimes/python) before deployment.
