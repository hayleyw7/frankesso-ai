"""One explicitly approved HTTPS search. No redirects, retries, cookies or link fetching."""
from html.parser import HTMLParser
import http.client
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

HOST = "html.duckduckgo.com"
PATH = "/html/"
DESTINATION = "https://" + HOST + PATH
MAX_RESPONSE = 512 * 1024
HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept": "text/html",
    "Accept-Encoding": "identity",
    "User-Agent": "LocalAgent/1.0 (human-approved search)",
}


class SearchResults(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.results = []
        self.href = None
        self.title = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and "result__a" in attrs.get("class", "").split():
            self.href = attrs.get("href", "")
            self.title = []

    def handle_data(self, data):
        if self.href is not None:
            self.title.append(data[:500])

    def handle_endtag(self, tag):
        if tag != "a" or self.href is None:
            return
        url = urljoin(DESTINATION, self.href)
        parsed = urlsplit(url)
        if parsed.hostname in {"duckduckgo.com", "www.duckduckgo.com", HOST}:
            url = parse_qs(parsed.query).get("uddg", [url])[0]
        parsed = urlsplit(url)
        if parsed.scheme in {"http", "https"} and parsed.hostname and not parsed.username:
            if len(self.results) < 5:
                self.results.append({"title": " ".join("".join(self.title).split())[:300], "url": url[:2000]})
        self.href = None
        self.title = []


def search(query, approval, connection_factory=None):
    """Approval is mandatory and precedes even DNS/connection construction."""
    if not isinstance(query, str) or not 1 <= len(query) <= 500:
        return {"error": "Query must be 1-500 characters", "network_request": False}
    body = urlencode({"q": query}).encode("ascii")
    details = (
        "Destination: " + DESTINATION + "\nMethod: POST\n"
        "Exact query (escaped for clarity): " + ascii(query) + "\n"
        "Exact form body: " + body.decode("ascii") + "\n"
        "Sent data: this query, standard HTTPS request headers, and your public IP address.\n"
        "No file contents or chat history are attached. If the query itself contains private data, it will be sent.\n"
        "This approval permits ONE search request. Redirects, retries and result-page visits are disabled."
    )
    if not approval("WEB SEARCH — ONE INTERNET REQUEST", details):
        return {"denied": True, "network_request": False}
    connection = None
    attempted = False
    try:
        # HTTPSConnection verifies TLS certificates by default. No environment proxies or cookies.
        factory = connection_factory or http.client.HTTPSConnection
        connection = factory(HOST, port=443, timeout=20)
        attempted = True
        connection.request("POST", PATH, body=body, headers=HEADERS)
        response = connection.getresponse()
        if 300 <= response.status < 400:
            return {"error": "Search service redirected. Redirect was NOT followed; another destination needs separate approval.",
                    "network_request": True, "status": response.status}
        if response.status != 200:
            return {"error": "Search service returned HTTP " + str(response.status) + ". No retry was made.",
                    "network_request": True, "status": response.status}
        if "text/html" not in response.getheader("Content-Type", "").lower():
            return {"error": "Unexpected search response format", "network_request": True}
        raw = response.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE:
            return {"error": "Search response exceeded size limit", "network_request": True}
        parsed = SearchResults()
        parsed.feed(raw.decode("utf-8", errors="replace"))
        return {"provider": "DuckDuckGo HTML", "query": query, "network_request": True,
                "results": parsed.results, "pages_fetched": False,
                "note": "Result titles and links only; source pages were not visited." if parsed.results else
                        "No usable results parsed. This may be a challenge page or provider format change; no retry was made."}
    except (OSError, http.client.HTTPException, ValueError):
        return {"error": "Search connection or parsing failed. No retry was made; local tools remain available.",
                "network_request": attempted}
    finally:
        if connection is not None:
            connection.close()
