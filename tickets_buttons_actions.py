"""Action buttons for ticket management (join, leave, close, cancel, delete)"""

import discord
import json
import asyncio
import traceback
import config
from typing import Optional, List
from tickets_cooldowns import get_ticket_lock, check_cooldown, set_cooldown, join_cooldowns, leave_cooldowns
from tickets_embeds import create_ticket_embed
from tickets_utils import generate_join_commands
from tickets_transcript import generate_transcript


class TicketActionView(discord.ui.View):
    """Action buttons for ticket (Join, Leave, Close, Cancel, Show Room Info)"""
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Show Room Info", style=discord.ButtonStyle.primary, emoji="🔢", custom_id="show_room_info_persistent", row=0)
    async def show_room_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show room info - REQUESTOR/STAFF/ADMIN/OFFICER/JOINED HELPERS"""
        bot = interaction.client
        ticket = await bot.db.get_ticket(interaction.channel_id)
        
        if not ticket:
            await interaction.response.send_message("❌ No active ticket found.", ephemeral=True)
            return
        
        # Check permissions - ONLY staff/admin/officer or requestor or helpers who JOINED
        member = interaction.user
        is_staff = any(member.get_role(rid) for rid in [config.ROLE_IDS.get("ADMIN"), config.ROLE_IDS.get("STAFF"), config.ROLE_IDS.get("OFFICER")] if rid)
        is_requestor = interaction.user.id == ticket["requestor_id"]
        is_helper_in_ticket = interaction.user.id in ticket["helpers"]
        
        if not (is_staff or is_requestor or is_helper_in_ticket):
            await interaction.response.send_message("❌ Only the requestor, helpers who joined this ticket, staff, officers, or admins can view room info.", ephemeral=True)
            return
        
        # Parse selected bosses
        try:
            selected_bosses_raw = ticket.get("selected_bosses", "[]")
            if isinstance(selected_bosses_raw, str):
                selected_bosses = json.loads(selected_bosses_raw)
            else:
                selected_bosses = selected_bosses_raw or []
        except:
            selected_bosses = []
        
        selected_server = ticket.get("selected_server", "Unknown")
        
        # Generate join commands
        join_commands = generate_join_commands(
            ticket["category"],
            selected_bosses,
            ticket["random_number"],
            selected_server
        )
        
        # Send ephemeral message with room info + WARNING TO NOT SHARE
        if join_commands:
            await interaction.response.send_message(
                f"🎮 **Room Number: `{ticket['random_number']}`**\n\n"
                f"**Join Commands:**\n{join_commands}\n\n"
                f"⚠️ **DO NOT share this room number with anyone outside this ticket!**",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"🎮 **Room Number: `{ticket['random_number']}`**\n\n"
                f"⚠️ **DO NOT share this room number with anyone outside this ticket!**",
                ephemeral=True
            )
    
    @discord.ui.button(label="Leave Ticket", style=discord.ButtonStyle.secondary, emoji="🚪", custom_id="leave_ticket_persistent", row=0)
    async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Helper leaves ticket - WITH 120 SECOND COOLDOWN"""
        # Check cooldown
        remaining = check_cooldown(interaction.user.id, leave_cooldowns)
        if remaining:
            await interaction.response.send_message(
                f"⏳ You're on cooldown! Please wait **{remaining} seconds** before leaving another ticket.",
                ephemeral=True
            )
            return
        
        bot = interaction.client
        ticket = await bot.db.get_ticket(interaction.channel_id)
        
        if not ticket:
            await interaction.response.send_message("❌ No active ticket found.", ephemeral=True)
            return
        
        if ticket.get("is_closed", False):
            await interaction.response.send_message("❌ This ticket is already closed.", ephemeral=True)
            return
        
        # Check if user is a helper
        if interaction.user.id not in ticket["helpers"]:
            await interaction.response.send_message("❌ You are not a helper in this ticket!", ephemeral=True)
            return
        
        # Remove helper
        ticket["helpers"].remove(interaction.user.id)
        await bot.db.save_ticket(ticket)
        
        # Set cooldown
        set_cooldown(interaction.user.id, leave_cooldowns)
        
        # Remove channel permissions
        try:
            await interaction.channel.set_permissions(interaction.user, overwrite=None)
        except Exception as e:
            print(f"Failed to remove permissions: {e}")
        
        # Update embed
        try:
            selected_bosses_raw = ticket.get("selected_bosses", "[]")
            if isinstance(selected_bosses_raw, str):
                selected_bosses = json.loads(selected_bosses_raw)
            else:
                selected_bosses = selected_bosses_raw or []
        except:
            selected_bosses = []
        
        selected_server = ticket.get("selected_server", "Unknown")
        
        embed = create_ticket_embed(
            category=ticket["category"],
            requestor_id=ticket["requestor_id"],
            in_game_name=ticket.get("in_game_name", "N/A"),
            concerns=ticket.get("concerns", "None"),
            helpers=ticket["helpers"],
            random_number=ticket["random_number"],
            selected_bosses=selected_bosses,
            selected_server=selected_server
        )
        
        # Update ticket message
        try:
            msg = await interaction.channel.fetch_message(ticket["embed_message_id"])
            await msg.edit(embed=embed)
        except Exception as e:
            print(f"Failed to update embed: {e}")
        
        await interaction.response.send_message(f"✅ You've left the ticket!", ephemeral=True)
        await interaction.channel.send(f"🚪 {interaction.user.mention} left the ticket.")
    
    @discord.ui.button(label="Join Ticket", style=discord.ButtonStyle.success, emoji="✅", custom_id="ticket_join_persistent", row=1)
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Helper joins ticket - ONE TICKET AT A TIME - WITH RACE CONDITION PROTECTION AND 120 SECOND COOLDOWN"""
        # Check cooldown FIRST
        remaining = check_cooldown(interaction.user.id, join_cooldowns)
        if remaining:
            await interaction.response.send_message(
                f"⏳ You're on cooldown! Please wait **{remaining} seconds** before joining another ticket.",
                ephemeral=True
            )
            return
        
        # === ACQUIRE LOCK TO PREVENT RACE CONDITIONS ===
        lock = get_ticket_lock(interaction.channel_id)
        
        async with lock:  # Only one person can execute this block at a time
            try:
                bot = interaction.client
                
                # === FRESH DATABASE READ (CRITICAL FOR RACE CONDITION FIX) ===
                ticket = await bot.db.get_ticket(interaction.channel_id)
                
                if not ticket:
                    await interaction.response.send_message("❌ No active ticket found.", ephemeral=True)
                    return
                
                if ticket.get("is_closed", False):
                    await interaction.response.send_message("❌ This ticket is already closed.", ephemeral=True)
                    return
                
                # Check if user is requestor
                if interaction.user.id == ticket["requestor_id"]:
                    await interaction.response.send_message("❌ You cannot join your own ticket!", ephemeral=True)
                    return
                
                # Check if user is already a helper (FRESH CHECK)
                if interaction.user.id in ticket["helpers"]:
                    await interaction.response.send_message("❌ You've already joined this ticket!", ephemeral=True)
                    return
                
                # Check if user is REQUESTOR of another active ticket - PREVENT JOINING
                all_tickets = await bot.db.get_all_tickets()
                for other_ticket in all_tickets:
                    if other_ticket["channel_id"] == interaction.channel_id:
                        continue
                    if interaction.user.id == other_ticket["requestor_id"]:
                        # Verify channel exists
                        other_channel = interaction.guild.get_channel(other_ticket["channel_id"])
                        if other_channel:
                            await interaction.response.send_message(
                                f"❌ You cannot join tickets while you have an active ticket as requestor: {other_channel.mention}\n"
                                "Please close or cancel your ticket first.",
                                ephemeral=True
                            )
                            return
                
                # Check if user is in another active ticket (with verification that ticket channel exists)
                for other_ticket in all_tickets:
                    if other_ticket["channel_id"] == interaction.channel_id:
                        continue
                    if interaction.user.id in other_ticket["helpers"]:
                        # Verify the channel actually exists
                        other_channel = interaction.guild.get_channel(other_ticket["channel_id"])
                        if other_channel:
                            # Channel exists, user is actually in another ticket
                            await interaction.response.send_message(
                                f"❌ You're already in another ticket: {other_channel.mention}\n"
                                "You must leave that ticket before joining a new one.\n\n"
                                "*If you believe this is an error, ask an admin to run `/free_helper @you`*",
                                ephemeral=True
                            )
                            return
                        else:
                            # Channel doesn't exist - remove user from phantom ticket
                            print(f"⚠️ Removing {interaction.user.id} from phantom ticket {other_ticket['channel_id']}")
                            other_ticket["helpers"].remove(interaction.user.id)
                            await bot.db.save_ticket(other_ticket)
                
                # Check if ticket is full (FRESH CHECK WITH LATEST DATA)
                max_helpers = config.HELPER_SLOTS.get(ticket["category"], 3)
                if len(ticket["helpers"]) >= max_helpers:
                    await interaction.response.send_message(
                        f"❌ This ticket is full! ({len(ticket['helpers'])}/{max_helpers} helpers)",
                        ephemeral=True
                    )
                    return
                
                # Check if user has helper role
                helper_role = interaction.guild.get_role(config.ROLE_IDS.get("HELPER"))
                if helper_role and helper_role not in interaction.user.roles:
                    await interaction.response.send_message("❌ You need the Helper role to join tickets!", ephemeral=True)
                    return
                
                # === SET COOLDOWN AFTER ALL CHECKS PASS ===
                set_cooldown(interaction.user.id, join_cooldowns)
                
                # Add helper
                ticket["helpers"].append(interaction.user.id)
                await bot.db.save_ticket(ticket)
                
                # Grant channel permissions
                await interaction.channel.set_permissions(
                    interaction.user,
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                )
                
                # Update embed
                try:
                    selected_bosses_raw = ticket.get("selected_bosses", "[]")
                    if isinstance(selected_bosses_raw, str):
                        selected_bosses = json.loads(selected_bosses_raw)
                    else:
                        selected_bosses = selected_bosses_raw or []
                except:
                    selected_bosses = []
                
                selected_server = ticket.get("selected_server", "Unknown")
                
                embed = create_ticket_embed(
                    category=ticket["category"],
                    requestor_id=ticket["requestor_id"],
                    in_game_name=ticket.get("in_game_name", "N/A"),
                    concerns=ticket.get("concerns", "None"),
                    helpers=ticket["helpers"],
                    random_number=ticket["random_number"],
                    selected_bosses=selected_bosses,
                    selected_server=selected_server
                )
                
                # Update ticket message
                try:
                    msg = await interaction.channel.fetch_message(ticket["embed_message_id"])
                    await msg.edit(embed=embed)
                except Exception as e:
                    print(f"Failed to update embed: {e}")
                
                # Generate join commands
                join_commands = generate_join_commands(
                    ticket["category"],
                    selected_bosses,
                    ticket["random_number"],
                    selected_server
                )
                
                # Show room number to helper
                if join_commands:
                    await interaction.response.send_message(
                        f"✅ You've joined the ticket!\n\n"
                        f"🎮 **Room Number: `{ticket['random_number']}`**\n\n"
                        f"**Join Commands:**\n{join_commands}\n\n"
                        f"⚠️ **DO NOT share this room number with anyone outside this ticket!**",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        f"✅ You've joined the ticket!\n\n"
                        f"🎮 **Room Number: `{ticket['random_number']}`**\n\n"
                        f"⚠️ **DO NOT share this room number with anyone outside this ticket!**",
                        ephemeral=True
                    )
                
                # Notify channel
                await interaction.channel.send(f"✅ {interaction.user.mention} joined the ticket!")
            
            except Exception as e:
                print(f"❌ Join button error: {e}")
                import traceback
                traceback.print_exc()
                try:
                    await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)
                except:
                    await interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="ticket_close_persistent", row=1)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Close ticket with rewards - STAFF/ADMIN/OFFICER/REQUESTOR"""
        bot = interaction.client
        ticket = await bot.db.get_ticket(interaction.channel_id)
        
        if not ticket:
            await interaction.response.send_message("❌ No active ticket found.", ephemeral=True)
            return
        
        if ticket.get("is_closed", False):
            await interaction.response.send_message("❌ This ticket is already closed.", ephemeral=True)
            return
        
        member = interaction.user
        is_staff = any(member.get_role(rid) for rid in [config.ROLE_IDS.get("ADMIN"), config.ROLE_IDS.get("STAFF"), config.ROLE_IDS.get("OFFICER")] if rid)
        is_requestor = interaction.user.id == ticket["requestor_id"]
        
        if not (is_staff or is_requestor):
            await interaction.response.send_message("❌ Only staff, officers, admins, or the requestor can close tickets.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        guild = interaction.guild
        admin_role = guild.get_role(config.ROLE_IDS.get("ADMIN"))
        staff_role = guild.get_role(config.ROLE_IDS.get("STAFF"))
        officer_role = guild.get_role(config.ROLE_IDS.get("OFFICER"))
        helper_role = guild.get_role(config.ROLE_IDS.get("HELPER"))
        
        # === STEP 1: REMOVE PERMISSIONS IMMEDIATELY ===
        new_overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }
        
        # ADMIN/STAFF/OFFICER roles get full access + manage channels
        if admin_role:
            new_overwrites[admin_role] = discord.PermissionOverwrite(
                view_channel=True, 
                send_messages=True, 
                read_message_history=True,
                manage_channels=True,
                manage_permissions=True
            )
        if staff_role:
            new_overwrites[staff_role] = discord.PermissionOverwrite(
                view_channel=True, 
                send_messages=True, 
                read_message_history=True,
                manage_channels=True,
                manage_permissions=True
            )
        if officer_role:
            new_overwrites[officer_role] = discord.PermissionOverwrite(
                view_channel=True, 
                send_messages=True, 
                read_message_history=True
            )
        
        # Block requestor UNLESS they are staff/officer/admin
        requestor = guild.get_member(ticket["requestor_id"])
        if requestor:
            is_requestor_staff = (admin_role and admin_role in requestor.roles) or \
                                 (staff_role and staff_role in requestor.roles) or \
                                 (officer_role and officer_role in requestor.roles)
            
            if not is_requestor_staff:
                # Regular requestor - block access
                new_overwrites[requestor] = discord.PermissionOverwrite(
                    view_channel=False,
                    send_messages=False,
                    read_message_history=False
                )
            # If requestor IS staff/officer/admin, they keep access via role permissions
        
        # Remove all helpers
        for helper_id in ticket["helpers"]:
            helper = guild.get_member(helper_id)
            if helper:
                is_helper_staff = (admin_role and admin_role in helper.roles) or \
                                  (staff_role and staff_role in helper.roles) or \
                                  (officer_role and officer_role in helper.roles)
                if not is_helper_staff:
                    new_overwrites[helper] = discord.PermissionOverwrite(
                        view_channel=False,
                        send_messages=False,
                        read_message_history=False
                    )
        
        # Block Helper ROLE
        if helper_role:
            new_overwrites[helper_role] = discord.PermissionOverwrite(
                view_channel=False,
                send_messages=False,
                read_message_history=False
            )
        
        await interaction.channel.edit(overwrites=new_overwrites)
        
        # === STEP 2: CREATE FINAL EMBED ===
        helpers_text = ", ".join([f"<@{h}>" for h in ticket["helpers"]]) if ticket["helpers"] else "None"
        
        # Get points per helper
        points_per = config.POINT_VALUES.get(ticket["category"], 0)
        total_points = points_per * len(ticket["helpers"]) if ticket["helpers"] else 0
        
        final_embed = discord.Embed(
            title=f"✅ {ticket['category']} (Completed)",
            description="**Ticket Completed! Points awarded to all helpers.**",
            color=config.COLORS["SUCCESS"],
            timestamp=discord.utils.utcnow()
        )
        final_embed.add_field(name="Requestor", value=f"<@{ticket['requestor_id']}>", inline=False)
        final_embed.add_field(name="Helpers", value=helpers_text, inline=False)
        final_embed.add_field(name="Points per Helper", value=f"**{points_per}**", inline=True)
        final_embed.add_field(name="Total Points Awarded", value=f"**{total_points}**", inline=True)
        final_embed.set_footer(text=f"Closed by {interaction.user}")
        
        await interaction.channel.send(embed=final_embed)
        
        # === STEP 3: AWARD POINTS ===
        volunteer_role = guild.get_role(config.ROLE_IDS.get("VOLUNTEER"))

        for helper_id in ticket["helpers"]:
            try:
                # Check for volunteer role
                helper_member = guild.get_member(helper_id)
                if helper_member and volunteer_role and volunteer_role in helper_member.roles:
                     print(f"ℹ️ {helper_member.name} is a Volunteer - Skipping points.")
                     continue

                new_points = await bot.db.add_points(helper_id, points_per)
                print(f"✅ Awarded {points_per} points to {helper_id} (Total: {new_points})")
            except Exception as e:
                print(f"⚠️ Failed to award points to {helper_id}: {e}")
        
        # === STEP 4: DATABASE OPERATIONS ===
        try:
            # Mark as closed
            ticket["is_closed"] = True
            await bot.db.save_ticket(ticket)
            
            # === NEW: INCREMENT TOTAL TICKETS COUNTER ===
            try:
                await bot.db.increment_total_tickets()
                print(f"✅ Incremented total tickets counter")
            except Exception as e:
                print(f"⚠️ Failed to increment total tickets: {e}")
            
            # Generate transcript
            try:
                await generate_transcript(interaction.channel, bot, ticket)
            except Exception as e:
                print(f"⚠️ Transcript generation failed: {e}")
            
            # Save history
            try:
                await bot.db.save_ticket_history({
                    "channel_id": ticket["channel_id"],
                    "category": ticket["category"],
                    "requestor_id": ticket["requestor_id"],
                    "helpers": json.dumps(ticket["helpers"]),
                    "points_per_helper": points_per,
                    "total_points_awarded": total_points,
                    "closed_by": interaction.user.id
                })
            except Exception as e:
                print(f"⚠️ History save failed: {e}")
            
            # Delete from active
            try:
                await bot.db.delete_ticket(ticket["channel_id"])
            except Exception as e:
                print(f"⚠️ Ticket deletion failed: {e}")
                
        except Exception as e:
            print(f"⚠️ Database error during close: {e}")
            traceback.print_exc()
        
        # === SEND DELETE BUTTON ===
        delete_embed = discord.Embed(
            title="🗑️ Delete Channel?",
            description=(
                "This ticket has been closed.\n\n"
                "Click the button below to delete this channel.\n"
                "Only staff can delete the channel."
            ),
            color=config.COLORS["SUCCESS"]
        )
        
        delete_view = DeleteChannelView()
        await interaction.followup.send(embed=delete_embed, view=delete_view, ephemeral=False)
    
    @discord.ui.button(label="Cancel Ticket", style=discord.ButtonStyle.secondary, emoji="❌", custom_id="ticket_cancel_persistent", row=1)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel ticket - STAFF/ADMIN/OFFICER/REQUESTOR"""
        bot = interaction.client
        ticket = await bot.db.get_ticket(interaction.channel_id)
        
        if not ticket:
            await interaction.response.send_message("❌ No active ticket found.", ephemeral=True)
            return
        
        if ticket.get("is_closed", False):
            await interaction.response.send_message("❌ This ticket is already closed.", ephemeral=True)
            return
        
        member = interaction.user
        is_staff = any(member.get_role(rid) for rid in [config.ROLE_IDS.get("ADMIN"), config.ROLE_IDS.get("STAFF"), config.ROLE_IDS.get("OFFICER")] if rid)
        is_requestor = interaction.user.id == ticket["requestor_id"]
        
        if not (is_staff or is_requestor):
            await interaction.response.send_message("❌ Only staff, officers, admins, or the requestor can cancel tickets.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        guild = interaction.guild
        admin_role = guild.get_role(config.ROLE_IDS.get("ADMIN"))
        staff_role = guild.get_role(config.ROLE_IDS.get("STAFF"))
        officer_role = guild.get_role(config.ROLE_IDS.get("OFFICER"))
        helper_role = guild.get_role(config.ROLE_IDS.get("HELPER"))
        
        # === STEP 1: REMOVE PERMISSIONS IMMEDIATELY ===
        new_overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }
        
        # ADMIN/STAFF/OFFICER roles get full access + manage channels
        if admin_role:
            new_overwrites[admin_role] = discord.PermissionOverwrite(
                view_channel=True, 
                send_messages=True, 
                read_message_history=True,
                manage_channels=True,
                manage_permissions=True
            )
        if staff_role:
            new_overwrites[staff_role] = discord.PermissionOverwrite(
                view_channel=True, 
                send_messages=True, 
                read_message_history=True,
                manage_channels=True,
                manage_permissions=True
            )
        if officer_role:
            new_overwrites[officer_role] = discord.PermissionOverwrite(
                view_channel=True, 
                send_messages=True, 
                read_message_history=True
            )
        
        # Block requestor UNLESS they are staff/officer/admin
        requestor = guild.get_member(ticket["requestor_id"])
        if requestor:
            is_requestor_staff = (admin_role and admin_role in requestor.roles) or \
                                 (staff_role and staff_role in requestor.roles) or \
                                 (officer_role and officer_role in requestor.roles)
            
            if not is_requestor_staff:
                # Regular requestor - block access
                new_overwrites[requestor] = discord.PermissionOverwrite(
                    view_channel=False,
                    send_messages=False,
                    read_message_history=False
                )
            # If requestor IS staff/officer/admin, they keep access via role permissions
        
        # Remove all helpers
        for helper_id in ticket["helpers"]:
            helper = guild.get_member(helper_id)
            if helper:
                is_helper_staff = (admin_role and admin_role in helper.roles) or \
                                  (staff_role and staff_role in helper.roles) or \
                                  (officer_role and officer_role in helper.roles)
                if not is_helper_staff:
                    new_overwrites[helper] = discord.PermissionOverwrite(
                        view_channel=False,
                        send_messages=False,
                        read_message_history=False
                    )
        
        # Block Helper ROLE
        if helper_role:
            new_overwrites[helper_role] = discord.PermissionOverwrite(
                view_channel=False,
                send_messages=False,
                read_message_history=False
            )
        
        await interaction.channel.edit(overwrites=new_overwrites)
        
        # === SEND CANCELLED EMBED ===
        helpers_text = ", ".join([f"<@{h}>" for h in ticket["helpers"]]) if ticket["helpers"] else "None"
        
        cancelled_embed = discord.Embed(
            title=f"❌ {ticket['category']} (Cancelled)",
            description="**This ticket was cancelled. No points were awarded.**",
            color=config.COLORS["DANGER"],
            timestamp=discord.utils.utcnow()
        )
        cancelled_embed.add_field(name="Requestor", value=f"<@{ticket['requestor_id']}>", inline=False)
        cancelled_embed.add_field(name="Helpers", value=helpers_text, inline=False)
        cancelled_embed.set_footer(text=f"Cancelled by {interaction.user}")
        
        await interaction.channel.send(embed=cancelled_embed)
        
        # === SEND DELETE BUTTON ===
        delete_embed = discord.Embed(
            title="🗑️ Delete Channel?",
            description=(
                "This ticket has been cancelled.\n\n"
                "Click the button below to delete this channel.\n"
                "Only staff can delete the channel."
            ),
            color=config.COLORS["DANGER"]
        )
        
        delete_view = DeleteChannelView()
        await interaction.followup.send(embed=delete_embed, view=delete_view, ephemeral=False)
        
        # === DATABASE OPERATIONS ===
        try:
            # Mark as closed (cancelled)
            ticket["is_closed"] = True
            await bot.db.save_ticket(ticket)
            
            # Generate transcript (cancelled)
            try:
                await generate_transcript(interaction.channel, bot, ticket, is_cancelled=True)
            except Exception as e:
                print(f"⚠️ Transcript generation failed: {e}")
            
            # Save history
            try:
                await bot.db.save_ticket_history({
                    "channel_id": ticket["channel_id"],
                    "category": ticket["category"],
                    "requestor_id": ticket["requestor_id"],
                    "helpers": json.dumps(ticket["helpers"]),
                    "points_per_helper": 0,
                    "total_points_awarded": 0,
                    "closed_by": interaction.user.id,
                    "cancelled": True
                })
            except Exception as e:
                print(f"⚠️ History save failed: {e}")
            
            # Delete from active
            try:
                await bot.db.delete_ticket(ticket["channel_id"])
            except Exception as e:
                print(f"⚠️ Ticket deletion failed: {e}")
                
        except Exception as e:
            print(f"⚠️ Database error during cancel: {e}")
            traceback.print_exc()


class DeleteChannelView(discord.ui.View):
    """View with delete channel button"""
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Delete Channel", style=discord.ButtonStyle.danger, emoji="🗑️", custom_id="delete_channel_persistent")
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Delete the channel - STAFF/ADMIN/OFFICER ONLY"""
        member = interaction.user
        is_staff = any(member.get_role(rid) for rid in [config.ROLE_IDS.get("ADMIN"), config.ROLE_IDS.get("STAFF"), config.ROLE_IDS.get("OFFICER")] if rid)
        
        if not is_staff:
            await interaction.response.send_message("❌ Only staff, officers, or admins can delete the channel.", ephemeral=True)
            return
        
        await interaction.response.send_message(
            f"🗑️ Channel will be deleted in 5 seconds...",
            ephemeral=False
        )
        
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason=f"Ticket closed and deleted by {interaction.user}")
        except:
            pass