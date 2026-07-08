VALID_TYPES = {"str", "float", "int", "enum", "bool", "date"}

TAB_FIELDS = {
    "PD": [
        {"key": "sector", "label": "Business Sector", "type": "enum", "required": True, "priority": 0, "options": ["Manufacturing", "Services", "Retail", "Agriculture", "Construction", "IT/Technology"]},
        {"key": "business_type", "label": "Business Type", "type": "enum", "required": True, "priority": 1, "options": ["Sole Proprietorship", "Partnership", "Private Limited", "LLP", "Public Limited"]},
        {"key": "annual_turnover", "label": "Annual Turnover (₹)", "type": "float", "required": True, "priority": 2, "options": None},
        {"key": "years_in_operation", "label": "Years in Operation", "type": "int", "required": True, "priority": 3, "options": None},
        {"key": "credit_score", "label": "Credit Score (CIBIL)", "type": "float", "required": True, "priority": 4, "options": None},
        {"key": "existing_loan_amount", "label": "Existing Loan Amount (₹)", "type": "float", "required": False, "priority": 5, "options": None},
        {"key": "gst_filing_consistency", "label": "GST Filing Consistency", "type": "enum", "required": False, "priority": 6, "options": ["Regular (monthly)", "Irregular", "New registrant", "Not registered"]},
    ],
    "LGD": [
        {"key": "loan_amount", "label": "Loan Amount (₹)", "type": "float", "required": True, "priority": 0, "options": None},
        {"key": "collateral_type", "label": "Collateral Type", "type": "enum", "required": True, "priority": 1, "options": ["Property", "Fixed Deposit", "Gold", "Inventory", "Receivables", "None"]},
        {"key": "collateral_value", "label": "Collateral Value (₹)", "type": "float", "required": True, "priority": 2, "options": None},
        {"key": "seniority", "label": "Loan Seniority", "type": "enum", "required": True, "priority": 3, "options": ["Senior Secured", "Senior Unsecured", "Subordinated", "Junior"]},
        {"key": "guarantee_type", "label": "Guarantee Type", "type": "enum", "required": False, "priority": 4, "options": ["Personal guarantee", "Corporate guarantee", "None"]},
    ],
    "ECL": [
        {"key": "pd_estimate", "label": "Probability of Default (%)", "type": "float", "required": True, "priority": 0, "options": None},
        {"key": "lgd_estimate", "label": "Loss Given Default (%)", "type": "float", "required": True, "priority": 1, "options": None},
        {"key": "ead_amount", "label": "Exposure at Default (₹)", "type": "float", "required": True, "priority": 2, "options": None},
        {"key": "risk_weight", "label": "Risk Weight (%)", "type": "float", "required": False, "priority": 3, "options": None},
        {"key": "macroeconomic_factor", "label": "Macroeconomic Scenario", "type": "enum", "required": False, "priority": 4, "options": ["Baseline", "Adverse", "Severely Adverse", "Optimistic"]},
    ],
    "Cascade": [
        {"key": "supplier_count", "label": "Number of Suppliers", "type": "int", "required": True, "priority": 0, "options": None},
        {"key": "buyer_concentration", "label": "Top Buyer Concentration (%)", "type": "float", "required": True, "priority": 1, "options": None},
        {"key": "keystone_exposure", "label": "Keystone Firm Exposure", "type": "enum", "required": True, "priority": 2, "options": ["High", "Medium", "Low", "None"]},
        {"key": "cluster_id", "label": "Industry Cluster", "type": "str", "required": False, "priority": 3, "options": None},
    ],
    "Report": [
        {"key": "applicant_name", "label": "Applicant Name", "type": "str", "required": True, "priority": 0, "options": None},
        {"key": "applicant_pan", "label": "PAN Number", "type": "str", "required": True, "priority": 1, "options": None},
        {"key": "business_address", "label": "Business Address", "type": "str", "required": True, "priority": 2, "options": None},
        {"key": "report_date", "label": "Report Date", "type": "date", "required": False, "priority": 3, "options": None},
    ],
}


def get_fields(tab_name):
    return TAB_FIELDS.get(tab_name, [])


def validate_field_type(type_name):
    if type_name not in VALID_TYPES:
        raise ValueError(f"Unknown field type: {type_name}. Valid types: {', '.join(sorted(VALID_TYPES))}")


def get_required_fields(tab_name):
    return [f for f in TAB_FIELDS.get(tab_name, []) if f["required"]]


def get_optional_fields(tab_name):
    return [f for f in TAB_FIELDS.get(tab_name, []) if not f["required"]]


def sorted_fields(tab_name):
    fields = TAB_FIELDS.get(tab_name, [])
    return sorted(fields, key=lambda f: (0 if f["required"] else 1, f["priority"]))
