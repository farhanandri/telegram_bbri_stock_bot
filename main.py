import logging
import asyncio
import aiohttp
from datetime import datetime, time
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import yfinance as yf

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Konfigurasi
TOKEN = "7986346335:AAHwnOObwky-Hz4z5uYgaGIH1D84sJqualw"
CHAT_ID = "5279114407"  # Hanya chat ID Anda yang bisa terima notifikasi
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
            
            # Weekend check (0-4 = Senin-Jumat)
            if current_day >= 5:
                return False
                
            # Market hours check (09:00-16:00 WIB)
            market_open = time(9, 0)
            market_close = time(16, 0)
            
            return market_open <= current_time <= market_close
        except Exception as e:
            logger.error(f"Error checking market hours: {e}")
            return False
    
    async def get_brri_price(self):
        """Ambil harga saham BBRI saja"""
        try:
            stock = yf.Ticker("BBRI.JK")
            history = stock.history(period="1d")
            
            if not history.empty:
                current_price = history['Close'].iloc[-1]
                return f"{current_price:,.0f}"
            else:
                return "N/A"
                        
        except Exception as e:
            logger.error(f"Error fetching stock price: {e}")
            return "Error"
    
    async def send_telegram_message(self, message):
        """Kirim pesan ke Telegram - HANYA untuk chat ID Anda"""
        try:
            url = f"{self.bot_url}/sendMessage"
            payload = {
                'chat_id': CHAT_ID,  # Hanya kirim ke chat ID Anda
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
        """Kirim update harga simple seperti bot SOL"""
        try:
            if self.is_market_hours():
                price = await self.get_brri_price()
                message = f"BBRI Price\n{price}"
                await self.send_telegram_message(message)
            else:
                # Diluar jam bursa, tidak kirim apa-apa (silent)
                pass
        except Exception as e:
            logger.error(f"❌ Error in price update: {e}")
    
    def setup_scheduler(self):
        """Setup scheduler untuk mengirim harga setiap menit"""
        try:
            # Kirim setiap menit dari Senin-Jumat (09:00-15:59)
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
            logger.info("📊 Akan kirim harga setiap menit (09:00-16:00 WIB, Senin-Jumat)")
            
            # Kirim pesan startup
            startup_msg = "🤖 BBRI Price Bot Started!\n⏰ Akan kirim harga setiap menit selama jam bursa"
            await self.send_telegram_message(startup_msg)
            
            # Keep running forever
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