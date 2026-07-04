# Runbook — Feature 004: Auth & workspaces

> Human items. Everything below is configuration only — the code paths are
> built and unit-tested; e2e runs on the dev sign-in and never needs real
> credentials.

## Environment variables

| Variable | Meaning |
|---|---|
| `ANALYST_DEV_LOGIN=1` | Enable the name-only dev sign-in (local dev / e2e ONLY — never production). |
| `ANALYST_GOOGLE_CLIENT_ID` / `ANALYST_GOOGLE_CLIENT_SECRET` | Google OAuth client. Both set → Google sign-in appears. |
| `ANALYST_MICROSOFT_CLIENT_ID` / `ANALYST_MICROSOFT_CLIENT_SECRET` | Microsoft (Entra ID) app. Both set → Microsoft sign-in appears. |
| `ANALYST_MICROSOFT_TENANT` | Optional; defaults to `common` (any Microsoft account). Set your tenant id to restrict. |
| `ANALYST_SESSION_SECRET` | HMAC key for session cookies & OAuth state. **Set a long random value in production** (`openssl rand -hex 32`); if unset a per-process random is used and sessions do not survive restarts. |
| `ANALYST_PUBLIC_URL` | The externally visible base URL (e.g. `https://analyst.example.com`) used to build OAuth redirect URIs. Defaults to the request's own base URL — set it explicitly when running behind a proxy. |

Auth enforcement turns ON automatically as soon as any of dev sign-in /
Google / Microsoft is configured. With none configured the API is open,
exactly as before this feature.

## Google Cloud console steps

1. https://console.cloud.google.com/ → create (or pick) a project.
2. **APIs & Services → OAuth consent screen**: User type *Internal* (Workspace
   org) or *External*; fill app name + support e-mail; scopes: only the
   non-sensitive defaults `openid`, `email`, `profile`. Publish.
3. **APIs & Services → Credentials → Create credentials → OAuth client ID**:
   - Application type: *Web application*.
   - Authorized redirect URI: `<ANALYST_PUBLIC_URL>/api/auth/callback/google`
     (for local trials: `http://localhost:8000/api/auth/callback/google`).
4. Copy the client ID/secret into `ANALYST_GOOGLE_CLIENT_ID` /
   `ANALYST_GOOGLE_CLIENT_SECRET`.

## Microsoft Entra ID (Azure) steps

1. https://entra.microsoft.com/ → **App registrations → New registration**.
   - Supported account types: your choice; matches `ANALYST_MICROSOFT_TENANT`
     (`common` = any account, or your tenant id for single-tenant).
   - Redirect URI: platform *Web*,
     `<ANALYST_PUBLIC_URL>/api/auth/callback/microsoft`.
2. **Certificates & secrets → New client secret** → copy the secret *value*.
3. **API permissions**: Microsoft Graph delegated `openid`, `email`,
   `profile` (default `User.Read` is fine too). Grant admin consent if your
   tenant requires it.
4. Set `ANALYST_MICROSOFT_CLIENT_ID` (Application/client ID) and
   `ANALYST_MICROSOFT_CLIENT_SECRET`; set `ANALYST_MICROSOFT_TENANT` if not
   `common`.

## First sign-in

The **first user ever to sign in becomes the admin** and gets the "Default"
workspace. Sign in yourself before exposing the URL to anyone else. The
admin creates workspaces and adds members by e-mail (members may be added
before they have ever signed in; the account is claimed by e-mail match).

## Verification checklist

- [ ] `GET /api/auth/providers` shows the expected providers as configured.
- [ ] Google round-trip: login → consent → back at the app, name in header.
- [ ] Microsoft round-trip: same.
- [ ] `ANALYST_SESSION_SECRET` set in production; `ANALYST_DEV_LOGIN` NOT set.
