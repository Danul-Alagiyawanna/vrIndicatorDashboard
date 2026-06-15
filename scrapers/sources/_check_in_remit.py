from scrapling.fetchers import StealthyFetcher

url = 'https://tradingeconomics.com/india/remittances'
page = StealthyFetcher.fetch(url, headless=True, network_idle=True)
rows = page.css('table#p tr') or page.css('table tr')
match = 0
for row in rows:
    cells = row.css('td')
    if len(cells) < 4:
        continue
    texts = [c.css('::text').get('').strip() for c in cells]
    if 'USD Million' in (texts[3] if len(texts) > 3 else ''):
        print(f'USD Million match #{match} ({len(cells)} cells): {texts}')
        match += 1
