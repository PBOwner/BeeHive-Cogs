import requests
import asyncio
import discord
from redbot.core import commands
import time, json
import io

class Malcore(commands.Cog):
    """malcore file upload and analysis via Discord"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def malcore(self, ctx, file_url: str = None):
        async with ctx.typing():
            if file_url:
                await ctx.send(f"Looking At {file_url}")
            else:
                await ctx.send("No URL provided.")

    # async def check_results(self, ctx, analysis_id, presid):
    #     vt_key = await self.bot.get_shared_api_tokens("virustotal")
    #     headers = {"x-apikey": vt_key["api_key"]}
        
    #     while True:
    #         response = requests.get(f'https://www.virustotal.com/api/v3/analyses/{analysis_id}', headers=headers)
    #         data = response.json()
            
    #         if "data" in data:
    #             attributes = data["data"].get("attributes")
    #             if attributes and attributes.get("status") == "completed":
    #                 stats = attributes.get("stats", {})
    #                 malicious_count = stats.get("malicious", 0)
    #                 suspicious_count = stats.get("suspicious", 0)
    #                 undetected_count = stats.get("undetected", 0)
    #                 harmless_count = stats.get("harmless", 0)
    #                 failure_count = stats.get("failure", 0)
    #                 unsupported_count = stats.get("type-unsupported", 0)
    #                 meta = data.get("meta", {}).get("file_info", {}).get("sha256")
                    
    #                 if meta:
    #                     embed = discord.Embed(url=f"https://www.virustotal.com/gui/file/{meta}")
    #                     if malicious_count > 0:
    #                         content = f"||<@{presid}>||"
    #                         embed.title = f"That file looks malicious!"
    #                         embed.description = f"One or more security vendors have marked this file as potentially dangerous.\n\nFor your own safety, you should not open, launch, or interact with it."
    #                         embed.color = 0xFF4545  # Red color
    #                         embed.set_thumbnail(url="https://www.beehive.systems/hubfs/Icon%20Packs/Red/warning-outline.png")
    #                     else:
    #                         content = f"||<@{presid}>||"
    #                         embed.title = f"That file looks safe!"
    #                         embed.color = 0x2BBD8E  # Green color
    #                         embed.description = f"There's nothing obviously malicious about this file - it should be safe."
    #                         embed.add_field(name="Overall verdict", value="Scanned and found safe", inline=False)
    #                         embed.set_thumbnail(url="https://www.beehive.systems/hubfs/Icon%20Packs/Green/checkmark-circle-outline.png")
                        
    #                     total_count = malicious_count + suspicious_count + undetected_count + harmless_count + failure_count + unsupported_count
    #                     percentpre = malicious_count / total_count if total_count > 0 else 0
    #                     percent = round(percentpre * 100, 2)
    #                     embed.add_field(name="Analysis results", value=f"**{percent}% of security vendors rated this file dangerous!**\n({malicious_count} malicious, {undetected_count} clean)", inline=False)

    #                     await ctx.send(content, embed=embed)
    #                     break
    #                 else:
    #                     await ctx.send("Error: SHA256 value not found in the analysis response.")
    #                     break
    #         else:
    #             await ctx.send("Error: Analysis ID not found or analysis not completed yet.")
    #             break
            
    #         try:
    #             await ctx.message.delete()
    #         except discord.errors.NotFound:
    #             pass
            
    #         await asyncio.sleep(3)