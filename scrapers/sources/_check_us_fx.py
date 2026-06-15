from scrapling.fetchers import StealthyFetcher

url = 'https://tradingeconomics.com/united-states/foreign-exchange-reserves'
page = StealthyFetcher.fetch(url, headless=True, network_idle=True)
rows = page.css('table#p tr') or page.css('table tr')
print(f'Total rows: {len(rows)}')
for row in rows:
    cells = row.css('td')
    if len(cells) < 4:
        continue
    texts = [c.css('::text').get('').strip() for c in cells]
    print(f'  ({len(cells)} cells): {texts}')
