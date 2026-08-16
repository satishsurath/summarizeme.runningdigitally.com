# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.2.x   | :white_check_mark: |
| 0.1.x   | :x:                |

Only the latest minor version receives security updates.

## Reporting a Vulnerability

We take the security of SummarizeMe seriously. If you believe you have found
a security vulnerability, please report it to us responsibly.

### How to Report

1. **Email:** security@runningdigitally.com
2. **Do NOT open a public GitHub issue** — this could expose the vulnerability
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### What to Expect

- **Acknowledgment:** We will acknowledge your report within 48 hours
- **Assessment:** We will assess the vulnerability within 5 business days
- **Fix:** We will work on a fix and keep you informed of progress
- **Disclosure:** We will coordinate with you on public disclosure timing
- **Credit:** We will credit reporters (unless anonymity is requested)

### Scope

The following are in scope:
- SQL injection vulnerabilities
- Authentication/authorization bypass
- Cross-site scripting (XSS)
- Server-side request forgery (SSRF)
- Insecure direct object references (IDOR)
- Information disclosure
- Denial of service (DoS)

### Out of Scope

- Issues in dependencies (report to the respective project)
- Social engineering attacks
- Physical security issues
- Issues requiring access to user accounts without consent

## Security Best Practices

### For Users

1. **Keep dependencies updated** — run `pip-audit` regularly
2. **Use strong passwords** for database and API keys
3. **Enable HTTPS** in production (use a reverse proxy like nginx/Caddy)
4. **Back up your database** regularly using `backup_database.py`
5. **Review environment variables** — never commit `.env` files

### For Contributors

1. **Never commit secrets** — use environment variables
2. **Use parameterized queries** — never concatenate user input into SQL
3. **Validate input** on all endpoints
4. **Run security audits** — `pip-audit`, `safety`, or similar tools
5. **Follow the principle of least privilege** for database users

## Security Features

- **Environment variable configuration** — no hardcoded credentials
- **SQL parameterization** — prevents SQL injection
- **Whitelist-based template selection** — restricts SQL view access
- **Structured logging** — security events are logged
- **Docker security** — non-root user, health checks, resource limits

## Dependencies

We monitor dependencies for known vulnerabilities:
- **pip-audit** — scan for known vulnerabilities in Python packages
- **Dependabot** — automated PRs for dependency updates (GitHub)
- **GitHub Advisory Database** — integrated into Dependabot

## Contact

For security concerns, email: security@runningdigitally.com
