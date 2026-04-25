from passlib.hash import bcrypt
hash = bcrypt.hash('AdminPass123!')
print(hash)
