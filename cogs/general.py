import discord
import time
import psutil
from discord.ext import commands

units = {
    'days'    : 86400,
    'hours'   : 3600,
    'minutes' : 60,
}
# Faster than psutil or vcgencmd 
def get_temp() -> str:
     with open('/sys/class/thermal/thermal_zone0/temp') as f:
        temp = f.read()
     return f"{temp[:2]}.{temp[2]}\N{DEGREE SIGN}C"

# Faster than psutil or /proc/uptime - probably faster to just timestamp on bot init
def get_uptime() -> str:
    uptime = []
    uptime_seconds = int(time.monotonic())
    for unit, ratio in units.items():
        if (conversion := uptime_seconds // ratio):
            uptime_seconds %= ratio
            unit_label = unit.rstrip('s') if conversion == 1 else unit
            uptime.append(f"{conversion} {unit_label}")
    return ', '.join(uptime)

class General(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot
    # psutil is pretty slow, may be better to send embed with all but CPU stats, then edit once done
    @commands.command(name='status', help='Provides ping, temperature and uptime of bot')
    async def status(self, ctx) -> None:
        latency = round(self.bot.latency * 1000)
        temp = get_temp()
        uptime = get_uptime()
        cpu_usage = psutil.cpu_percent(percpu=True)
        cpu_summary = '\n'.join(f"{core + 1}: {load}%" for core, load in enumerate(cpu_usage))

        embed = discord.Embed(
            title="CPU load",
            description=cpu_summary,
            color=0x2BE02B)
        embed.add_field(name="Ping", value=f"{latency}ms", inline=True)
        embed.add_field(name="Temperature", value=f"{temp}", inline=True)
        embed.set_thumbnail(url=ctx.author.avatar.url)
        embed.set_footer(text=f"uptime: {uptime}")
        await ctx.reply(embed=embed)

    @commands.command(name='unload', help='Admin-only: unloads a given cog')
    @commands.is_owner()
    async def unload(self, ctx, cog: str) -> None:
        try:
            await self.bot.unload_extension(f'cogs.{cog}')
        except Exception:
            embed = discord.Embed(
                description=f'Failed to unload cog: `{cog}`.',
                color=0xE02B2B)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description=f'Unloaded cog: `{cog}`',
                color=0x2BE02B)
            await ctx.send(embed=embed)

    @commands.command(name='load', help='Admin-only: loads a given cog')
    @commands.is_owner()
    async def load(self, ctx, cog: str) -> None:
        try:
            await self.bot.load_extension(f'cogs.{cog}')
        except Exception:
            embed = discord.Embed(
                description=f'Failed to load cog: `{cog}`.',
                color=0xE02B2B)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description=f'Loaded cog: `{cog}`',
                color=0x2BE02B)
            await ctx.send(embed=embed)

async def setup(bot) -> None:
    await bot.add_cog(General(bot))