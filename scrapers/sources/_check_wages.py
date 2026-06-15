from scrapling.fetchers import StealthyFetcher

checks = [
    ('CN', 'https://tradingeconomics.com/china/wages', 'CNY/Year'),
    ('IN', 'https://tradingeconomics.com/india/wages', 'INR/Month'),
    ('SL', 'https://tradingeconomics.com/sri-lanka/wages', 'LKR/Month'),
]

for country, url, unit in checks:
    page = StealthyFetcher.fetch(url, headless=True, network_idle=True)
    rows = page.css('table#p tr') or page.css('table tr')
    found = False
    units_seen = set()
    for row in rows:
        cells = row.css('td')
        if len(cells) < 4:
            continue
        texts = [c.css('::text').get('').strip() for c in cells]
        u = texts[3] if len(texts) > 3 else ''
        if u:
            units_seen.add(u)
        if unit in u:
            print(f'{country} OK: {texts}')
            found = True
            break
    if not found:
        print(f'{country}: unit "{unit}" NOT found. Available: {units_seen}')
