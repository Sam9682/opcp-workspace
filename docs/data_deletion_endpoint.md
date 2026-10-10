# Data Deletion Endpoint - RGPD Compliance

## Overview

The data deletion endpoint implements the RGPD (GDPR) "right to be forgotten" requirement, allowing users to request deletion of their personal data.

## Endpoint

**DELETE /api/users/me**

Authenticated users can request deletion of their account and personal data.

### Response

```json
{
  "success": true,
  "message": "Your account deletion has been scheduled. Your data will be permanently deleted on 2024-03-15.",
  "scheduled_for": "2024-03-15T10:30:00+00:00"
}
```

## Implementation Details

### Immediate Actions

When a user requests deletion:
1. A `ScheduledUserDeletion` record is created with deletion date = now + 30 days
2. User account is immediately deactivated (`is_email_verified` set to `false`)
3. User cannot login anymore

### Scheduled Processing

A background job runs daily at 2:00 AM to process scheduled deletions.

### Data Handling Strategy

The deletion process follows these rules to balance RGPD compliance with legal requirements:

#### Anonymized (Preserved but Anonymized)
- **User Profile**: Email changed to `deleted_user_{id}@deleted.local`, name changed to "Deleted User"
- **Forum Topics**: Preserved for community value, author reference removed
- **Forum Posts**: Preserved for community value, author reference removed
- **Events Created**: Preserved, creator reference removed

#### Deleted
- **Event Registrations**: Completely removed
- **Documents Uploaded**: Removed from database (files should be cleaned separately)
- **Notifications**: Completely removed
- **Notification Preferences**: Completely removed

#### Preserved (Legal Compliance)
- **Payment Records**: Fully preserved with user_id reference (required for accounting/legal)
- **Audit Logs**: Fully preserved (required for legal compliance)

### Database Schema

```sql
CREATE TABLE scheduled_user_deletions (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  requested_at TIMESTAMP WITH TIME ZONE NOT NULL,
  scheduled_for TIMESTAMP WITH TIME ZONE NOT NULL,
  user_email VARCHAR(255) NOT NULL,
  user_full_name VARCHAR(255) NOT NULL,
  UNIQUE(user_id)
);
```

## Testing

Comprehensive tests are provided in `tests/test_user_data_deletion.py`:

- Request deletion successfully
- Prevent duplicate deletion requests
- Verify authentication required
- Test data anonymization process
- Verify payment records preserved
- Verify audit logs preserved
- Test scheduled processing

## Background Job

The deletion processing job is configured in `app/scheduler.py`:

```python
# Run user deletion check daily at 2:00 AM
self.scheduler.add_job(
    self.user_deletion_job,
    trigger=CronTrigger(hour=2, minute=0),
    id='user_deletion',
    name='Process scheduled user deletions',
    replace_existing=True
)
```

## Legal Compliance

This implementation complies with:
- **RGPD Article 17**: Right to erasure ("right to be forgotten")
- **30-day grace period**: Allows for recovery if user changes mind
- **Legal record preservation**: Maintains financial and audit records as required by law
- **Data minimization**: Only preserves what's legally necessary

## Future Enhancements

Potential improvements:
1. Email notification when deletion is scheduled
2. Email reminder 7 days before deletion
3. Cancellation endpoint to stop scheduled deletion
4. Admin interface to view scheduled deletions
5. Automatic file cleanup from storage service
