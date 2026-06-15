from scrapling.fetchers import StealthyFetcher

url = 'https://www.tradingview.com/symbols/CSELK-ASI/technicals/'
page = StealthyFetcher.fetch(url, headless=True, network_idle=True)

# Try common price selectors
for sel in [
    '[data-field="last_price"]',
    '[class*="price"]',
    '[class*="last"]',
    '[class*="value"]',
    'span[class*="price"]',
]:
    els = page.css(sel)
    if els:
        texts = [e.css('::text').get('').strip() for e in els[:3]]
        texts = [t for t in texts if t]
        if texts:
            print(f'{sel}: {texts}')

# Also dump page title and any text containing 21,6
import re
html = page.html
matches = re.findall(r'21[,.]6\d+', html)
print('Price pattern matches:', matches[:5])

# Check meta tags
metas = page.css('meta[property*="price"], meta[name*="price"]')
for m in metas:
    print('meta:', m.attrib)
