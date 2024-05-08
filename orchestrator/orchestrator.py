from redbot.core import Config, commands
import discord
from discord.ui import Button, View

class Orchestrator(commands.Cog):
    """See info about the servers your bot is in.
    
    For bot owners only.
    """

    def __init__(self, bot):
        self.config = Config.get_conf(self, identifier=806715409318936616)
        self.bot = bot

    # This cog does not store any End User Data
    async def red_get_data_for_user(self, *, user_id: int):
        return {}
    async def red_delete_data_for_user(self, *, requester, user_id: int) -> None:
        pass

    @commands.hybrid_command(name="orchestrator", aliases=["botservers"])
    @commands.is_owner()
    async def orchestrator(self, ctx):
        """See and manage the servers that your bot instance is in."""
        await ctx.defer()
        guilds = [guild async for guild in self.bot.fetch_guilds(limit=None)]
        # Filter out guilds with None member_count before sorting
        guilds_filtered = [guild for guild in guilds if guild.member_count is not None]
        guilds_sorted = sorted(guilds_filtered, key=lambda x: x.member_count, reverse=True)
        
        embeds = []
        guild_ids = []
        for guild in guilds_sorted:
            embed_color = discord.Color.from_rgb(255, 255, 254)
            guild_owner = await self.bot.fetch_user(guild.owner_id) if guild.owner_id else 'Unknown'
            full_guild = await self.bot.fetch_guild(guild.id)
            embed_description = (
                f"**Members:** `{full_guild.member_count}`\n"
                f"**Active:** `{full_guild.presence_count}`\n"
                f"**Owner:** `{guild_owner}`\n"
                f"**Created At:** `{full_guild.created_at.strftime('%Y-%m-%d %H:%M:%S')}`\n"
                f"**Boost Level:** `{full_guild.premium_tier}`\n"
                f"**Boosts:** `{full_guild.premium_subscription_count}`\n"
                f"**Features:** `{', '.join(full_guild.features) if full_guild.features else 'None'}`"
            )
            embed = discord.Embed(title=guild.name, description=embed_description, color=embed_color)
            embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
            embed.add_field(name="Guild ID", value=str(guild.id))
            embed.add_field(name="Verification Level", value=str(guild.verification_level))
            embed.add_field(name="Explicit Content Filter", value=str(guild.explicit_content_filter))
            embed.add_field(name="Default Notifications", value=str(guild.default_notifications))
            embed.add_field(name="Number of Roles", value=str(len(guild.roles)))
            embed.add_field(name="Number of Emojis", value=str(len(guild.emojis)))
            embed.add_field(name="Number of Text Channels", value=str(len(guild.text_channels)))
            embed.add_field(name="Number of Voice Channels", value=str(len(guild.voice_channels)))
            embeds.append(embed)
            guild_ids.append(guild.id)
        
        if not guilds_sorted:
            return await ctx.send("No guilds available.")
        
        # Paginator view with buttons
        class PaginatorView(View):
            def __init__(self, embeds, guild_ids):
                super().__init__()
                self.embeds = embeds
                self.guild_ids = guild_ids
                self.current_page = 0
                self.invite_button = Button(emoji="🔗", label="Generate invite", style=discord.ButtonStyle.secondary, row=1, custom_id="invite_btn")
                self.leave_button = Button(emoji="🗑️", label="Leave server", style=discord.ButtonStyle.danger, row=1, custom_id="leave_btn")
                self.previous_button = Button(label="Previous", style=discord.ButtonStyle.primary, row=2, custom_id="previous_btn")
                self.next_button = Button(label="Next", style=discord.ButtonStyle.primary, row=2, custom_id="next_btn")
                self.add_item(self.previous_button)
                self.add_item(self.next_button)
                self.add_item(self.invite_button)
                self.add_item(self.leave_button)
            
            async def interaction_check(self, interaction):
                return interaction.user == ctx.author
            
            async def on_timeout(self):
                self.previous_button.disabled = True
                self.next_button.disabled = True
                self.invite_button.disabled = True
                self.leave_button.disabled = True
                self.stop()

            async def previous_button_callback(self, interaction):
                if self.current_page > 0:
                    self.current_page -= 1
                    await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)
            
            async def next_button_callback(self, interaction):
                if self.current_page < len(self.embeds) - 1:
                    self.current_page += 1
                    await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)
            
            async def invite_button_callback(self, interaction):
                guild_id = self.guild_ids[self.current_page]
                guild = self.bot.get_guild(guild_id)
                if guild:
                    invites = await guild.invites()
                    if invites:
                        invite = invites[0]  # Use the first available invite
                    else:
                        # If no invites are available, try to create one if the bot has permissions
                        if guild.me.guild_permissions.create_instant_invite:
                            invite = await guild.text_channels[0].create_invite(max_age=300)  # Invite expires after 5 minutes
                        else:
                            invite = None
                    if invite:
                        await interaction.response.send_message(f"Invite for {guild.name}: {invite.url}", ephemeral=True)
                    else:
                        await interaction.response.send_message("No available invites and cannot create one.", ephemeral=True)
                else:
                    await interaction.response.send_message(f"Could not access guild with ID: {guild_id}", ephemeral=True)
            
            async def leave_button_callback(self, interaction):
                guild_id = self.guild_ids[self.current_page]
                guild = self.bot.get_guild(guild_id)
                if guild:
                    await guild.leave()
                    await interaction.response.send_message(f"Left guild: {guild.name} (ID: {guild_id})", ephemeral=True)
                    # Update the embeds and guild_ids to reflect the change
                    del self.embeds[self.current_page]
                    del self.guild_ids[self.current_page]
                    # If the current page is now out of range, move back one
                    if self.current_page >= len(self.embeds):
                        self.current_page = max(len(self.embeds) - 1, 0)
                    # Update the message with the new current page embed
                    await interaction.message.edit(embed=self.embeds[self.current_page] if self.embeds else None, view=self)
                else:
                    await interaction.response.send_message(f"Could not leave guild with ID: {guild_id}", ephemeral=True)
        
        paginator_view = PaginatorView(embeds, guild_ids)
        paginator_view.invite_button.callback = paginator_view.invite_button_callback
        paginator_view.leave_button.callback = paginator_view.leave_button_callback
        paginator_view.previous_button.callback = paginator_view.previous_button_callback
        paginator_view.next_button.callback = paginator_view.next_button_callback
        
        await ctx.send(embed=embeds[0], view=paginator_view)
