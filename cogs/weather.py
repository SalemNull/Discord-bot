import discord
import os
import logging
import datetime
from dotenv import find_dotenv, load_dotenv, set_key, get_key
from discord.ext import commands, tasks
from aiohttp import ClientError, ClientSession
from zoneinfo import ZoneInfo

from accuweather import (
    AccuWeather,
    ApiError,
    InvalidApiKeyError,
    InvalidCoordinatesError,
    RequestsExceededError,
)
# GLOBALS
MAX_LOC = 2
DEG = "\N{DEGREE SIGN}"
log = logging.getLogger(__name__)

# iterable unpacking makes this a neat one liner - these will be the times the weather is updated
times = [datetime.time(hour=hour, tzinfo=ZoneInfo("America/Los_Angeles"))
        for hour in [*range(3), *range(8,24)]]

# TODO : command to add a new location
# TODO : stop storing location info in env - consider just pickling the object  

# set_key(env_file, f"LOC{i}", f"{new_loc_code}")


def load_locs():
    locs = {}
    env_file = find_dotenv()
    for i in range(MAX_LOC):
        key = get_key(env_file, f"LOC{i}")
        if key:
            locs[key] = get_key(env_file, f"NAME{i}")
    return locs
    

class Weather(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.api_key = os.getenv('ACCU_API')
        self.daily = []
        self.requests_remaining = 50
        self.locs = load_locs()
        if self.locs:
            self.update_topic.start()

    # Remove scheduling on unload
    def cog_unload(self) -> None:
        self.update_topic.cancel()

    @tasks.loop(time=times)
    async def update_topic(self) -> None:
        # If the bot just started, or if it's 8AM let's update the multi day forecast 
        if self.update_topic.next_iteration.time() == times[4] or not self.daily:
            update_forecast = True
            self.daily = []
        else:
            update_forecast = False
        report = await self.get_weather(update_forecast)
        if report:
            report += '\n'.join(self.daily)
            log.info(f'Updating channel description')
            await self.channel.edit(topic=report)

    @update_topic.before_loop
    async def before_update(self) -> None:
        log.info("Waiting to initialize weather")
        await self.bot.wait_until_ready()
        self.channel = self.bot.get_channel(int(os.getenv('CHANNEL_ID'))) 

    # Use Accuweather API to create object for current conditions & forcasts
    async def get_weather(self, update_forecast: bool) -> str:
        current_summary = ""
        async with ClientSession() as websession:
            for location, name in self.locs.items():
                try:
                    weather = AccuWeather(
                        self.api_key,
                        websession,
                        location_key=location,
                        language="en")
                    # Get current weather conditions for this location and format
                    current_conditions = await weather.async_get_current_conditions()
                    self.requests_remaining = weather.requests_remaining
                    temperature = int(current_conditions['RealFeelTemperature']['Imperial']['Value'])
                    description = current_conditions['WeatherText']
                    current_summary += f"{name}: {temperature}{DEG} - {description}\n"

                    # Update the daily forecast and format self.daily 
                    if update_forecast:
                        forecast_daily = await weather.async_get_daily_forecast(days=5, metric=False)
                        log.info(f'Daily updated for {name}.')
                        entry = f"{name}: \n"
                        for day in forecast_daily[:3]:
                            date = day['Date'][5:10]
                            maximum = int(day['TemperatureMax']['Value'])
                            minimum = int(day['TemperatureMin']['Value'])
                            entry += f"{date}: [H: {maximum}{DEG}  L: {minimum}{DEG}]\n"
                        self.daily.append(entry)
                except (ApiError, InvalidApiKeyError, InvalidCoordinatesError,
                        ClientError, RequestsExceededError) as error:
                    log.exception(error)
                    return None
        self.last_ran = datetime.datetime.now().strftime('%H:%M')
        current_summary += f"\n{self.requests_remaining} API calls remaining - updated {self.last_ran}\n\n"
        return current_summary

async def setup(bot) -> None:
    await bot.add_cog(Weather(bot))
