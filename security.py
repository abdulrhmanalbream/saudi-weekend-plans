# Saudi Weekend Planner: passwords, session tokens and login limits
import hashlib
import hmac
import secrets
import time

# PBKDF2 runs SHA-256 many times, so guessing a password from its hash is slow
ITERATIONS = 200_000
# a token stays valid for 12 hours
TOKEN_HOURS = 12
# after 5 wrong passwords, the username waits 5 minutes
MAX_FAILS = 5
LOCK_SECONDS = 300


def hash_password(password, salt=None):
    """Returns (salt, hash) as hex text. A new random salt is made when none is given."""
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), bytes.fromhex(salt), ITERATIONS)
    return salt, digest.hex()


def check_password(password, salt, stored_hash):
    # compare_digest takes the same time for every input, so timing tells nothing
    _, digest = hash_password(password, salt)
    return hmac.compare_digest(digest, stored_hash)


def new_token():
    # 32 random bytes, safe to put in a header
    return secrets.token_urlsafe(32)


class LoginLimiter:
    """Counts wrong passwords per username and locks it for a while."""

    def __init__(self):
        # username -> [number of fails, time of the first fail]
        self.fails = {}

    def locked_for(self, username):
        # seconds left on the lock, or 0
        count, first = self.fails.get(username, [0, 0])
        if count >= MAX_FAILS:
            left = LOCK_SECONDS - (time.time() - first)
            if left > 0:
                return int(left)
            del self.fails[username]
        return 0

    def failed(self, username):
        count, first = self.fails.get(username, [0, time.time()])
        self.fails[username] = [count + 1, first]

    def succeeded(self, username):
        self.fails.pop(username, None)
