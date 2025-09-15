import yfinance as yf
import requests
import asyncio
import aiohttp
from datetime import datetime

async def test_yfinance():
    print("Testing yfinance...")
    try:
        stock = yf.Ticker("BBRI.JK")
        info = stock.info
        history = stock.history(period="1d")
        print("yfinance SUCCESS:")
        print(f"Info: {info}")
        print(f"History: {history}")
        return True
    except Exception as e:
        print(f"yfinance ERROR: {e}")
        return False

async def test_idx_api():
    print("Testing IDX API...")
    try:
        url = "https://www.idx.co.id/umbraco/Surface/StockData/GetSecuritiesStock"
        params = {'code': 'BBRI', 'sort': 'Code', 'order': 'asc'}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=10) as response:
                data = await response.json()
                print("IDX API SUCCESS:")
                print(f"Data: {data}")
                return True
    except Exception as e:
        print(f"IDX API ERROR: {e}")
        return False

async def test_direct_finance():
    print("Testing direct finance APIs...")
    try:
        # Coba API alternatif
        url = "https://query1.finance.yahoo.com/v8/finance/chart/BBRI.JK"
        response = requests.get(url, timeout=10)
        print(f"Yahoo Finance API Status: {response.status_code}")
        if response.status_code == 200:
            print("Yahoo Finance API SUCCESS")
            return True
    except Exception as e:
        print(f"Direct API ERROR: {e}")
    
    return False

async def main():
    print("Running API tests...")
    results = await asyncio.gather(
        test_yfinance(),
        test_idx_api(),
        test_direct_finance()
    )
    
    print(f"\nTest Results: {sum(results)}/3 passed")

if __name__ == "__main__":
    asyncio.run(main())