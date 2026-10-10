#!/usr/bin/env python3
"""Script to verify and fix admin user account"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.models import User, UserRole
from app.auth.password import hash_password, verify_password

def main():
    db = SessionLocal()
    
    try:
        # Check for admin user
        admin = db.query(User).filter(User.email == "admin@opcp-psmc.com").first()
        
        if not admin:
            print("❌ Admin user not found!")
            print("\nCreating admin user...")
            
            admin = User(
                email="admin@opcp-psmc.com",
                password_hash=hash_password("Admin1234!"),
                first_name="Admin",
                last_name="OPCP",
                role=UserRole.ADMINISTRATOR,
                is_email_verified=True
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)
            
            print("✅ Admin user created successfully!")
            print(f"   Email: {admin.email}")
            print(f"   Password: Admin1234!")
            print(f"   Role: {admin.role.value}")
            print(f"   Email Verified: {admin.is_email_verified}")
        else:
            print("✅ Admin user found!")
            print(f"   ID: {admin.id}")
            print(f"   Email: {admin.email}")
            print(f"   Name: {admin.first_name} {admin.last_name}")
            print(f"   Role: {admin.role.value}")
            print(f"   Email Verified: {admin.is_email_verified}")
            
            # Check if email is verified
            if not admin.is_email_verified:
                print("\n⚠️  Email is NOT verified!")
                response = input("Do you want to verify the email? (y/n): ")
                if response.lower() == 'y':
                    admin.is_email_verified = True
                    db.commit()
                    print("✅ Email verified!")
            
            # Test password
            print("\n🔑 Testing password...")
            test_passwords = ["Admin1234!", "PAssword1234!", "Password1234!"]
            
            for pwd in test_passwords:
                if verify_password(pwd, admin.password_hash):
                    print(f"✅ Password '{pwd}' is correct!")
                    break
            else:
                print("❌ None of the test passwords match!")
                response = input("\nDo you want to reset the password to 'Admin1234!'? (y/n): ")
                if response.lower() == 'y':
                    admin.password_hash = hash_password("Admin1234!")
                    db.commit()
                    print("✅ Password reset to 'Admin1234!'")
        
        print("\n" + "="*50)
        print("Login credentials:")
        print("  Email: admin@opcp-psmc.com")
        print("  Password: Admin1234!")
        print("="*50)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()
