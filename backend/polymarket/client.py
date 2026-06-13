import time
from decimal import Decimal
from polymarket import AsyncPublicClient, AsyncSecureClient
from polymarket.streams import MarketSpec, CryptoPricesSpec, UserSpec
from backend.config import settings


class PolymarketClient:
    """
    Thin wrapper around AsyncSecureClient and AsyncPublicClient.
    Must be used as an async context manager or closed via await client.close().
    """

    def __init__(self):
        self._public: AsyncPublicClient | None = None
        self._secure: AsyncSecureClient | None = None

    async def connect(self):
        self._public = AsyncPublicClient()
        self._secure = await AsyncSecureClient.create(
            private_key=settings.polymarket_private_key,
            wallet=settings.polymarket_wallet_address,
        )
        await self._secure.setup_trading_approvals()

    async def close(self):
        if self._secure:
            await self._secure.close()
        if self._public:
            await self._public.close()

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *_):
        await self.close()

    # ── Market discovery ──────────────────────────────────────────────────────

    async def find_btc_5min_markets(self) -> list:
        """Return all open BTC 5-minute Up/Down markets sorted by start_date."""
        results = []
        markets = self._public.list_markets(closed=False, page_size=50)
        async for page in markets:
            for market in page.items:
                slug = market.slug or ""
                if "btc" in slug.lower() and "updown" in slug.lower().replace("-", ""):
                    results.append(market)
        return sorted(results, key=lambda m: m.state.start_date or 0)

    async def get_order_book(self, token_id: str):
        return await self._public.get_order_book(token_id=token_id)

    async def get_midpoint(self, token_id: str) -> Decimal:
        return await self._public.get_midpoint(token_id=token_id)

    # ── Order placement ───────────────────────────────────────────────────────

    async def place_limit_buy(self, token_id: str, price: str, size: str) -> str | None:
        """Place maker limit BUY order. Returns order_id or None on failure."""
        response = await self._secure.place_limit_order(
            token_id=token_id,
            side="BUY",
            price=price,
            size=size,
        )
        return response.order_id if response.ok else None

    async def place_limit_sell(self, token_id: str, price: str, size: str,
                                expiration_seconds: int = 10) -> str | None:
        """Place expiring maker limit SELL (10s TTL = FAK behaviour without taker fee)."""
        response = await self._secure.place_limit_order(
            token_id=token_id,
            side="SELL",
            price=price,
            size=size,
            expiration=int(time.time()) + expiration_seconds,
        )
        return response.order_id if response.ok else None

    async def place_market_sell_fak(self, token_id: str, shares: str) -> str | None:
        """Fill-and-Kill market sell — for emergency exits and S3c bail."""
        response = await self._secure.place_market_order(
            token_id=token_id,
            side="SELL",
            shares=shares,
            order_type="FAK",
        )
        return response.order_id if response.ok else None

    async def cancel_order(self, order_id: str) -> bool:
        response = await self._secure.cancel_order(order_id=order_id)
        return bool(response.canceled)

    async def cancel_all_market_orders(self, token_id: str):
        await self._secure.cancel_market_orders(token_id=token_id)

    async def get_wallet_balance(self) -> Decimal:
        values = await self._secure.get_portfolio_values(market=[])
        return values[0].value if values else Decimal("0")

    # ── Realtime stream ───────────────────────────────────────────────────────

    async def subscribe_market_and_btc(self, up_token_id: str, down_token_id: str):
        """
        Returns a merged async stream of:
          - MarketPriceChangeEvent / MarketBestBidAskEvent for UP and DOWN tokens
          - CryptoPricesBinanceEvent for BTC/USDT spot
          - UserSpec for fill confirmations
        """
        stream = await self._secure.subscribe([
            MarketSpec(token_ids=[up_token_id, down_token_id]),
            CryptoPricesSpec(topic="prices.crypto.binance", symbols=["btcusdt"]),
            UserSpec(),
        ])
        return stream
