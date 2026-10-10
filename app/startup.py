"""Startup utilities for application initialization"""
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.user import User, UserRole
from app.auth.password import hash_password
from app.logging_config import logger


def create_default_admin():
    """Create default admin user if no users exist in the database"""
    db: Session = SessionLocal()
    try:
        # Check if any users exist
        user_count = db.query(User).count()
        
        if user_count == 0:
            logger.info("No users found in database. Creating default admin user...")
            
            # Create default admin user
            default_admin = User(
                email="admin@opcp-psmc.com",
                password_hash=hash_password("Admin1234!"),
                first_name="Admin",
                last_name="OPCP",
                role=UserRole.ADMINISTRATOR,
                is_email_verified=True,
                membership_expires_at=None,  # Lifetime membership
                membership_status="active"
            )
            
            db.add(default_admin)
            db.commit()
            db.refresh(default_admin)
            
            logger.info(f"Default admin user created: {default_admin.email}")
            logger.info("Default credentials - Email: admin@opcp-psmc.com, Password: Admin1234!")
        else:
            logger.info(f"Database already contains {user_count} user(s). Skipping default admin creation.")
            
    except Exception as e:
        logger.error(f"Error creating default admin user: {str(e)}")
        db.rollback()
    finally:
        db.close()
