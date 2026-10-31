# Service Account Keys

Private credentials for external service integrations. Credential files are
ignored by Git; this provisioning README is intentionally tracked.

## Contents

| File | Service | Purpose |
|---|---|---|
| `gee-service-account.json` | Google Earth Engine | Remote sensing data access (NDVI, satellite imagery) |

## Provisioning

1. Create the service account in the external provider's console
2. Download the credential JSON
3. Place it in this directory
4. Reference it in `.env`:
   ```
   GEE_SERVICE_ACCOUNT_KEY=config/keys/gee-service-account.json
   ```

## Security

- **Gitignored**: Credential files under `config/keys/` are in `.gitignore`; `README.md` is explicitly exempted so the provisioning instructions stay versioned.
- **Never commit** private keys, API tokens, or service account JSON
- **Rotate** compromised credentials immediately and history-scrub the repository
