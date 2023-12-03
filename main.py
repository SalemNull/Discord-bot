import discord
import os
import random
import logging
import asyncio

from dotenv import find_dotenv, load_dotenv, set_key, get_key
from discord.ext import commands, tasks
from aiohttp import ClientError, ClientSession
from datetime import datetime

from accuweather import (
    AccuWeather,
    ApiError,
    InvalidApiKeyError,
    InvalidCoordinatesError,
    RequestsExceededError,
)

# GLOBALS
MAX_LOC = 2
LOC_CODE = {}
FORECAST_FREQ = 18
DAILY = []
DEG = "\N{DEGREE SIGN}"

# Load file path for dotenv 
env_file = find_dotenv()
load_dotenv()


for i in range(MAX_LOC):
    key = get_key(env_file, f"LOC{i}")
    if key:
        LOC_CODE[key] = get_key(env_file, f"NAME{i}")

print(f"Location code list: {LOC_CODE}")

#TODO: command to add a new location to .env 
# set_key(env_file, f"LOC{i}", f"{new_loc_code}")


# Create a Discord client instance and set the command prefix
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

# Set the confirmation message when the bot is ready
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    
    # list will be True if it has any elements.
    if LOC_CODE:
        update_topic.start()


@bot.command()
async def greet(ctx):
    response = f'Hello {ctx.author.display_name}, I am your discord bot'
    await ctx.send(response)


#TODO: eventually change from time interval to specific times for updating current conditions & daily forecasts
@tasks.loop(minutes=65)
async def update_topic():
    print("Starting Update")
    channel = bot.get_channel(int(os.getenv('CHANNEL_ID')))
    api_key = os.getenv('ACCU_API')
    update_forecast = not (update_topic.current_loop % FORECAST_FREQ)

    if update_forecast: #TODO : and check requests remaining was not already 0 - i.e. keep old data
        global DAILY
        DAILY = []
                    

    report = await get_weather(api_key, update_forecast)

    if report:
        for item in DAILY:
            report += f"\n{item}"

        print(f"------FINAL REPORT IS ------\n{report}\n")
        await channel.edit(topic=report)

    else:
        print("Error returned")
    

# Use Accuweather API to create initial objects for current conditions & forcasts
async def get_weather(api_key, update_forecast):
    current_summary = ""
    requests_remaining = 0
    print(f"update_forecast within function is: {update_forecast}")

    for location, name in LOC_CODE.items():

        async with ClientSession() as websession:
            try:
                weather = AccuWeather(
                    api_key,
                    websession,
                    location_key=location,
                    language="en",
                )
                # Get current weather conditions for this location
                current_conditions = await weather.async_get_current_conditions()

                # If a long duration has passed update the daily forecast 
                if update_forecast:
                    forecast_daily = await weather.async_get_daily_forecast(days=5, metric=False)
                    print("updated daily forecast")
            except (
                ApiError,
                InvalidApiKeyError,
                InvalidCoordinatesError,
                ClientError,
                RequestsExceededError,
            ) as error:
                print(f"Error: {error}")
                return None

            else:
                requests_remaining = weather.requests_remaining
                temperature = int(current_conditions['RealFeelTemperature']['Imperial']['Value'])
                description = current_conditions['WeatherText']
                current_summary += f"{name}: {temperature}{DEG} - {description}\n"
                
                if update_forecast:
                    global DAILY
                    entry = f"{name}: \n"

                    for day in forecast_daily[:3]:
                        date = day['Date'][5:10]
                        maximum = int(day['TemperatureMax']['Value'])
                        minimum = int(day['TemperatureMin']['Value'])
                        entry += f"{date}: [H: {maximum}{DEG}  L: {minimum}{DEG}]\n"
                        
                        
                    DAILY.append(entry)

    current_summary += f"\n{requests_remaining} API calls remaining - updated {datetime.now().strftime('%H:%M')}\n"
    return current_summary


# Retrieve token from the .env file
bot.run(os.getenv('TOKEN'))