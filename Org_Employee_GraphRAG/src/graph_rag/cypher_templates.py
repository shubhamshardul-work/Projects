"""
Cypher Templates — few-shot examples for common query patterns.
"""

FEW_SHOT_EXAMPLES = [
    {
        "question": "Find people with Python skills who are at Expert level",
        "cypher": """MATCH (e:Employee)-[hs:HAS_SKILL]->(s:Skill)
WHERE s.name = 'Python' AND hs.proficiency_level = 'Expert'
AND e.employment_status = 'Active'
RETURN e.full_name AS name, e.designation AS designation,
       hs.proficiency_level AS proficiency, hs.years_experience AS skill_years,
       e.total_exp_yrs AS total_experience
ORDER BY hs.years_experience DESC"""
    },
    {
        "question": "I want people with Machine Learning skills who have AWS certifications",
        "cypher": """MATCH (e:Employee)-[hs:HAS_SKILL]->(s:Skill)
WHERE s.name = 'Machine Learning' AND hs.proficiency_level IN ['Advanced', 'Expert']
AND e.employment_status = 'Active'
MATCH (e)-[:HOLDS_CERTIFICATION]->(c:Certification)
WHERE c.name CONTAINS 'AWS'
RETURN DISTINCT e.full_name AS name, e.designation AS designation,
       hs.proficiency_level AS ml_proficiency,
       c.name AS certification
ORDER BY e.full_name"""
    },
    {
        "question": "Find employees who have worked on Banking projects with data engineering skills",
        "cypher": """MATCH (e:Employee)-[a:ASSIGNED_TO]->(p:Project)
WHERE p.industry_vertical = 'Banking & Financial Services'
MATCH (e)-[hs:HAS_SKILL]->(s:Skill)
WHERE s.sub_category IN ['Data Engineering', 'Big Data', 'Data Platform']
AND e.employment_status = 'Active'
RETURN DISTINCT e.full_name AS name, e.designation AS designation,
       p.name AS project, a.role_on_project AS role,
       collect(DISTINCT s.name) AS data_skills
ORDER BY e.full_name"""
    },
    {
        "question": "Who are the top performers in the Data & AI department?",
        "cypher": """MATCH (e:Employee)-[:WORKS_IN]->(d:Department {name: 'Data & AI'})
MATCH (e)-[r:REVIEWED_BY]->()
WHERE r.overall_rating = 'Exceeds Expectations'
AND e.employment_status = 'Active'
RETURN e.full_name AS name, e.designation AS designation,
       r.review_year AS year, r.overall_rating AS rating,
       r.weighted_avg AS score
ORDER BY r.review_year DESC, r.weighted_avg DESC"""
    },
    {
        "question": "List all employees in the Mumbai office with cloud skills",
        "cypher": """MATCH (e:Employee)-[:BASED_AT]->(o:Office {city: 'Mumbai'})
MATCH (e)-[hs:HAS_SKILL]->(s:Skill)
WHERE s.sub_category = 'Cloud Platform'
AND e.employment_status = 'Active'
RETURN e.full_name AS name, e.designation AS designation,
       s.name AS cloud_skill, hs.proficiency_level AS proficiency
ORDER BY s.name, hs.proficiency_level DESC"""
    },
    {
        "question": "Find people with Python and Machine Learning skills who have certifications and worked on AI projects",
        "cypher": """MATCH (e:Employee)-[hs1:HAS_SKILL]->(s1:Skill {name: 'Python'})
WHERE hs1.proficiency_level IN ['Advanced', 'Expert']
MATCH (e)-[hs2:HAS_SKILL]->(s2:Skill {name: 'Machine Learning'})
WHERE hs2.proficiency_level IN ['Advanced', 'Expert']
MATCH (e)-[:HOLDS_CERTIFICATION]->(c:Certification)
MATCH (e)-[a:ASSIGNED_TO]->(p:Project)
WHERE p.name CONTAINS 'AI' OR p.industry_vertical CONTAINS 'Technology'
AND e.employment_status = 'Active'
RETURN DISTINCT e.full_name AS name, e.designation AS designation,
       hs1.proficiency_level AS python_level,
       hs2.proficiency_level AS ml_level,
       collect(DISTINCT c.name) AS certifications,
       collect(DISTINCT p.name) AS projects
ORDER BY e.full_name"""
    },
    {
        "question": "Who reports to Rahul Kapoor?",
        "cypher": """MATCH (e:Employee)-[:REPORTS_TO]->(m:Employee)
WHERE m.full_name = 'Rahul Kapoor'
RETURN e.full_name AS name, e.designation AS designation,
       e.employee_band AS band, e.work_mode AS work_mode
ORDER BY e.career_level"""
    },
    {
        "question": "What skills does project Customer 360 Analytics Platform require?",
        "cypher": """MATCH (p:Project)-[rs:REQUIRES_SKILL]->(s:Skill)
WHERE p.name = 'Customer 360 Analytics Platform'
RETURN s.name AS skill, s.category AS category,
       rs.importance_level AS importance
ORDER BY rs.importance_level, s.name"""
    },
    {
        "question": "Show me employees who completed Kubernetes training and have the certification",
        "cypher": """MATCH (e:Employee)-[ct:COMPLETED_TRAINING]->(t:Training)
WHERE t.name CONTAINS 'Kubernetes' AND ct.status = 'Completed'
MATCH (e)-[:HOLDS_CERTIFICATION]->(c:Certification)
WHERE c.name CONTAINS 'Kubernetes'
AND e.employment_status = 'Active'
RETURN e.full_name AS name, e.designation AS designation,
       t.name AS training, ct.score AS training_score,
       c.name AS certification
ORDER BY ct.score DESC"""
    },
    {
        "question": "How many employees are in each department?",
        "cypher": """MATCH (e:Employee)-[:WORKS_IN]->(d:Department)
WHERE e.employment_status = 'Active'
RETURN d.name AS department, d.service_line AS service_line,
       count(e) AS employee_count
ORDER BY employee_count DESC"""
    },
    {
        "question": "Find available people for a new project requiring Python, AWS, and Machine Learning",
        "cypher": """MATCH (e:Employee)-[hs:HAS_SKILL]->(s:Skill)
WHERE s.name IN ['Python', 'AWS', 'Machine Learning']
AND hs.proficiency_level IN ['Advanced', 'Expert']
AND e.employment_status = 'Active'
WITH e, collect(DISTINCT s.name) AS matched_skills, count(DISTINCT s) AS skill_count
WHERE skill_count >= 2
OPTIONAL MATCH (e)-[a:ASSIGNED_TO]->(p:Project {status: 'Active'})
WITH e, matched_skills, sum(COALESCE(a.allocation_pct, 0)) AS current_allocation
WHERE current_allocation < 100
RETURN e.full_name AS name, e.designation AS designation,
       matched_skills, current_allocation AS current_allocation_pct,
       (100 - current_allocation) AS available_pct
ORDER BY available_pct DESC, size(matched_skills) DESC"""
    },
]


def get_few_shot_text() -> str:
    """Format few-shot examples as text for prompt injection."""
    lines = []
    for i, ex in enumerate(FEW_SHOT_EXAMPLES, 1):
        lines.append(f"Example {i}:")
        lines.append(f"Question: {ex['question']}")
        lines.append(f"Cypher:\n{ex['cypher']}")
        lines.append("")
    return "\n".join(lines)
