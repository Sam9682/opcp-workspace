#!/usr/bin/env python3
import os
os.environ['DATABASE_URL'] = 'postgresql://OPCP_user:OPCP_password@localhost:5432/OPCP_db'

import sys
sys.path.insert(0, '/home/ubuntu/ai-OPCP')

from app.database import SessionLocal
from app.models import User, UserRole
from app.auth.password import hash_password

db = SessionLocal()

try:
    # Check for typo email
    user = db.query(User).filter(User.email == 'admin@opcp-psmc.com').first()
    
    if user:
        print(f"User {user.email} found")
        if not user.is_email_verified:
            user.is_email_verified = True
            db.commit()
            print("✅ Email verified")
        else:
            print("✅ Email already verified")
    else:
        print("Creating admin@opcp-psmc.com user...")
        user = User(
            email='admin@opcp-psmc.com',
            password_hash=hash_password('Admin1234!'),
            first_name='Admin',
            last_name='OPCP',
            role=UserRole.ADMINISTRATOR,
            is_email_verified=True
        )
        db.add(user)
        db.commit()
        print("✅ User created and verified")
    
    print(f"\nLogin: admin@opcp-psmc.com")
    print(f"Password: Admin1234!")
    
finally:
    db.close()
