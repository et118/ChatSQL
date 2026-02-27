import hashlib
import bcrypt
import base64

# We do some extra work since apparently bcrypt doesnt support too long passwords. So we
# do a sha256 hash first, and then make it into base64. See https://pypi.org/project/bcrypt/ 
# close to the bottom of the page.
def hash_password(string: str):
    password_bytes = string.encode("utf-8")
    if len(password_bytes) > 72:
        password_bytes = hashlib.sha256(password_bytes).digest()
        password_bytes = base64.b64encode(password_bytes)
    hash = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hash.decode("utf-8")

def verify_hashed_password(password, password_hash):
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))

def hash_auth_token(string):
    return hashlib.sha256(string.encode("utf-8")).hexdigest()
