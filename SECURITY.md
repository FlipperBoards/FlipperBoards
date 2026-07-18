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

FlipperBoards currently has **no built-in authentication** — it is designed to
run on a trusted local network. Do not expose the API/UI ports directly to the
internet; put it behind a VPN, or a reverse proxy with authentication, if you
need remote access.
