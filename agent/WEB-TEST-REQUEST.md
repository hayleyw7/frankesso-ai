# Approved live test — 2026-10-28

The user approved this exact test. It completed successfully with one approval prompt and one HTTPS POST, returning five search titles/links, including `https://www.python.org/doc/`. No redirects, retries or result-page visits occurred. This approval is consumed and does not authorize future searches.

- Provider: DuckDuckGo HTML
- Exact destination: `https://html.duckduckgo.com/html/`
- Method: `POST`
- Exact query: `Python official documentation`
- Exact form body: `q=Python+official+documentation`
- Data exposure: the query, standard HTTPS headers, and the requesting computer's public IP. No user files, chat history, credentials, or cookies are attached.
- Scope: one request only. No redirects, retries, or result-page fetches.

The provider may reject automated requests or return a challenge. Approval does not guarantee usable results. No alternate endpoint will be tried without separate approval.
