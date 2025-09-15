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

class StockBot:
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
    
    async def get_stock_price_yahoo(self, symbol):
        """Ambil harga saham dari Yahoo Finance API"""
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json'
            }
            
            async with self.session.get(url, headers=headers, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    result = data.get('chart', {}).get('result', [])
                    if result:
                        meta = result[0].get('meta', {})
                        regular_market_price = meta.get('regularMarketPrice')
                        
                        if regular_market_price:
                            return regular_market_price
            return None
        except Exception as e:
            logger.error(f"Yahoo API error for {symbol}: {e}")
            return None
    
    async def get_stock_price_google(self, symbol):
        """Alternative: Google Finance"""
        try:
            url = f"https://www.google.com/finance/quote/{symbol}:IDX"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            async with self.session.get(url, headers=headers, timeout=10) as response:
                if response.status == 200:
                    html = await response.text()
                    
                    # Cari harga dalam HTML
                    import re
                    price_pattern = r'\"(\d+\.\d+)\"'
                    matches = re.findall(price_pattern, html)
                    
                    for match in matches:
                        price = float(match)
                        if 100 < price < 10000:  # Filter reasonable price range
                            return price
            return None
        except Exception as e:
            logger.error(f"Google Finance error for {symbol}: {e}")
            return None
    
    async def get_stock_price(self, symbol):
        """Ambil harga saham dengan multiple fallback"""
        try:
            # Coba Yahoo Finance dulu
            price = await self.get_stock_price_yahoo(symbol)
            if price:
                return f"{price:,.0f}"
            
            # Fallback ke Google Finance
            price = await self.get_stock_price_google(symbol)
            if price:
                return f"{price:,.0f}"
                        
            return "N/A"
        except Exception as e:
            logger.error(f"Error fetching {symbol} price: {e}")
            return "Error"
    
    async def get_all_prices(self):
        """Ambil harga untuk semua saham"""
        try:
            # Ambil harga BBRI dan CDIA secara bersamaan
            bbri_price = await self.get_stock_price("BBRI.JK")
            cdia_price = await self.get_stock_price("CDIA.JK")
            
            return bbri_price, cdia_price
        except Exception as e:
            logger.error(f"Error getting all prices: {e}")
            return "Error", "Error"
    
    async def send_telegram_message(self, message):
        """Kirim pesan ke Telegram"""
        try:
            url = f"{self.bot_url}/sendMessage"
            payload = {
                'chat_id': CHAT_ID,
                'text': message,
                'parse_mode': 'HTML'
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
        """Kirim update harga untuk semua saham"""
        try:
            if self.is_market_hours():
                bbri_price, cdia_price = await self.get_all_prices()
                
                # Format pesan dengan emoticon menarik
                message = (
                    f"🚀 <b>STOCK UPDATE</b> 🚀\n\n"
                    f"🏦 <b>BBRI</b>: <code>Rp {bbri_price}</code>\n"
                    f"💎 <b>CDIA</b>: <code>Rp {cdia_price}</code>\n\n"
                    f"⏰ {datetime.now(WIB).strftime('%H:%M:%S')} WIB\n"
                    f"📅 {datetime.now(WIB).strftime('%d/%m/%Y')}"
                )
                
                success = await self.send_telegram_message(message)
                
                if not success:
                    # Fallback tanpa HTML
                    fallback_msg = (
                        f"STOCK UPDATE\n\n"
                        f"BBRI: Rp {bbri_price}\n"
                        f"CDIA: Rp {cdia_price}\n\n"
                        f"Waktu: {datetime.now(WIB).strftime('%H:%M:%S')} WIB"
                    )
                    payload = {
                        'chat_id': CHAT_ID,
                        'text': fallback_msg
                    }
                    async with self.session.post(self.bot_url + "/sendMessage", json=payload):
                        pass
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
                name='stock_price_update'
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
            
            logger.info("🤖 Stock Price Bot Started!")
            logger.info("📊 Monitoring: BBRI & CDIA")
            logger.info("⏰ Schedule: Senin-Jumat, 09:00-16:00 WIB")
            
            # Kirim pesan startup
            startup_msg = (
                "🤖 <b>Stock Price Bot Started!</b>\n\n"
                "📊 <b>Monitoring:</b> BBRI & CDIA\n"
                "⏰ <b>Schedule:</b> Setiap menit (09:00-16:00 WIB)\n"
                "✅ <b>Status:</b> Active"
            )
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
    bot = StockBot()
    await bot.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"💥 Unexpected error: {e}")