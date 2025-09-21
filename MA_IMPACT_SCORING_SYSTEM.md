# Medicare Advantage Impact Scoring System

**Version**: 2.0
**Implementation Date**: September 20, 2025
**Purpose**: Enhanced detection and scoring of Medicare Advantage legislation impact on SNF operations

---

## Overview

The Enhanced SNF Relevance Classifier now includes specialized detection for Medicare Advantage (MA) legislation that affects skilled nursing facilities. This addresses the critical gap where MA bills with significant SNF impact were previously underscored or missed entirely.

### Why This Matters
- **30-40% of SNF revenue** comes from Medicare Advantage plans
- MA policy changes directly affect SNF operations, cash flow, and patient admissions
- Previous system missed indirect but high-impact MA legislation

---

## MA Impact Categories & Scoring

### 1. **Payment/Reimbursement Changes**
**Score Range**: 80-100 relevance
**Priority**: Critical

**Detection Keywords:**
- prompt payment, payment timeline, payment delay
- provider payment, reimbursement schedule
- claims payment, payment processing

**SNF Impact**:
- Payment delays create severe cash flow problems
- SNFs often wait 30-60+ days for MA payments
- Forces expensive bridge financing and credit facilities

**Example**: S-119-2879 (MA Prompt Payment) - **85/100 relevance**

---

### 2. **Prior Authorization Changes**
**Score Range**: 70-90 relevance
**Priority**: High

**Detection Keywords:**
- prior authorization, preauthorization
- utilization review, medical necessity
- coverage determination

**SNF Impact**:
- Affects SNF admission patterns and length of stay
- Changes to PA requirements impact referral flow
- Administrative burden on SNF staff

---

### 3. **Network Adequacy Requirements**
**Score Range**: 60-80 relevance
**Priority**: Moderate-High

**Detection Keywords:**
- network adequacy, provider network
- network participation, provider access
- network standards, adequate network

**SNF Impact**:
- Determines SNF ability to serve MA beneficiaries
- Network participation affects market share
- Compliance costs for network standards

---

### 4. **Quality Programs/Star Ratings**
**Score Range**: 50-70 relevance
**Priority**: Moderate

**Detection Keywords:**
- Star Ratings, MA Star Ratings
- bonus payment, quality bonus
- performance measures, HEDIS, HOS, CAHPS

**SNF Impact**:
- MA plan Star Ratings affect referral patterns
- Quality bonuses influence plan behavior toward SNFs
- Indirect impact through plan incentives

---

## Enhanced Scoring Matrix

| Bill Type | Base Score | Max Score | Priority | Context Notes |
|-----------|------------|-----------|----------|---------------|
| **Direct SNF** | 85 | 100 | 1 | Explicitly mentions SNFs |
| **MA Payment** | 75 | 95 | 2 | Critical cash flow impact |
| **MA Prior Auth** | 65 | 85 | 2 | Affects admission patterns |
| **MA Network** | 55 | 75 | 3 | Market participation impact |
| **MA Quality** | 45 | 65 | 3 | Indirect referral impact |
| **LTC Related** | 35 | 55 | 3 | Competing providers |
| **Medicare General** | 25 | 45 | 4 | Potential SNF impact |
| **Healthcare General** | 15 | 35 | 5 | Minimal SNF relevance |

---

## Context Notes System

Each MA bill receives automatic context notes explaining its SNF relevance:

### **Payment Impact Bills**
*"30-40% of SNF revenue comes from Medicare Advantage plans. Payment delays severely impact SNF cash flow and operations."*

### **Prior Authorization Bills**
*"MA prior authorization changes affect SNF admission patterns and length of stay decisions."*

### **Network Adequacy Bills**
*"Network participation requirements determine SNF ability to serve MA beneficiaries in their market."*

### **Quality Program Bills**
*"MA Star Ratings affect plan bonus payments and can influence referral patterns to SNFs."*

---

## Implementation Features

### 🎯 **Special MA Flagging**
- Bills with `ma_impact: true` are flagged for special attention
- Dashboard highlighting for MA legislation
- Separate tracking category for MA bills

### 📝 **Detailed Explanations**
- Each bill gets human-readable explanation
- Context notes explain specific SNF relevance
- Scoring rationale provided

### 📊 **Enhanced Analytics**
- Track MA bills separately from general Medicare legislation
- Monitor MA policy trends affecting SNFs
- Report on cumulative MA impact

---

## Examples of Improved Scoring

### Before Enhanced System:
- **S-119-2879** (MA Prompt Payment): Not scored or low score
- **S-119-2865** (Advance Care Planning): Risk-based score only
- **General MA Bills**: Often missed or underscored

### After Enhanced System:
- **S-119-2879**: **85/100** - High impact due to cash flow dependency
- **S-119-2865**: **60/100** - Moderate impact on care planning
- **MA Bills**: Consistently detected and appropriately scored

---

## Usage Guidelines

### **High Priority Monitoring** (80+ Score)
- Direct SNF legislation
- MA payment/reimbursement changes
- Immediate implementation tracking required

### **Moderate Priority** (50-79 Score)
- MA prior authorization changes
- Network adequacy requirements
- Quarterly review sufficient

### **Watch List** (25-49 Score)
- General Medicare legislation
- MA quality programs
- Annual review adequate

### **Low Priority** (<25 Score)
- General healthcare bills
- Non-healthcare legislation
- Filter out unless specific interest

---

## Integration Points

### **Bill Collection Services**
- Enhanced screening of MA-related bills
- Automatic flagging during ingestion
- Priority processing for MA legislation

### **Alert System**
- Special alerts for high-impact MA bills
- Escalation for payment-related legislation
- Notifications to financial and operations teams

### **Dashboard Integration**
- MA impact indicators
- Separate MA bill category
- Context notes display

---

## Monitoring & Updates

### **Quarterly Reviews**
- Assess MA bill detection accuracy
- Update keyword lists based on new terminology
- Refine scoring based on actual SNF impact

### **Annual Calibration**
- Review scoring matrix effectiveness
- Update context explanations
- Incorporate industry feedback

---

## Technical Implementation

### **Files Modified**
- `services/ai/enhanced_relevance_classifier.py` - New MA detection engine
- `apply_enhanced_classifier.py` - Database update utility
- Dashboard integration (pending)

### **Database Changes**
- Updated relevance scores for existing bills
- New scoring rationale stored
- MA impact flag added to bill records

---

*This system ensures that Medicare Advantage legislation affecting SNF operations receives appropriate attention and priority, given that MA plans represent 30-40% of typical SNF revenue streams.*