from UserManager import UserManager
import Session
from Log import Log
import sasl

class XMPPAuth(sasl.auth.Authenticator):
    """To authenticate XMPP users.
    Plan to support 2 methods:
        PLAIN: just username & password
        X-BBS-OAUTH: use OAuth token
    """

    def __init__(self, service_type, host, service_name):
        self._service_type = service_type
        self._host = host
        self._service_name = service_name
        self._username = None

    def service_type(self):
        return self._service_type

    def host(self):
        return self._host

    def service_name(self):
        return self._service_name
    
    def username(self):
        return self._username

    def password(self):
        raise NotImplementedError

    def get_password(self):
        raise NotImplementedError

    def verify_token(self, token):
        """Verify token"""

        try:
            result = Session.SessionManager.CheckSession(token)
            if result is not None:
                self._username = result
            else:
                Log.warn("XMPPAuth: fail to verify session")
            return result is not None
        except Exception as e:
            Log.warn("XMPPAuth: exception in CheckSession: %r" % e)
            return False

    def verify_password(self, authorize, username, passwd):
        """Verify password"""

        if (authorize and username != authorize):
            Log.warn("XMPPAuth: user %s does not match authorize %s" % (username, authorize))
            return False

        username = username.encode("gbk")
#        print "trying to auth %s pass %s" % (user, passwd)
        user = UserManager.LoadUser(username)
        if (user == None):
            Log.warn("XMPPAuth: user not exist: %s" % username)
            return False

        if (user.Authorize(passwd)):
#            print "OK"
            return True

        Log.warn("XMPPAuth: user %s auth failed!" % username)

#        print "Wrong PW"
        return False

