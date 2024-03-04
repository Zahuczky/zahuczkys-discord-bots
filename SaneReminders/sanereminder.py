import os
import discord

from discord.ext import commands, tasks
from dotenv import load_dotenv

import re
import datetime
import words2num
import mysql.connector
import sched, time

import dateparser

from mysql.connector import Error

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
HOST = os.getenv('DB_HOST')
USER = os.getenv('DB_USER')
PASSWORD = os.getenv('DB_PASS')
DATABASE = os.getenv('DB_NAME')
PORT = os.getenv('DB_PORT')
TABLE = os.getenv('DB_TABLE')

bot = commands.Bot(command_prefix='.', intents=discord.Intents.all())

def connect2db():
    connection = mysql.connector.connect(host=HOST,
                                            port=PORT,
                                            database=DATABASE,
                                            user=USER,
                                            password=PASSWORD)
    return connection

import re

def natural_language_to_timestamp(phrase):
    # Extract the time part from the phrase using regex
    match = re.search(r'(in|on|at) (.*) to|to .* (in|on|at) (.*)', phrase)
    if match:
        # group(2) and group(4) match the time part
        time_part = match.group(2) or match.group(4)
    else:
        return None

    # Use dateparser to parse the time part
    parsed_date = dateparser.parse(time_part, settings={'PREFER_DATES_FROM': 'future'})

    # Check if parsed_date is None
    if parsed_date is None:
        return None

    # Convert datetime object to timestamp
    parsed_date = parsed_date.timestamp()

    return parsed_date


@bot.command(name='remindme', help='Set up reminders, just like Aquarius once did')
async def remindme(ctx):
    ctx.message.content = ctx.message.content[9:]

    if ctx.message.content == ' help':
        await ctx.send("""To set up a reminder, type `.remindme in 5 minutes to take out the trash` or `.remindme to take out the trash in 5 minutes` or `.remindme to take out the trash at 5pm` or something similar.
                       Please keep in mind that the `in/on/at` part and the `to` part are pretty important. That's how I figure whats time and what's the reminder.
                       So you can use `remindme in 10 minutes to do something` but you can't use `remindme 10 minutes do something`.
                       \nTo list all your reminders, just type `.remindme list`
                       \nTo delete a reminder you can use `.remindme delete <id>` where `<id>` is the id of the reminder you want to delete.
                       """)
        return

    print(f"-{ctx.message.content}-")

    if ctx.message.content.startswith(' delete'):
        try:
            id = int(ctx.message.content[7:])
        except Exception as e:
            await ctx.send(f'No idea what you did but I was expecting something like `.remindme delete 69420`.')
            return
        
        connection = connect2db()
        cursor = connection.cursor()
        sql = f"SELECT * FROM {TABLE} WHERE id = %s"
        cursor.execute(sql, (id,))
        record = cursor.fetchone()
        if record is None:
            await ctx.send('No reminder with that id was found.')
            return
        if record[3] != ctx.author.id:
            await ctx.send('You can only delete your own reminders.')
            return
        if record[1] != ctx.guild.id:
            await ctx.send('You can only delete reminders from this server.')
            return
        
        sql = f"DELETE FROM {TABLE} WHERE id = %s AND user = %s AND guild = %s"
        cursor.execute(sql, (id, ctx.author.id, ctx.guild.id,))
        connection.commit()
        cursor.close()
        connection.close()
        await ctx.send('Reminder deleted.')
        return

    if ctx.message.content == ' list':
        connection = connect2db()
        cursor = connection.cursor()
        sql = f"SELECT * FROM {TABLE} WHERE user = %s AND done = 0 AND guild = %s"
        cursor.execute(sql, (ctx.author.id,ctx.guild.id,))
        records = cursor.fetchall()
        cursor.close()
        connection.close()
        if len(records) == 0:
            await ctx.send('You have no reminders set up.')
            return
        response = 'Here are your reminders:\n'
        for record in records:
            response += f'Id: {record[0]} Reminder: {record[5]} Time: <t:{record[4]}> (<t:{record[4]}:R>)\n'
        await ctx.send(response)
        return
    
    try:
        timestamp = natural_language_to_timestamp(ctx.message.content)
    except Exception as e:
        await ctx.send(f'I died in ways I didn\'t know were possible. Please try again. You should check this out <@225605002809311232>.')
        return

    # Check if timestamp is None
    if timestamp is None:
        await ctx.send("""I don\'t understand that time, please try again in a more descriptive manner.\nFor example: `.remindme in 5 minutes to take out the trash` or `.remindme to take out the trash in 5 minutes` or `.remindme to take out the trash at 5pm`
Please keep in mind that the `in/on/at` part and the `to` part are pretty important. That's how I figure whats time and what's the reminder.
So you can use `remindme in 10 minutes to do something` but you can't use `remindme 10 minutes do something`.
Use `.remindme help` for more info.
                       """)
        return

    # Round the timestamp to integer
    timestamp = round(timestamp)

    if not isinstance(timestamp, int):
        await ctx.send("""I don\'t understand that time, please try again in a more descriptive manner.\nFor example: `.remindme in 5 minutes to take out the trash` or `.remindme to take out the trash in 5 minutes` or `.remindme to take out the trash at 5pm`
Please keep in mind that the `in/on/at` part and the `to` part are pretty important. That's how I figure whats time and what's the reminder.
So you can use `remindme in 10 minutes to do something` but you can't use `remindme 10 minutes do something`.
Use `.remindme help` for more info.
                       """)
        return

    connection = connect2db()
    db_Info = connection.get_server_info()
    #print("Connected to MySQL Server version ", db_Info)
    cursor = connection.cursor()
    sql = f"select database(); INSERT INTO {TABLE} (guild, channel, user, time, message) VALUES (%s, %s, %s, %s, %s)"
    val = (ctx.guild.id, ctx.channel.id, ctx.author.id, timestamp, ctx.message.content)
    res = cursor.execute(sql, val, multi=True)
    res.send(None)
    record = cursor.fetchone()
    #print("Data was uploaded to the db")
    cursor.close()
    connection.close()

    response = f'Okay, I will remind you at <t:{timestamp}> (<t:{timestamp}:R>)'
    await ctx.send(response)

@tasks.loop(seconds=20)
async def check_db():
    current_time = round(datetime.datetime.now().timestamp())
    #print("Checking for reminders...")
    connection = connect2db()
    cursor = connection.cursor()
    sql = f"SELECT * FROM {TABLE} WHERE time < %s AND done = 0"
    cursor.execute(sql, (current_time,))
    records = cursor.fetchall()
    #print("Found reminders: ", records)
    for record in records:
        reminderId = record[0]
        id = record[1]
        guild = bot.get_guild(id)
        channel = guild.get_channel(int(record[2]))
        user = guild.get_member(int(record[3]))
        message = record[5]
        response = f'Hey {user.mention}! You asked me to remind you of this: {message}'
        await channel.send(response)
        sql2 = f"UPDATE {TABLE} SET done = 1 WHERE id = {reminderId}"
        cursor.execute(sql2)
        connection.commit()
    cursor.close()
    connection.close()

@bot.event
async def on_ready():
    check_db.start()


bot.run(TOKEN)