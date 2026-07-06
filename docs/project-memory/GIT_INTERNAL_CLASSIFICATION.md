# Git/GitHub vs Internal Classification

## May be eligible for Git/GitHub after review
- Generic source code without secrets or customer-specific data
- Generic tests using synthetic data
- Public-safe architecture examples
- Reusable deployment tooling without internal credentials/addresses
- Open-source notices and dependency metadata

## Internal only by default
- Real customer names, invoices, requests and transaction records
- Bank statements and reconciliation data
- Personal information
- Credentials, tokens, keys, connection strings and secrets
- Internal network details when security-sensitive
- Company strategy and non-public operating plans
- Real production logs containing business data
- Internal AI prompts/knowledge containing confidential information
- Contracts and non-public financial information

## Required release check
Before public push:
1. secret scan
2. real-data scan
3. customer/company confidentiality review
4. path/network metadata review
5. license review
6. synthetic test data confirmation
