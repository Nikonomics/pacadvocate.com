#!/usr/bin/env python3
"""
Bill Risk Service
Integration service for adding risk analysis to bill processing
"""

import logging
from typing import Dict, Optional
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from services.analysis.risk_analyzer import BillRiskAnalyzer
from sqlalchemy.orm import Session
from models.legislation import Bill

logger = logging.getLogger(__name__)

class BillRiskService:
    """Service for analyzing and updating bill risk scores"""

    def __init__(self, db_session: Session = None):
        self.db_session = db_session
        self.risk_analyzer = BillRiskAnalyzer()

    def analyze_and_update_bill_risk(self, bill: Bill) -> Dict:
        """
        Analyze bill risk and update the bill record

        Args:
            bill: Bill model instance

        Returns:
            Risk analysis results
        """
        try:
            # Perform risk analysis
            risk_result = self.risk_analyzer.analyze_bill_risk(
                title=bill.title or "",
                summary=bill.summary or "",
                full_text=bill.full_text or ""
            )

            # Update bill risk fields if database session available
            if self.db_session:
                bill.reimbursement_risk = risk_result['reimbursement_risk']
                bill.staffing_risk = risk_result['staffing_risk']
                bill.compliance_risk = risk_result['compliance_risk']
                bill.quality_risk = risk_result['quality_risk']
                bill.total_risk_score = risk_result['total_risk_score']
                bill.risk_tags = risk_result['risk_tags']

                self.db_session.commit()
                logger.info(f"Updated risk scores for bill {bill.bill_number}: {risk_result['total_risk_score']}/100")

            return risk_result

        except Exception as e:
            logger.error(f"Error analyzing bill risk for {bill.bill_number}: {e}")
            if self.db_session:
                self.db_session.rollback()
            raise

    def analyze_bill_data(self, bill_data: Dict) -> Dict:
        """
        Analyze risk for bill data dictionary (without database update)

        Args:
            bill_data: Dictionary with title, summary, full_text keys

        Returns:
            Risk analysis results
        """
        return self.risk_analyzer.analyze_bill_risk(
            title=bill_data.get('title', ''),
            summary=bill_data.get('summary', ''),
            full_text=bill_data.get('full_text', '')
        )

    def batch_analyze_bills(self, bills: list, update_database: bool = True) -> Dict:
        """
        Analyze risk for multiple bills

        Args:
            bills: List of Bill model instances or dictionaries
            update_database: Whether to update database records

        Returns:
            Batch analysis summary
        """
        results = {
            'total_analyzed': 0,
            'total_updated': 0,
            'high_risk_bills': 0,
            'moderate_risk_bills': 0,
            'low_risk_bills': 0,
            'errors': []
        }

        for bill in bills:
            try:
                if isinstance(bill, Bill):
                    # Bill model instance
                    if update_database and self.db_session:
                        risk_result = self.analyze_and_update_bill_risk(bill)
                        results['total_updated'] += 1
                    else:
                        risk_result = self.risk_analyzer.analyze_bill_risk(
                            title=bill.title or "",
                            summary=bill.summary or "",
                            full_text=bill.full_text or ""
                        )
                else:
                    # Dictionary
                    risk_result = self.analyze_bill_data(bill)

                results['total_analyzed'] += 1

                # Count risk levels
                risk_level = risk_result.get('risk_level', 'MINIMAL')
                if risk_level in ['CRITICAL', 'HIGH']:
                    results['high_risk_bills'] += 1
                elif risk_level == 'MODERATE':
                    results['moderate_risk_bills'] += 1
                else:
                    results['low_risk_bills'] += 1

            except Exception as e:
                bill_id = getattr(bill, 'bill_number', bill.get('bill_number', 'unknown'))
                error_msg = f"Error analyzing bill {bill_id}: {str(e)}"
                logger.error(error_msg)
                results['errors'].append(error_msg)

        logger.info(f"Batch analysis complete: {results['total_analyzed']} bills analyzed, "
                   f"{results['high_risk_bills']} high risk, {results['moderate_risk_bills']} moderate risk")

        return results

    def get_high_risk_bills(self, min_risk_score: int = 40) -> Optional[list]:
        """
        Get bills with risk scores above threshold

        Args:
            min_risk_score: Minimum total risk score

        Returns:
            List of high-risk bills or None if no database session
        """
        if not self.db_session:
            logger.warning("No database session available for querying bills")
            return None

        try:
            high_risk_bills = self.db_session.query(Bill).filter(
                Bill.total_risk_score >= min_risk_score,
                Bill.is_active == True
            ).order_by(Bill.total_risk_score.desc()).all()

            return high_risk_bills

        except Exception as e:
            logger.error(f"Error querying high-risk bills: {e}")
            return []

    def get_risk_summary_stats(self) -> Optional[Dict]:
        """
        Get summary statistics for risk scores across all bills

        Returns:
            Risk statistics or None if no database session
        """
        if not self.db_session:
            logger.warning("No database session available for stats")
            return None

        try:
            from sqlalchemy import func

            stats = self.db_session.query(
                func.count(Bill.id).label('total_bills'),
                func.avg(Bill.total_risk_score).label('avg_risk_score'),
                func.max(Bill.total_risk_score).label('max_risk_score'),
                func.count(Bill.id).filter(Bill.total_risk_score >= 70).label('critical_risk'),
                func.count(Bill.id).filter(Bill.total_risk_score >= 40).label('high_risk'),
                func.count(Bill.id).filter(Bill.total_risk_score >= 20).label('moderate_risk'),
                func.count(Bill.id).filter(Bill.total_risk_score > 0).label('some_risk'),
            ).filter(Bill.is_active == True).first()

            return {
                'total_bills': stats.total_bills or 0,
                'average_risk_score': round(stats.avg_risk_score or 0, 2),
                'maximum_risk_score': stats.max_risk_score or 0,
                'critical_risk_bills': stats.critical_risk or 0,
                'high_risk_bills': stats.high_risk or 0,
                'moderate_risk_bills': stats.moderate_risk or 0,
                'bills_with_risk': stats.some_risk or 0
            }

        except Exception as e:
            logger.error(f"Error getting risk statistics: {e}")
            return {}

# Convenience functions for easy import
def analyze_bill_risk_quick(title: str, summary: str = "", full_text: str = "") -> Dict:
    """Quick risk analysis without database integration"""
    analyzer = BillRiskAnalyzer()
    return analyzer.analyze_bill_risk(title, summary, full_text)

def create_risk_service(db_session: Session = None) -> BillRiskService:
    """Create a risk service instance"""
    return BillRiskService(db_session)


if __name__ == "__main__":
    # Test the service
    print("🧪 Testing Bill Risk Service")
    print("=" * 40)

    # Test without database
    service = BillRiskService()

    # Test bill data
    test_bill = {
        'title': 'SNF Payment Reform and Minimum Staffing Act',
        'summary': 'Reduces Medicare Part A payment rates by 15% and requires minimum nurse-to-patient ratios',
        'full_text': 'This Act shall reduce Medicare reimbursement for skilled nursing facilities by 15% starting January 2025. Additionally, all SNFs must maintain a minimum staffing ratio of 1 RN per 15 patients during all shifts. Facilities must submit monthly quality measure reports and implement new documentation requirements for QAPI programs.'
    }

    result = service.analyze_bill_data(test_bill)

    print(f"📋 Test Bill Analysis:")
    print(f"   Risk Level: {result['risk_level']}")
    print(f"   Total Score: {result['total_risk_score']}/100")
    print(f"   Individual Scores:")
    print(f"     Reimbursement: {result['reimbursement_risk']}/40")
    print(f"     Staffing: {result['staffing_risk']}/30")
    print(f"     Compliance: {result['compliance_risk']}/20")
    print(f"     Quality: {result['quality_risk']}/10")

    import json
    risk_tags = json.loads(result['risk_tags'])
    print(f"   Risk Tags: {', '.join(risk_tags)}")

    print(f"\n✅ Risk service test completed!")