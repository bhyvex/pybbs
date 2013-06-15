#!/usr/bin/env python
import Config
import PostEntry
import Post
import os

class MailBox:
    name = ''

    def __init__(self, username):
        self.name = username

    def path_of(self, path):
        return "%s/mail/%c/%s/%s" % (Config.BBS_ROOT, self.name[0].upper(), self.name, path)

    def folder_path(self, folder):
        if (folder == 'inbox'):
            return self.path_of(".DIR")
        elif (folder == 'sent'):
            return self.path_of(".SENT")
        else:
            # fail-safe
            return self.path_of(".DIR")

    def get_folder(self, folder):
        return Folder(self, folder, self.folder_path(folder))

class Folder:
    def __init__(self, mailbox, name, path):
        self.name = name
        self.path = path
        self.mailbox = mailbox

    def count(self):
        try:
            st = os.stat(self.path)
        except:
            return 0

        return st.st_size / PostEntry.PostEntry.size

    def get_entry(self, index):
        if (index < 0 or index >= self.count()):
            return None

        try:
            with open(self.path, "rb") as dirf:
                dirf.seek(index * PostEntry.PostEntry.size)
                data = dirf.read(PostEntry.PostEntry.size)
                if (len(data) < PostEntry.PostEntry.size):
                    return None
                return PostEntry.PostEntry(data)
        except:
            return None

    def set_entry(self, index, entry):
        if (index < 0 or index >= self.count()):
            return False

        try:
            with open(self.path, "r+b") as dirf:
                dirf.seek(index * PostEntry.PostEntry.size)
                dirf.write(entry.pack())
                return True
        except:
            return False

    def get_content(self, index):
        entry = self.get_entry(index)
        if (entry is None):
            return None
        path = self.mailbox.path_of(entry.filename)
        post = Post.Post(path)
        return post

