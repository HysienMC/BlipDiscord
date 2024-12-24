@bot.command()
async def serverinfo(ctx):
    """Displays detailed information about the Discord server."""
    guild = ctx.guild  # The server where the command is executed

    # Fetch server information
    server_name = guild.name
    server_owner = guild.owner
    created_at = guild.created_at.strftime("%B %d, %Y %H:%M:%S")
    member_count = guild.member_count
    role_count = len(guild.roles)
    channel_count = len(guild.channels)
    text_channels = len(guild.text_channels)
    voice_channels = len(guild.voice_channels)
    category_count = len(guild.categories)
    icon_url = guild.icon.url if guild.icon else None
    server_id = guild.id
    boost_level = guild.premium_tier
    booster_count = len(guild.premium_subscribers)

    # Create the embed
    embed = discord.Embed(
        title=f"Server Information: {server_name}",
        description="Here are the details about this server:",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()  # Use UTC for consistency
    )

    if icon_url:
        embed.set_thumbnail(url=icon_url)  # Server icon
    else:
        embed.set_thumbnail(url="https://i.imgur.com/wSTFkRM.png")  # Default image

    embed.add_field(name="📛 Server Name", value=server_name, inline=False)
    embed.add_field(name="👑 Owner", value=f"{server_owner} ({server_owner.id})", inline=True)
    embed.add_field(name="🆔 Server ID", value=server_id, inline=True)
    embed.add_field(name="📅 Created On", value=created_at, inline=False)
    embed.add_field(name="👥 Members", value=member_count, inline=True)
    embed.add_field(name="🎭 Roles", value=role_count, inline=True)
    embed.add_field(name="📚 Categories", value=category_count, inline=True)
    embed.add_field(
        name="💬 Channels",
        value=f"{channel_count} total\n{text_channels} text, {voice_channels} voice",
        inline=False
    )
    embed.add_field(name="✨ Boost Level", value=f"Level {boost_level}", inline=True)
    embed.add_field(name="🚀 Boosters", value=booster_count, inline=True)

    embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)

    # Send the embed
    await ctx.send(embed=embed)
