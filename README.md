# r99info: a Discord <--> Project1999 bridge
# (This documentation is out of date, and no longer works.)

## Prerequisites
This bot is written in Python, expected to be run on Linux, and is developed on
Debian Stretch 32-bit.

To run, you need:
* WINE (apt install wine)
* Xpra server (see https://xpra.org/trac/wiki/Download#Linux)
* Xpra client
* Titanium EverQuest install with Project1999 patches
* xdotool (apt install xdotool)
* Python 3.5 (apt install python3.5)
* discord.py (apt install python3-pip; pip install discord.py)
* isodate library (apt install python3-isodate)
* OpenCV library
* A Discord bot static token (see e.g. https://github.com/Habchy/BasicBot/wiki/Step-3)


### EQ on Linux
First, get EQ running.  Copy the EverQuest installation into a directory on
the linux host.  Add a shell script to the eq directory such as:

```sh
#!/bin/bash
# start.sh -- start/restart EQ.
while true; do
    /usr/bin/wine /path/to/everquest/eqclient.exe patchme
done
```

Make sure the script is executable.  Then, in the everquest directory,
run `xpra start --start=./start.sh`.  This will start EQ in the background.  Connect to
the server using whatever Xpra client you've got, and ensure you can log into a character.

The bot assumes that there will be a character logged in.  **WITHOUT FOOD OR DRINK**

### Configuring the bot
Copy the file `conf.py.template` to `conf.py`, and modify the variables to point to
your EQ installation and your bot token.

### Running the bot
The main program is `botmain.py`.  Run this program to start the bot.  It should produce
output similar to the following:
```
INFO:botmain:Initializing log_tap
INFO:botmain:Initializing eqcmd
INFO:botmain:Connecting to discord
WARNING:discord.client:PyNaCl is not installed, voice will NOT be supported
INFO:discord.client:on_message has successfully been registered as an event
INFO:discord.client:logging in using static token
INFO:discord.gateway:Created websocket connected to wss://gateway.discord.gg?encoding=json&v=6
INFO:discord.gateway:sent the identify payload to create the websocket
INFO:chat:Logged in as R99Watch-Dev (ID:...) | Connected to 1 servers | Connected to 2 users
INFO:chat:--------
INFO:chat:Current Discord.py Version: 0.16.12 | Current Python Version: 3.5.2
INFO:chat:--------
INFO:chat:Use this link to invite R99Watch-Dev:
INFO:chat:https://discordapp.com/oauth2/authorize?client_id=...&scope=bot&permissions=8
INFO:chat:--------
INFO:botmain:Installing modules
```

It may take a while for the bot to get started.  Particularly, the "Initializing eqcmd"
line may take up to a minute, as the bot is waiting for an "out of food" message to ensure
that EQ is really running.

### Connecting to a server
You must be an administrator on a Discord server to invite the bot to join.  If you are,
click the link in the text output to invite the bot to the server.  You should make the
bot an administrator so it can delete issued commands.

Once the bot is on the server, choose a channel and issue the "!bind" command.

