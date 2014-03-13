from twisted.words.protocols import irc
from twisted.internet import reactor, protocol
from grabber import Grabber
from sqlalchemy import create_engine, MetaData
from setup import engine, metadata
import redditupdate

import time
import os
import ConfigParser
import logging

import actions
import sys

try:
    config = ConfigParser.RawConfigParser()
    config.read(sys.argv[1])

    log = logging.getLogger(__name__)
    log.setLevel(logging.DEBUG)
    fh = logging.FileHandler(config.get('hoggy', 'logfile'))
    fh.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s %(name)-12s: %(levelname)-8s %(message)s')
    fh.setFormatter(formatter)

    sh = logging.StreamHandler()
    sh.setLevel(logging.DEBUG)

    log.addHandler(sh)
    log.addHandler(fh)
except ConfigParser.NoSectionError:
    print "Config file is un-readable or not present.  Make sure you've created a config.ini (see config.ini.default for an example)"
    exit()


class HoggyBot(irc.IRCClient):
    """A logging IRC bot."""
    nickname = config.get('irc', 'nick')
    try:
        password = config.get('irc', 'password')
    except:
        password = None
    lineRate = 1

    def __init__(self, *args, **kwargs):
        self.commander = actions.Commander(self)
        self.grabber = Grabber()

    # callbacks for events
    def connectionMade(self):
        irc.IRCClient.connectionMade(self)
        
    def connectionLost(self, reason):
        irc.IRCClient.connectionLost(self, reason)

    def signedOn(self):
        """Called when bot has succesfully signed on to server."""
        for channel in self.factory.channels:
            self.join(channel)

    def joined(self, channel):
        """This will get called when the bot joins the channel."""
        self.msg(channel, "I have arrived!")
	if self.password:
            print "Registering username %s with %s" % (self.nickname, self.password)
            self.msg('NickServ', 'IDENTIFY %s' % self.password)
        self.reddit_update = redditupdate.RedditUpdateThread(self, channel)
        self.reddit_update.parse_threads(self.reddit_update.request_threads(),False)
        self.reddit_update.start()

    def privmsg(self, user, channel, msg):
        """This will get called when the bot receives a message."""
        user = user.split('!', 1)[0]

        # Check to see if they're sending me a private message
        if channel == self.nickname:
            message = self.commander.recv(msg,user)
            self.msg(user, message)
            return

        message = self.commander.recv(msg, user)
        self.grabber.stack(user, msg)
        if message:
            if message[:3] == "/me":
                message = message[4:]
                self.describe(channel,message)
            else:
                self.msg(channel, message)

    # For fun, override the method that determines how a nickname is changed on
    # collisions. The default method appends an underscore.
    def alterCollidedNick(self, nickname):
        """
        Generate an altered version of a nickname that caused a collision in an
        effort to create an unused related name for subsequent registration.
        """
        return nickname + '^'

class HoggyBotFactory(protocol.ClientFactory):
    """A factory for HoggyBots.

    A new protocol instance will be created each time we connect to the server.
    """

    def __init__(self, channels, filename):
        self.channels = channels.split(",")
        self.filename = filename

    def buildProtocol(self, addr):
        p = HoggyBot()
        p.factory = self
        return p

    def clientConnectionLost(self, connector, reason):
        """If we get disconnected, reconnect to server."""
        connector.connect()

    def clientConnectionFailed(self, connector, reason):
        print "connection failed, retrying..."
        connector.connect()


if __name__ == '__main__':
    # create factory protocol and application
    f = HoggyBotFactory(config.get('irc', 'channels'), config.get('irc', 'log'))

    # connect factory to this host and port
    reactor.connectTCP(config.get('irc', 'host'),config.getint('irc', 'port') , f)

    # run bot
    reactor.run()
