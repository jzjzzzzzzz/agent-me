# Security policy

## Supported versions

Security fixes target the latest release on `main`.

## Reporting a vulnerability

Use the repository's **Security → Report a vulnerability** flow. Do not disclose exploitable details in a public issue. Include affected version, reproduction steps, impact, and a suggested fix if available.

Do not send real credentials or private user data in a report. Maintainers will acknowledge a complete report, investigate it, and coordinate a fix and disclosure.

## Operator responsibilities

This framework cannot make private documents safe to publish. Operators must review knowledge content, configure rate limiting and TLS, protect provider credentials, and publish an accurate privacy notice for their deployment.

## Automated checks

Pull requests and `main` run the normal lint/test/container workflow plus CodeQL
`security-extended` analysis for Python and JavaScript/TypeScript. CodeQL also runs weekly so new
queries can inspect unchanged code. Dependabot monitors Python, npm, GitHub Actions, and container
dependencies; secret scanning is enabled on the public repository.

These checks complement review, locked dependency audits, threat modeling, and deployment controls.
A green scan does not prove that knowledge content is publishable or that an operator's ingress,
rate limits, credentials, and privacy notice are correctly configured.
