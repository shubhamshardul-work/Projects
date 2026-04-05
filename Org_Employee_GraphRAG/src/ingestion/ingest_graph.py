"""
Graph Ingestion — loads DataFrames into Neo4j as nodes and relationships.

Creates constraints/indexes first, then upserts all entities.
"""
from __future__ import annotations

from typing import Any, Dict

import pandas as pd

from src.neo4j_manager import Neo4jManager
from src.utils.logger import log


# ───────────────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────────────

def _safe(val: Any) -> Any:
    """Convert pandas NaN / NaT to None for Neo4j."""
    if pd.isna(val):
        return None
    if isinstance(val, pd.Timestamp):
        return val.isoformat()
    return val


def _row_dict(row: pd.Series) -> Dict[str, Any]:
    """Convert a DataFrame row to a clean dict."""
    return {k: _safe(v) for k, v in row.items()}


# ───────────────────────────────────────────────────────────────────────
# Constraints & Indexes
# ───────────────────────────────────────────────────────────────────────

_CONSTRAINTS = [
    "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Employee) REQUIRE e.employee_id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (s:Skill) REQUIRE s.skill_id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Project) REQUIRE p.project_id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Department) REQUIRE d.department_id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (o:Office) REQUIRE o.office_id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (cl:CareerLevel) REQUIRE cl.level IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Certification) REQUIRE c.name IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (t:Training) REQUIRE t.name IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (cl:Client) REQUIRE cl.name IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (u:University) REQUIRE u.name IS UNIQUE",
]


def create_constraints(db: Neo4jManager) -> None:
    """Create uniqueness constraints and indexes."""
    log.info("[bold yellow]Creating constraints & indexes …[/]")
    for cypher in _CONSTRAINTS:
        db.run_write(cypher)
    log.info(f"  ✅ {len(_CONSTRAINTS)} constraints created")


# ───────────────────────────────────────────────────────────────────────
# Node Ingestion
# ───────────────────────────────────────────────────────────────────────

def ingest_career_levels(db: Neo4jManager, df: pd.DataFrame) -> None:
    """Ingest CareerLevel nodes."""
    log.info("[bold magenta]Ingesting CareerLevel nodes …[/]")
    query = """
    UNWIND $rows AS row
    MERGE (cl:CareerLevel {level: toInteger(row.level)})
    SET cl.level_category  = row.level_category,
        cl.designation     = row.designation,
        cl.min_exp_yrs     = toFloat(row.min_exp_yrs),
        cl.span_of_control = row.span_of_control,
        cl.reports_to      = row.reports_to,
        cl.description     = row.description
    """
    rows = []
    for _, r in df.iterrows():
        rows.append({
            "level": int(r["Level #"]),
            "level_category": _safe(r["Level Category"]),
            "designation": _safe(r["Designation"]),
            "min_exp_yrs": _safe(r["Min Exp (Yrs)"]),
            "span_of_control": _safe(r["Typical Span of Control"]),
            "reports_to": _safe(r["Reports To"]),
            "description": _safe(r["Description"]),
        })
    db.run_write_batch(query, rows)
    log.info(f"  ✅ {len(rows)} CareerLevel nodes")


def ingest_departments(db: Neo4jManager, df: pd.DataFrame) -> None:
    """Ingest Department nodes."""
    log.info("[bold magenta]Ingesting Department nodes …[/]")
    query = """
    UNWIND $rows AS row
    MERGE (d:Department {department_id: row.department_id})
    SET d.name           = row.name,
        d.service_line   = row.service_line,
        d.business_group = row.business_group,
        d.cost_center    = row.cost_center,
        d.parent_group   = row.parent_group
    """
    rows = []
    for _, r in df.iterrows():
        rows.append({
            "department_id": r["Department_ID"],
            "name": _safe(r["Department_Name"]),
            "service_line": _safe(r["Service_Line"]),
            "business_group": _safe(r["Business_Group"]),
            "cost_center": _safe(r["Cost_Center"]),
            "parent_group": _safe(r["Parent_Group"]),
        })
    db.run_write_batch(query, rows)
    log.info(f"  ✅ {len(rows)} Department nodes")


def ingest_offices(db: Neo4jManager, df: pd.DataFrame) -> None:
    """Ingest Office nodes."""
    log.info("[bold magenta]Ingesting Office nodes …[/]")
    query = """
    UNWIND $rows AS row
    MERGE (o:Office {office_id: row.office_id})
    SET o.city              = row.city,
        o.country           = row.country,
        o.region            = row.region,
        o.address           = row.address,
        o.postal_code       = row.postal_code,
        o.phone             = row.phone,
        o.is_hq             = row.is_hq,
        o.time_zone         = row.time_zone,
        o.seating_capacity  = toInteger(row.seating_capacity)
    """
    rows = []
    for _, r in df.iterrows():
        rows.append({
            "office_id": r["Office_ID"],
            "city": _safe(r["City"]),
            "country": _safe(r["Country"]),
            "region": _safe(r["Region"]),
            "address": _safe(r["Address"]),
            "postal_code": _safe(r["Postal_Code"]),
            "phone": _safe(r["Phone"]),
            "is_hq": _safe(r["Is_HQ"]),
            "time_zone": _safe(r["Time_Zone"]),
            "seating_capacity": _safe(r["Seating_Capacity"]),
        })
    db.run_write_batch(query, rows)
    log.info(f"  ✅ {len(rows)} Office nodes")


def ingest_skills_catalog(db: Neo4jManager, df: pd.DataFrame) -> None:
    """Ingest Skill nodes from the catalog."""
    log.info("[bold magenta]Ingesting Skill nodes …[/]")
    query = """
    UNWIND $rows AS row
    MERGE (s:Skill {skill_id: row.skill_id})
    SET s.name          = row.name,
        s.category      = row.category,
        s.sub_category  = row.sub_category,
        s.description   = row.description
    """
    rows = []
    for _, r in df.iterrows():
        rows.append({
            "skill_id": r["Skill_ID"],
            "name": _safe(r["Skill_Name"]),
            "category": _safe(r["Skill_Category"]),
            "sub_category": _safe(r["Sub_Category"]),
            "description": _safe(r["Description"]),
        })
    db.run_write_batch(query, rows)
    log.info(f"  ✅ {len(rows)} Skill nodes")


def ingest_employees(db: Neo4jManager, df: pd.DataFrame) -> None:
    """Ingest Employee nodes."""
    log.info("[bold magenta]Ingesting Employee nodes …[/]")
    query = """
    UNWIND $rows AS row
    MERGE (e:Employee {employee_id: row.employee_id})
    SET e.first_name        = row.first_name,
        e.last_name         = row.last_name,
        e.full_name         = row.full_name,
        e.gender            = row.gender,
        e.date_of_birth     = row.date_of_birth,
        e.nationality       = row.nationality,
        e.career_level      = toInteger(row.career_level),
        e.level_category    = row.level_category,
        e.designation       = row.designation,
        e.employee_band     = row.employee_band,
        e.work_email        = row.work_email,
        e.personal_email    = row.personal_email,
        e.work_phone        = row.work_phone,
        e.mobile            = row.mobile,
        e.date_of_joining   = row.date_of_joining,
        e.employment_type   = row.employment_type,
        e.employment_status = row.employment_status,
        e.education_level   = row.education_level,
        e.degree            = row.degree,
        e.annual_ctc_lpa    = toFloat(row.annual_ctc_lpa),
        e.currency          = row.currency,
        e.notice_period     = row.notice_period,
        e.work_mode         = row.work_mode,
        e.cost_center       = row.cost_center,
        e.years_at_company  = toFloat(row.years_at_company),
        e.total_exp_yrs     = toFloat(row.total_exp_yrs)
    """
    rows = []
    for _, r in df.iterrows():
        rows.append({
            "employee_id": r["Employee_ID"],
            "first_name": _safe(r["First_Name"]),
            "last_name": _safe(r["Last_Name"]),
            "full_name": _safe(r["Full_Name"]),
            "gender": _safe(r["Gender"]),
            "date_of_birth": _safe(r["Date_of_Birth"]),
            "nationality": _safe(r["Nationality"]),
            "career_level": _safe(r["Career_Level"]),
            "level_category": _safe(r["Level_Category"]),
            "designation": _safe(r["Designation"]),
            "employee_band": _safe(r["Employee_Band"]),
            "work_email": _safe(r["Work_Email"]),
            "personal_email": _safe(r["Personal_Email"]),
            "work_phone": _safe(r["Work_Phone"]),
            "mobile": _safe(r["Mobile"]),
            "date_of_joining": _safe(r["Date_of_Joining"]),
            "employment_type": _safe(r["Employment_Type"]),
            "employment_status": _safe(r["Employment_Status"]),
            "education_level": _safe(r["Education_Level"]),
            "degree": _safe(r["Degree"]),
            "annual_ctc_lpa": _safe(r["Annual_CTC_LPA"]),
            "currency": _safe(r["Currency"]),
            "notice_period": _safe(r["Notice_Period"]),
            "work_mode": _safe(r["Work_Mode"]),
            "cost_center": _safe(r["Cost_Center"]),
            "years_at_company": _safe(r["Years_at_accen"]),
            "total_exp_yrs": _safe(r["Total_Exp_Yrs"]),
        })
    db.run_write_batch(query, rows)
    log.info(f"  ✅ {len(rows)} Employee nodes")


def ingest_projects(db: Neo4jManager, df: pd.DataFrame) -> None:
    """Ingest Project + Client nodes."""
    log.info("[bold magenta]Ingesting Project & Client nodes …[/]")

    # Projects
    proj_query = """
    UNWIND $rows AS row
    MERGE (p:Project {project_id: row.project_id})
    SET p.name              = row.name,
        p.project_code      = row.project_code,
        p.project_type      = row.project_type,
        p.status            = row.status,
        p.start_date        = row.start_date,
        p.planned_end_date  = row.planned_end_date,
        p.project_value_inr = toFloat(row.project_value_inr),
        p.currency          = row.currency,
        p.industry_vertical = row.industry_vertical
    """
    # Clients
    client_query = """
    UNWIND $rows AS row
    MERGE (c:Client {name: row.client_name})
    """
    rows = []
    client_rows = []
    for _, r in df.iterrows():
        rows.append({
            "project_id": r["Project_ID"],
            "name": _safe(r["Project_Name"]),
            "project_code": _safe(r["Project_Code"]),
            "project_type": _safe(r["Project_Type"]),
            "status": _safe(r["Status"]),
            "start_date": _safe(r["Start_Date"]),
            "planned_end_date": _safe(r["Planned_End_Date"]),
            "project_value_inr": _safe(r["Project_Value_INR"]),
            "currency": _safe(r["Currency"]),
            "industry_vertical": _safe(r["Industry_Vertical"]),
        })
        client_name = _safe(r["Client_Name"])
        if client_name:
            client_rows.append({"client_name": client_name})

    db.run_write_batch(proj_query, rows)
    log.info(f"  ✅ {len(rows)} Project nodes")

    # Deduplicate clients
    seen = set()
    unique_clients = []
    for c in client_rows:
        if c["client_name"] not in seen:
            seen.add(c["client_name"])
            unique_clients.append(c)
    db.run_write_batch(client_query, unique_clients)
    log.info(f"  ✅ {len(unique_clients)} Client nodes")


# ───────────────────────────────────────────────────────────────────────
# Relationship Ingestion
# ───────────────────────────────────────────────────────────────────────

def ingest_employee_relationships(
    db: Neo4jManager,
    employees_df: pd.DataFrame,
) -> None:
    """
    Create relationships from the Employees sheet:
      - WORKS_IN → Department
      - BASED_AT → Office
      - REPORTS_TO → Employee (manager)
      - AT_CAREER_LEVEL → CareerLevel
      - STUDIED_AT → University
    """
    log.info("[bold magenta]Ingesting Employee relationships …[/]")

    # WORKS_IN
    query = """
    UNWIND $rows AS row
    MATCH (e:Employee {employee_id: row.emp_id})
    MATCH (d:Department {department_id: row.dept_id})
    MERGE (e)-[:WORKS_IN]->(d)
    """
    rows = [{"emp_id": r["Employee_ID"], "dept_id": r["Department_ID"]}
            for _, r in employees_df.iterrows() if _safe(r["Department_ID"])]
    db.run_write_batch(query, rows)
    log.info(f"  ✅ {len(rows)} WORKS_IN relationships")

    # BASED_AT
    query = """
    UNWIND $rows AS row
    MATCH (e:Employee {employee_id: row.emp_id})
    MATCH (o:Office {office_id: row.office_id})
    MERGE (e)-[:BASED_AT]->(o)
    """
    rows = [{"emp_id": r["Employee_ID"], "office_id": r["Office_ID"]}
            for _, r in employees_df.iterrows() if _safe(r["Office_ID"])]
    db.run_write_batch(query, rows)
    log.info(f"  ✅ {len(rows)} BASED_AT relationships")

    # REPORTS_TO
    query = """
    UNWIND $rows AS row
    MATCH (e:Employee {employee_id: row.emp_id})
    MATCH (m:Employee {employee_id: row.mgr_id})
    MERGE (e)-[:REPORTS_TO]->(m)
    """
    rows = [{"emp_id": r["Employee_ID"], "mgr_id": r["Manager_ID"]}
            for _, r in employees_df.iterrows() if _safe(r["Manager_ID"])]
    db.run_write_batch(query, rows)
    log.info(f"  ✅ {len(rows)} REPORTS_TO relationships")

    # AT_CAREER_LEVEL
    query = """
    UNWIND $rows AS row
    MATCH (e:Employee {employee_id: row.emp_id})
    MATCH (cl:CareerLevel {level: toInteger(row.level)})
    MERGE (e)-[:AT_CAREER_LEVEL]->(cl)
    """
    rows = [{"emp_id": r["Employee_ID"], "level": int(r["Career_Level"])}
            for _, r in employees_df.iterrows() if _safe(r["Career_Level"])]
    db.run_write_batch(query, rows)
    log.info(f"  ✅ {len(rows)} AT_CAREER_LEVEL relationships")

    # STUDIED_AT (create University nodes on-the-fly)
    uni_query = """
    UNWIND $rows AS row
    MERGE (u:University {name: row.university})
    """
    rel_query = """
    UNWIND $rows AS row
    MATCH (e:Employee {employee_id: row.emp_id})
    MATCH (u:University {name: row.university})
    MERGE (e)-[:STUDIED_AT]->(u)
    """
    rows = [{"emp_id": r["Employee_ID"], "university": _safe(r["University"])}
            for _, r in employees_df.iterrows() if _safe(r["University"])]
    # Create university nodes
    seen = set()
    uni_rows = []
    for row in rows:
        if row["university"] not in seen:
            seen.add(row["university"])
            uni_rows.append({"university": row["university"]})
    db.run_write_batch(uni_query, uni_rows)
    log.info(f"  ✅ {len(uni_rows)} University nodes")
    db.run_write_batch(rel_query, rows)
    log.info(f"  ✅ {len(rows)} STUDIED_AT relationships")


def ingest_department_heads(
    db: Neo4jManager,
    departments_df: pd.DataFrame,
) -> None:
    """Create HEADED_BY relationships from Department → Employee."""
    log.info("[bold magenta]Ingesting HEADED_BY relationships …[/]")
    query = """
    UNWIND $rows AS row
    MATCH (d:Department {department_id: row.dept_id})
    MATCH (e:Employee {employee_id: row.head_id})
    MERGE (d)-[:HEADED_BY]->(e)
    """
    rows = [{"dept_id": r["Department_ID"], "head_id": r["Practice_Head_EmpID"]}
            for _, r in departments_df.iterrows() if _safe(r["Practice_Head_EmpID"])]
    db.run_write_batch(query, rows)
    log.info(f"  ✅ {len(rows)} HEADED_BY relationships")


def ingest_employee_skills(db: Neo4jManager, df: pd.DataFrame) -> None:
    """Create HAS_SKILL relationships with properties."""
    log.info("[bold magenta]Ingesting HAS_SKILL relationships …[/]")
    query = """
    UNWIND $rows AS row
    MATCH (e:Employee {employee_id: row.emp_id})
    MATCH (s:Skill {skill_id: row.skill_id})
    MERGE (e)-[r:HAS_SKILL]->(s)
    SET r.proficiency_level = row.proficiency,
        r.years_experience  = toFloat(row.years_exp),
        r.last_used_date    = row.last_used,
        r.is_primary        = row.is_primary,
        r.assessment_type   = row.assessment
    """
    rows = []
    for _, r in df.iterrows():
        rows.append({
            "emp_id": r["Employee_ID"],
            "skill_id": r["Skill_ID"],
            "proficiency": _safe(r["Proficiency_Level"]),
            "years_exp": _safe(r["Years_Experience"]),
            "last_used": _safe(r["Last_Used_Date"]),
            "is_primary": _safe(r["Is_Primary_Skill"]),
            "assessment": _safe(r["Assessment_Type"]),
        })
    db.run_write_batch(query, rows)
    log.info(f"  ✅ {len(rows)} HAS_SKILL relationships")


def ingest_project_assignments(db: Neo4jManager, df: pd.DataFrame) -> None:
    """Create ASSIGNED_TO relationships with properties."""
    log.info("[bold magenta]Ingesting ASSIGNED_TO relationships …[/]")
    query = """
    UNWIND $rows AS row
    MATCH (e:Employee {employee_id: row.emp_id})
    MATCH (p:Project {project_id: row.proj_id})
    MERGE (e)-[r:ASSIGNED_TO {assignment_id: row.assignment_id}]->(p)
    SET r.role_on_project   = row.role,
        r.start_date        = row.start_date,
        r.end_date          = row.end_date,
        r.allocation_pct    = toFloat(row.allocation),
        r.billing_rate_inr  = toFloat(row.billing_rate),
        r.total_hours_billed = toFloat(row.total_hours),
        r.is_billable       = row.is_billable,
        r.performance       = row.performance
    """
    rows = []
    for _, r in df.iterrows():
        rows.append({
            "assignment_id": r["Assignment_ID"],
            "emp_id": r["Employee_ID"],
            "proj_id": r["Project_ID"],
            "role": _safe(r["Role_on_Project"]),
            "start_date": _safe(r["Start_Date"]),
            "end_date": _safe(r["End_Date"]),
            "allocation": _safe(r["Allocation_Pct"]),
            "billing_rate": _safe(r["Billing_Rate_INR"]),
            "total_hours": _safe(r["Total_Hours_Billed"]),
            "is_billable": _safe(r["Is_Billable"]),
            "performance": _safe(r["Perf_on_Project"]),
        })
    db.run_write_batch(query, rows)
    log.info(f"  ✅ {len(rows)} ASSIGNED_TO relationships")


def ingest_project_skills(db: Neo4jManager, df: pd.DataFrame) -> None:
    """Create REQUIRES_SKILL relationships on Projects."""
    log.info("[bold magenta]Ingesting REQUIRES_SKILL relationships …[/]")
    query = """
    UNWIND $rows AS row
    MATCH (p:Project {project_id: row.proj_id})
    MATCH (s:Skill {skill_id: row.skill_id})
    MERGE (p)-[r:REQUIRES_SKILL]->(s)
    SET r.importance_level = row.importance
    """
    rows = [{"proj_id": r["Project_ID"], "skill_id": r["Skill_ID"],
             "importance": _safe(r["Importance_Level"])}
            for _, r in df.iterrows()]
    db.run_write_batch(query, rows)
    log.info(f"  ✅ {len(rows)} REQUIRES_SKILL relationships")


def ingest_project_relationships(
    db: Neo4jManager,
    projects_df: pd.DataFrame,
) -> None:
    """Create Project → Department, Project → Office, Project → Client."""
    log.info("[bold magenta]Ingesting Project relationships …[/]")

    # BELONGS_TO_DEPT
    query = """
    UNWIND $rows AS row
    MATCH (p:Project {project_id: row.proj_id})
    MATCH (d:Department {department_id: row.dept_id})
    MERGE (p)-[:BELONGS_TO_DEPT]->(d)
    """
    rows = [{"proj_id": r["Project_ID"], "dept_id": r["Department_ID"]}
            for _, r in projects_df.iterrows() if _safe(r["Department_ID"])]
    db.run_write_batch(query, rows)
    log.info(f"  ✅ {len(rows)} BELONGS_TO_DEPT relationships")

    # DELIVERED_FROM
    query = """
    UNWIND $rows AS row
    MATCH (p:Project {project_id: row.proj_id})
    MATCH (o:Office {office_id: row.office_id})
    MERGE (p)-[:DELIVERED_FROM]->(o)
    """
    rows = [{"proj_id": r["Project_ID"], "office_id": r["Delivery_Office_ID"]}
            for _, r in projects_df.iterrows() if _safe(r["Delivery_Office_ID"])]
    db.run_write_batch(query, rows)
    log.info(f"  ✅ {len(rows)} DELIVERED_FROM relationships")

    # FOR_CLIENT
    query = """
    UNWIND $rows AS row
    MATCH (p:Project {project_id: row.proj_id})
    MATCH (c:Client {name: row.client_name})
    MERGE (p)-[:FOR_CLIENT]->(c)
    """
    rows = [{"proj_id": r["Project_ID"], "client_name": _safe(r["Client_Name"])}
            for _, r in projects_df.iterrows() if _safe(r["Client_Name"])]
    db.run_write_batch(query, rows)
    log.info(f"  ✅ {len(rows)} FOR_CLIENT relationships")


def ingest_certifications(db: Neo4jManager, df: pd.DataFrame) -> None:
    """Create Certification nodes + HOLDS_CERTIFICATION + VALIDATES_SKILL."""
    log.info("[bold magenta]Ingesting Certifications …[/]")

    # Create unique Certification nodes
    cert_query = """
    UNWIND $rows AS row
    MERGE (c:Certification {name: row.cert_name})
    SET c.issuing_body = row.issuing_body
    """
    seen = set()
    cert_nodes = []
    for _, r in df.iterrows():
        name = _safe(r["Certification_Name"])
        if name and name not in seen:
            seen.add(name)
            cert_nodes.append({"cert_name": name, "issuing_body": _safe(r["Issuing_Body"])})
    db.run_write_batch(cert_query, cert_nodes)
    log.info(f"  ✅ {len(cert_nodes)} Certification nodes")

    # HOLDS_CERTIFICATION relationships
    rel_query = """
    UNWIND $rows AS row
    MATCH (e:Employee {employee_id: row.emp_id})
    MATCH (c:Certification {name: row.cert_name})
    MERGE (e)-[r:HOLDS_CERTIFICATION {cert_id: row.cert_id}]->(c)
    SET r.issue_date     = row.issue_date,
        r.expiry_date    = row.expiry_date,
        r.status         = row.status,
        r.certificate_no = row.cert_no
    """
    rows = []
    for _, r in df.iterrows():
        rows.append({
            "cert_id": r["Cert_ID"],
            "emp_id": r["Employee_ID"],
            "cert_name": _safe(r["Certification_Name"]),
            "issue_date": _safe(r["Issue_Date"]),
            "expiry_date": _safe(r["Expiry_Date"]),
            "status": _safe(r["Status"]),
            "cert_no": _safe(r["Certificate_No"]),
        })
    db.run_write_batch(rel_query, rows)
    log.info(f"  ✅ {len(rows)} HOLDS_CERTIFICATION relationships")

    # VALIDATES_SKILL
    val_query = """
    UNWIND $rows AS row
    MATCH (c:Certification {name: row.cert_name})
    MATCH (s:Skill {skill_id: row.skill_id})
    MERGE (c)-[:VALIDATES_SKILL]->(s)
    """
    val_rows = []
    seen_pairs = set()
    for _, r in df.iterrows():
        cert_name = _safe(r["Certification_Name"])
        skill_id = _safe(r["Related_Skill_ID"])
        if cert_name and skill_id and (cert_name, skill_id) not in seen_pairs:
            seen_pairs.add((cert_name, skill_id))
            val_rows.append({"cert_name": cert_name, "skill_id": skill_id})
    db.run_write_batch(val_query, val_rows)
    log.info(f"  ✅ {len(val_rows)} VALIDATES_SKILL relationships")


def ingest_performance_reviews(db: Neo4jManager, df: pd.DataFrame) -> None:
    """Create REVIEWED_BY relationships with review data as properties."""
    log.info("[bold magenta]Ingesting Performance Reviews …[/]")
    query = """
    UNWIND $rows AS row
    MATCH (e:Employee {employee_id: row.emp_id})
    MATCH (reviewer:Employee {employee_id: row.reviewer_id})
    MERGE (e)-[r:REVIEWED_BY {review_id: row.review_id}]->(reviewer)
    SET r.review_year        = toInteger(row.review_year),
        r.review_period      = row.review_period,
        r.overall_rating     = row.overall_rating,
        r.goals_score        = toFloat(row.goals_score),
        r.competency_score   = toFloat(row.competency_score),
        r.weighted_avg       = toFloat(row.weighted_avg),
        r.promotion_eligible = row.promotion_eligible,
        r.increment_pct      = toFloat(row.increment_pct),
        r.bonus_pct          = toFloat(row.bonus_pct),
        r.review_date        = row.review_date
    """
    rows = []
    for _, r in df.iterrows():
        reviewer = _safe(r["Reviewer_ID"])
        if not reviewer:
            continue
        rows.append({
            "review_id": r["Review_ID"],
            "emp_id": r["Employee_ID"],
            "reviewer_id": reviewer,
            "review_year": _safe(r["Review_Year"]),
            "review_period": _safe(r["Review_Period"]),
            "overall_rating": _safe(r["Overall_Rating"]),
            "goals_score": _safe(r["Goals_Score_5"]),
            "competency_score": _safe(r["Competency_5"]),
            "weighted_avg": _safe(r["Weighted_Avg_5"]),
            "promotion_eligible": _safe(r["Promotion_Eligible"]),
            "increment_pct": _safe(r["Increment_Pct"]),
            "bonus_pct": _safe(r["Bonus_Pct"]),
            "review_date": _safe(r["Review_Date"]),
        })
    db.run_write_batch(query, rows)
    log.info(f"  ✅ {len(rows)} REVIEWED_BY relationships")


def ingest_training_records(db: Neo4jManager, df: pd.DataFrame) -> None:
    """Create Training nodes + COMPLETED_TRAINING + DEVELOPS_SKILL."""
    log.info("[bold magenta]Ingesting Training Records …[/]")

    # Create unique Training nodes
    train_query = """
    UNWIND $rows AS row
    MERGE (t:Training {name: row.name})
    SET t.training_type = row.training_type,
        t.provider      = row.provider
    """
    seen = set()
    train_nodes = []
    for _, r in df.iterrows():
        name = _safe(r["Training_Name"])
        if name and name not in seen:
            seen.add(name)
            train_nodes.append({
                "name": name,
                "training_type": _safe(r["Training_Type"]),
                "provider": _safe(r["Provider"]),
            })
    db.run_write_batch(train_query, train_nodes)
    log.info(f"  ✅ {len(train_nodes)} Training nodes")

    # COMPLETED_TRAINING relationships
    rel_query = """
    UNWIND $rows AS row
    MATCH (e:Employee {employee_id: row.emp_id})
    MATCH (t:Training {name: row.training_name})
    MERGE (e)-[r:COMPLETED_TRAINING {training_id: row.training_id}]->(t)
    SET r.start_date    = row.start_date,
        r.end_date      = row.end_date,
        r.duration_hrs  = toFloat(row.duration_hrs),
        r.status        = row.status,
        r.score         = toFloat(row.score),
        r.is_mandatory  = row.is_mandatory
    """
    rows = []
    for _, r in df.iterrows():
        rows.append({
            "training_id": r["Training_ID"],
            "emp_id": r["Employee_ID"],
            "training_name": _safe(r["Training_Name"]),
            "start_date": _safe(r["Start_Date"]),
            "end_date": _safe(r["End_Date"]),
            "duration_hrs": _safe(r["Duration_Hrs"]),
            "status": _safe(r["Status"]),
            "score": _safe(r["Score_100"]),
            "is_mandatory": _safe(r["Is_Mandatory"]),
        })
    db.run_write_batch(rel_query, rows)
    log.info(f"  ✅ {len(rows)} COMPLETED_TRAINING relationships")

    # DEVELOPS_SKILL
    dev_query = """
    UNWIND $rows AS row
    MATCH (t:Training {name: row.training_name})
    MATCH (s:Skill {skill_id: row.skill_id})
    MERGE (t)-[:DEVELOPS_SKILL]->(s)
    """
    dev_rows = []
    seen_pairs = set()
    for _, r in df.iterrows():
        name = _safe(r["Training_Name"])
        skill_id = _safe(r["Related_Skill_ID"])
        if name and skill_id and (name, skill_id) not in seen_pairs:
            seen_pairs.add((name, skill_id))
            dev_rows.append({"training_name": name, "skill_id": skill_id})
    db.run_write_batch(dev_query, dev_rows)
    log.info(f"  ✅ {len(dev_rows)} DEVELOPS_SKILL relationships")


# ───────────────────────────────────────────────────────────────────────
# Master Orchestrator
# ───────────────────────────────────────────────────────────────────────

def run_full_ingestion(
    db: Neo4jManager,
    sheets: Dict[str, pd.DataFrame],
    clear_first: bool = True,
) -> Dict[str, int]:
    """
    Run the full ingestion pipeline.

    Args:
        db:          Connected Neo4jManager instance.
        sheets:      Dict of sheet_name → DataFrame from data_loader.
        clear_first: If True, wipe the database before ingesting.

    Returns:
        Final node/relationship counts.
    """
    log.info("[bold green]═══ Starting Full Ingestion Pipeline ═══[/]")

    if clear_first:
        db.clear_database()

    # 1. Constraints
    create_constraints(db)

    # 2. Reference / Catalog nodes
    ingest_career_levels(db, sheets["Career Levels"])
    ingest_departments(db, sheets["Departments"])
    ingest_offices(db, sheets["Offices"])
    ingest_skills_catalog(db, sheets["Skills Catalog"])

    # 3. Core entity nodes
    ingest_employees(db, sheets["Employees"])
    ingest_projects(db, sheets["Projects"])

    # 4. Relationships from Employees sheet
    ingest_employee_relationships(db, sheets["Employees"])
    ingest_department_heads(db, sheets["Departments"])

    # 5. Junction / mapping relationships
    ingest_employee_skills(db, sheets["Employee Skills"])
    ingest_project_assignments(db, sheets["Project Assignments"])
    ingest_project_skills(db, sheets["Project Skills"])
    ingest_project_relationships(db, sheets["Projects"])

    # 6. Certifications & Training
    ingest_certifications(db, sheets["Certifications"])
    ingest_training_records(db, sheets["Training Records"])

    # 7. Performance Reviews
    ingest_performance_reviews(db, sheets["Performance Reviews"])

    # Final stats
    counts = db.get_counts()
    log.info(
        f"[bold green]═══ Ingestion Complete ═══[/] "
        f"Nodes: {counts['nodes']}  |  Relationships: {counts['relationships']}"
    )
    return counts
