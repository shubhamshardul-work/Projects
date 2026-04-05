"""
Graph Schema — textual description of the Neo4j schema for LLM context.
"""

GRAPH_SCHEMA = """
=== NEO4J GRAPH SCHEMA ===

NODE TYPES:
-----------

1. (:Employee)
   Properties: employee_id, first_name, last_name, full_name, gender, date_of_birth,
               nationality, career_level (int 1-12), level_category, designation,
               employee_band, work_email, personal_email, work_phone, mobile,
               date_of_joining, employment_type (Permanent/Contract),
               employment_status (Active/Inactive), education_level, degree,
               annual_ctc_lpa, currency, notice_period, work_mode (Hybrid/Remote/On-site),
               cost_center, years_at_company, total_exp_yrs

2. (:Skill)
   Properties: skill_id, name, category (Technical/Soft Skill/Domain/Tool),
               sub_category, description

3. (:Project)
   Properties: project_id, name, project_code, project_type (T&M/Fixed Price),
               status (Active/Completed/Planning), start_date, planned_end_date,
               project_value_inr, currency, industry_vertical

4. (:Department)
   Properties: department_id, name, service_line, business_group, cost_center, parent_group

5. (:Office)
   Properties: office_id, city, country, region, address, postal_code, phone,
               is_hq, time_zone, seating_capacity

6. (:CareerLevel)
   Properties: level (int 1-12, 1=highest), level_category, designation,
               min_exp_yrs, span_of_control, reports_to, description

7. (:Certification)
   Properties: name, issuing_body

8. (:Training)
   Properties: name, training_type (External/Internal), provider

9. (:Client)
   Properties: name

10. (:University)
    Properties: name


RELATIONSHIP TYPES:
-------------------

(Employee)-[:HAS_SKILL {proficiency_level, years_experience, is_primary, assessment_type, last_used_date}]->(Skill)
   proficiency_level values: Beginner, Intermediate, Advanced, Expert

(Employee)-[:WORKS_IN]->(Department)

(Employee)-[:BASED_AT]->(Office)

(Employee)-[:REPORTS_TO]->(Employee)
   Represents the manager hierarchy

(Employee)-[:AT_CAREER_LEVEL]->(CareerLevel)

(Employee)-[:ASSIGNED_TO {assignment_id, role_on_project, start_date, end_date, allocation_pct, billing_rate_inr, total_hours_billed, is_billable, performance}]->(Project)
   role_on_project values: Delivery Director, Workstream Lead, Technical Manager, Module Lead,
                           Data Engineer, ML Engineer, Cloud Architect, etc.
   performance values: Exceeds, Meets, Partially Meets

(Employee)-[:HOLDS_CERTIFICATION {cert_id, issue_date, expiry_date, status, certificate_no}]->(Certification)

(Employee)-[:COMPLETED_TRAINING {training_id, start_date, end_date, duration_hrs, status, score, is_mandatory}]->(Training)

(Employee)-[:REVIEWED_BY {review_id, review_year, review_period, overall_rating, goals_score, competency_score, weighted_avg, promotion_eligible, increment_pct, bonus_pct, review_date}]->(Employee)
   overall_rating values: Exceeds Expectations, Meets Expectations, Partially Meets

(Employee)-[:STUDIED_AT]->(University)

(Project)-[:REQUIRES_SKILL {importance_level}]->(Skill)
   importance_level values: Core, Supporting

(Project)-[:BELONGS_TO_DEPT]->(Department)

(Project)-[:DELIVERED_FROM]->(Office)

(Project)-[:FOR_CLIENT]->(Client)

(Certification)-[:VALIDATES_SKILL]->(Skill)

(Training)-[:DEVELOPS_SKILL]->(Skill)

(Department)-[:HEADED_BY]->(Employee)


KEY ENUMERATIONS:
-----------------
Departments: Data & AI, Cloud & Infrastructure, Cybersecurity, Digital Commerce,
             Enterprise Platforms, Finance & Risk, Supply Chain & Operations,
             Human Capital Mgmt, Strategy & Consulting, Intelligent Automation

Offices: Mumbai (HQ), Bangalore, Hyderabad, Pune, Delhi NCR, New York, London, Singapore, Sydney, Dubai

Skills (sample): Python, SQL, Apache Spark, AWS, Azure, GCP, Machine Learning,
                 Deep Learning, NLP / Generative AI, Power BI, Tableau, Databricks,
                 Snowflake, Docker, Kubernetes, Terraform, React, Node.js, JIRA

Industry Verticals: Banking & Financial Services, Energy & Utilities, Retail,
                    Technology, Healthcare, Telecommunications, Insurance
"""


SCHEMA_FOR_CYPHER = """
Node properties:
Employee {employee_id: STRING, full_name: STRING, gender: STRING, designation: STRING, employment_status: STRING, career_level: INTEGER, work_mode: STRING, total_exp_yrs: FLOAT, years_at_company: FLOAT, education_level: STRING, degree: STRING, annual_ctc_lpa: FLOAT}
Skill {skill_id: STRING, name: STRING, category: STRING, sub_category: STRING}
Project {project_id: STRING, name: STRING, project_type: STRING, status: STRING, industry_vertical: STRING, project_value_inr: FLOAT}
Department {department_id: STRING, name: STRING, service_line: STRING, business_group: STRING}
Office {office_id: STRING, city: STRING, country: STRING}
CareerLevel {level: INTEGER, designation: STRING, level_category: STRING}
Certification {name: STRING, issuing_body: STRING}
Training {name: STRING, training_type: STRING, provider: STRING}
Client {name: STRING}
University {name: STRING}

Relationship properties:
(:Employee)-[:HAS_SKILL {proficiency_level: STRING, years_experience: FLOAT, is_primary: STRING}]->(:Skill)
(:Employee)-[:ASSIGNED_TO {role_on_project: STRING, allocation_pct: FLOAT, performance: STRING}]->(:Project)
(:Employee)-[:HOLDS_CERTIFICATION {status: STRING, issue_date: STRING, expiry_date: STRING}]->(:Certification)
(:Employee)-[:COMPLETED_TRAINING {status: STRING, score: FLOAT}]->(:Training)
(:Employee)-[:REVIEWED_BY {review_year: INTEGER, overall_rating: STRING, weighted_avg: FLOAT, promotion_eligible: STRING}]->(:Employee)
(:Project)-[:REQUIRES_SKILL {importance_level: STRING}]->(:Skill)

The relationships available:
(:Employee)-[:HAS_SKILL]->(:Skill)
(:Employee)-[:WORKS_IN]->(:Department)
(:Employee)-[:BASED_AT]->(:Office)
(:Employee)-[:REPORTS_TO]->(:Employee)
(:Employee)-[:AT_CAREER_LEVEL]->(:CareerLevel)
(:Employee)-[:ASSIGNED_TO]->(:Project)
(:Employee)-[:HOLDS_CERTIFICATION]->(:Certification)
(:Employee)-[:COMPLETED_TRAINING]->(:Training)
(:Employee)-[:REVIEWED_BY]->(:Employee)
(:Employee)-[:STUDIED_AT]->(:University)
(:Project)-[:REQUIRES_SKILL]->(:Skill)
(:Project)-[:BELONGS_TO_DEPT]->(:Department)
(:Project)-[:DELIVERED_FROM]->(:Office)
(:Project)-[:FOR_CLIENT]->(:Client)
(:Certification)-[:VALIDATES_SKILL]->(:Skill)
(:Training)-[:DEVELOPS_SKILL]->(:Skill)
(:Department)-[:HEADED_BY]->(:Employee)
"""
