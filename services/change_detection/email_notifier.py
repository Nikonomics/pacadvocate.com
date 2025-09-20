import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from jinja2 import Environment, DictLoader
import json
import os
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from models.change_detection import ChangeAlert, AlertPriority, AlertPreferences
from models.legislation import Bill, User

load_dotenv()
logger = logging.getLogger(__name__)

@dataclass
class EmailContent:
    """Email content structure"""
    subject: str
    html_body: str
    text_body: str
    priority: str  # 'high', 'normal', 'low'

@dataclass
class NotificationResult:
    """Result of email notification attempt"""
    success: bool
    message: str
    email_sent: bool
    recipient_count: int
    errors: List[str]

class EmailNotifier:
    """Email notification system for bill change alerts"""

    def __init__(self, session: Session):
        self.session = session

        # Email configuration from environment
        self.smtp_server = os.getenv('SMTP_SERVER', 'localhost')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_username = os.getenv('SMTP_USERNAME', '')
        self.smtp_password = os.getenv('SMTP_PASSWORD', '')
        self.sender_email = os.getenv('SENDER_EMAIL', 'alerts@snflegtracker.com')
        self.sender_name = os.getenv('SENDER_NAME', 'SNF Leg Tracker')
        self.use_tls = os.getenv('SMTP_USE_TLS', 'true').lower() == 'true'

        # Testing mode (prints instead of sending)
        self.test_mode = os.getenv('EMAIL_TEST_MODE', 'true').lower() == 'true'

        # Template system
        self.template_env = Environment(loader=DictLoader(self._get_email_templates()))

        logger.info(f"Email notifier initialized - Test mode: {self.test_mode}")

    def send_single_alert(self, alert: ChangeAlert, user: User, bill: Bill) -> NotificationResult:
        """Send notification for a single alert"""

        try:
            # Check if user wants email notifications
            if not self._should_send_email(user, alert):
                return NotificationResult(
                    success=True,
                    message="Email notification skipped per user preferences",
                    email_sent=False,
                    recipient_count=0,
                    errors=[]
                )

            # Generate email content
            email_content = self._generate_single_alert_email(alert, user, bill)

            # Send email
            result = self._send_email(
                user.email,
                email_content.subject,
                email_content.html_body,
                email_content.text_body,
                email_content.priority
            )

            if result:
                # Mark alert as sent
                alert.is_sent = True
                alert.sent_at = datetime.utcnow()
                self.session.commit()

                return NotificationResult(
                    success=True,
                    message="Email sent successfully",
                    email_sent=True,
                    recipient_count=1,
                    errors=[]
                )
            else:
                return NotificationResult(
                    success=False,
                    message="Failed to send email",
                    email_sent=False,
                    recipient_count=0,
                    errors=["SMTP send failed"]
                )

        except Exception as e:
            logger.error(f"Error sending single alert email: {e}")
            return NotificationResult(
                success=False,
                message=f"Error: {str(e)}",
                email_sent=False,
                recipient_count=0,
                errors=[str(e)]
            )

    def send_digest_email(self, user: User, alerts: List[Tuple[ChangeAlert, Bill]],
                         period_days: int = 1) -> NotificationResult:
        """Send digest email with multiple alerts"""

        try:
            if not alerts:
                return NotificationResult(
                    success=True,
                    message="No alerts to send",
                    email_sent=False,
                    recipient_count=0,
                    errors=[]
                )

            # Check user preferences
            if not self._should_send_digest(user, len(alerts)):
                return NotificationResult(
                    success=True,
                    message="Digest email skipped per user preferences",
                    email_sent=False,
                    recipient_count=0,
                    errors=[]
                )

            # Generate digest email content
            email_content = self._generate_digest_email(user, alerts, period_days)

            # Send email
            result = self._send_email(
                user.email,
                email_content.subject,
                email_content.html_body,
                email_content.text_body,
                email_content.priority
            )

            if result:
                # Mark alerts as sent
                for alert, _ in alerts:
                    alert.is_sent = True
                    alert.sent_at = datetime.utcnow()
                self.session.commit()

                return NotificationResult(
                    success=True,
                    message=f"Digest email sent with {len(alerts)} alerts",
                    email_sent=True,
                    recipient_count=1,
                    errors=[]
                )
            else:
                return NotificationResult(
                    success=False,
                    message="Failed to send digest email",
                    email_sent=False,
                    recipient_count=0,
                    errors=["SMTP send failed"]
                )

        except Exception as e:
            logger.error(f"Error sending digest email: {e}")
            return NotificationResult(
                success=False,
                message=f"Error: {str(e)}",
                email_sent=False,
                recipient_count=0,
                errors=[str(e)]
            )

    def send_weekly_summary(self, user: User, summary_data: Dict) -> NotificationResult:
        """Send weekly summary of bill activity"""

        try:
            # Generate summary email
            email_content = self._generate_weekly_summary_email(user, summary_data)

            # Send email
            result = self._send_email(
                user.email,
                email_content.subject,
                email_content.html_body,
                email_content.text_body,
                'normal'
            )

            if result:
                return NotificationResult(
                    success=True,
                    message="Weekly summary sent successfully",
                    email_sent=True,
                    recipient_count=1,
                    errors=[]
                )
            else:
                return NotificationResult(
                    success=False,
                    message="Failed to send weekly summary",
                    email_sent=False,
                    recipient_count=0,
                    errors=["SMTP send failed"]
                )

        except Exception as e:
            logger.error(f"Error sending weekly summary: {e}")
            return NotificationResult(
                success=False,
                message=f"Error: {str(e)}",
                email_sent=False,
                recipient_count=0,
                errors=[str(e)]
            )

    def _should_send_email(self, user: User, alert: ChangeAlert) -> bool:
        """Check if email should be sent based on user preferences"""

        # Get user preferences
        preferences = self.session.query(AlertPreferences).filter(
            AlertPreferences.user_id == user.id
        ).first()

        if not preferences:
            return True  # Default to sending if no preferences set

        # Check if email notifications are enabled
        if not preferences.email_enabled:
            return False

        # Check minimum priority
        priority_order = [AlertPriority.LOW, AlertPriority.MEDIUM, AlertPriority.HIGH, AlertPriority.URGENT]
        if priority_order.index(alert.priority) < priority_order.index(preferences.min_priority):
            return False

        # Check quiet hours
        if preferences.quiet_hours_start and preferences.quiet_hours_end:
            now = datetime.utcnow()
            current_time = now.strftime("%H:%M")

            if (preferences.quiet_hours_start <= current_time <= preferences.quiet_hours_end):
                # Don't send during quiet hours unless urgent
                if alert.priority != AlertPriority.URGENT:
                    return False

        return True

    def _should_send_digest(self, user: User, alert_count: int) -> bool:
        """Check if digest email should be sent"""

        preferences = self.session.query(AlertPreferences).filter(
            AlertPreferences.user_id == user.id
        ).first()

        if not preferences or not preferences.email_enabled:
            return False

        # Check frequency preference
        if preferences.email_frequency == 'immediate':
            return False  # Individual alerts should be sent instead

        # Always send if there are alerts for weekly/daily digests
        return alert_count > 0

    def _send_email(self, recipient: str, subject: str, html_body: str,
                   text_body: str, priority: str = 'normal') -> bool:
        """Send email via SMTP"""

        if self.test_mode:
            # Test mode - just print the email
            print(f"\n{'='*60}")
            print(f"TEST MODE EMAIL")
            print(f"{'='*60}")
            print(f"To: {recipient}")
            print(f"Subject: {subject}")
            print(f"Priority: {priority}")
            print(f"\nText Body:\n{text_body}")
            print(f"\nHTML Body:\n{html_body[:300]}...")
            print(f"{'='*60}\n")
            return True

        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.sender_name} <{self.sender_email}>"
            msg['To'] = recipient

            # Set priority header
            if priority == 'high':
                msg['X-Priority'] = '1'
                msg['X-MSMail-Priority'] = 'High'
            elif priority == 'low':
                msg['X-Priority'] = '5'
                msg['X-MSMail-Priority'] = 'Low'

            # Add text and HTML parts
            text_part = MIMEText(text_body, 'plain')
            html_part = MIMEText(html_body, 'html')

            msg.attach(text_part)
            msg.attach(html_part)

            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()

                if self.smtp_username and self.smtp_password:
                    server.login(self.smtp_username, self.smtp_password)

                server.send_message(msg)

            logger.info(f"Email sent successfully to {recipient}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {recipient}: {e}")
            return False

    def _generate_single_alert_email(self, alert: ChangeAlert, user: User, bill: Bill) -> EmailContent:
        """Generate email content for a single alert"""

        template = self.template_env.get_template('single_alert')

        # Priority styling
        priority_colors = {
            AlertPriority.URGENT: '#dc3545',    # Red
            AlertPriority.HIGH: '#fd7e14',      # Orange
            AlertPriority.MEDIUM: '#ffc107',    # Yellow
            AlertPriority.LOW: '#6c757d'        # Gray
        }

        priority_labels = {
            AlertPriority.URGENT: '🚨 URGENT',
            AlertPriority.HIGH: '⚠️ HIGH',
            AlertPriority.MEDIUM: '📋 MEDIUM',
            AlertPriority.LOW: '📝 LOW'
        }

        context = {
            'user_name': user.full_name or 'User',
            'alert': alert,
            'bill': bill,
            'priority_color': priority_colors.get(alert.priority, '#6c757d'),
            'priority_label': priority_labels.get(alert.priority, 'MEDIUM'),
            'bill_url': f"#{bill.id}",  # Placeholder URL
            'unsubscribe_url': f"#unsubscribe/{user.id}",  # Placeholder URL
        }

        html_body = template.render(**context)
        text_body = self._html_to_text(html_body)

        # Generate subject
        subject = f"{priority_labels.get(alert.priority, 'ALERT')}: {alert.title}"

        # Determine email priority
        email_priority = 'high' if alert.priority in [AlertPriority.URGENT, AlertPriority.HIGH] else 'normal'

        return EmailContent(
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            priority=email_priority
        )

    def _generate_digest_email(self, user: User, alerts: List[Tuple[ChangeAlert, Bill]],
                             period_days: int) -> EmailContent:
        """Generate digest email content"""

        template = self.template_env.get_template('digest')

        # Group alerts by priority
        alerts_by_priority = {
            AlertPriority.URGENT: [],
            AlertPriority.HIGH: [],
            AlertPriority.MEDIUM: [],
            AlertPriority.LOW: []
        }

        for alert, bill in alerts:
            alerts_by_priority[alert.priority].append((alert, bill))

        # Calculate summary stats
        total_alerts = len(alerts)
        unique_bills = len(set(bill.id for _, bill in alerts))
        high_priority_count = len(alerts_by_priority[AlertPriority.URGENT]) + len(alerts_by_priority[AlertPriority.HIGH])

        context = {
            'user_name': user.full_name or 'User',
            'period_days': period_days,
            'period_text': 'day' if period_days == 1 else f'{period_days} days',
            'total_alerts': total_alerts,
            'unique_bills': unique_bills,
            'high_priority_count': high_priority_count,
            'alerts_by_priority': alerts_by_priority,
            'dashboard_url': "#dashboard",  # Placeholder URL
            'unsubscribe_url': f"#unsubscribe/{user.id}",  # Placeholder URL
        }

        html_body = template.render(**context)
        text_body = self._html_to_text(html_body)

        subject = f"SNF Legislation Digest: {total_alerts} alerts ({period_days} day{'s' if period_days > 1 else ''})"

        return EmailContent(
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            priority='normal'
        )

    def _generate_weekly_summary_email(self, user: User, summary_data: Dict) -> EmailContent:
        """Generate weekly summary email content"""

        template = self.template_env.get_template('weekly_summary')

        context = {
            'user_name': user.full_name or 'User',
            'summary_data': summary_data,
            'dashboard_url': "#dashboard",
            'unsubscribe_url': f"#unsubscribe/{user.id}",
        }

        html_body = template.render(**context)
        text_body = self._html_to_text(html_body)

        subject = "SNF Legislation Weekly Summary"

        return EmailContent(
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            priority='normal'
        )

    def _html_to_text(self, html_content: str) -> str:
        """Convert HTML email to plain text"""
        # Simple HTML to text conversion
        import re

        # Remove HTML tags
        text = re.sub('<[^<]+?>', '', html_content)

        # Clean up whitespace
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r' +', ' ', text)

        return text.strip()

    def _get_email_templates(self) -> Dict[str, str]:
        """Return email templates"""

        return {
            'single_alert': '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; }
        .header { background-color: #f8f9fa; padding: 20px; }
        .priority-badge {
            background-color: {{ priority_color }};
            color: white;
            padding: 5px 10px;
            border-radius: 3px;
            font-weight: bold;
        }
        .alert-content { padding: 20px; }
        .bill-details { background-color: #f8f9fa; padding: 15px; margin: 15px 0; }
        .footer { font-size: 12px; color: #6c757d; padding: 20px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>SNF Legislation Alert</h1>
        <span class="priority-badge">{{ priority_label }}</span>
    </div>

    <div class="alert-content">
        <h2>{{ alert.title }}</h2>
        <p>{{ alert.message }}</p>

        <div class="bill-details">
            <h3>Bill Details:</h3>
            <p><strong>{{ bill.bill_number }}</strong> - {{ bill.title }}</p>
            <p><strong>Status:</strong> {{ bill.status }}</p>
            {% if bill.sponsor %}<p><strong>Sponsor:</strong> {{ bill.sponsor }}</p>{% endif %}
            {% if bill.relevance_score %}<p><strong>Relevance Score:</strong> {{ bill.relevance_score }}/100</p>{% endif %}
        </div>

        <p><a href="{{ bill_url }}">View Full Bill Details</a></p>
    </div>

    <div class="footer">
        <p>You received this alert because you subscribed to SNF legislation updates.</p>
        <p><a href="{{ unsubscribe_url }}">Unsubscribe</a> | Manage Preferences</p>
    </div>
</body>
</html>
            ''',

            'digest': '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; }
        .header { background-color: #f8f9fa; padding: 20px; }
        .summary-stats { display: flex; justify-content: space-around; margin: 20px 0; }
        .stat-box { text-align: center; padding: 15px; background-color: #e9ecef; border-radius: 5px; }
        .alert-section { margin: 20px 0; }
        .alert-item { border-left: 4px solid #007bff; padding: 10px; margin: 10px 0; background-color: #f8f9fa; }
        .priority-urgent { border-left-color: #dc3545; }
        .priority-high { border-left-color: #fd7e14; }
        .priority-medium { border-left-color: #ffc107; }
        .priority-low { border-left-color: #6c757d; }
        .footer { font-size: 12px; color: #6c757d; padding: 20px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>SNF Legislation Digest</h1>
        <p>Your {{ period_text }} summary of legislative activity</p>
    </div>

    <div class="summary-stats">
        <div class="stat-box">
            <h3>{{ total_alerts }}</h3>
            <p>Total Alerts</p>
        </div>
        <div class="stat-box">
            <h3>{{ unique_bills }}</h3>
            <p>Bills Updated</p>
        </div>
        <div class="stat-box">
            <h3>{{ high_priority_count }}</h3>
            <p>High Priority</p>
        </div>
    </div>

    {% for priority, priority_alerts in alerts_by_priority.items() if priority_alerts %}
    <div class="alert-section">
        <h2>{{ priority.value|title }} Priority ({{ priority_alerts|length }})</h2>
        {% for alert, bill in priority_alerts %}
        <div class="alert-item priority-{{ priority.value }}">
            <h4>{{ alert.title }}</h4>
            <p>{{ bill.bill_number }}: {{ bill.title[:100] }}{% if bill.title|length > 100 %}...{% endif %}</p>
            <small>{{ alert.created_at.strftime('%m/%d/%Y %H:%M') }}</small>
        </div>
        {% endfor %}
    </div>
    {% endfor %}

    <div style="text-align: center; margin: 30px;">
        <a href="{{ dashboard_url }}" style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">View Dashboard</a>
    </div>

    <div class="footer">
        <p>SNF Legislation Tracker - Keeping you informed on skilled nursing facility legislation.</p>
        <p><a href="{{ unsubscribe_url }}">Unsubscribe</a> | Manage Preferences</p>
    </div>
</body>
</html>
            ''',

            'weekly_summary': '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; }
        .header { background-color: #f8f9fa; padding: 20px; }
        .summary-section { margin: 20px 0; padding: 15px; background-color: #f8f9fa; }
        .metric { display: inline-block; margin: 10px; padding: 10px; background-color: white; border-radius: 5px; }
        .footer { font-size: 12px; color: #6c757d; padding: 20px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Weekly Summary</h1>
        <p>SNF Legislation Activity Overview</p>
    </div>

    <div class="summary-section">
        <h2>This Week's Activity</h2>

        <div class="metric">
            <strong>{{ summary_data.new_bills or 0 }}</strong><br>
            New Bills
        </div>

        <div class="metric">
            <strong>{{ summary_data.status_changes or 0 }}</strong><br>
            Status Changes
        </div>

        <div class="metric">
            <strong>{{ summary_data.high_relevance_updates or 0 }}</strong><br>
            High Relevance Updates
        </div>

        {% if summary_data.top_bills %}
        <h3>Top Bills This Week:</h3>
        <ul>
        {% for bill in summary_data.top_bills %}
            <li>{{ bill.bill_number }}: {{ bill.title[:80] }}{% if bill.title|length > 80 %}...{% endif %}</li>
        {% endfor %}
        </ul>
        {% endif %}
    </div>

    <div style="text-align: center; margin: 30px;">
        <a href="{{ dashboard_url }}" style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">View Full Dashboard</a>
    </div>

    <div class="footer">
        <p>SNF Legislation Tracker Weekly Summary</p>
        <p><a href="{{ unsubscribe_url }}">Unsubscribe</a> | Manage Preferences</p>
    </div>
</body>
</html>
            '''
        }

    def test_email_configuration(self) -> Dict[str, any]:
        """Test email configuration"""

        test_result = {
            'smtp_configured': bool(self.smtp_server and self.smtp_port),
            'credentials_configured': bool(self.smtp_username and self.smtp_password),
            'sender_configured': bool(self.sender_email),
            'test_mode': self.test_mode,
            'connection_test': False,
            'error': None
        }

        if not self.test_mode:
            try:
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    if self.use_tls:
                        server.starttls()
                    if self.smtp_username and self.smtp_password:
                        server.login(self.smtp_username, self.smtp_password)
                    test_result['connection_test'] = True
            except Exception as e:
                test_result['error'] = str(e)

        return test_result

    def get_notification_stats(self, days: int = 7) -> Dict[str, any]:
        """Get email notification statistics"""

        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)

            total_alerts = self.session.query(ChangeAlert).filter(
                ChangeAlert.created_at >= cutoff_date
            ).count()

            sent_alerts = self.session.query(ChangeAlert).filter(
                ChangeAlert.created_at >= cutoff_date,
                ChangeAlert.is_sent == True
            ).count()

            by_priority = {}
            for priority in AlertPriority:
                count = self.session.query(ChangeAlert).filter(
                    ChangeAlert.created_at >= cutoff_date,
                    ChangeAlert.priority == priority,
                    ChangeAlert.is_sent == True
                ).count()
                by_priority[priority.value] = count

            return {
                'period_days': days,
                'total_alerts_created': total_alerts,
                'emails_sent': sent_alerts,
                'delivery_rate_percent': round((sent_alerts / total_alerts * 100) if total_alerts > 0 else 0, 1),
                'by_priority': by_priority,
                'test_mode': self.test_mode
            }

        except Exception as e:
            logger.error(f"Error getting notification stats: {e}")
            return {'error': str(e)}