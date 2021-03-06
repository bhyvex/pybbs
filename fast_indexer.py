""" Fast indexer
    Supports fast query of posts from a certain thread.
"""
import threading
import os
import time
import sqlite3

import BoardManager
import PostEntry
import Config
from Log import Log
from Util import Util

INDEX_INTERVAL = 15
INDEX_DB = "index.db"

class State(object):
    """ FastIndexer's shared state """
    def __init__(self):
        self.locks = {}

class IndexBoardInfo(object):
    """ Indexing status of one board """
    def __init__(self, board, last_idx):
        self.board = board
        self.last_idx = last_idx

class FastIndexer(threading.Thread):
    """ The Fast Indexer """
    def __init__(self, state):
        threading.Thread.__init__(self)
        self.stopped = False
        self.board_info = {}
        self.conn = None

        self.init_conn()
        self.load_idx_status()
        self.state = state
        Log.info("FastIndexer init...")
        try:
            self.index_boards()
        except Exception as exc:
            Log.error("Exception caught initializing FastIndexer: %r" % exc)
            raise exc
        Log.info("FastIndexer inited")
        self.close_conn()

    def init_conn(self):
        """ Initialize database connection """
        self.conn = sqlite3.connect(os.path.join(Config.BBS_ROOT, INDEX_DB),
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        self.conn.row_factory = sqlite3.Row

    def close_conn(self):
        """ Close database connection """
        self.conn.close()

    def run(self):
        Log.info("FastIndexer start")
        self.init_conn()
        while True:
            if self.stopped:
                break
            try:
                self.index_boards()
            except Exception as exc:
                Log.error("Exception caught in FastIndexer: %r" % exc)

            time.sleep(INDEX_INTERVAL)
        self.close_conn()

    def init_buf(self, board):
        """ Initialize buffer table. """
        self.conn.execute("drop table if exists %s"
                % buf_table_name(board))
        self.conn.execute("create table %s("\
                "id int, xid int, tid int, rid int, time int"\
                ")" % buf_table_name(board))
        self.conn.commit()

    def load_idx_status(self):
        """ Load latest indexing status. """
        self.conn.execute("create table if not exists status("\
                "board text, last_idx int)")
        self.conn.commit()
        try:
            for row in self.conn.execute("select * from status"):
                idx_info = IndexBoardInfo(**row)
                self.board_info[idx_info.board] = idx_info
        except:
            Log.info("Index info not present")

    def insert_idx_status(self, idx_obj):
        """ Insert new indexing status for 'idx_obj'. """
        self.conn.execute("insert into status values (?, ?)",
                (idx_obj.board, idx_obj.last_idx))
        self.conn.commit()

    def remove_idx_status(self, idx_obj):
        """ Remove indexing status for 'idx_obj'. """
        self.conn.execute("delete from status where board=?",
                (idx_obj.board, ))
        self.conn.commit()

    def index_boards(self):
        """ Index all the boards. """
        boards = BoardManager.BoardManager.boards.keys()
        for board in boards:
            try:
                self.index_board(board)
            except Exception as exc:
                Log.error("Exception caught when indexing %s: %r"
                        % (board, exc))

    def index_board(self, board):
        """ Index one board (name: board)"""
        boardobj = BoardManager.BoardManager.GetBoard(board)
        if not boardobj:
            Log.error("Error loading board %s" % board)
            return

        if board in self.board_info:
            idx_obj = self.board_info[board]
        else:
            idx_obj = IndexBoardInfo(board, 0)
            self.board_info[board] = idx_obj

        bdir_path = boardobj.GetDirPath()
        with open(bdir_path, 'rb') as bdir:
            Util.FLock(bdir, shared=True)
            try:
                if not board in self.state.locks:
                    self.state.locks[board] = threading.Lock()

                status = os.stat(bdir_path)
                if status.st_mtime <= idx_obj.last_idx:
                    # why <? anyway...
                    return

                Log.debug("Board %s updated. Indexing..." % board)

                # index into buffer table
                self.init_buf(board)
                for idx in xrange(status.st_size / PostEntry.PostEntry.size):
                    post_entry = PostEntry.PostEntry(
                            bdir.read(PostEntry.PostEntry.size))
                    self.insert_entry(board, post_entry, idx)
                self.conn.commit()

                # commit buffer table
                self.state.locks[board].acquire()
                try:
                    self.remove_idx_status(idx_obj)
                    self.commit_buf(board)
                    self.create_db_index(board)
                    idx_obj.last_idx = status.st_mtime
                    self.insert_idx_status(idx_obj)
                finally:
                    self.state.locks[board].release()

                Log.debug("Board %s indexed." % board)
            finally:
                Util.FUnlock(bdir)

    def insert_entry(self, board, post_entry, idx):
        """ Insert into the buffer board """
        self.conn.execute("insert into %s values (?, ?, ?, ?, ?)"
                % buf_table_name(board),
                (idx, post_entry.id, post_entry.groupid,
                    post_entry.reid, post_entry.GetPostTime()))
        # batch commit later

    def commit_buf(self, board):
        """ Rename the temporary table to final table """
        self.conn.execute("drop table if exists %s" % table_name(board))
        self.conn.execute("alter table %s rename to %s" %
                (buf_table_name(board), table_name(board)))
        self.conn.commit()

    def create_db_index(self, board):
        """ Create database index for faster query. """
        idx_name = "idx_tid_%s" % board
        self.conn.execute("drop index if exists %s" % idx_name)
        self.conn.execute("create index %s on %s ( tid )" %
                (idx_name, table_name(board)))
        self.conn.commit()

def query_by_tid(state, board, tid, start, count):
    """ Query in the index of board 'board' for all threads with tid 'tid'
            starting from 'start', return 'count' results """
    conn = sqlite3.connect(os.path.join(Config.BBS_ROOT, INDEX_DB),
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    conn.row_factory = sqlite3.Row
    state.locks[board].acquire()

    try:
        result = []
        for row in conn.execute(
                "select id, xid from %s where tid=? order by id limit %d offset %d"
                % (table_name(board), count, start), (tid, )):
            result.append((row['id'] + 1, row['xid']))
    finally:
        state.locks[board].release()
        conn.close()

    return result

def table_name(board):
    """ Table name for board 'board' """
    return "idx_" + board

def buf_table_name(board):
    """ Temporary table name for board 'board' """
    return "tmp_idx_" + board

