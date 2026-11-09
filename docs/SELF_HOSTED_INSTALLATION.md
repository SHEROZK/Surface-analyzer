# Self-hosted installation

Surface Analyzer is installed as a private, customer-managed application. This guide uses Docker Compose and keeps PostgreSQL and Redis on the private Compose network.

## Requirements

- Windows 11 with Docker Desktop, or a Linux server with Docker Engine and the Docker Compose plugin
- 4 CPU cores and 8 GB RAM as a practical starting point; image processing benefits from more memory
- Persistent disk space for the database and uploaded room/product images
- A browser on the same machine or LAN

## Windows quick install

1. Download or clone this repository onto the installation machine.
2. Open PowerShell in the repository folder.
3. Run:

   ```powershell
   Set-ExecutionPolicy -Scope Process Bypass
   .\scripts\install.ps1
   ```

The installer creates `.env` only when one does not already exist. It generates unique database and signing secrets, then builds and starts the application. It never overwrites an existing `.env`.

Open the studio at http://localhost:3000. The API is available at http://localhost:8000. For another device on the LAN, set `NEXT_PUBLIC_API_URL` to an API URL reachable from that device, set `CORS_ORIGINS` to the studio origin, and rebuild the web image.

## Linux / manual install

1. Copy `.env.production.example` to `.env`.
2. Replace `POSTGRES_PASSWORD` and `AUTH_SECRET` with unique random values.
3. Set `NEXT_PUBLIC_API_URL` to the URL browsers will use to reach the API.
4. Set `CORS_ORIGINS` to the exact studio origin(s), comma-separated.
5. Start the stack:

   ```bash
   docker compose -f docker-compose.production.yml up -d --build
   ```

## Network and security

- PostgreSQL and Redis are not published on host ports.
- The API binds to 127.0.0.1 by default. The studio binds to 0.0.0.0 on port 3000.
- If users on other machines need the API, deliberately change `API_BIND` to a private LAN interface or place both services behind a TLS reverse proxy. Do not expose the API or studio directly to the public internet without TLS, firewall rules, and a reviewed deployment configuration.
- The current browser client uses a bearer token in browser session storage. Protect the studio origin against XSS and do not host untrusted scripts on it.
- Keep `.env` private. Do not commit it or share its secrets.
- Uploaded files and database data are held in named Docker volumes.

## Backup and restore

Stop writes before making a consistent backup. For a basic database backup:

```bash
docker compose -f docker-compose.production.yml exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > surface-analyzer.sql
```

Back up the `api_uploads` volume as well as the database. A database-only backup does not include room photos or product textures. Store backups outside the installation machine and test restores before relying on them.

## Updating

Back up the database and uploads first, then update the repository to the desired release and run:

```bash
docker compose -f docker-compose.production.yml up -d --build
```

The API container applies Alembic migrations at startup. Review release notes and migration compatibility before upgrading a production installation.

## Current limitations

This is the first customer-managed Docker deployment path, not a signed native installer. It does not yet include automated backup scheduling, one-click rollback, TLS certificate provisioning, a Windows service wrapper, or a graphical update manager. Those remain installation-hardening tasks.
