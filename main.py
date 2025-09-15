import logging
import asyncio
import aiohttp
from datetime import datetime, time
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import requests
import json
import os

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Konfigurasi
TOKEN = "7986346335:AAHwnOObwky-Hz4z5uYgaGIH1D84sJqualw"
CHAT_ID = "5279114407"
WIB = pytz.timezone('Asia/Jakarta')

class BBRIBot:
    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=WIB)
        self.bot_url = f"https://api.telegram.org/bot{TOKEN}"
        self.session = None
        
    async def init_session(self):
        """Initialize aiohttp session"""
        if not self.session:
            self.session = aiohttp.ClientSession()
        
    def is_market_hours(self):
        """Cek apakah sekarang jam bursa"""
        try:
            now = datetime.now(WIB)
            current_time = now.time()
            current_day = now.weekday()
            
            if current_day >= 5:
                return False
                
            market_open = time(9, 0)
            market_close = time(16, 0)
            
            return market_open <= current_time <= market_close
        except Exception as e:
            logger.error(f"Error checking market hours: {e}")
            return False
    
    async def get_brri_price_alpha(self):
        """Gunakan Alpha Vantage API (lebih reliable)"""
        try:
            # Alpha Vantage free API key
            api_key = "demo"  # Ganti dengan API key sendiri jika perlu
            url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=BBRI.JK&apikey={api_key}"
            
            async with self.session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'Global Quote' in data and data['Global Quote']:
                        quote = data['Global Quote']
                        price = quote.get('05. price', 'N/A')
                        return price
            return None
        except Exception as e:
            logger.error(f"Alpha Vantage error: {e}")
            return None
    
    async def get_brri_price_marketstack(self):
        """Gunakan Marketstack API"""
        try:
            api_key = "demo"  # Free tier
            url = f"http://api.marketstack.com/v1/eod/latest?symbols=BBRI.JK&access_key={api_key}"
            
            async with self.session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('data'):
                        stock_data = data['data'][0]
                        price = stock_data.get('close', 'N/A')
                        return price
            return None
        except Exception as e:
            logger.error(f"Marketstack error: {e}")
            return None
    
    async def get_brri_price_fallback(self):
        """Fallback: IDX API atau sumber lain"""
        try:
            # Coba IDX API
            url = "https://www.idx.co.id/umbraco/Surface/StockData/GetSecuritiesStock?code=BBRI"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            async with self.session.get(url, headers=headers, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if data and len(data) > 0:
                        price = data[0].get('Price', 'N/A')
                        return price
            return None
        except Exception as e:
            logger.error(f"Fallback error: {e}")
            return None
    
    async def get_brri_price(self):
        """Ambil harga dengan multiple fallback"""
        try:
            # Coba berbagai API berurutan
            apis = [
                self.get_brri_price_alpha,
                self.get_brri_price_marketstack,
                self.get_brri_price_fallback
            ]
            
            for api in apis:
                price = await api()
                if price and price != 'N/A':
                    return f"{float(price):,.0f}"
                await asyncio.sleep(1)  # Jeda antar requests
                        
            return "N/A"
        except Exception as e:
            logger.error(f"Error fetching stock price: {e}")
            return "Error"
    
    async def send_telegram_message(self, message):
        """Kirim pesan ke Telegram"""
        try:
            url = f"{self.bot_url}/sendMessage"
            payload = {
                'chat_id': CHAT_ID,
                'text': message
            }
            
            async with self.session.post(url, json=payload) as response:
                if response.status == 200:
                    logger.info("✅ Message sent")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Failed to send: {error_text}")
                    return False
        except Exception as e:
            logger.error(f"❌ Telegram error: {e}")
            return False
    
    async def send_price_update(self):
        """Kirim update harga simple"""
        try:
            if self.is_market_hours():
                price = await self.get_brri_price()
                message = f"BBRI Price\n{price}"
                await self.send_telegram_message(message)
            else:
                # Diluar jam bursa, tidak kirim apa-apa
                pass
        except Exception as e:
            logger.error(f"❌ Error in price update: {e}")
    
    def setup_scheduler(self):
        """Setup scheduler"""
        try:
            trigger = CronTrigger(
                day_of_week='mon-fri',
                hour='9-15',
                minute='*',
                timezone=WIB
            )
            
            self.scheduler.add_job(
                self.send_price_update,
                trigger=trigger,
                max_instances=1,
                name='bbri_price_update'
            )
            
            logger.info("✅ Scheduler setup completed")
        except Exception as e:
            logger.error(f"❌ Scheduler error: {e}")
    
    async def run(self):
        """Jalankan bot"""
        try:
            await self.init_session()
            self.setup_scheduler()
            self.scheduler.start()
            
            logger.info("🤖 BBRI Price Bot Started!")
            
            # Kirim pesan startup
            startup_msg = "🤖 BBRI Price Bot Started!\n⏰ Akan kirim harga setiap menit selama jam bursa"
            await self.send_telegram_message(startup_msg)
            
            # Keep running
            while True:
                await asyncio.sleep(3600)
                
        except Exception as e:
            logger.error(f"❌ Bot error: {e}")
        finally:
            if self.session:
                await self.session.close()

async def main():
    bot = BBRIBot()
    await bot.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"💥 Unexpected error: {e}")