if __package__:
    from .classes import wb_price
else:
    from classes import wb_price
from typing import Any



PARAMS: dict[str, Any] = {
    'wb': wb_price
}
""" dict of parsers functions

    using to choose what parser need to parsing data
"""

URLS: dict[str, str] = {
    'wb': f'https://card.wb.ru/cards/v4/detail?appType=1&curr=byn&dest=-59208&spp=30&nm='
}

