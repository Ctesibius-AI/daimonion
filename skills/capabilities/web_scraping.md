# Web Scraping

## When Active
When extracting data from websites, parsing HTML, or building scrapers.

## Instructions
- Prefer structured APIs over scraping when available (REST, GraphQL, RSS feeds)
- Use `requests` + `BeautifulSoup` for simple static pages; `playwright` or `selenium` for JS-rendered content
- Set proper User-Agent headers; respect `robots.txt` and rate limits
- Use CSS selectors over XPath when possible — more readable and maintainable
- Handle pagination: detect next-page links, cursor params, or infinite scroll triggers
- Implement retry logic with exponential backoff for failed requests
- Parse dates, prices, and structured data into typed objects immediately
- Store raw HTML alongside extracted data for debugging and re-extraction
- Handle encoding issues: detect charset from headers and meta tags
- For large-scale scraping: use async requests, connection pooling, caching
- Always validate extracted data: check for empty results, changed page structure
- Output as JSON, CSV, or directly into dataframes depending on downstream use
