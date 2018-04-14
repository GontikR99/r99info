# r99info: a Discord <--> Project1999 bridge

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
* PIP to install python packages (apt install python3-pip)
* discord.py (pip3 install discord.py)
* isodate library (apt install python3-isodate)
* OpenCV library (pip3 install opencv-python)
* A Discord bot static token (see e.g. https://github.com/Habchy/BasicBot/wiki/Step-3)


### EQ on Linux
First, get EQ running.  Copy the EverQuest installation into a directory on
the linux host.

Next, start two separate instances of xpra:

```sh
$ xpra start
seamless session now available on display :0
$ xpra start
seamless session now available on display :1 
```

Then, attach the second to the first:
```sh
$ DISPLAY=:1 xpra attach :0 &
2018-04-13 21:08:33,128 Xpra gtk2 client version 2.2.6-r18968 32-bit
2018-04-13 21:08:33,128  running on Linux Debian 9.4 stretch
...
```

### Configuring the bot
Copy the file `conf.py.template` to `conf.py`, and modify the variables to point to
your EQ installation and your bot token.


### Running the bot
The main program is `relogger.py`.  Run this program to start the bot.
```sh
$ DISPLAY=:0 ./relogger.py
```

```
[2018-04-13 08:56:08,371] INFO | relogger | Starting EQ
[2018-04-13 08:56:14,889] INFO | relogger | Clicking EULA button
[2018-04-13 08:56:18,196] INFO | relogger | Passing logo screen
[2018-04-13 08:56:18,948] INFO | relogger | Clicking login button
[2018-04-13 08:56:23,930] INFO | relogger | Entering username/password
[2018-04-13 08:56:34,517] INFO | relogger | Selecting server
[2018-04-13 08:56:50,636] INFO | relogger | Waiting for character select
[2018-04-13 08:57:18,298] INFO | relogger | Entering world
[2018-04-13 08:57:43,786] INFO | relogger | Waiting for world to load
[2018-04-13 08:57:44,692] INFO | relogger | Starting bot
[2018-04-13 08:57:44,908] INFO | botmain | Initializing eqlog
[2018-04-13 08:57:44,909] INFO | botmain | Initializing eqcmd
[2018-04-13 08:58:08,977] INFO | botmain | Connecting to discord 
[2018-04-13 08:58:08,978] WARNING | discord.client | PyNaCl is not installed, voice will NOT be supported
[2018-04-13 08:58:08,978] INFO | discord.client | on_message has successfully been registered as an event
[2018-04-13 08:58:08,978] INFO | discord.client | logging in using static token
[2018-04-13 08:58:09,193] INFO | discord.gateway | Created websocket connected to wss://gateway.discord.gg?encoding=json&v=6
[2018-04-13 08:58:09,204] INFO | discord.gateway | sent the identify payload to create the websocket
[2018-04-13 08:58:11,261] INFO | chat | Logged in as ... (ID:....) | Connected to 1 servers | Connected to 74 use
rs
[2018-04-13 08:58:11,261] INFO | chat | --------
[2018-04-13 08:58:11,261] INFO | chat | Current Discord.py Version: 0.16.12 | Current Python Version: 3.5.3
[2018-04-13 08:58:11,261] INFO | chat | --------
[2018-04-13 08:58:11,261] INFO | chat | Use this link to invite ...:
[2018-04-13 08:58:11,261] INFO | chat | https://discordapp.com/oauth2/authorize?client_id=...&scope=bot&permissions=8
[2018-04-13 08:58:11,261] INFO | chat | --------
[2018-04-13 08:58:11,261] INFO | botmain | Installing modules 
```

It may take a while for the bot to get started.  Even once the bot is logged in, it waits for an "out of food" message to ensure
that EQ is really running.

### Connecting to a server
You must be an administrator on a Discord server to invite the bot to join.  If you are,
click the link in the text output to invite the bot to the server.  You should make the
bot an administrator so it can delete issued commands.

Once the bot is on the server, choose a channel and issue the "!bind" command.

