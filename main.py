import logging
import asyncio
import aiohttp
from datetime import datetime, time
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
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
    
    async def get_brri_price_yahoo(self):
        """Ambil harga langsung dari Yahoo Finance API"""
        try:
            url = "https://query1.finance.yahoo.com/v8/finance/chart/BBRI.JK"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json'
            }
            
            async with self.session.get(url, headers=headers, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Debug: Lihat struktur response
                    logger.info(f"Yahoo API Response: {json.dumps(data)[:200]}...")
                    
                    result = data.get('chart', {}).get('result', [])
                    if result:
                        meta = result[0].get('meta', {})
                        regular_market_price = meta.get('regularMarketPrice')
                        
                        if regular_market_price:
                            return regular_market_price
            return None
        except Exception as e:
            logger.error(f"Yahoo API error: {e}")
            return None
    
    async def get_brri_price_google(self):
        """Alternative: Google Finance"""
        try:
            url = "https://www.google.com/finance/quote/BBRI:IDX"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            async with self.session.get(url, headers=headers, timeout=10) as response:
                if response.status == 200:
                    html = await response.text()
                    
                    # Cari harga dalam HTML
                    if 'BBRI' in html:
                        # Cari pattern harga
                        import re
                        price_pattern = r'\"(\d+\.\d+)\"'
                        matches = re.findall(price_pattern, html)
                        
                        for match in matches:
                            price = float(match)
                            if 1000 < price < 10000:  # Filter reasonable price range
                                return price
            return None
        except Exception as e:
            logger.error(f"Google Finance error: {e}")
            return None
    
    async def get_brri_price(self):
        """Ambil harga dengan multiple fallback"""
        try:
            # Coba Yahoo Finance dulu
            price = await self.get_brri_price_yahoo()
            if price:
                return f"{price:,.0f}"
            
            # Fallback ke Google Finance
            price = await self.get_brri_price_google()
            if price:
                return f"{price:,.0f}"
                        
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
                success = await self.send_telegram_message(message)
                
                if not success:
                    logger.error("Failed to send Telegram message")
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
            
            # Test langsung
            await self.send_price_update()
            
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