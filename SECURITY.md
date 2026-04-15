# Security Policy

## Reporting a vulnerability

If you discover a security vulnerability, please report it responsibly.

**Do NOT open a public issue.** Instead, email: **security@dataspoc.com**

We will acknowledge receipt within 48 hours and provide an initial assessment within 7 days.

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Scope

DataSpoc Pipe delegates all access control to cloud IAM. The following are in scope:

- Code injection via pipeline configuration
- Path traversal in bucket/file operations
- Secret leakage in logs or manifests
- Dependency vulnerabilities

The following are out of scope:

- Cloud IAM misconfiguration (user responsibility)
- Singer tap vulnerabilities (report to tap maintainers)
