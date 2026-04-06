import datetime

import httpx

COINPAPRIKA_HISTORICAL_URL_TMPL = "https://api.coinpaprika.com/v1/tickers/{asset_id}/historical"
DEFILLAMA_STABLECOIN_URL_TMPL = "https://stablecoins.llama.fi/stablecoin/{llama_id}"
DEFILLAMA_STABLECOINS_URL = "https://stablecoins.llama.fi/stablecoins?includePrices=true"

DEFILLAMA_ID_BY_SYMBOL = {
    "USDC": "2",
    "USDT": "1",
    "FDUSD": "119",
}


async def fetch_stablecoin_supply_history(asset_id: str, days: int = 3650):
    """
    Fetch stablecoin daily history from Coinpaprika and derive circulating supply.
    Supply ~= market_cap / price.
    """
    if not (asset_id or "").strip():
        return []
    day_count = max(1, int(days))
    start_date = (datetime.datetime.utcnow() - datetime.timedelta(days=day_count)).strftime("%Y-%m-%d")
    params = {"start": start_date, "interval": "1d"}
    headers = {"accept": "application/json", "User-Agent": "Mozilla/5.0"}

    data = None
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            url = COINPAPRIKA_HISTORICAL_URL_TMPL.format(asset_id=asset_id.strip())
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        code = e.response.status_code if e.response is not None else 0
        if code not in (401, 402, 403, 429):
            raise

    if isinstance(data, list) and data:
        rows = []
        for row in data:
            ts = (row.get("timestamp") or "").strip()
            if not ts:
                continue
            day = ts[:10]
            price = float(row.get("price") or 0)
            mcap = float(row.get("market_cap") or 0)
            if price <= 0 or mcap <= 0:
                continue
            supply = mcap / price if price > 0 else 0
            rows.append({
                "trading_date": day,
                "price_usd": round(price, 8),
                "market_cap_usd": round(mcap, 2),
                "supply_amount": round(supply, 2),
            })
        uniq = {}
        for r in rows:
            uniq[r["trading_date"]] = r
        if uniq:
            return [uniq[d] for d in sorted(uniq.keys())]

    # Fallback: DeFiLlama long history
    return await _fetch_stablecoin_supply_history_llama(asset_id=asset_id, days=day_count)


async def _fetch_stablecoin_supply_history_llama(asset_id: str, days: int = 3650):
    symbol = _symbol_from_asset_id(asset_id)
    llama_id = DEFILLAMA_ID_BY_SYMBOL.get(symbol)
    if not llama_id:
        llama_id = await _resolve_defillama_id_by_symbol(symbol)
        if llama_id:
            DEFILLAMA_ID_BY_SYMBOL[symbol] = llama_id
    if not llama_id:
        return []

    cutoff_ts = int((datetime.datetime.utcnow() - datetime.timedelta(days=max(1, int(days)))).timestamp())
    headers = {"accept": "application/json", "User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient(timeout=30) as client:
        url = DEFILLAMA_STABLECOIN_URL_TMPL.format(llama_id=llama_id)
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    chain_balances = data.get("chainBalances") or {}
    by_day = {}
    for chain_obj in chain_balances.values():
        tokens = chain_obj.get("tokens") or []
        for row in tokens:
            ts = int(row.get("date") or 0)
            if ts <= 0 or ts < cutoff_ts:
                continue
            circ = row.get("circulating") or {}
            amt = float(circ.get("peggedUSD") or 0)
            if amt <= 0:
                continue
            day = datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
            by_day[day] = by_day.get(day, 0.0) + amt

    rows = []
    for day in sorted(by_day.keys()):
        supply = round(by_day[day], 2)
        rows.append({
            "trading_date": day,
            "price_usd": 1.0,
            "market_cap_usd": supply,
            "supply_amount": supply,
        })
    return rows


def _symbol_from_asset_id(asset_id: str):
    x = (asset_id or "").lower()
    if x.startswith("usdc-"):
        return "USDC"
    if x.startswith("usdt-"):
        return "USDT"
    if x.startswith("fdusd-"):
        return "FDUSD"
    return x.split("-")[0].upper()


async def _resolve_defillama_id_by_symbol(symbol: str):
    if not symbol:
        return None
    headers = {"accept": "application/json", "User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(DEFILLAMA_STABLECOINS_URL, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    for a in data.get("peggedAssets", []):
        if (a.get("symbol") or "").upper() == symbol.upper():
            sid = a.get("id")
            if sid is not None:
                return str(sid)
    return None


async def fetch_usdc_supply_history(days: int = 3650):
    return await fetch_stablecoin_supply_history("usdc-usd-coin", days=days)
