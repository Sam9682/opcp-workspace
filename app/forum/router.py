"""Forum API endpoints

This module provides REST API endpoints for forum functionality including
topics and posts. All endpoints require authenticated member access.

Validates Requirements 3.1, 3.2, 3.3, 3.4, 10.2
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import User, Topic, Post
from app.forum.dependencies import get_verified_member, get_administrator
from app.forum.config_service import get_view_button_enabled
from app.forum.schemas import (
    TopicCreate,
    TopicResponse,
    TopicDetailResponse,
    PostCreate,
    PostResponse
)
from app.auth.schemas import ErrorResponse
from app.logging_config import logger
from app.services.notification_service import notification_service


router = APIRouter(prefix="/api/forum", tags=["forum"])


@router.get("/config")
async def get_forum_config(
    db: Session = Depends(get_db)
):
    """Return the public forum configuration (public, unauthenticated).

    Exposes the ``view_button_enabled`` flag so logged-out visitors on the home
    page can decide whether to render the "View" button. No auth dependency is
    used here, consistent with ``/forum/topics/public``.

    Args:
        db: Database session

    Returns:
        A JSON object of the shape ``{"view_button_enabled": <bool>}``.
    """
    return {"view_button_enabled": get_view_button_enabled(db)}


@router.get("/topics/public", response_model=list[TopicResponse])
async def list_topics_public(
    db: Session = Depends(get_db)
):
    """List all forum topics (public access).
    
    Public endpoint that allows unauthenticated users to see the list of topics.
    Users must be authenticated to view topic details.
    
    Args:
        db: Database session
        
    Returns:
        List of forum topics with metadata
    """
    logger.info("Public access to forum topics list")
    
    # Query topics with post count
    topics = db.query(
        Topic,
        func.count(Post.id).label('post_count')
    ).outerjoin(
        Post, Topic.id == Post.topic_id
    ).group_by(
        Topic.id
    ).order_by(
        Topic.is_pinned.desc(),
        Topic.created_at.desc()
    ).all()
    
    # Build response with author names
    result = []
    for topic, post_count in topics:
        author = db.query(User).filter(User.id == topic.author_id).first()
        author_name = f"{author.first_name} {author.last_name}" if author else "Unknown"
        
        result.append(TopicResponse(
            id=topic.id,
            title=topic.title,
            author_id=topic.author_id,
            author_name=author_name,
            is_pinned=topic.is_pinned,
            is_locked=topic.is_locked,
            created_at=topic.created_at,
            updated_at=topic.updated_at,
            post_count=post_count
        ))
    
    return result


@router.get("/topics", response_model=list[TopicResponse])
async def list_topics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_verified_member)
):
    """List all forum topics.
    
    Requires authenticated member access (Requirement 3.4).
    Returns all topics with author information (Requirement 3.1).
    
    Args:
        db: Database session
        current_user: Authenticated and verified member
        
    Returns:
        List of forum topics with metadata
    """
    logger.info(f"User {current_user.id} listing forum topics")
    
    # Query topics with post count
    topics = db.query(
        Topic,
        func.count(Post.id).label('post_count')
    ).outerjoin(
        Post, Topic.id == Post.topic_id
    ).group_by(
        Topic.id
    ).order_by(
        Topic.is_pinned.desc(),
        Topic.created_at.desc()
    ).all()
    
    # Build response with author names
    result = []
    for topic, post_count in topics:
        author = db.query(User).filter(User.id == topic.author_id).first()
        author_name = f"{author.first_name} {author.last_name}" if author else "Unknown"
        
        result.append(TopicResponse(
            id=topic.id,
            title=topic.title,
            author_id=topic.author_id,
            author_name=author_name,
            is_pinned=topic.is_pinned,
            is_locked=topic.is_locked,
            created_at=topic.created_at,
            updated_at=topic.updated_at,
            post_count=post_count
        ))
    
    return result


@router.post("/topics", response_model=TopicResponse, status_code=status.HTTP_201_CREATED)
async def create_topic(
    topic_data: TopicCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_verified_member)
):
    """Create a new forum topic.
    
    Requires authenticated member access (Requirement 3.4).
    Associates topic with authenticated user (Requirement 3.2).
    
    Args:
        topic_data: Topic creation data
        db: Database session
        current_user: Authenticated and verified member
        
    Returns:
        Created topic with metadata
    """
    logger.info(f"User {current_user.id} creating topic: {topic_data.title}")
    
    # Create new topic
    new_topic = Topic(
        title=topic_data.title,
        author_id=current_user.id,
        is_pinned=False,
        is_locked=False
    )
    
    db.add(new_topic)
    db.commit()
    db.refresh(new_topic)
    
    author_name = f"{current_user.first_name} {current_user.last_name}"
    
    return TopicResponse(
        id=new_topic.id,
        title=new_topic.title,
        author_id=new_topic.author_id,
        author_name=author_name,
        is_pinned=new_topic.is_pinned,
        is_locked=new_topic.is_locked,
        created_at=new_topic.created_at,
        updated_at=new_topic.updated_at,
        post_count=0
    )


@router.get("/topics/{topic_id}", response_model=TopicDetailResponse)
async def get_topic(
    topic_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_verified_member)
):
    """Get a specific topic with all its posts.
    
    Requires authenticated member access (Requirement 3.4).
    Returns posts with author and timestamp (Requirement 3.6).
    Posts are ordered chronologically (Requirement 3.3).
    
    Args:
        topic_id: UUID of the topic
        db: Database session
        current_user: Authenticated and verified member
        
    Returns:
        Topic details with all posts
        
    Raises:
        HTTPException 404: If topic not found
    """
    from uuid import UUID
    
    try:
        topic_uuid = UUID(topic_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse.create(
                code="INVALID_TOPIC_ID",
                message="Invalid topic ID format",
                details={}
            )
        )
    
    # Fetch topic
    topic = db.query(Topic).filter(Topic.id == topic_uuid).first()
    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse.create(
                code="TOPIC_NOT_FOUND",
                message="Topic not found",
                details={"topic_id": topic_id}
            )
        )
    
    # Fetch posts ordered chronologically (Requirement 3.3)
    posts = db.query(Post).filter(
        Post.topic_id == topic_uuid,
        Post.is_hidden == False  # Don't show hidden posts to regular users
    ).order_by(Post.created_at.asc()).all()
    
    # Build response with author names
    topic_author = db.query(User).filter(User.id == topic.author_id).first()
    topic_author_name = f"{topic_author.first_name} {topic_author.last_name}" if topic_author else "Unknown"
    
    post_responses = []
    for post in posts:
        post_author = db.query(User).filter(User.id == post.author_id).first()
        post_author_name = f"{post_author.first_name} {post_author.last_name}" if post_author else "Unknown"
        
        post_responses.append(PostResponse(
            id=post.id,
            topic_id=post.topic_id,
            author_id=post.author_id,
            author_name=post_author_name,
            content=post.content,
            is_hidden=post.is_hidden,
            created_at=post.created_at,
            updated_at=post.updated_at
        ))
    
    return TopicDetailResponse(
        id=topic.id,
        title=topic.title,
        author_id=topic.author_id,
        author_name=topic_author_name,
        is_pinned=topic.is_pinned,
        is_locked=topic.is_locked,
        created_at=topic.created_at,
        updated_at=topic.updated_at,
        post_count=len(post_responses),
        posts=post_responses
    )


@router.get("/topics/{topic_id}/public", response_model=TopicDetailResponse)
async def get_topic_public(
    topic_id: str,
    db: Session = Depends(get_db)
):
    """Get a specific topic with all its posts (public access, read-only).
    
    Public endpoint that allows unauthenticated users to read forum topics.
    Users must be authenticated to post replies.
    
    Args:
        topic_id: UUID of the topic
        db: Database session
        
    Returns:
        Topic details with all posts
        
    Raises:
        HTTPException 404: If topic not found
    """
    from uuid import UUID
    
    try:
        topic_uuid = UUID(topic_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse.create(
                code="INVALID_TOPIC_ID",
                message="Invalid topic ID format",
                details={}
            )
        )
    
    # Fetch topic
    topic = db.query(Topic).filter(Topic.id == topic_uuid).first()
    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse.create(
                code="TOPIC_NOT_FOUND",
                message="Topic not found",
                details={"topic_id": topic_id}
            )
        )
    
    # Fetch posts ordered chronologically
    posts = db.query(Post).filter(
        Post.topic_id == topic_uuid,
        Post.is_hidden == False  # Don't show hidden posts
    ).order_by(Post.created_at.asc()).all()
    
    # Build response with author names
    topic_author = db.query(User).filter(User.id == topic.author_id).first()
    topic_author_name = f"{topic_author.first_name} {topic_author.last_name}" if topic_author else "Unknown"
    
    post_responses = []
    for post in posts:
        post_author = db.query(User).filter(User.id == post.author_id).first()
        post_author_name = f"{post_author.first_name} {post_author.last_name}" if post_author else "Unknown"
        
        post_responses.append(PostResponse(
            id=post.id,
            topic_id=post.topic_id,
            author_id=post.author_id,
            author_name=post_author_name,
            content=post.content,
            is_hidden=post.is_hidden,
            created_at=post.created_at,
            updated_at=post.updated_at
        ))
    
    logger.info(f"Public access to topic {topic_id}")
    
    return TopicDetailResponse(
        id=topic.id,
        title=topic.title,
        author_id=topic.author_id,
        author_name=topic_author_name,
        is_pinned=topic.is_pinned,
        is_locked=topic.is_locked,
        created_at=topic.created_at,
        updated_at=topic.updated_at,
        post_count=len(post_responses),
        posts=post_responses
    )


@router.get("/topics/{topic_id}/publichtml", response_class=HTMLResponse)
async def get_topic_public_html(
    topic_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Get a specific topic with all its posts as HTML (public access)."""
    from uuid import UUID
    
    try:
        topic_uuid = UUID(topic_id)
    except ValueError:
        return HTMLResponse(content="<h1>Invalid topic ID</h1>", status_code=400)
    
    topic = db.query(Topic).filter(Topic.id == topic_uuid).first()
    if not topic:
        return HTMLResponse(content="<h1>Topic not found</h1>", status_code=404)
    
    posts = db.query(Post).filter(
        Post.topic_id == topic_uuid,
        Post.is_hidden == False
    ).order_by(Post.created_at.asc()).all()
    
    topic_author = db.query(User).filter(User.id == topic.author_id).first()
    topic_author_name = f"{topic_author.first_name} {topic_author.last_name}" if topic_author else "Unknown"
    
    posts_html = ""
    for post in posts:
        post_author = db.query(User).filter(User.id == post.author_id).first()
        post_author_name = f"{post_author.first_name} {post_author.last_name}" if post_author else "Unknown"
        posts_html += f"""
        <div style="border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px; background: #f9f9f9;">
            <div style="font-weight: bold; color: #333;">{post_author_name}</div>
            <div style="font-size: 0.85em; color: #666; margin: 5px 0;">{post.created_at.strftime('%d/%m/%Y %H:%M')}</div>
            <div style="margin-top: 10px; white-space: pre-wrap;">{post.content}</div>
        </div>
        """
    
    # Get first post content for description
    first_post_content = posts[0].content[:200] if posts else "Discussion sur le forum OPCP"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>{topic.title} - OPCP Forum</title>
        <meta property="og:title" content="{topic.title}" />
        <meta property="og:description" content="{first_post_content}" />
        <meta property="og:type" content="article" />
        <meta property="og:url" content="https://opcp-psmc.com/api/forum/topics/{topic_id}/publichtml" />
        <meta property="og:site_name" content="OPCP Forum" />
        <meta name="description" content="{first_post_content}" />
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background: #fff; }}
            h1 {{ color: #1a1a1a; border-bottom: 2px solid #1a1a1a; padding-bottom: 10px; }}
            .meta {{ color: #666; font-size: 0.9em; margin: 10px 0; }}
        </style>
    </head>
    <body>
        <h1>{topic.title}</h1>
        <div class="meta">
            Créé par {topic_author_name} le {topic.created_at.strftime('%d/%m/%Y %H:%M')}
        </div>
        <div style="margin-top: 30px;">
            {posts_html}
        </div>
    </body>
    </html>
    """
    
    logger.info(f"Public HTML access to topic {topic_id}")
    return HTMLResponse(content=html_content)


@router.post("/topics/{topic_id}/posts", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_post(
    topic_id: str,
    post_data: PostCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_verified_member)
):
    """Add a reply to a topic.
    
    Requires authenticated member access (Requirement 3.4).
    Associates post with authenticated user (Requirement 3.3).
    
    Args:
        topic_id: UUID of the topic
        post_data: Post creation data
        db: Database session
        current_user: Authenticated and verified member
        
    Returns:
        Created post with metadata
        
    Raises:
        HTTPException 404: If topic not found
        HTTPException 403: If topic is locked
    """
    from uuid import UUID
    
    try:
        topic_uuid = UUID(topic_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse.create(
                code="INVALID_TOPIC_ID",
                message="Invalid topic ID format",
                details={}
            )
        )
    
    # Check if topic exists
    topic = db.query(Topic).filter(Topic.id == topic_uuid).first()
    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse.create(
                code="TOPIC_NOT_FOUND",
                message="Topic not found",
                details={"topic_id": topic_id}
            )
        )
    
    # Check if topic is locked
    if topic.is_locked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ErrorResponse.create(
                code="TOPIC_LOCKED",
                message="Cannot post to a locked topic",
                details={"topic_id": topic_id}
            )
        )
    
    logger.info(f"User {current_user.id} posting to topic {topic_id}")
    
    # Create new post
    new_post = Post(
        topic_id=topic_uuid,
        author_id=current_user.id,
        content=post_data.content,
        is_hidden=False
    )
    
    db.add(new_post)
    db.commit()
    db.refresh(new_post)
    
    # Send notification to topic author if they're not the one posting (Requirement 10.2)
    if topic.author_id != current_user.id:
        author_name = f"{current_user.first_name} {current_user.last_name}"
        try:
            notification_service.send_forum_reply_notification(
                db=db,
                user_id=topic.author_id,
                topic_title=topic.title,
                reply_author=author_name,
                reply_content=post_data.content
            )
            logger.info(f"Sent forum reply notification to user {topic.author_id}")
        except Exception as e:
            # Don't fail the post creation if notification fails
            logger.error(f"Failed to send forum reply notification: {str(e)}")
    
    author_name = f"{current_user.first_name} {current_user.last_name}"
    
    return PostResponse(
        id=new_post.id,
        topic_id=new_post.topic_id,
        author_id=new_post.author_id,
        author_name=author_name,
        content=new_post.content,
        is_hidden=new_post.is_hidden,
        created_at=new_post.created_at,
        updated_at=new_post.updated_at
    )


@router.put("/posts/{post_id}", response_model=PostResponse)
async def update_post(
    post_id: str,
    post_data: PostCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_verified_member)
):
    """Update a forum post.
    
    Requires authenticated member access and post ownership.
    Users can only edit their own posts, but administrators can edit any post.
    
    Args:
        post_id: UUID of the post to update
        post_data: Updated post content
        db: Database session
        current_user: Authenticated and verified member
        
    Returns:
        Updated post with metadata
        
    Raises:
        HTTPException 400: If post ID format is invalid
        HTTPException 404: If post not found
        HTTPException 403: If user is not the post author and not an administrator
    """
    from uuid import UUID
    from app.models.user import UserRole
    
    try:
        post_uuid = UUID(post_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse.create(
                code="INVALID_POST_ID",
                message="Invalid post ID format",
                details={}
            )
        )
    
    # Fetch post
    post = db.query(Post).filter(Post.id == post_uuid).first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse.create(
                code="POST_NOT_FOUND",
                message="Post not found",
                details={"post_id": post_id}
            )
        )
    
    # Check if user is the post author or an administrator
    if post.author_id != current_user.id and current_user.role != UserRole.ADMINISTRATOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ErrorResponse.create(
                code="NOT_POST_AUTHOR",
                message="You can only edit your own posts",
                details={"post_id": post_id}
            )
        )
    
    logger.info(f"User {current_user.id} updating post {post_id}")
    
    # Update post content
    post.content = post_data.content
    
    db.commit()
    db.refresh(post)
    
    # Get the post author's name for the response
    post_author = db.query(User).filter(User.id == post.author_id).first()
    author_name = f"{post_author.first_name} {post_author.last_name}" if post_author else "Unknown"
    
    return PostResponse(
        id=post.id,
        topic_id=post.topic_id,
        author_id=post.author_id,
        author_name=author_name,
        content=post.content,
        is_hidden=post.is_hidden,
        created_at=post.created_at,
        updated_at=post.updated_at
    )


@router.put("/posts/{post_id}/hide", status_code=status.HTTP_200_OK)
async def hide_post(
    post_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_administrator)
):
    """Hide a forum post (admin only).

    Requires administrator role (Requirement 7.2).
    Marks post as hidden and excludes from normal display (Requirement 3.5).
    Logs moderation action in audit log (Requirement 7.5).

    Args:
        post_id: UUID of the post to hide
        db: Database session
        current_user: Authenticated administrator

    Returns:
        Success message

    Raises:
        HTTPException 400: If post ID format is invalid
        HTTPException 404: If post not found
    """
    from uuid import UUID
    from app.models import AuditLog

    try:
        post_uuid = UUID(post_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse.create(
                code="INVALID_POST_ID",
                message="Invalid post ID format",
                details={}
            )
        )

    # Fetch post
    post = db.query(Post).filter(Post.id == post_uuid).first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse.create(
                code="POST_NOT_FOUND",
                message="Post not found",
                details={"post_id": post_id}
            )
        )

    # Mark post as hidden (Requirement 3.5)
    post.is_hidden = True

    # Log moderation action in audit log (Requirement 7.5)
    audit_entry = AuditLog(
        admin_id=current_user.id,
        action="hide_post",
        target_type="post",
        target_id=post.id,
        details={
            "post_id": str(post.id),
            "topic_id": str(post.topic_id),
            "author_id": str(post.author_id),
            "content_preview": post.content[:100] if len(post.content) > 100 else post.content
        }
    )

    db.add(audit_entry)
    db.commit()

    logger.info(f"Administrator {current_user.id} hid post {post_id}")

    return {
        "success": True,
        "message": "Post has been hidden successfully",
        "post_id": str(post.id)
    }


@router.delete("/posts/{post_id}", status_code=status.HTTP_200_OK)
async def delete_post(
    post_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_administrator)
):
    """Delete a forum post (admin only).

    Requires administrator role.
    Permanently deletes the post from the database.
    Logs deletion action in audit log.

    Args:
        post_id: UUID of the post to delete
        db: Database session
        current_user: Authenticated administrator

    Returns:
        Success message

    Raises:
        HTTPException 400: If post ID format is invalid
        HTTPException 404: If post not found
    """
    from uuid import UUID
    from app.models import AuditLog

    try:
        post_uuid = UUID(post_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse.create(
                code="INVALID_POST_ID",
                message="Invalid post ID format",
                details={}
            )
        )

    # Fetch post
    post = db.query(Post).filter(Post.id == post_uuid).first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse.create(
                code="POST_NOT_FOUND",
                message="Post not found",
                details={"post_id": post_id}
            )
        )

    # Log deletion action in audit log before deleting
    audit_entry = AuditLog(
        admin_id=current_user.id,
        action="delete_post",
        target_type="post",
        target_id=post.id,
        details={
            "post_id": str(post.id),
            "topic_id": str(post.topic_id),
            "author_id": str(post.author_id),
            "content_preview": post.content[:100] if len(post.content) > 100 else post.content
        }
    )

    db.add(audit_entry)
    
    # Delete the post
    db.delete(post)
    db.commit()

    logger.info(f"Administrator {current_user.id} deleted post {post_id}")

    return {
        "success": True,
        "message": "Post has been deleted successfully",
        "post_id": str(post_id)
    }


