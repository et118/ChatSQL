import hashlib
import bcrypt
import base64

# We do some extra work since apparently bcrypt doesnt support too long passwords. So we
# do a sha256 hash first, and then make it into base64. See https://pypi.org/project/bcrypt/ 
# close to the bottom of the page.
def hash_string(string: str):
    password_bytes = string.encode("utf-8")
    if len(password_bytes) > 72:
        password_bytes = hashlib.sha256(password_bytes).digest()
        password_bytes = base64.b64encode(password_bytes)
    hash = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hash.decode("utf-8")
