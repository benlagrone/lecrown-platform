import pytest
from unittest.mock import patch, MagicMock

from app.services.communication import (
    send_communication_email,
    handle_inbound_reply,
    record_task_progress,
    CommunicationConfigurationError,
    CommunicationDeliveryError,
    ALLOWED_RECIPIENTS
)
from app.services.communication import TaskProgressRecord


def test_allowed_recipients():
    """Test that only authorized recipients are allowed"""
    assert "benjaminlagrone@gmail.com" in ALLOWED_RECIPIENTS
    assert "jie.huang@lecrowndevelopment.com" in ALLOWED_RECIPIENTS


@patch('app.services.communication.requests.post')
def test_send_communication_email_success(mock_post):
    """Test successful email sending"""
    # Mock the access token request
    mock_post.return_value.ok = True
    mock_post.return_value.json.return_value = {"access_token": "test_access_token"}
    
    # Mock the email send request
    mock_send_response = MagicMock()
    mock_send_response.ok = True
    mock_send_response.json.return_value = {"id": "test_message_id"}
    mock_post.side_effect = [mock_post.return_value, mock_send_response]
    
    # This should not raise an exception
    message_id = send_communication_email(
        recipient_email="benjaminlagrone@gmail.com",
        subject="Test Subject",
        content="Test content",
        task_id="test_task_123",
        task_type="gov_contract"
    )
    
    assert message_id == "test_message_id"


@patch('app.services.communication.requests.post')
def test_send_communication_email_unauthorized_recipient(mock_post):
    """Test that sending to unauthorized recipient raises error"""
    mock_post.return_value.ok = True
    mock_post.return_value.json.return_value = {"access_token": "test_access_token"}
    
    with pytest.raises(CommunicationConfigurationError) as excinfo:
        send_communication_email(
            recipient_email="unauthorized@example.com",
            subject="Test Subject",
            content="Test content",
            task_id="test_task_123",
            task_type="gov_contract"
        )
    
    assert "not authorized for automated communication" in str(excinfo.value)


@patch('app.services.communication.requests.post')
def test_send_communication_email_token_failure(mock_post):
    """Test that token refresh failures raise appropriate errors"""
    # Mock the access token request to fail
    mock_post.return_value.ok = False
    mock_post.return_value.text = "Token refresh failed"
    
    with pytest.raises(CommunicationConfigurationError) as excinfo:
        send_communication_email(
            recipient_email="benjaminlagrone@gmail.com",
            subject="Test Subject",
            content="Test content",
            task_id="test_task_123",
            task_type="gov_contract"
        )
    
    assert "Failed to refresh the Gmail access token" in str(excinfo.value)


@patch('app.services.communication.requests.post')
def test_send_communication_email_send_failure(mock_post):
    """Test that email send failures raise appropriate errors"""
    # Mock the access token request
    mock_post.return_value.ok = True
    mock_post.return_value.json.return_value = {"access_token": "test_access_token"}
    
    # Mock the email send request to fail
    mock_send_response = MagicMock()
    mock_send_response.ok = False
    mock_send_response.text = "Email send failed"
    mock_post.side_effect = [mock_post.return_value, mock_send_response]
    
    with pytest.raises(CommunicationDeliveryError) as excinfo:
        send_communication_email(
            recipient_email="benjaminlagrone@gmail.com",
            subject="Test Subject",
            content="Test content",
            task_id="test_task_123",
            task_type="gov_contract"
        )
    
    assert "Communication email send failed" in str(excinfo.value)


def test_handle_inbound_reply_unauthorized_sender():
    """Test that replies from unauthorized senders are rejected"""
    result = handle_inbound_reply(
        message_id="test_message_123",
        sender_email="unauthorized@example.com",
        subject="Test Reply",
        content="Test reply content"
    )
    
    assert result is False


def test_handle_inbound_reply_authorized_sender():
    """Test that replies from authorized senders are accepted"""
    result = handle_inbound_reply(
        message_id="test_message_123",
        sender_email="benjaminlagrone@gmail.com",
        subject="Test Reply",
        content="Test reply content"
    )
    
    assert result is True


def test_record_task_progress():
    """Test task progress recording"""
    record = record_task_progress(
        task_id="test_task_123",
        task_type="gov_contract",
        recipient="benjaminlagrone@gmail.com",
        subject="Test Subject",
        content="Test content",
        status="sent"
    )
    
    assert isinstance(record, TaskProgressRecord)
    assert record.task_id == "test_task_123"
    assert record.recipient == "benjaminlagrone@gmail.com"
    assert record.subject == "Test Subject"
    assert record.content == "Test content"
    assert record.status == "sent"


def test_record_task_progress_with_related_task():
    """Test task progress recording with related task"""
    record = record_task_progress(
        task_id="test_task_123",
        task_type="gov_contract",
        recipient="jie.huang@lecrowndevelopment.com",
        subject="Test Subject",
        content="Test content",
        status="sent",
        related_task_id="related_task_456"
    )
    
    assert isinstance(record, TaskProgressRecord)
    assert record.related_task_id == "related_task_456"

