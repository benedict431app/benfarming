import secrets
key = secrets.token_hex(32)
print(f"Your secret key: {key}")
print(f"Add to .env: SECRET_KEY={key}")