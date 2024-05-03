import stripe #type: ignore
from redbot.core import Config, commands, checks #type: ignore
from redbot.core.bot import Red #type: ignore
import discord #type: ignore
import asyncio
from datetime import datetime

class StripeIdentity(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890, force_registration=True)
        self.config.register_global(
            stripe_api_key="",
            verification_channel=None,
            age_verified_role=None,
            id_verified_role=None,
            pending_verification_sessions={}
        )

    async def initialize(self):
        api_key = await self.bot.get_shared_api_tokens("stripe")
        stripe.api_key = api_key.get("api_key")
        self.verification_channel_id = await self.config.verification_channel()
        self.age_verified_role_id = await self.config.age_verified_role()
        self.id_verified_role_id = await self.config.id_verified_role()

    @commands.command(name="setverificationchannel")
    @checks.admin_or_permissions(manage_guild=True)
    async def set_verification_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        """
        Set the channel where verification results will be sent.
        """
        await self.config.verification_channel.set(channel.id)
        embed = discord.Embed(description=f"Verification results will now be sent to {channel.mention}.", color=discord.Color.green())
        await ctx.send(embed=embed)

    @commands.command(name="setageverifiedrole")
    @checks.admin_or_permissions(manage_roles=True)
    async def set_age_verified_role(self, ctx: commands.Context, role: discord.Role):
        """
        Set the role to give to users who are verified as 18 or older.
        """
        await self.config.age_verified_role.set(role.id)
        embed = discord.Embed(description=f"Role for age verified users set to {role.name}.", color=discord.Color.green())
        await ctx.send(embed=embed)

    @commands.command(name="setidverifiedrole")
    @checks.admin_or_permissions(manage_roles=True)
    async def set_id_verified_role(self, ctx: commands.Context, role: discord.Role):
        """
        Set the role to give to users who have been completely ID verified.
        """
        await self.config.id_verified_role.set(role.id)
        embed = discord.Embed(description=f"Role for ID verified users set to {role.name}.", color=discord.Color.green())
        await ctx.send(embed=embed)

    @commands.command(name="cancelverification")
    @checks.admin_or_permissions(manage_guild=True)
    async def cancel_verification(self, ctx: commands.Context, user: discord.Member):
        """
        Cancel a pending verification session for a user and remove it from the list of sessions.
        """
        session_id = await self.config.pending_verification_sessions.get_raw(user.id, default=None)
        if session_id:
            try:
                stripe.identity.VerificationSession.cancel(session_id)
                embed = discord.Embed(description=f"Verification session for {user.display_name} has been canceled and removed.", color=discord.Color.green())
                await ctx.send(embed=embed)
            except stripe.error.StripeError as e:
                embed = discord.Embed(description=f"Failed to cancel the verification session: {e.user_message}", color=discord.Color.red())
                await ctx.send(embed=embed)
            finally:
                await self.config.pending_verification_sessions.clear_raw(user.id)
        else:
            embed = discord.Embed(description=f"No pending verification session found for {user.display_name}.", color=discord.Color.orange())
            await ctx.send(embed=embed)

    @commands.command(name="agecheck")
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def age_check(self, ctx: commands.Context, user: discord.Member):
        """
        Perform an age check on a user using Stripe Identity.
        """
        try:
            verification_session = stripe.identity.VerificationSession.create(
                type='document',
                metadata={
                    'discord_user_id': str(user.id),
                    'discord_server_id': str(ctx.guild.id),
                    'verification_command': 'agecheck'
                },
                options={
                    'document': {
                        'allowed_types': ['driving_license', 'passport', 'id_card'],
                        'require_id_number': True,
                        'require_live_capture': True,
                        'require_matching_selfie': True,
                    },
                }
            )
            await self.config.pending_verification_sessions.set_raw(user.id, value=verification_session.id)
            dm_embed = discord.Embed(
                title="Age Verification Required",
                description=(
                    f"Hello {user.mention},\n"
                    "To remain in the server, you need to prove you are **18+**. "
                    "Please complete the verification using the following link: "
                    f"[Click here to verify your age securely]({verification_session.url})\n"
                    "You have 15 minutes to complete this process. If you do not complete verification, you will be removed from the server for safety."
                ),
                color=discord.Color.blue()
            )
            dm_message = await user.send(embed=dm_embed)
            embed = discord.Embed(description=f"Verification session created for {user.display_name}. Instructions have been sent via DM.", color=discord.Color.green())
            await ctx.send(embed=embed)

            async def check_verification_status(session_id):
                session = stripe.identity.VerificationSession.retrieve(session_id)
                if session.status == 'requires_input':
                    for event in session.last_error:
                        if event.code in ['consent_declined', 'device_unsupported', 'under_supported_age', 'phone_otp_declined', 'email_verification_declined']:
                            return event.code, session
                return session.status == 'verified', session

            await asyncio.sleep(900)  # Wait for 15 minutes
            status, session = await check_verification_status(verification_session.id)
            if status in ['consent_declined', 'device_unsupported', 'under_supported_age', 'phone_otp_declined', 'email_verification_declined']:
                embed = discord.Embed(description=f"Verification failed due to {status.replace('_', ' ')}.", color=discord.Color.red())
                await ctx.send(embed=embed)
            elif not status:
                await ctx.guild.kick(user, reason="Did not verify age")
                dm_embed = discord.Embed(
                    title="Verification Incomplete",
                    description=f"Verification was not completed in time. You have been removed from the server {ctx.guild.name}.",
                    color=discord.Color.red()
                )
                await dm_message.edit(embed=dm_embed)
            else:
                verification_channel = self.bot.get_channel(self.verification_channel_id)
                if verification_channel:
                    dob = datetime.fromisoformat(session.last_verification_report.document.dob)
                    age = (datetime.now() - dob).days // 365
                    if age < 18:
                        await ctx.guild.ban(user, reason="User is underage - ID Validated by BeeHive")
                        dm_embed = discord.Embed(
                            title="Underage - Banned",
                            description=(
                                "You have been banned from the server because you are under 18.\n"
                                "You may return once you are 18 years of age or older...\n\n"
                                "Please don't take this ban personally - we're sure you're a great person to meet and interact with, but...the internet can be a dangerous place sometimes, and this is as much to keep us safe as it is to keep you safe."
                            ),
                            color=discord.Color.red()
                        )
                        await dm_message.edit(embed=dm_embed)
                    else:
                        age_verified_role = ctx.guild.get_role(self.age_verified_role_id)
                        if age_verified_role:
                            await user.add_roles(age_verified_role, reason="Age verified as 18+")
                        result_embed = discord.Embed(title="Age Verification Result", color=discord.Color.green())
                        result_embed.add_field(name="User", value=f"{user} ({user.id})", inline=False)
                        result_embed.add_field(name="Age", value=str(age), inline=False)
                        await verification_channel.send(embed=result_embed)
            await self.config.pending_verification_sessions.set_raw(user.id, value=None)
        except stripe.error.StripeError as e:
            embed = discord.Embed(description=f"Failed to create a verification session: {e.user_message}", color=discord.Color.red())
            await ctx.send(embed=embed)
        except discord.HTTPException as e:
            embed = discord.Embed(description=f"Failed to send DM to {user.display_name}: {e.text}", color=discord.Color.red())
            await ctx.send(embed=embed)

    @commands.command(name="identitycheck")
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def identity_check(self, ctx: commands.Context, user: discord.Member):
        """
        Perform a full identity check on a user using Stripe Identity.
        """
        try:
            verification_session = stripe.identity.VerificationSession.create(
                type='document',
                metadata={
                    'discord_user_id': str(user.id),
                    'discord_server_id': str(ctx.guild.id),
                    'verification_command': 'identitycheck'
                },
                options={
                    'document': {
                        'allowed_types': ['driving_license', 'passport', 'id_card'],
                        'require_id_number': True,
                        'require_live_capture': True,
                        'require_matching_selfie': True,
                    },
                }
            )
            await self.config.pending_verification_sessions.set_raw(user.id, value=verification_session.id)
            dm_embed = discord.Embed(
                title="Identity verification required",
                description=(
                    f"Hello {user.mention},\n"
                    "To access certain features of the server, we require a full identity verification process. "
                    "Please complete the verification using the following link: "
                    f"{verification_session.url}\n"
                    "You have 15 minutes to complete this process."
                ),
                color=discord.Color(0xff4545)
            )
            dm_message = await user.send(embed=dm_embed)
            embed = discord.Embed(description=f"Identity verification session created for {user.display_name}. Instructions have been sent via DM.", color=discord.Color.green())
            await ctx.send(embed=embed)

            async def check_verification_status(session_id):
                # Check if the session has been cancelled before proceeding
                if await self.config.pending_verification_sessions.get_raw(user.id, default=None) != session_id:
                    return 'cancelled', None
                session = stripe.identity.VerificationSession.retrieve(session_id)
                if session.status == 'requires_input':
                    for event in session.last_error:
                        if event.code in ['consent_declined', 'device_unsupported', 'under_supported_age', 'phone_otp_declined', 'email_verification_declined']:
                            return event.code, session
                return session.status, session

            await asyncio.sleep(900)  # Wait for 15 minutes
            status, session = await check_verification_status(verification_session.id)
            if status == 'cancelled':
                embed = discord.Embed(description=f"Identity verification for {user.display_name} has been cancelled.", color=discord.Color.orange())
                await ctx.send(embed=embed)
            elif status in ['consent_declined', 'device_unsupported', 'under_supported_age', 'phone_otp_declined', 'email_verification_declined']:
                embed = discord.Embed(description=f"Identity verification failed due to {status.replace('_', ' ')}.", color=discord.Color.red())
                await ctx.send(embed=embed)
            elif status != 'verified':
                await ctx.guild.kick(user, reason="Did not verify identity")
                dm_embed = discord.Embed(
                    title="Verification Incomplete",
                    description=f"Identity verification was not completed in time. You have been removed from the server {ctx.guild.name}.",
                    color=discord.Color.red()
                )
                await dm_message.edit(embed=dm_embed)
            else:
                id_verified_role = ctx.guild.get_role(self.id_verified_role_id)
                if id_verified_role:
                    await user.add_roles(id_verified_role, reason="Identity verified")
                verification_channel = self.bot.get_channel(self.verification_channel_id)
                if verification_channel:
                    result_embed = discord.Embed(title="Identity Verification Result", color=discord.Color.blue())
                    result_embed.add_field(name="User", value=f"{user} ({user.id})", inline=False)
                    result_embed.add_field(name="Document Status", value=session.last_verification_report.document.status, inline=False)
                    result_embed.add_field(name="Name", value=session.last_verification_report.document.name, inline=False)
                    result_embed.add_field(name="DOB", value=session.last_verification_report.document.dob, inline=False)
                    result_embed.add_field(name="Address", value=session.last_verification_report.document.address, inline=False)
                    if hasattr(session, 'risk_insights'):
                        result_embed.add_field(name="Risk Insights", value=str(session.risk_insights), inline=False)
                    await verification_channel.send(embed=result_embed)
            await self.config.pending_verification_sessions.set_raw(user.id, value=None)
        except stripe.error.StripeError as e:
            embed = discord.Embed(description=f"Failed to create an identity verification session: {e.user_message}", color=discord.Color.red())
            await ctx.send(embed=embed)
        except discord.HTTPException as e:
            embed = discord.Embed(description=f"Failed to send DM to {user.display_name}: {e.text}", color=discord.Color.red())
            await ctx.send(embed=embed)

    @commands.command(name="pendingverifications")
    async def pending_verifications(self, ctx):
        """Show all pending verifications and their details."""
        pending_sessions = await self.config.pending_verification_sessions.all()
        if not pending_sessions:
            embed = discord.Embed(description="There are no pending verification sessions.", color=discord.Color.orange())
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(title="Pending Verification Sessions", color=discord.Color.blue())
        current_time = discord.utils.utcnow()
        for user_id, session_info in pending_sessions.items():
            member = ctx.guild.get_member(int(user_id))
            if member:
                if session_info is not None:
                    # Assuming session_info is a timestamp string, parse it into a datetime object
                    try:
                        start_time = datetime.fromisoformat(session_info)
                        time_remaining = discord.utils.format_dt(start_time + datetime.timedelta(minutes=15), style='R')
                        embed.add_field(name=f"User: {member.display_name} (ID: {user_id})", value=f"Time remaining: {time_remaining}", inline=False)
                    except ValueError:
                        embed.add_field(name=f"User: {member.display_name} (ID: {user_id})", value="Invalid session start time.", inline=False)
                else:
                    embed.add_field(name=f"User: {member.display_name} (ID: {user_id})", value="Session info not available.", inline=False)
            else:
                embed.add_field(name=f"User ID: {user_id}", value="Member not found in this guild.", inline=False)
        await ctx.send(embed=embed)
