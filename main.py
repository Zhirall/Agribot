import discord
from discord import app_commands
from discord.ext import commands
import json
import asyncio
import os
import time
from dotenv import load_dotenv
from database import Database

load_dotenv()
TOKEN = os.getenv("TOKEN")
FARMERS_ROLE_ID = int(os.getenv("FARMERS_ROLE_ID"))

db = Database()

with open("timers.json", "r", encoding="utf-8") as f:
    CROP_DATA = json.load(f)

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)


async def get_or_create_emoji(guild: discord.Guild, crop: str):
    name = crop.replace(" ", "_").lower()
    found = discord.utils.get(guild.emojis, name=name)
    if found:
        return str(found)

    path = os.path.join("emojis", f"{crop}.png")
    if os.path.exists(path):
        with open(path, "rb") as f:
            img = f.read()
        try:
            new_emoji = await guild.create_custom_emoji(name=name, image=img)
            return str(new_emoji)
        except discord.HTTPException:
            pass
    return "🪴"


def get_crop_image_path(crop: str):
    """Get the path to the crop image if it exists"""
    path = os.path.join("emojis", f"{crop}.png")
    return path if os.path.exists(path) else None


async def timer_task(timer_id: int, duration: int, user_id: int, crop: str, emoji: str):
    await asyncio.sleep(duration)
    
    user = bot.get_user(user_id)
    if user:
        try:
            embed = discord.Embed(
                title="🎉 Crop Ready!",
                description=f"Your **{crop}** is ready to harvest!",
                color=discord.Color.green()
            )
            embed.add_field(name="Crop", value=f"{emoji} {crop}", inline=False)
            
            image_path = get_crop_image_path(crop)
            if image_path:
                file = discord.File(image_path, filename=f"{crop}.png")
                embed.set_thumbnail(url=f"attachment://{crop}.png")
                await user.send(embed=embed, file=file)
            else:
                await user.send(embed=embed)
        except discord.Forbidden:
            pass
    
    db.remove_timer(timer_id)


async def restore_timers():
    active = db.get_active_timers()
    now = int(time.time())
    
    for timer in active:
        timer_id, user_id, crop, end_time, emoji, channel_id = timer
        remaining = end_time - now
        
        if remaining > 0:
            asyncio.create_task(timer_task(timer_id, remaining, user_id, crop, emoji))
        else:
            user = bot.get_user(user_id)
            if user:
                try:
                    embed = discord.Embed(
                        title="🎉 Crop Ready!",
                        description=f"Your **{crop}** is ready to harvest!",
                        color=discord.Color.green()
                    )
                    embed.add_field(name="Crop", value=f"{emoji} {crop}", inline=False)
                    
                    image_path = get_crop_image_path(crop)
                    if image_path:
                        file = discord.File(image_path, filename=f"{crop}.png")
                        embed.set_thumbnail(url=f"attachment://{crop}.png")
                        await user.send(embed=embed, file=file)
                    else:
                        await user.send(embed=embed)
                except discord.Forbidden:
                    pass
            db.remove_timer(timer_id)

@bot.tree.command(name="farm", description="Start growing a crop from the farm list.")
@app_commands.choices(_crop=[
    app_commands.Choice(name=crop, value=crop) for crop in CROP_DATA.keys()
])
@app_commands.rename(_crop="crop")
async def farm(interaction: discord.Interaction, _crop: app_commands.Choice[str]):
    crop = _crop.value
    crop_data = CROP_DATA.get(crop)
    if not crop_data:
        embed = discord.Embed(
            title="❌ Crop Not Found",
            description=f"The crop **{crop}** doesn't exist in the farm list.",
            color=discord.Color.red()
        )
        embed.add_field(
            name="Available Crops",
            value=", ".join(CROP_DATA.keys()),
            inline=False
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    guild = interaction.guild
    emoji = await get_or_create_emoji(guild, crop)
    duration = crop_data["growthTimeSeconds"]
    end_time = int(time.time()) + duration

    db.add_timer(
        user_id=interaction.user.id,
        crop=crop,
        end_time=end_time,
        emoji=emoji,
        channel_id=interaction.channel.id
    )

    all_timers = db.get_all_timers()
    timer_id = all_timers[-1][0]

    # Create embed with thumbnail
    embed = discord.Embed(
        title="🌱 Crop Planted!",
        description=f"You successfully planted **{crop}**!",
        color=discord.Color.blue()
    )
    embed.add_field(name="Crop", value=f"{emoji} {crop}", inline=True)
    embed.add_field(name="Ready", value=f"<t:{end_time}:R>", inline=True)
    embed.add_field(name="Harvest Time", value=f"<t:{end_time}:f>", inline=False)
    embed.set_footer(text=f"{interaction.user.name}'s Farm", icon_url=interaction.user.display_avatar.url)
    embed.timestamp = discord.utils.utcnow()
    
    # Add thumbnail if image exists
    image_path = get_crop_image_path(crop)
    if image_path:
        file = discord.File(image_path, filename=f"{crop}.png")
        embed.set_thumbnail(url=f"attachment://{crop}.png")
        await interaction.response.send_message(embed=embed, file=file, ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed, ephemeral=True)

    asyncio.create_task(timer_task(timer_id, duration, interaction.user.id, crop, emoji))


@bot.tree.command(name="farm-list", description="List your active farm timers.")
async def farm_list(interaction: discord.Interaction):
    all_timers = db.get_active_timers()
    user_timers = [t for t in all_timers if t[1] == interaction.user.id]
    
    if not user_timers:
        embed = discord.Embed(
            title="🌾 Your Farm",
            description="You have no active crops right now! Use `/farm` to start growing.",
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"{interaction.user.name}'s Farm", icon_url=interaction.user.display_avatar.url)
        embed.timestamp = discord.utils.utcnow()
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    # Sort by end_time (soonest first)
    user_timers.sort(key=lambda t: t[3])

    embed = discord.Embed(
        title="🌾 Your Active Farm",
        description=f"You are currently growing **{len(user_timers)}** crop{'s' if len(user_timers) != 1 else ''}",
        color=discord.Color.green()
    )

    for timer in user_timers:
        timer_id, user_id, crop, end_time, emoji, channel_id = timer
        
        embed.add_field(
            name=f"{emoji} {crop}",
            value=f"Ready: <t:{end_time}:R>\n<t:{end_time}:f>",
            inline=True
        )

    embed.set_footer(text=f"{interaction.user.name}'s Farm", icon_url=interaction.user.display_avatar.url)
    embed.timestamp = discord.utils.utcnow()
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="farm-clear", description="Clear all your active farm timers.")
async def farm_clear(interaction: discord.Interaction):
    all_timers = db.get_all_timers()
    user_timers = [t for t in all_timers if t[1] == interaction.user.id]
    count = len(user_timers)
    
    if count == 0:
        embed = discord.Embed(
            title="🌾 No Crops to Clear",
            description="You don't have any active crops to clear.",
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"{interaction.user.name}'s Farm", icon_url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    for timer in user_timers:
        db.remove_timer(timer[0])
    
    embed = discord.Embed(
        title="🧹 Farm Cleared",
        description=f"Successfully cleared **{count}** timer{'s' if count != 1 else ''} from your farm.",
        color=discord.Color.red()
    )
    embed.add_field(name="Crops Removed", value=str(count), inline=True)
    embed.set_footer(text=f"{interaction.user.name}'s Farm", icon_url=interaction.user.display_avatar.url)
    embed.timestamp = discord.utils.utcnow()
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="farm-clear-all", description="Clear ALL farm timers from everyone (Admin only).")
@app_commands.checks.has_permissions(administrator=True)
async def farm_clear_all(interaction: discord.Interaction):
    count = len(db.get_all_timers())
    
    if count == 0:
        embed = discord.Embed(
            title="🌾 No Crops to Clear",
            description="There are no active farm timers to clear.",
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"Checked by {interaction.user.name}", icon_url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)
        return
    
    db.clear_all()
    
    embed = discord.Embed(
        title="🧹 All Farm Timers Cleared",
        description=f"Successfully cleared **{count}** timer{'s' if count != 1 else ''} from all users.",
        color=discord.Color.red()
    )
    embed.add_field(name="Total Timers Removed", value=str(count), inline=True)
    embed.set_footer(text=f"Cleared by {interaction.user.name}", icon_url=interaction.user.display_avatar.url)
    embed.timestamp = discord.utils.utcnow()
    
    await interaction.response.send_message(embed=embed)


@bot.event
async def on_ready():
    await bot.tree.sync()
    await restore_timers()
    print(f"✅ Logged in as {bot.user}")
    print(f"📊 Restored {len(db.get_active_timers())} active timers")

bot.run(TOKEN)