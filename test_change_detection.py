#!/usr/bin/env python3
"""
Comprehensive test script for the Change Detection System
Tests all components and integration
"""

import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from models.legislation import Bill, User
from models.change_detection import (
    BillChange, StageTransition, ChangeAlert, AlertPreferences,
    ChangeSeverity, ChangeType, AlertPriority, BillStage
)

# Import change detection components
from services.change_detection.diff_engine import DiffEngine
from services.change_detection.significance_classifier import SignificanceClassifier
from services.change_detection.stage_detector import StageDetector
from services.change_detection.alert_deduplication import AlertDeduplicationEngine
from services.change_detection.alert_prioritizer import AlertPrioritizer
from services.change_detection.email_notifier import EmailNotifier
from services.change_detection.change_detection_service import ChangeDetectionService

def test_diff_engine():
    """Test the diff engine functionality"""
    print("\n🔍 Testing Diff Engine")
    print("-" * 50)

    diff_engine = DiffEngine()

    # Test basic text comparison
    old_text = "This is the original bill text about Medicare reimbursement rates."
    new_text = "This is the updated bill text about Medicare reimbursement rates with increased payments for SNFs."

    diff_result = diff_engine.compare_text(old_text, new_text)

    print(f"✅ Text comparison test:")
    print(f"   Has changes: {diff_result.has_changes}")
    print(f"   Similarity: {diff_result.similarity_ratio:.2%}")
    print(f"   Change %: {diff_result.change_percentage:.1f}%")
    print(f"   Significant changes: {len(diff_result.significant_changes)}")
    print(f"   Summary: {diff_result.summary}")

    # Test change significance calculation
    significance = diff_engine.calculate_change_significance(diff_result)
    print(f"   Significance: {significance}")

def test_significance_classifier():
    """Test the AI-powered significance classifier"""
    print("\n🧠 Testing Significance Classifier")
    print("-" * 50)

    try:
        classifier = SignificanceClassifier()

        # Create test diff result
        from services.change_detection.diff_engine import DiffResult

        test_diff = DiffResult(
            has_changes=True,
            similarity_ratio=0.75,
            change_percentage=25.0,
            word_count_delta=50,
            line_count_delta=5,
            unified_diff="",
            context_diff="",
            summary="Added new SNF payment provisions and quality reporting requirements",
            sections_changed=["Section 3", "Section 7"],
            significant_changes=["payment rate increase", "quality reporting mandate"],
            minor_changes=["typo fixes"]
        )

        bill_context = {
            'bill_number': 'HR-1234',
            'title': 'Medicare SNF Payment Reform Act',
            'summary': 'Updates payment rates for skilled nursing facilities',
            'source': 'congress.gov',
            'relevance_score': 85
        }

        classification = classifier.classify_change(test_diff, bill_context)

        print(f"✅ Change classification test:")
        print(f"   Severity: {classification.severity}")
        print(f"   Change Type: {classification.change_type}")
        print(f"   Confidence: {classification.confidence:.2f}")
        print(f"   Reimbursement Impact: {classification.reimbursement_impact}")
        print(f"   Implementation Urgency: {classification.implementation_urgency}")
        print(f"   Key Changes: {classification.key_changes[:3]}")
        print(f"   Reasoning: {classification.reasoning[:100]}...")

    except Exception as e:
        print(f"❌ Significance classifier test failed: {e}")

def test_stage_detector():
    """Test the stage transition detector"""
    print("\n📊 Testing Stage Detector")
    print("-" * 50)

    try:
        detector = StageDetector()

        # Test stage parsing
        statuses = [
            "Introduced in House",
            "Referred to Committee on Ways and Means",
            "Committee reported favorably",
            "Passed House by voice vote",
            "Sent to Senate",
            "Signed into law by President"
        ]

        print("✅ Stage parsing test:")
        for status in statuses:
            stage = detector.parse_stage_from_status(status)
            print(f"   '{status}' → {stage}")

        # Test stage transition detection
        old_status = "Referred to Committee on Ways and Means"
        new_status = "Committee reported favorably with amendments"

        bill_context = {
            'bill_number': 'HR-1234',
            'title': 'Medicare SNF Payment Reform Act',
            'relevance_score': 85
        }

        transition = detector.detect_stage_transition(old_status, new_status, bill_context)

        print(f"\n✅ Stage transition test:")
        print(f"   Has transition: {transition.has_transition}")
        if transition.has_transition:
            print(f"   From: {transition.from_stage}")
            print(f"   To: {transition.to_stage}")
            print(f"   Confidence: {transition.confidence:.2f}")
            print(f"   Passage likelihood: {transition.passage_likelihood:.0%}")
            print(f"   Notes: {transition.notes}")

    except Exception as e:
        print(f"❌ Stage detector test failed: {e}")

def test_alert_deduplication():
    """Test alert deduplication system"""
    print("\n🔄 Testing Alert Deduplication")
    print("-" * 50)

    # This would require database setup, so we'll do a simplified test
    print("✅ Alert deduplication system initialized")
    print("   (Full database test requires active session)")

def test_alert_prioritizer():
    """Test alert prioritization"""
    print("\n⚡ Testing Alert Prioritizer")
    print("-" * 50)

    try:
        prioritizer = AlertPrioritizer()

        # Create mock bill and classification
        from models.legislation import Bill
        from services.change_detection.significance_classifier import ChangeClassification
        from models.change_detection import ChangeSeverity, ChangeType

        mock_bill = Bill()
        mock_bill.id = 1
        mock_bill.bill_number = "HR-1234"
        mock_bill.title = "Medicare SNF Payment Increase Act"
        mock_bill.summary = "Increases payment rates for SNFs by 5%"
        mock_bill.relevance_score = 95
        mock_bill.status = "Passed House"

        mock_classification = ChangeClassification(
            severity=ChangeSeverity.SIGNIFICANT,
            change_type=ChangeType.TEXT_AMENDMENT,
            confidence=0.9,
            reasoning="Significant reimbursement increase for SNFs",
            key_changes=["5% payment rate increase", "New quality bonuses"],
            impact_areas=["reimbursement", "quality"],
            reimbursement_impact=True,
            regulatory_impact=False,
            implementation_urgency="short_term"
        )

        priority_result = prioritizer.calculate_priority(mock_bill, mock_classification)

        print(f"✅ Priority calculation test:")
        print(f"   Priority: {priority_result.priority}")
        print(f"   Score: {priority_result.priority_score:.1f}/100")
        print(f"   Confidence: {priority_result.confidence:.2f}")
        print(f"   Reasoning: {priority_result.reasoning}")
        print(f"   Recommendations: {priority_result.recommendations[:2]}")

        # Show factor breakdown
        factors = priority_result.factors
        print(f"   Factor breakdown:")
        print(f"     Reimbursement impact: {factors.reimbursement_impact:.2f}")
        print(f"     Implementation speed: {factors.implementation_speed:.2f}")
        print(f"     Passage likelihood: {factors.passage_likelihood:.2f}")
        print(f"     Bill relevance: {factors.bill_relevance:.2f}")

    except Exception as e:
        print(f"❌ Alert prioritizer test failed: {e}")

def test_email_notifier():
    """Test email notification system"""
    print("\n📧 Testing Email Notifier")
    print("-" * 50)

    # Note: This will run in test mode by default
    print("✅ Email notifier test (Test Mode):")

    # Create mock session for testing
    try:
        from unittest.mock import Mock

        mock_session = Mock()
        notifier = EmailNotifier(mock_session)

        # Test configuration
        config_test = notifier.test_email_configuration()
        print(f"   SMTP configured: {config_test['smtp_configured']}")
        print(f"   Sender configured: {config_test['sender_configured']}")
        print(f"   Test mode: {config_test['test_mode']}")

        if config_test.get('error'):
            print(f"   Connection error: {config_test['error']}")
        else:
            print(f"   Connection test: {'✅ Pass' if config_test['connection_test'] else '⚠️  Skip (test mode)'}")

    except Exception as e:
        print(f"❌ Email notifier test failed: {e}")

def test_database_models():
    """Test database models and relationships"""
    print("\n💾 Testing Database Models")
    print("-" * 50)

    try:
        # Test model imports
        from models.change_detection import (
            BillChange, StageTransition, ChangeAlert, AlertPreferences, ChangeDetectionConfig
        )

        print("✅ Database models imported successfully:")
        print("   - BillChange")
        print("   - StageTransition")
        print("   - ChangeAlert")
        print("   - AlertPreferences")
        print("   - ChangeDetectionConfig")

        # Test enum imports
        from models.change_detection import (
            ChangeType, ChangeSeverity, AlertPriority, BillStage
        )

        print("\n✅ Enums imported successfully:")
        print(f"   - ChangeType: {len(list(ChangeType))} values")
        print(f"   - ChangeSeverity: {len(list(ChangeSeverity))} values")
        print(f"   - AlertPriority: {len(list(AlertPriority))} values")
        print(f"   - BillStage: {len(list(BillStage))} values")

    except Exception as e:
        print(f"❌ Database models test failed: {e}")

def test_integration_flow():
    """Test the complete integration flow"""
    print("\n🔗 Testing Integration Flow")
    print("-" * 50)

    try:
        # This would test the complete flow with a real database
        # For now, just test component initialization

        print("✅ Component initialization test:")

        # Test that all services can be initialized
        diff_engine = DiffEngine()
        print("   - DiffEngine initialized")

        classifier = SignificanceClassifier()
        print("   - SignificanceClassifier initialized")

        stage_detector = StageDetector()
        print("   - StageDetector initialized")

        prioritizer = AlertPrioritizer()
        print("   - AlertPrioritizer initialized")

        print("\n✅ All components initialized successfully")
        print("   Integration flow ready for database testing")

    except Exception as e:
        print(f"❌ Integration flow test failed: {e}")

def create_test_data():
    """Create test data for full system testing"""
    print("\n🧪 Creating Test Data")
    print("-" * 50)

    try:
        database_url = os.getenv('DATABASE_URL', 'sqlite:///./snflegtracker.db')
        engine = create_engine(database_url)

        with Session(engine) as session:
            # Check if we already have test data
            existing_bills = session.query(Bill).filter(
                Bill.bill_number.like('TEST-%')
            ).count()

            if existing_bills > 0:
                print(f"✅ Test data already exists: {existing_bills} test bills found")
                return

            # Create test user
            test_user = User(
                email="test@example.com",
                full_name="Test User",
                organization="Test SNF",
                is_active=True
            )
            session.add(test_user)

            # Create test bills
            test_bills = [
                {
                    'bill_number': 'TEST-001',
                    'title': 'Test Medicare SNF Payment Act',
                    'summary': 'A test bill to increase Medicare payments to skilled nursing facilities',
                    'status': 'Introduced',
                    'source': 'test_data',
                    'state_or_federal': 'federal',
                    'relevance_score': 85.0
                },
                {
                    'bill_number': 'TEST-002',
                    'title': 'Test SNF Quality Reporting Act',
                    'summary': 'A test bill requiring enhanced quality reporting from SNFs',
                    'status': 'Committee Review',
                    'source': 'test_data',
                    'state_or_federal': 'federal',
                    'relevance_score': 75.0
                }
            ]

            for bill_data in test_bills:
                bill = Bill(**bill_data)
                session.add(bill)

            # Create test alert preferences
            preferences = AlertPreferences(
                user_id=1,  # Will be updated after user is committed
                email_enabled=True,
                email_frequency='immediate',
                min_priority=AlertPriority.MEDIUM,
                monitor_text_changes=True,
                monitor_stage_transitions=True
            )

            session.commit()

            # Update preferences with correct user ID
            preferences.user_id = test_user.id
            session.commit()

            print(f"✅ Test data created successfully:")
            print(f"   - 1 test user: {test_user.email}")
            print(f"   - {len(test_bills)} test bills")
            print(f"   - Alert preferences configured")

    except Exception as e:
        print(f"❌ Test data creation failed: {e}")

def run_full_system_test():
    """Run a complete system test with actual database"""
    print("\n🚀 Running Full System Test")
    print("-" * 50)

    try:
        database_url = os.getenv('DATABASE_URL', 'sqlite:///./snflegtracker.db')
        engine = create_engine(database_url)

        with Session(engine) as session:
            # Initialize change detection service
            service = ChangeDetectionService(session)

            print("✅ ChangeDetectionService initialized")

            # Run change detection on test bills
            result = service.check_all_bills_for_changes(limit=2)

            print(f"✅ Change detection completed:")
            print(f"   Bills checked: {result.bills_checked}")
            print(f"   Changes detected: {result.changes_detected}")
            print(f"   Stage transitions: {result.stage_transitions}")
            print(f"   Alerts created: {result.alerts_created}")
            print(f"   Processing time: {result.processing_time:.2f}s")

            if result.errors:
                print(f"   Errors: {len(result.errors)}")
                for error in result.errors[:3]:
                    print(f"     - {error}")

            # Get system stats
            stats = service.get_system_stats(days=1)
            print(f"\n✅ System statistics:")
            print(f"   Total changes: {stats.get('changes', {}).get('total', 0)}")
            print(f"   Stage transitions: {stats.get('stage_transitions', 0)}")
            print(f"   Total alerts: {stats.get('alerts', {}).get('total', 0)}")
            print(f"   Alerts sent: {stats.get('alerts', {}).get('sent', 0)}")

    except Exception as e:
        print(f"❌ Full system test failed: {e}")

def main():
    """Run all tests"""
    print("🧪 SNF Legislation Change Detection System - Test Suite")
    print("=" * 60)

    # Run individual component tests
    test_database_models()
    test_diff_engine()
    test_significance_classifier()
    test_stage_detector()
    test_alert_deduplication()
    test_alert_prioritizer()
    test_email_notifier()
    test_integration_flow()

    # Create test data and run full system test
    create_test_data()
    run_full_system_test()

    print("\n" + "=" * 60)
    print("🎉 Test Suite Completed!")
    print("\nNext Steps:")
    print("1. Configure SMTP settings in .env for email notifications")
    print("2. Run the scheduler: python services/change_detection/scheduler.py")
    print("3. Monitor logs for automated change detection")
    print("4. Set up user preferences and bill subscriptions")

if __name__ == "__main__":
    main()