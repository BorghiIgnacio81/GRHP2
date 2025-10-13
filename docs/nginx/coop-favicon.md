# Nginx snippets: COOP header and favicon

Place the following in your site config (inside the `server` block for `148.230.72.135`) to set a COOP header on proxied responses and serve a favicon:

```
# Serve a favicon to avoid 404 in browser console
location = /favicon.ico {
    alias /srv/static/nucleo/icons/favicon.ico;
    access_log off;
    log_not_found off;
}

# Add Cross-Origin-Opener-Policy for proxied responses
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    add_header Cross-Origin-Opener-Policy same-origin always;
}
```

Warnings:
- Serving the COOP header on all responses can break cross-origin resource usage (embedding, fonts, images) if those resources are fetched from other origins and not allowed. Test after enabling.
- Prefer enabling HTTPS on the site; browsers only treat COOP as trustworthy on secure contexts. Serving over HTTPS is the recommended long-term fix.
