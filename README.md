# LTRC-Manager
A program for managing LTRC results

Latest version: v0.5.1

## Docker Deployment

The repo now includes:

- `backend.Dockerfile` for the FastAPI API
- `frontend.Dockerfile` for the React app served by Nginx
- `docker-compose.yml` for a single-domain deployment shape

Quick start:

1. Copy `.env.example` to `.env`
2. Fill in your Discord OAuth values and allowed Discord user IDs
3. Make sure your Google Sheets credentials JSON exists in `assets/`
4. Run `docker compose up --build -d`

The Docker setup is designed for a VPS that already runs `nginx` on the host:

- frontend container listens on `127.0.0.1:8080`
- backend container listens on `127.0.0.1:8000`
- host `nginx` should terminate HTTPS and proxy traffic to the frontend container

The frontend container proxies `/auth`, `/ltrc`, `/health`, `/docs`, `/redoc`, and `/openapi.json` to the backend container.

For production Discord login, use HTTPS and set:

- `FRONTEND_BASE_URL` to your full public app URL, including `/LTRC-Manager`
- `CORS_ALLOWED_ORIGINS` to the origin only, without the path
- `DISCORD_REDIRECT_URI` to `https://your-domain/LTRC-Manager/auth/callback`
- `APP_ENV=production`

### Host Nginx Example

For `https://app.blazico.nl/LTRC-Manager`, point your VPS `nginx` site at the frontend container with a path-prefix proxy. The trailing slash on `proxy_pass` is important because it strips `/LTRC-Manager/` before forwarding to the container.

```nginx
server {
    listen 443 ssl http2;
    server_name app.blazico.nl;

    ssl_certificate /path/to/fullchain.pem;
    ssl_certificate_key /path/to/privkey.pem;

    location = /LTRC-Manager {
        return 301 /LTRC-Manager/;
    }

    location /LTRC-Manager/ {
        proxy_pass http://127.0.0.1:8080/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

For this deployment target, use these values in `.env`:

- `FRONTEND_BASE_URL=https://app.blazico.nl/LTRC-Manager`
- `CORS_ALLOWED_ORIGINS=https://app.blazico.nl`
- `DISCORD_REDIRECT_URI=https://app.blazico.nl/LTRC-Manager/auth/callback`

This keeps public traffic on your existing host `nginx` setup, avoids binding Docker to port `80`, and makes the frontend work correctly from the `/LTRC-Manager` subpath.
