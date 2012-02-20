#!/usr/bin/env python

"""Data service
   by henryhu
   2010.12.06    created.
"""

import cgi
import mimetools
import os
import string
import struct
import urlparse
import SocketServer
import socket
import re
import sys
from pwd import getpwnam
from SocketServer import BaseServer
from BaseHTTPServer import *
from OpenSSL import SSL
from Post import Post
from Board import Board
from Session import Session
from BCache import BCache
from Config import Config
from BoardManager import BoardManager
from User import User
from UCache import UCache
from UserManager import UserManager
from Session import SessionManager
from Auth import Auth
from MsgBox import MsgBox
from FavBoard import FavBoard
from Log import Log

class DataService(BaseHTTPRequestHandler):
    classes = { "post"      : Post, 
               "board"      : Board,
               "session"    : Session,
               "user"       : User,
               "auth"       : Auth,
               "favboard"   : FavBoard,
              }
    classes_keys = classes.keys()

    def parse_req(self, req):
        m = re.search("^/(.*)/(.*)$", req)
        if (m != None):
            return (m.group(1), m.group(2))
        else:
            raise exception()

    def setup(self):
        self.connection = self.request
        self.rfile = socket._fileobject(self.request, "rb", self.rbufsize)
        self.wfile = socket._fileobject(self.request, "wb", self.wbufsize)

    def address_string(self):
        try:
            ip = self.headers['X-Forwarded-For']
        except KeyError:
            return self.client_address[0]
        return ip
        
    def writedata(self, data, type = ''):
        try:
            self.send_response(200)
            self.send_header('Content-Length', len(data))
            if len(type) > 0:
                self.send_header('Content-Type', type)
            self.end_headers()
            self.wfile.write(data)
        except:
            pass

    def return_error(self, code, reason):
        self.send_response(code, reason)
        self.end_headers()

    def do_POST(self):
        url_tuple = urlparse.urlsplit(self.path)
        params = dict(urlparse.parse_qsl(url_tuple[3]))
        req = url_tuple[2]

        ctype, pdict = cgi.parse_header(self.headers.getheader('content-type'))
        if ctype == 'multipart/form-data':
            postvars = cgi.parse_multipart(self.rfile, pdict)
            for i in postvars:
                postvars[i] = postvars[i][0]
        elif ctype == 'application/x-www-form-urlencoded':
            length = int(self.headers.getheader('content-length'))
            postvars = dict(urlparse.parse_qsl(self.rfile.read(length), keep_blank_values=1))
        else:
            postvars = {}
        
        params = dict(params.items() + postvars.items())
        session = self.GetSession(params)

        try:
            cls, op = self.parse_req(req)
        except:
            self.log_error('Bad request: %s', req)
            self.return_error(400, 'bad request')
            return

        if (cls in DataService.classes_keys):
            DataService.classes[cls].POST(self, session, params, op)
        else:
            self.log_error('Bad POST %s', self.path)
            self.return_error(400, 'bad request')

    def GetSession(self, params):
        if (params.has_key('session')):
            sid = params['session']
            return SessionManager.GetSession(sid)
        else:
            return None

    def do_GET(self):
        url_tuple = urlparse.urlsplit(self.path)
        params = dict(cgi.parse_qsl(url_tuple[3]))
        req = url_tuple[2]
        session = self.GetSession(params)

        try:
            cls, op = self.parse_req(req)
        except:
            self.log_error('Bad request: %s', req)
            self.return_error(400, 'bad request')
            return

        if (cls in DataService.classes_keys):
            DataService.classes[cls].GET(self, session, params, op)
        else:
            self.log_error('Bad GET: %s', self.path)
            self.return_error(400, 'bad request')

class MyServer(SocketServer.ThreadingMixIn, HTTPServer):
    def __init__(self, server_address, HandlerClass):
        BaseServer.__init__(self, server_address, HandlerClass)
        self.Init()

        ctx = SSL.Context(SSL.SSLv23_METHOD)
        fpem = Config.GetString('BBS_DATASVC_CERT', 'server.pem')
        ctx.use_privatekey_file(fpem)
        ctx.use_certificate_file(fpem)
        self.socket = SSL.Connection(ctx, socket.socket(self.address_family, self.socket_type))
        self.server_bind()
        self.server_activate()

    def Init(self):
        Config.LoadConfig()
        BCache.Init()
        BoardManager.Init()
        UCache.Init()

    pass

def main():
    try:
        userinfo = getpwnam('bbs')
        os.setuid(userinfo[2])
    except:
        Log.error("Failed to find user 'bbs'!")
        sys.exit(1)

    port = 8080
    server = MyServer(('', port), DataService)
    print 'Starting at port %d...' % port
    try:
        server.serve_forever()
    except:
        pass
        
if __name__ == '__main__':
    main()   

