#!/usr/bin/env python
from Util import Util
import mailbox
import json
from errors import *

DEFAULT_MAIL_VIEW_COUNT = 20

class Mail:
    @staticmethod
    def GET(svc, session, params, action):
        if (session is None): raise Unauthorized('login first')
        if (action == 'list'):
            folder = svc.get_str(params, 'folder', 'inbox')
            start = svc.get_int(params, 'start', 0)
            end = svc.get_int(params, 'end', 0)
            count = svc.get_int(params, 'count', 0)
            svc.writedata(Mail.List(session.GetUser(), folder, start, count, end))
        elif (action == 'view'):
            folder = svc.get_str(params, 'folder', 'inbox')
            index = svc.get_int(params, 'index')
            svc.writedata(Mail.View(session.GetUser(), folder, index))
        else:
            raise WrongArgs('unknown action')

    @staticmethod
    def POST(svc, session, params, action):
        raise WrongArgs('unknown action')

    @staticmethod
    def List(user, folder, start, count, end):
        mbox = mailbox.MailBox(user.GetName())
        folder = mbox.get_folder(folder)
        total = folder.count()

        start, end = Util.CheckRange(start, end, count, DEFAULT_MAIL_VIEW_COUNT, total)
        if (start <= end and start >= 1 and end <= total):
            result = '{ "start": %d, "end": %d, "mails": [\n' % (start, end)
            first = True
            for i in range(start - 1, end):
                entry = folder.get_entry(i)
                if entry is None:
                    continue
                if not first:
                    result += ',\n'
                post = entry.GetInfo('mail')
                post['id'] = i+1
                result += json.dumps(post)
                first = False
            result += '\n]}'
            return result
        else:
            raise OutOfRange('out of range')

    @staticmethod
    def View(user, folder, index):
        mbox = mailbox.MailBox(user.GetName())
        folder = mbox.get_folder(folder)

        post = folder.get_content(index - 1)
        return json.dumps(post.GetInfo())
