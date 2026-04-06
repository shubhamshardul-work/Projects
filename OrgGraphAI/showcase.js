/* ══════════════════════════════════════════════════════════════
   OrgGraph AI — Showcase JS v2
   Real Neo4j data · Cinematic reveal · Interactive detail panel
   ══════════════════════════════════════════════════════════════ */

/* ── Palette ─────────────────────────────────────────── */
const C = {
  employee:      '#8b5cf6',
  manager:       '#a78bfa',
  department:    '#3b82f6',
  office:        '#06b6d4',
  skill:         '#10b981',
  project:       '#f59e0b',
  certification: '#ec4899',
};
function rgba(hex, a) {
  const v = hex.replace('#', '');
  return `rgba(${parseInt(v.slice(0,2),16)},${parseInt(v.slice(2,4),16)},${parseInt(v.slice(4,6),16)},${a})`;
}

/* ══════════════════════════════════════════════════════════════
   GRAPH DATA  —  extracted from knowledge_graph.txt (Neo4j export)
   5 employees across 4 departments, 5 offices, 5 countries
   ══════════════════════════════════════════════════════════════ */
const ALL_NODES = [
  /* ── 5 Main Employees ─────────────────────────────── */
  { id:'emp_ishita', label:'Ishita Aggarwal\nDirector', group:'employee', size:30,
    details:{ type:'Employee', empId:'EMP0005', fullName:'Ishita Aggarwal',
      designation:'Director', level:'L4', department:'Supply Chain & Operations',
      office:'Pune (OFF004)', experience:'20 yrs total · 4 yrs at org',
      education:'MCA in Electronics Eng., BITS Pilani', workMode:'On-site',
      skills:[
        {name:'Python',proficiency:'Intermediate',yrs:1.9,primary:true},
        {name:'React',proficiency:'Intermediate',yrs:2.3},
        {name:'Azure Data Factory',proficiency:'Advanced',yrs:3.7},
        {name:'Team Leadership',proficiency:'Expert',yrs:4.1},
        {name:'Stakeholder Mgmt',proficiency:'Advanced',yrs:6.8},
        {name:'JIRA',proficiency:'Intermediate',yrs:5.3},
      ],
      certifications:['Certified Scrum Master (CSM)','Snowflake SnowPro Core'],
      reviews:['2022 — Exceeds Expectations ✦','2023 — Exceeds Expectations ✦','2024 — Exceeds Expectations ✦'],
      trainings:['Power BI Advanced Analytics — Score: 72'],
    }},
  { id:'emp_aarti', label:'Aarti Naik\nAssoc. Director', group:'employee', size:28,
    details:{ type:'Employee', empId:'EMP0010', fullName:'Aarti Naik',
      designation:'Associate Director', level:'L5', department:'Digital Commerce',
      office:'Bangalore (OFF002)', experience:'17 yrs total · 13 yrs at org',
      education:'M.Sc in Computer Science, NIT Trichy', workMode:'Hybrid',
      skills:[
        {name:'Python',proficiency:'Advanced',yrs:7.4,primary:true},
        {name:'AWS',proficiency:'Expert',yrs:5.6},
        {name:'Kubernetes',proficiency:'Advanced',yrs:4.0},
        {name:'Problem Solving',proficiency:'Advanced',yrs:3.8},
      ],
      certifications:[],
      reviews:['2022 — Meets Expectations','2023 — Meets Expectations','2024 — Meets Expectations'],
      trainings:['Spark Performance Tuning — Score: 89','Cloud Architecture — Score: 100','Cybersecurity Awareness — Score: 70'],
    }},
  { id:'emp_ritesh', label:'Ritesh Shah\nTeam Lead', group:'employee', size:26,
    details:{ type:'Employee', empId:'EMP0050', fullName:'Ritesh Shah',
      designation:'Team Lead / Specialist', level:'L9', department:'Data & AI',
      office:'Sydney (OFF009)', experience:'6 yrs total · 4 yrs at org',
      education:'MCA in Math & Computing, Stanford', workMode:'Hybrid',
      skills:[
        {name:'Python',proficiency:'Advanced',yrs:3.2,primary:true},
        {name:'AWS',proficiency:'Advanced',yrs:0.7},
        {name:'MLflow',proficiency:'Expert',yrs:1.2},
        {name:'Project Management',proficiency:'Advanced',yrs:2.9},
        {name:'Team Leadership',proficiency:'Intermediate',yrs:1.6},
        {name:'Confluence',proficiency:'Beginner',yrs:4.8},
      ],
      certifications:['Tableau Desktop Specialist','HashiCorp Terraform Associate'],
      reviews:['2022 — Partially Meets','2023 — Partially Meets','2024 — Does Not Meet'],
      trainings:['Generative AI Fundamentals — Score: 81','Leadership Excellence Program — Score: 99','Cloud Architecture — Score: 97'],
    }},
  { id:'emp_ravi', label:'Ravi Naik\nSoftware Engineer', group:'employee', size:24,
    details:{ type:'Employee', empId:'EMP0100', fullName:'Ravi Naik',
      designation:'Software Engineer', level:'L11', department:'Data & AI',
      office:'Delhi NCR (OFF005)', experience:'2 yrs total · 2 yrs at org',
      education:'BCA in Computer Science, BITS Pilani', workMode:'Hybrid',
      skills:[
        {name:'GCP',proficiency:'Intermediate',yrs:1.2},
        {name:'Scala',proficiency:'Advanced',yrs:1.1},
        {name:'React',proficiency:'Advanced',yrs:1.0},
        {name:'Problem Solving',proficiency:'Beginner',yrs:1.8,primary:true},
      ],
      certifications:[],
      reviews:['2023 — Exceeds Expectations','2024 — Partially Meets'],
      trainings:['MLOps & Model Deployment — Score: 63','Power BI Analytics — In Progress','Generative AI Fundamentals — In Progress'],
    }},
  { id:'emp_sneha', label:'Sneha Mishra\nAssoc. SE', group:'employee', size:22,
    details:{ type:'Employee', empId:'EMP0150', fullName:'Sneha Mishra',
      designation:'Associate Software Engineer', level:'L12', department:'Strategy & Consulting',
      office:'Singapore (OFF008)', experience:'Intern · 2 yrs at org',
      education:'B.Sc in IT, IIIT Hyderabad', workMode:'Hybrid',
      skills:[
        {name:'Apache Kafka',proficiency:'Beginner',yrs:0.4,primary:true},
        {name:'Azure',proficiency:'Beginner',yrs:0.4},
        {name:'Power BI',proficiency:'Intermediate',yrs:0.3},
        {name:'Snowflake',proficiency:'Advanced',yrs:0.4},
        {name:'Project Management',proficiency:'Beginner',yrs:0.4},
        {name:'Team Leadership',proficiency:'Intermediate',yrs:0.1},
        {name:'Energy & Utilities',proficiency:'Expert',yrs:0.4},
        {name:'JIRA',proficiency:'Beginner',yrs:0.3},
        {name:'Git / GitHub',proficiency:'Beginner',yrs:0.4},
      ],
      certifications:['AWS Certified Data Engineer'],
      reviews:['2024 — Meets Expectations'],
      trainings:['Stakeholder Management Workshop — Score: 68','Advanced SQL Optimization — In Progress'],
    }},

  /* ── 5 Managers (reporting line) ──────────────────── */
  { id:'mgr_sophie', label:'Sophie Iyer\nManaging Director', group:'manager', size:20,
    details:{ type:'Manager', empId:'EMP0003', fullName:'Sophie Iyer', designation:'Managing Director',
      note:'Manages Ishita Aggarwal (Director)' }},
  { id:'mgr_varun', label:'Varun Tanaka\nDirector', group:'manager', size:18,
    details:{ type:'Manager', empId:'EMP0004', fullName:'Varun Tanaka', designation:'Director',
      note:'Manages Aarti Naik (Associate Director)' }},
  { id:'mgr_rchopra', label:'Ravi Chopra\nAssoc. Manager', group:'manager', size:18,
    details:{ type:'Manager', empId:'EMP0043', fullName:'Ravi Chopra', designation:'Associate Manager',
      note:'Manages Ritesh Shah (Team Lead)' }},
  { id:'mgr_rajesh', label:'Rajesh Kapoor\nTeam Lead', group:'manager', size:18,
    details:{ type:'Manager', empId:'EMP0051', fullName:'Rajesh Kapoor', designation:'Team Lead / Specialist',
      note:'Manages Ravi Naik (Software Engineer)' }},
  { id:'mgr_emily', label:'Emily Joshi\nTeam Lead', group:'manager', size:18,
    details:{ type:'Manager', empId:'EMP0055', fullName:'Emily Joshi', designation:'Team Lead / Specialist',
      note:'Manages Sneha Mishra (Associate SE)' }},

  /* ── 4 Departments ────────────────────────────────── */
  { id:'dept_supply', label:'Supply Chain\n& Operations', group:'department', size:22,
    details:{ type:'Department', id:'DEPT007', name:'Supply Chain & Operations', groupName:'Business Services' }},
  { id:'dept_digital', label:'Digital\nCommerce', group:'department', size:22,
    details:{ type:'Department', id:'DEPT004', name:'Digital Commerce', groupName:'Digital Group' }},
  { id:'dept_data', label:'Data & AI', group:'department', size:24,
    details:{ type:'Department', id:'DEPT001', name:'Data & AI', groupName:'Technology Group' }},
  { id:'dept_strategy', label:'Strategy &\nConsulting', group:'department', size:22,
    details:{ type:'Department', id:'DEPT009', name:'Strategy & Consulting', groupName:'Advisory' }},

  /* ── 5 Offices ────────────────────────────────────── */
  { id:'off_pune', label:'Pune\nOFF004', group:'office', size:18,
    details:{ type:'Office', id:'OFF004', city:'Pune', address:'Magarpatta City, Pune 411013', country:'India' }},
  { id:'off_blr', label:'Bangalore\nOFF002', group:'office', size:18,
    details:{ type:'Office', id:'OFF002', city:'Bangalore', address:'Manyata Tech Park, Hebbal 560045', country:'India' }},
  { id:'off_syd', label:'Sydney\nOFF009', group:'office', size:18,
    details:{ type:'Office', id:'OFF009', city:'Sydney', address:'Level 10, Sydney Olympic Park, NSW 2127', country:'Australia' }},
  { id:'off_del', label:'Delhi NCR\nOFF005', group:'office', size:18,
    details:{ type:'Office', id:'OFF005', city:'Delhi NCR', address:'DLF Cyber City, Gurugram 122002', country:'India' }},
  { id:'off_sgp', label:'Singapore\nOFF008', group:'office', size:18,
    details:{ type:'Office', id:'OFF008', city:'Singapore', address:'1 Harbourfront Place, 098633', country:'Singapore' }},

  /* ── 15 Skills ────────────────────────────────────── */
  { id:'skill_python',     label:'Python',              group:'skill', size:18,
    details:{ type:'Skill', name:'Python' }},
  { id:'skill_aws',        label:'AWS',                 group:'skill', size:16,
    details:{ type:'Skill', name:'AWS' }},
  { id:'skill_react',      label:'React',               group:'skill', size:15,
    details:{ type:'Skill', name:'React' }},
  { id:'skill_team_lead',  label:'Team\nLeadership',    group:'skill', size:17,
    details:{ type:'Skill', name:'Team Leadership' }},
  { id:'skill_problem',    label:'Problem\nSolving',    group:'skill', size:16,
    details:{ type:'Skill', name:'Problem Solving' }},
  { id:'skill_pm',         label:'Project\nManagement', group:'skill', size:16,
    details:{ type:'Skill', name:'Project Management' }},
  { id:'skill_jira',       label:'JIRA',                group:'skill', size:14,
    details:{ type:'Skill', name:'JIRA' }},
  { id:'skill_adf',        label:'Azure Data\nFactory', group:'skill', size:15,
    details:{ type:'Skill', name:'Azure Data Factory' }},
  { id:'skill_kubernetes',  label:'Kubernetes',          group:'skill', size:15,
    details:{ type:'Skill', name:'Kubernetes' }},
  { id:'skill_mlflow',     label:'MLflow',              group:'skill', size:15,
    details:{ type:'Skill', name:'MLflow' }},
  { id:'skill_scala',      label:'Scala',               group:'skill', size:14,
    details:{ type:'Skill', name:'Scala' }},
  { id:'skill_kafka',      label:'Apache\nKafka',       group:'skill', size:15,
    details:{ type:'Skill', name:'Apache Kafka' }},
  { id:'skill_powerbi',    label:'Power BI',            group:'skill', size:14,
    details:{ type:'Skill', name:'Power BI' }},
  { id:'skill_snowflake',  label:'Snowflake',           group:'skill', size:15,
    details:{ type:'Skill', name:'Snowflake' }},
  { id:'skill_stakeholder',label:'Stakeholder\nMgmt',   group:'skill', size:14,
    details:{ type:'Skill', name:'Stakeholder Management' }},

  /* ── 4 Projects ───────────────────────────────────── */
  { id:'proj_healthcare',  label:'Healthcare\nData Lake',      group:'project', size:20,
    details:{ type:'Project', id:'PRJ009', name:'Healthcare Data Lake', status:'Active', start:'2024-03-10' }},
  { id:'proj_idp',         label:'Intelligent Doc\nProcessing', group:'project', size:20,
    details:{ type:'Project', id:'PRJ011', name:'Intelligent Document Processing', status:'Completed', start:'2023-08-03' }},
  { id:'proj_ecommerce',   label:'E-commerce\nRecommendation', group:'project', size:20,
    details:{ type:'Project', id:'PRJ010', name:'E-commerce Recommendation Engine', status:'Active', start:'2024-05-01' }},
  { id:'proj_oracle',      label:'Oracle ERP\nCloud Migr.',    group:'project', size:19,
    details:{ type:'Project', id:'PRJ014', name:'Oracle ERP Cloud Migration', status:'Completed', start:'2023-02-28' }},

  /* ── 5 Certifications ─────────────────────────────── */
  { id:'cert_csm',       label:'Certified\nScrum Master',  group:'certification', size:16,
    details:{ type:'Certification', name:'Certified Scrum Master (CSM)', org:'Scrum Alliance' }},
  { id:'cert_snowpro',   label:'Snowflake\nSnowPro Core',  group:'certification', size:16,
    details:{ type:'Certification', name:'Snowflake SnowPro Core', org:'Snowflake' }},
  { id:'cert_tableau',   label:'Tableau\nDesktop Spec.',    group:'certification', size:16,
    details:{ type:'Certification', name:'Tableau Desktop Specialist', org:'Tableau / Salesforce' }},
  { id:'cert_terraform', label:'Terraform\nAssociate',      group:'certification', size:16,
    details:{ type:'Certification', name:'HashiCorp Terraform Associate', org:'HashiCorp' }},
  { id:'cert_aws_de',    label:'AWS Data\nEngineer',        group:'certification', size:16,
    details:{ type:'Certification', name:'AWS Certified Data Engineer', org:'Amazon Web Services' }},
];

/* ── Edges (50 total) ─────────────────────────────────── */
const ALL_EDGES = [
  /* REPORTS_TO (5) */
  { id:'e0',  from:'emp_ishita', to:'mgr_sophie',  label:'REPORTS_TO',             relType:'REPORTS_TO' },
  { id:'e1',  from:'emp_aarti',  to:'mgr_varun',   label:'REPORTS_TO',             relType:'REPORTS_TO' },
  { id:'e2',  from:'emp_ritesh', to:'mgr_rchopra',  label:'REPORTS_TO',             relType:'REPORTS_TO' },
  { id:'e3',  from:'emp_ravi',   to:'mgr_rajesh',  label:'REPORTS_TO',             relType:'REPORTS_TO' },
  { id:'e4',  from:'emp_sneha',  to:'mgr_emily',   label:'REPORTS_TO',             relType:'REPORTS_TO' },

  /* BELONGS_TO_DEPARTMENT (5) */
  { id:'e5',  from:'emp_ishita', to:'dept_supply',  label:'BELONGS_TO_DEPARTMENT',  relType:'BELONGS_TO_DEPARTMENT' },
  { id:'e6',  from:'emp_aarti',  to:'dept_digital', label:'BELONGS_TO_DEPARTMENT',  relType:'BELONGS_TO_DEPARTMENT' },
  { id:'e7',  from:'emp_ritesh', to:'dept_data',    label:'BELONGS_TO_DEPARTMENT',  relType:'BELONGS_TO_DEPARTMENT' },
  { id:'e8',  from:'emp_ravi',   to:'dept_data',    label:'BELONGS_TO_DEPARTMENT',  relType:'BELONGS_TO_DEPARTMENT' },
  { id:'e9',  from:'emp_sneha',  to:'dept_strategy',label:'BELONGS_TO_DEPARTMENT',  relType:'BELONGS_TO_DEPARTMENT' },

  /* LOCATED_AT_OFFICE (5) */
  { id:'e10', from:'emp_ishita', to:'off_pune',     label:'LOCATED_AT_OFFICE',      relType:'LOCATED_AT_OFFICE' },
  { id:'e11', from:'emp_aarti',  to:'off_blr',      label:'LOCATED_AT_OFFICE',      relType:'LOCATED_AT_OFFICE' },
  { id:'e12', from:'emp_ritesh', to:'off_syd',      label:'LOCATED_AT_OFFICE',      relType:'LOCATED_AT_OFFICE' },
  { id:'e13', from:'emp_ravi',   to:'off_del',      label:'LOCATED_AT_OFFICE',      relType:'LOCATED_AT_OFFICE' },
  { id:'e14', from:'emp_sneha',  to:'off_sgp',      label:'LOCATED_AT_OFFICE',      relType:'LOCATED_AT_OFFICE' },

  /* HAS_SKILL — Ishita (6) */
  { id:'e15', from:'emp_ishita', to:'skill_python',      label:'HAS_SKILL', relType:'HAS_SKILL' },
  { id:'e16', from:'emp_ishita', to:'skill_react',       label:'HAS_SKILL', relType:'HAS_SKILL' },
  { id:'e17', from:'emp_ishita', to:'skill_adf',         label:'HAS_SKILL', relType:'HAS_SKILL' },
  { id:'e18', from:'emp_ishita', to:'skill_team_lead',   label:'HAS_SKILL', relType:'HAS_SKILL' },
  { id:'e19', from:'emp_ishita', to:'skill_stakeholder', label:'HAS_SKILL', relType:'HAS_SKILL' },
  { id:'e20', from:'emp_ishita', to:'skill_jira',        label:'HAS_SKILL', relType:'HAS_SKILL' },
  /* HAS_SKILL — Aarti (4) */
  { id:'e21', from:'emp_aarti',  to:'skill_python',      label:'HAS_SKILL', relType:'HAS_SKILL' },
  { id:'e22', from:'emp_aarti',  to:'skill_aws',         label:'HAS_SKILL', relType:'HAS_SKILL' },
  { id:'e23', from:'emp_aarti',  to:'skill_kubernetes',  label:'HAS_SKILL', relType:'HAS_SKILL' },
  { id:'e24', from:'emp_aarti',  to:'skill_problem',     label:'HAS_SKILL', relType:'HAS_SKILL' },
  /* HAS_SKILL — Ritesh (5) */
  { id:'e25', from:'emp_ritesh', to:'skill_python',      label:'HAS_SKILL', relType:'HAS_SKILL' },
  { id:'e26', from:'emp_ritesh', to:'skill_aws',         label:'HAS_SKILL', relType:'HAS_SKILL' },
  { id:'e27', from:'emp_ritesh', to:'skill_mlflow',      label:'HAS_SKILL', relType:'HAS_SKILL' },
  { id:'e28', from:'emp_ritesh', to:'skill_pm',          label:'HAS_SKILL', relType:'HAS_SKILL' },
  { id:'e29', from:'emp_ritesh', to:'skill_team_lead',   label:'HAS_SKILL', relType:'HAS_SKILL' },
  /* HAS_SKILL — Ravi (3) */
  { id:'e30', from:'emp_ravi',   to:'skill_scala',       label:'HAS_SKILL', relType:'HAS_SKILL' },
  { id:'e31', from:'emp_ravi',   to:'skill_react',       label:'HAS_SKILL', relType:'HAS_SKILL' },
  { id:'e32', from:'emp_ravi',   to:'skill_problem',     label:'HAS_SKILL', relType:'HAS_SKILL' },
  /* HAS_SKILL — Sneha (6) */
  { id:'e33', from:'emp_sneha',  to:'skill_kafka',       label:'HAS_SKILL', relType:'HAS_SKILL' },
  { id:'e34', from:'emp_sneha',  to:'skill_powerbi',     label:'HAS_SKILL', relType:'HAS_SKILL' },
  { id:'e35', from:'emp_sneha',  to:'skill_snowflake',   label:'HAS_SKILL', relType:'HAS_SKILL' },
  { id:'e36', from:'emp_sneha',  to:'skill_pm',          label:'HAS_SKILL', relType:'HAS_SKILL' },
  { id:'e37', from:'emp_sneha',  to:'skill_team_lead',   label:'HAS_SKILL', relType:'HAS_SKILL' },
  { id:'e38', from:'emp_sneha',  to:'skill_jira',        label:'HAS_SKILL', relType:'HAS_SKILL' },

  /* ASSIGNED_TO_PROJECT (6) */
  { id:'e39', from:'emp_aarti',  to:'proj_healthcare',  label:'ASSIGNED_TO_PROJECT',  relType:'ASSIGNED_TO_PROJECT' },
  { id:'e40', from:'emp_aarti',  to:'proj_idp',         label:'ASSIGNED_TO_PROJECT',  relType:'ASSIGNED_TO_PROJECT' },
  { id:'e41', from:'emp_ravi',   to:'proj_ecommerce',   label:'ASSIGNED_TO_PROJECT',  relType:'ASSIGNED_TO_PROJECT' },
  { id:'e42', from:'emp_ravi',   to:'proj_oracle',      label:'ASSIGNED_TO_PROJECT',  relType:'ASSIGNED_TO_PROJECT' },
  { id:'e43', from:'emp_sneha',  to:'proj_ecommerce',   label:'ASSIGNED_TO_PROJECT',  relType:'ASSIGNED_TO_PROJECT' },
  { id:'e44', from:'emp_sneha',  to:'proj_idp',         label:'ASSIGNED_TO_PROJECT',  relType:'ASSIGNED_TO_PROJECT' },

  /* HOLDS_CERTIFICATION (5) */
  { id:'e45', from:'emp_ishita', to:'cert_csm',       label:'HOLDS_CERTIFICATION',  relType:'HOLDS_CERTIFICATION' },
  { id:'e46', from:'emp_ishita', to:'cert_snowpro',   label:'HOLDS_CERTIFICATION',  relType:'HOLDS_CERTIFICATION' },
  { id:'e47', from:'emp_ritesh', to:'cert_tableau',   label:'HOLDS_CERTIFICATION',  relType:'HOLDS_CERTIFICATION' },
  { id:'e48', from:'emp_ritesh', to:'cert_terraform', label:'HOLDS_CERTIFICATION',  relType:'HOLDS_CERTIFICATION' },
  { id:'e49', from:'emp_sneha',  to:'cert_aws_de',    label:'HOLDS_CERTIFICATION',  relType:'HOLDS_CERTIFICATION' },
];

/* ══════════════════════════════════════════════════════════════
   VIS.JS NODE STYLES
   ══════════════════════════════════════════════════════════════ */
const NODE_STYLES = {
  employee:{
    shape:'dot',
    color:{ background:rgba(C.employee,.9), border:C.employee,
            highlight:{background:'#a78bfa',border:'#c4b5fd'} },
    font:{ color:'#f3f4f6', size:13, face:'Inter, sans-serif', multi:'md' },
    borderWidth:3, shadow:{ enabled:true, color:rgba(C.employee,.35), size:20, x:0, y:0 },
  },
  manager:{
    shape:'dot',
    color:{ background:rgba(C.manager,.7), border:rgba(C.manager,.9),
            highlight:{background:'#c4b5fd',border:'#ddd6fe'} },
    font:{ color:'#e2e8f0', size:11, face:'Inter, sans-serif', multi:'md' },
    borderWidth:2, shadow:{ enabled:true, color:rgba(C.manager,.2), size:12, x:0, y:0 },
  },
  department:{
    shape:'box',
    color:{ background:rgba(C.department,.12), border:rgba(C.department,.7),
            highlight:{background:rgba(C.department,.22),border:'#93c5fd'} },
    font:{ color:'#dbeafe', size:12, face:'Inter, sans-serif', multi:'md' },
    borderWidth:2, margin:12,
  },
  office:{
    shape:'box',
    color:{ background:rgba(C.office,.10), border:rgba(C.office,.7),
            highlight:{background:rgba(C.office,.20),border:'#67e8f9'} },
    font:{ color:'#cffafe', size:11, face:'Inter, sans-serif', multi:'md' },
    borderWidth:2, margin:10,
  },
  skill:{
    shape:'ellipse',
    color:{ background:rgba(C.skill,.12), border:rgba(C.skill,.8),
            highlight:{background:rgba(C.skill,.22),border:'#6ee7b7'} },
    font:{ color:'#d1fae5', size:11, face:'Inter, sans-serif', multi:'md' },
    borderWidth:2, margin:8,
  },
  project:{
    shape:'hexagon',
    color:{ background:rgba(C.project,.14), border:rgba(C.project,.8),
            highlight:{background:rgba(C.project,.24),border:'#fcd34d'} },
    font:{ color:'#fef3c7', size:11, face:'Inter, sans-serif', multi:'md' },
    borderWidth:2, margin:12,
  },
  certification:{
    shape:'diamond',
    color:{ background:rgba(C.certification,.12), border:rgba(C.certification,.8),
            highlight:{background:rgba(C.certification,.22),border:'#f9a8d4'} },
    font:{ color:'#fce7f3', size:10, face:'Inter, sans-serif', multi:'md' },
    borderWidth:2, margin:10,
  },
};

const EDGE_STYLES = {
  REPORTS_TO:             { color:rgba(C.manager,.5),       width:2.5 },
  BELONGS_TO_DEPARTMENT:  { color:rgba(C.department,.4),    width:2.0 },
  LOCATED_AT_OFFICE:      { color:rgba(C.office,.35),       width:1.6, dashes:true },
  HAS_SKILL:              { color:rgba(C.skill,.4),         width:1.6 },
  ASSIGNED_TO_PROJECT:    { color:rgba(C.project,.45),      width:2.0 },
  HOLDS_CERTIFICATION:    { color:rgba(C.certification,.4), width:1.6 },
};

/* ══════════════════════════════════════════════════════════════
   DETAIL PANEL RENDERING
   ══════════════════════════════════════════════════════════════ */
function renderDetail(nodeId) {
  const node = ALL_NODES.find(n => n.id === nodeId);
  if (!node || !node.details) return '';
  const d = node.details;

  switch (d.type) {
    case 'Employee': return renderEmployee(d);
    case 'Manager':  return renderManager(d);
    case 'Department': return renderDepartment(d, nodeId);
    case 'Office':   return renderOffice(d, nodeId);
    case 'Skill':    return renderSkillDetail(d, nodeId);
    case 'Project':  return renderProject(d, nodeId);
    case 'Certification': return renderCert(d, nodeId);
    default: return '';
  }
}

function badge(label, color) {
  return `<div class="detail-type-badge" style="background:${rgba(color,.12)};color:${color};border:1px solid ${rgba(color,.25)}">${label}</div>`;
}

function renderEmployee(d) {
  let html = badge('Employee', C.employee);
  html += `<div class="detail-name">${d.fullName}</div>`;
  html += `<div class="detail-role">${d.designation} · ${d.level}</div>`;
  html += `<div class="detail-meta">`;
  html += `<div class="meta-item"><i class="ph ph-identification-badge"></i> ${d.empId}</div>`;
  html += `<div class="meta-item"><i class="ph ph-buildings"></i> ${d.department}</div>`;
  html += `<div class="meta-item"><i class="ph ph-map-pin"></i> ${d.office}</div>`;
  html += `<div class="meta-item"><i class="ph ph-briefcase"></i> ${d.experience}</div>`;
  html += `<div class="meta-item"><i class="ph ph-graduation-cap"></i> ${d.education}</div>`;
  html += `<div class="meta-item"><i class="ph ph-desktop"></i> ${d.workMode}</div>`;
  html += `</div>`;

  /* Skills */
  html += `<div class="detail-section"><h4><i class="ph ph-lightbulb"></i> Skills (${d.skills.length})</h4><div class="skill-tags">`;
  d.skills.forEach(s => {
    html += `<span class="skill-tag${s.primary?' primary':''}">${s.name} · ${s.proficiency}${s.yrs ? ' · '+s.yrs+'y' : ''}</span>`;
  });
  html += `</div></div>`;

  /* Certifications */
  if (d.certifications && d.certifications.length) {
    html += `<div class="detail-section"><h4><i class="ph ph-certificate"></i> Certifications</h4><ul class="detail-list">`;
    d.certifications.forEach(c => { html += `<li><i class="ph ph-seal-check"></i> ${c}</li>`; });
    html += `</ul></div>`;
  }

  /* Reviews */
  if (d.reviews && d.reviews.length) {
    html += `<div class="detail-section"><h4><i class="ph ph-star"></i> Performance Reviews</h4><ul class="detail-list">`;
    d.reviews.forEach(r => { html += `<li><i class="ph ph-chart-line-up"></i> ${r}</li>`; });
    html += `</ul></div>`;
  }

  /* Trainings */
  if (d.trainings && d.trainings.length) {
    html += `<div class="detail-section"><h4><i class="ph ph-book-open"></i> Trainings</h4><ul class="detail-list">`;
    d.trainings.forEach(t => { html += `<li><i class="ph ph-notebook"></i> ${t}</li>`; });
    html += `</ul></div>`;
  }

  return html;
}

function renderManager(d) {
  let html = badge('Manager', C.manager);
  html += `<div class="detail-name">${d.fullName}</div>`;
  html += `<div class="detail-role">${d.designation}</div>`;
  html += `<div class="detail-meta">`;
  html += `<div class="meta-item"><i class="ph ph-identification-badge"></i> ${d.empId}</div>`;
  html += `</div>`;
  html += `<div class="detail-section"><h4><i class="ph ph-users"></i> Reporting Line</h4>`;
  html += `<p style="font-size:.84rem;color:#9ca3af">${d.note}</p></div>`;
  return html;
}

function renderDepartment(d, nodeId) {
  let html = badge('Department', C.department);
  html += `<div class="detail-name">${d.name}</div>`;
  html += `<div class="detail-role">${d.id} · ${d.groupName}</div>`;
  html += `<div class="detail-section"><h4><i class="ph ph-users"></i> Employees</h4>`;
  getConnectedEmps(nodeId, 'BELONGS_TO_DEPARTMENT').forEach(emp => {
    html += `<div class="connected-emp"><i class="ph ph-user"></i> <strong>${emp.details.fullName}</strong> — ${emp.details.designation}</div>`;
  });
  html += `</div>`;
  return html;
}

function renderOffice(d, nodeId) {
  let html = badge('Office', C.office);
  html += `<div class="detail-name">${d.city}</div>`;
  html += `<div class="detail-role">${d.id} · ${d.country}</div>`;
  html += `<div class="detail-meta"><div class="meta-item"><i class="ph ph-map-pin"></i> ${d.address}</div></div>`;
  html += `<div class="detail-section"><h4><i class="ph ph-users"></i> Employees</h4>`;
  getConnectedEmps(nodeId, 'LOCATED_AT_OFFICE').forEach(emp => {
    html += `<div class="connected-emp"><i class="ph ph-user"></i> <strong>${emp.details.fullName}</strong> — ${emp.details.designation}</div>`;
  });
  html += `</div>`;
  return html;
}

function renderSkillDetail(d, nodeId) {
  let html = badge('Skill', C.skill);
  html += `<div class="detail-name">${d.name}</div>`;
  html += `<div class="detail-section"><h4><i class="ph ph-users"></i> Employees with this skill</h4>`;
  const emps = getConnectedEmps(nodeId, 'HAS_SKILL');
  emps.forEach(emp => {
    const skillInfo = emp.details.skills?.find(s => s.name === d.name);
    const prof = skillInfo ? skillInfo.proficiency : '';
    const yrs = skillInfo ? skillInfo.yrs + 'y' : '';
    html += `<div class="connected-emp"><i class="ph ph-user"></i> <strong>${emp.details.fullName}</strong> — ${prof} ${yrs}</div>`;
  });
  html += `</div>`;
  return html;
}

function renderProject(d, nodeId) {
  let html = badge('Project', C.project);
  html += `<div class="detail-name">${d.name}</div>`;
  html += `<div class="detail-role">${d.id} · ${d.status}</div>`;
  html += `<div class="detail-meta"><div class="meta-item"><i class="ph ph-calendar"></i> Started ${d.start}</div></div>`;
  html += `<div class="detail-section"><h4><i class="ph ph-users"></i> Assigned Employees</h4>`;
  getConnectedEmps(nodeId, 'ASSIGNED_TO_PROJECT').forEach(emp => {
    html += `<div class="connected-emp"><i class="ph ph-user"></i> <strong>${emp.details.fullName}</strong> — ${emp.details.designation}</div>`;
  });
  html += `</div>`;
  return html;
}

function renderCert(d, nodeId) {
  let html = badge('Certification', C.certification);
  html += `<div class="detail-name">${d.name}</div>`;
  html += `<div class="detail-role">${d.org}</div>`;
  html += `<div class="detail-section"><h4><i class="ph ph-users"></i> Held by</h4>`;
  getConnectedEmps(nodeId, 'HOLDS_CERTIFICATION').forEach(emp => {
    html += `<div class="connected-emp"><i class="ph ph-user"></i> <strong>${emp.details.fullName}</strong></div>`;
  });
  html += `</div>`;
  return html;
}

function getConnectedEmps(nodeId, relType) {
  return ALL_EDGES
    .filter(e => e.relType === relType && e.to === nodeId)
    .map(e => ALL_NODES.find(n => n.id === e.from))
    .filter(Boolean);
}

/* ══════════════════════════════════════════════════════════════
   GRAPH INITIALIZATION & CINEMATIC REVEAL
   ══════════════════════════════════════════════════════════════ */
let network = null;
let nodesDS = null;
let edgesDS = null;

function initGraph() {
  const container = document.getElementById('graph-canvas');
  const loader = document.getElementById('graph-loader');
  if (!container) return;

  /* 1. Build vis.js DataSets with styled nodes */
  const styledNodes = ALL_NODES.map(n => ({
    ...n,
    ...NODE_STYLES[n.group],
    physics: true,
  }));
  const styledEdges = ALL_EDGES.map(e => {
    const st = EDGE_STYLES[e.relType] || { color: '#444', width: 1 };
    return {
      ...e,
      arrows: { to: { enabled: true, scaleFactor: 0.5 } },
      smooth: { enabled: true, type: 'cubicBezier', roundness: 0.18 },
      font: { color:'#64748b', size: e.label.length > 16 ? 7 : 8, face:'Inter, sans-serif', strokeWidth:3, strokeColor:'#020205', align:'middle' },
      color: { color: st.color },
      width: st.width,
      dashes: st.dashes || false,
    };
  });

  nodesDS = new vis.DataSet(styledNodes);
  edgesDS = new vis.DataSet(styledEdges);

  /* 2. Create network with physics — stabilization runs before first paint */
  network = new vis.Network(container, { nodes: nodesDS, edges: edgesDS }, {
    autoResize: true,
    physics: {
      enabled: true,
      stabilization: { enabled: true, iterations: 350, fit: true },
      barnesHut: {
        gravitationalConstant: -4500,
        centralGravity: 0.25,
        springLength: 160,
        springConstant: 0.018,
        damping: 0.12,
        avoidOverlap: 0.45,
      },
    },
    interaction: {
      hover: true, tooltipDelay: 200,
      dragNodes: true, zoomView: true, dragView: true,
    },
    layout: { improvedLayout: true },
  });

  /* 3. After stabilization — freeze, hide, reveal */
  network.once('stabilizationIterationsDone', () => {
    const positions = network.getPositions();

    /* Freeze physics, fix all node positions */
    network.setOptions({ physics: false });
    const fixUpdates = ALL_NODES.map(n => ({
      id: n.id,
      x: positions[n.id].x,
      y: positions[n.id].y,
      fixed: { x: true, y: true },
      hidden: true,
    }));
    nodesDS.update(fixUpdates);
    edgesDS.update(ALL_EDGES.map(e => ({ id: e.id, hidden: true })));

    /* Hide loader */
    loader.classList.add('hidden');

    /* Start cinematic reveal */
    revealGraph();
  });

  /* 4. Interaction handlers */
  network.on('click', params => {
    if (params.nodes.length > 0) {
      showDetail(params.nodes[0]);
      highlightConnected(params.nodes[0]);
    } else {
      hideDetail();
      resetHighlight();
    }
  });

  network.on('hoverNode', params => {
    container.style.cursor = 'pointer';
  });
  network.on('blurNode', () => {
    container.style.cursor = 'default';
  });

  /* Filter toolbar */
  document.querySelectorAll('.graph-filter').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.graph-filter').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      applyFilter(btn.dataset.filter);
    });
  });

  /* Replay button */
  document.getElementById('replay-btn')?.addEventListener('click', () => {
    hideDetail();
    resetHighlight();
    nodesDS.update(ALL_NODES.map(n => ({ id: n.id, hidden: true })));
    edgesDS.update(ALL_EDGES.map(e => ({ id: e.id, hidden: true })));
    revealGraph();
  });
}

/* ── Cinematic Staged Reveal ─────────────────────────── */
function revealGraph() {
  const empIds = ALL_NODES.filter(n => n.group === 'employee').map(n => n.id);
  const mgrIds = ALL_NODES.filter(n => n.group === 'manager').map(n => n.id);
  const deptIds = ALL_NODES.filter(n => n.group === 'department').map(n => n.id);
  const offIds = ALL_NODES.filter(n => n.group === 'office').map(n => n.id);
  const skillIds = ALL_NODES.filter(n => n.group === 'skill').map(n => n.id);
  const projIds = ALL_NODES.filter(n => n.group === 'project').map(n => n.id);
  const certIds = ALL_NODES.filter(n => n.group === 'certification').map(n => n.id);

  const structEdges = ALL_EDGES.filter(e => ['REPORTS_TO','BELONGS_TO_DEPARTMENT','LOCATED_AT_OFFICE'].includes(e.relType)).map(e => e.id);
  const skillEdges = ALL_EDGES.filter(e => e.relType === 'HAS_SKILL').map(e => e.id);
  const projEdges = ALL_EDGES.filter(e => e.relType === 'ASSIGNED_TO_PROJECT').map(e => e.id);
  const certEdges = ALL_EDGES.filter(e => e.relType === 'HOLDS_CERTIFICATION').map(e => e.id);

  const stages = [
    { ids: empIds,       type: 'node', delay: 90 },
    { ids: mgrIds,       type: 'node', delay: 70 },
    { ids: deptIds,      type: 'node', delay: 55 },
    { ids: offIds,       type: 'node', delay: 55 },
    { ids: structEdges,  type: 'edge', delay: 28 },
    { ids: skillIds,     type: 'node', delay: 40 },
    { ids: skillEdges,   type: 'edge', delay: 22 },
    { ids: projIds,      type: 'node', delay: 55 },
    { ids: certIds,      type: 'node', delay: 55 },
    { ids: projEdges,    type: 'edge', delay: 30 },
    { ids: certEdges,    type: 'edge', delay: 30 },
  ];

  let t = 300; /* initial delay */
  stages.forEach(stage => {
    stage.ids.forEach((id, i) => {
      setTimeout(() => {
        if (stage.type === 'node') nodesDS.update({ id, hidden: false });
        else edgesDS.update({ id, hidden: false });
      }, t + i * stage.delay);
    });
    t += stage.ids.length * stage.delay + 120;
  });

  /* Final fit */
  setTimeout(() => {
    network.fit({ animation: { duration: 700, easingFunction: 'easeInOutQuad' } });
  }, t + 200);
}

/* ── Highlight connected nodes on click ──────────────── */
let selectedNode = null;

function highlightConnected(nodeId) {
  selectedNode = nodeId;
  const connNodes = new Set(network.getConnectedNodes(nodeId));
  connNodes.add(nodeId);
  const connEdges = new Set(network.getConnectedEdges(nodeId));

  nodesDS.update(ALL_NODES.map(n => {
    const active = connNodes.has(n.id);
    return {
      id: n.id,
      opacity: active ? 1.0 : 0.15,
      font: { ...(NODE_STYLES[n.group].font), color: active ? (NODE_STYLES[n.group].font.color) : 'rgba(148,163,184,0.2)' },
    };
  }));
  edgesDS.update(ALL_EDGES.map(e => ({
    id: e.id,
    hidden: !connEdges.has(e.id),
  })));
}

function resetHighlight() {
  selectedNode = null;
  nodesDS.update(ALL_NODES.map(n => ({
    id: n.id,
    opacity: 1.0,
    hidden: false,
    font: NODE_STYLES[n.group].font,
  })));
  edgesDS.update(ALL_EDGES.map(e => ({ id: e.id, hidden: false })));
}

/* ── Filter toolbar ──────────────────────────────────── */
function applyFilter(mode) {
  hideDetail();
  if (mode === 'all') { resetHighlight(); return; }

  const showGroups = {
    employees: ['employee','manager','department','office'],
    skills:    ['employee','skill'],
    projects:  ['employee','project'],
    certs:     ['employee','certification'],
  }[mode] || [];

  const showRelTypes = {
    employees: ['REPORTS_TO','BELONGS_TO_DEPARTMENT','LOCATED_AT_OFFICE'],
    skills:    ['HAS_SKILL'],
    projects:  ['ASSIGNED_TO_PROJECT'],
    certs:     ['HOLDS_CERTIFICATION'],
  }[mode] || [];

  nodesDS.update(ALL_NODES.map(n => ({
    id: n.id,
    hidden: !showGroups.includes(n.group),
    opacity: 1.0,
    font: NODE_STYLES[n.group].font,
  })));
  edgesDS.update(ALL_EDGES.map(e => ({
    id: e.id,
    hidden: !showRelTypes.includes(e.relType),
  })));

  setTimeout(() => {
    network.fit({ animation: { duration: 500, easingFunction: 'easeInOutQuad' } });
  }, 100);
}

/* ── Detail Panel Show/Hide ──────────────────────────── */
function showDetail(nodeId) {
  const placeholder = document.getElementById('detail-placeholder');
  const content = document.getElementById('detail-content');
  const inner = document.getElementById('detail-inner');
  if (!content || !inner) return;

  inner.innerHTML = renderDetail(nodeId);
  placeholder.style.display = 'none';
  content.style.display = 'block';
  /* Re-trigger animation */
  content.style.animation = 'none';
  content.offsetHeight; /* reflow */
  content.style.animation = '';
}

function hideDetail() {
  const placeholder = document.getElementById('detail-placeholder');
  const content = document.getElementById('detail-content');
  if (placeholder) placeholder.style.display = '';
  if (content) content.style.display = 'none';
}

/* ══════════════════════════════════════════════════════════════
   GSAP SCROLL ANIMATIONS & COUNTER
   ══════════════════════════════════════════════════════════════ */
function initAnimations() {
  gsap.registerPlugin(ScrollTrigger);

  /* Animate sections on scroll */
  gsap.utils.toArray('.anim-in').forEach((el, i) => {
    gsap.to(el, {
      scrollTrigger: { trigger: el, start: 'top 88%', once: true },
      y: 0, opacity: 1, duration: 0.75, delay: i * 0.05,
      ease: 'power2.out',
    });
  });

  /* Animated stat counters */
  document.querySelectorAll('.stat-number[data-target]').forEach(el => {
    const target = parseInt(el.dataset.target, 10);
    ScrollTrigger.create({
      trigger: el,
      start: 'top 90%',
      once: true,
      onEnter: () => animateCounter(el, target),
    });
  });
}

function animateCounter(el, target) {
  const duration = 1800;
  const start = performance.now();
  function tick(now) {
    const progress = Math.min((now - start) / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    el.textContent = Math.round(target * eased).toLocaleString();
    if (progress < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

/* ══════════════════════════════════════════════════════════════
   INIT
   ══════════════════════════════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', () => {
  initAnimations();
  initGraph();

  /* Detail panel close button */
  document.getElementById('detail-close')?.addEventListener('click', () => {
    hideDetail();
    resetHighlight();
  });
});
