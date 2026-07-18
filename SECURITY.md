# Security Policy

## Reporting a Vulnerability

Please report security issues privately — **do not open a public issue** for
anything exploitable.

Email **hello@flipperboards.com** with:

- A description of the issue and its impact
- Steps to reproduce
- Any suggested fix, if you have one

You'll get an acknowledgement within a few days. Once a fix ships, we're happy
to credit you in the release notes (or keep you anonymous — your call).

## Deployment guidance

FlipperBoards is designed for trusted private networks. Optional password
protection (Config → Security) restricts control to people with the password
while leaving displays open — enable it whenever untrusted people share the
network (guest Wi-Fi, public venues).

Even with the password enabled, do not expose the API/UI ports directly to
the internet; put it behind a VPN, or a reverse proxy with authentication, if
you need remote access. Reads (display state, screen list) are intentionally
unauthenticated so wall-mounted displays work unattended.
