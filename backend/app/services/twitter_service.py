from app.models.content import Content


def publish(content: Content) -> dict:
    return {
        "status": "not_implemented",
        "detail": "Twitter/X publishing has not been wired yet.",
        "content_id": content.id,
    }
