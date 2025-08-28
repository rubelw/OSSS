# versions/0020_seed_dept_position_index.py
from alembic import op
import sqlalchemy as sa
from io import StringIO
import csv

revision = "0020_seed_dept_position_index"
down_revision = "0019_add_dept_position_index"

def _has_column(conn, table, column) -> bool:
    insp = sa.inspect(conn)
    return any(c["name"] == column for c in insp.get_columns(table))

def _has_constraint(conn, table, constraint_name) -> bool:
    return conn.execute(
        sa.text("""
            SELECT 1
            FROM pg_constraint
            WHERE conrelid = :tbl::regclass
              AND conname = :cname
        """),
        {"tbl": table, "cname": constraint_name},
    ).first() is not None

def upgrade():
    conn = op.get_bind()

    # Ensure 'id' primary key and unique pair constraint exist (idempotent)
    if not _has_column(conn, "department_position_index", "id"):
        op.add_column(
            "department_position_index",
            sa.Column(
                "id",
                sa.dialects.postgresql.UUID(as_uuid=True),
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
        )
        if not _has_constraint(conn, "department_position_index", "department_position_index_pk"):
            op.create_primary_key(
                "department_position_index_pk",
                "department_position_index",
                ["id"],
            )
        if not _has_constraint(conn, "department_position_index", "uq_deptpos_pair"):
            op.create_unique_constraint(
                "uq_deptpos_pair",
                "department_position_index",
                ["department_id", "position_id"],
            )
        # drop the default so future inserts use explicit values only
        op.alter_column("department_position_index", "id", server_default=None)

    # ── Seed data from embedded CSV (columns: Position,Unit) ────────────────
    CSV_DATA = '''\
Position,Unit
Activity Sponsor,Athletics Activities Enrichment
Assistant Coach,Athletics Activities Enrichment
Athletic Trainer,Athletics Activities Enrichment
Club Sponsor,Athletics Activities Enrichment
Debate Coach,Athletics Activities Enrichment
Esports Coach,Athletics Activities Enrichment
Head Coach,Athletics Activities Enrichment
Performing Arts Director,Athletics Activities Enrichment
Robotics Coach,Athletics Activities Enrichment
Strength And Conditioning Coach,Athletics Activities Enrichment
Student Government Advisor,Athletics Activities Enrichment
Theater Director,Athletics Activities Enrichment
Yearbook Advisor,Athletics Activities Enrichment
Board Chair,Board Of Education Governing Board
Board Clerk,Board Of Education Governing Board
Board Vice Chair,Board Of Education Governing Board
School Board Member Trustee,Board Of Education Governing Board
Accountant,Business Accounting
Accounts Payable Specialist,Business Accounting
Accounts Receivable Specialist,Business Accounting
Business Manager,Business Accounting
Buyer,Business Accounting
Compliance Officer,Business Accounting
Controller,Business Accounting
E Rate Coordinator,Business Accounting
Federal Programs Director,Business Accounting
Grant Writer,Business Accounting
Grants Manager,Business Accounting
Insurance Coordinator,Business Accounting
Payroll Manager,Business Accounting
Payroll Specialist,Business Accounting
Purchasing Director,Business Accounting
Records Retention Manager,Business Accounting
Risk Manager,Business Accounting
Admissions Director,Communications Pr Advancement
Advancement Development Director,Communications Pr Advancement
Alumni Relations Director,Communications Pr Advancement
Annual Giving Manager,Communications Pr Advancement
Capital Campaign Manager,Communications Pr Advancement
Communications Director,Communications Pr Advancement
Community Engagement Coordinator,Communications Pr Advancement
Enrollment Director,Communications Pr Advancement
Family Engagement Coordinator,Communications Pr Advancement
Financial Aid Director,Communications Pr Advancement
Graphic Designer,Communications Pr Advancement
Interpreter Services Coordinator,Communications Pr Advancement
Major Gifts Officer,Communications Pr Advancement
Marketing Director,Communications Pr Advancement
Marketing Manager,Communications Pr Advancement
Media Relations Manager,Communications Pr Advancement
Public Relations Director,Communications Pr Advancement
Social Media Manager,Communications Pr Advancement
Translation Services Coordinator,Communications Pr Advancement
Accreditation Coordinator,Curriculum Instruction Assessment
Director Of Accountability,Curriculum Instruction Assessment
Director Of Assessment Research Evaluation,Curriculum Instruction Assessment
Director Of Curriculum And Instruction,Curriculum Instruction Assessment
Director Of Data Analytics,Curriculum Instruction Assessment
Instructional Materials Coordinator,Curriculum Instruction Assessment
Professional Development Coordinator,Curriculum Instruction Assessment
Teacher Induction Coordinator,Curriculum Instruction Assessment
Textbook Coordinator,Curriculum Instruction Assessment
Data Analyst,Data Sis Analytics
Data Engineer,Data Sis Analytics
Etl Developer,Data Sis Analytics
Sis Administrator,Data Sis Analytics
Chief Communications Officer,Division Of Communications Engagement
Chief Financial Officer,Division Of Finance
Chief Human Resources Officer,Division Of Human Resources
Human Resources Director,Division Of Human Resources
Chief Operations Officer,Division Of Operations
Chief Schools Officer,Division Of Schools
Chief Academic Officer,Division Of Teaching Learning Accountability
Director Of Student Support Services,Division Of Teaching Learning Accountability
Chief Information Officer,Division Of Technology Data
Chief Technology Officer,Division Of Technology Data
After School Program Director,Early Childhood Extended Programs
Before School Program Director,Early Childhood Extended Programs
Director Of Early Childhood,Early Childhood Extended Programs
Enrichment Coordinator,Early Childhood Extended Programs
Extended Day Coordinator,Early Childhood Extended Programs
Preschool Assistant,Early Childhood Extended Programs
Preschool Teacher,Early Childhood Extended Programs
Summer School Coordinator,Early Childhood Extended Programs
Carpenter,Facilities Maintenance
Custodial Supervisor,Facilities Maintenance
Custodian,Facilities Maintenance
Director Of Facilities,Facilities Maintenance
Electrician,Facilities Maintenance
Energy Manager,Facilities Maintenance
Facilities Manager,Facilities Maintenance
Groundskeeper,Facilities Maintenance
Hvac Technician,Facilities Maintenance
Inventory Specialist,Facilities Maintenance
Irrigation Technician,Facilities Maintenance
Locksmith,Facilities Maintenance
Maintenance Technician,Facilities Maintenance
Night Lead,Facilities Maintenance
Painter,Facilities Maintenance
Plant Manager,Facilities Maintenance
Plumber,Facilities Maintenance
Porter,Facilities Maintenance
Sustainability Manager,Facilities Maintenance
Warehouse Receiving,Facilities Maintenance
Campus Minister,Faith Based Religious If Applicable
Chaplain,Faith Based Religious If Applicable
Religion Teacher,Faith Based Religious If Applicable
Service Learning Coordinator,Faith Based Religious If Applicable
Theology Teacher,Faith Based Religious If Applicable
Administrative Assistant,Front Office School Support
Attendance Clerk,Front Office School Support
Data Clerk,Front Office School Support
Health Office Clerk,Front Office School Support
Office Manager,Front Office School Support
Receptionist,Front Office School Support
School Secretary,Front Office School Support
Sis Clerk,Front Office School Support
Student Services Clerk,Front Office School Support
Benefits Manager,Hr Operations Talent
Benefits Specialist,Hr Operations Talent
Hr Generalist,Hr Operations Talent
Hr Manager,Hr Operations Talent
Recruiter,Hr Operations Talent
Av Media Technician,It Infrastructure Support
Cloud Administrator,It Infrastructure Support
Database Administrator,It Infrastructure Support
Director Of Technology,It Infrastructure Support
Field Technician,It Infrastructure Support
Help Desk Manager,It Infrastructure Support
Help Desk Technician,It Infrastructure Support
Information Security Officer,It Infrastructure Support
It Director,It Infrastructure Support
Network Administrator,It Infrastructure Support
Server Administrator,It Infrastructure Support
Systems Administrator,It Infrastructure Support
Web Administrator,It Infrastructure Support
Webmaster,It Infrastructure Support
Baker,Nutrition Services
Cafeteria Manager,Nutrition Services
Cashier Point Of Sale Operator,Nutrition Services
Cook,Nutrition Services
Dietitian,Nutrition Services
Director Of Nutrition Services,Nutrition Services
Food Service Director,Nutrition Services
Kitchen Manager,Nutrition Services
Nutritionist,Nutrition Services
Prep Cook,Nutrition Services
Campus Police Officer,Safety Security Emergency Management
Campus Supervisor,Safety Security Emergency Management
Director Of Safety Security,Safety Security Emergency Management
Emergency Management Director,Safety Security Emergency Management
Emergency Preparedness Coordinator,Safety Security Emergency Management
School Resource Officer,Safety Security Emergency Management
Security Guard,Safety Security Emergency Management
Activities Director,School Leadership
Assistant Athletics Director,School Leadership
Assistant Principal,School Leadership
Associate Principal,School Leadership
Athletics Director,School Leadership
Dean Of Academics,School Leadership
Dean Of Students,School Leadership
Director Of Residential Life,School Leadership
Grade Level Dean,School Leadership
Head Of Lower School,School Leadership
Head Of Middle School,School Leadership
Head Of Upper School,School Leadership
Principal,School Leadership
Vice Principal,School Leadership
504 Coordinator,Special Education Related Services
Behavior Interventionist,Special Education Related Services
Board Certified Behavior Analyst,Special Education Related Services
Certified Occupational Therapy Assistant,Special Education Related Services
Deaf Hard Of Hearing Teacher,Special Education Related Services
Director Of Special Education,Special Education Related Services
Instructional Aide,Special Education Related Services
Occupational Therapist,Special Education Related Services
Orientation And Mobility Specialist,Special Education Related Services
Paraprofessional,Special Education Related Services
Physical Therapist,Special Education Related Services
Physical Therapist Assistant,Special Education Related Services
School Psychologist,Special Education Related Services
Sign Language Interpreter,Special Education Related Services
Special Education Teacher,Special Education Related Services
Sped Case Manager,Special Education Related Services
Sped Compliance Coordinator,Special Education Related Services
Speech Language Pathologist,Special Education Related Services
Teachers Aide,Special Education Related Services
Transition Specialist,Special Education Related Services
Vision Specialist,Special Education Related Services
Vocational Specialist,Special Education Related Services
Alternative Education Director,Special Programs
Ap Coordinator,Special Programs
Apprenticeship Coordinator,Special Programs
Archivist,Special Programs
Cte Director,Special Programs
Homestay Coordinator,Special Programs
Ib Coordinator,Special Programs
International Student Program Director,Special Programs
Librarian,Special Programs
Mailroom Clerk,Special Programs
Pathways Coordinator,Special Programs
Print Shop Manager,Special Programs
Testing Site Manager,Special Programs
Virtual Online Program Director,Special Programs
Volunteer Coordinator,Special Programs
Attendance Officer,Student Services School Level
Behavior Support Coach,Student Services School Level
College Counselor,Student Services School Level
Family Liaison,Student Services School Level
Financial Aid Advisor,Student Services School Level
Foster Care Liaison,Student Services School Level
Guidance Counselor,Student Services School Level
Health Aide,Student Services School Level
Mckinney Vento Liaison,Student Services School Level
Mtss Coordinator,Student Services School Level
Records Clerk,Student Services School Level
Registrar,Student Services School Level
Restorative Practices Coordinator,Student Services School Level
Rti Coordinator,Student Services School Level
School Counselor,Student Services School Level
School Nurse,Student Services School Level
School Social Worker,Student Services School Level
Testing And Assessment Coordinator,Student Services School Level
Truancy Officer,Student Services School Level
Assistant Superintendent,Superintendent S Office
Associate Superintendent,Superintendent S Office
Chief Equity Officer,Superintendent S Office
Chief Of Staff,Superintendent S Office
Deputy Superintendent,Superintendent S Office
General Counsel,Superintendent S Office
Head Of School,Superintendent S Office
Ombudsperson,Superintendent S Office
Superintendent,Superintendent S Office
Art Teacher,Teaching Instructional Support
Band Director,Teaching Instructional Support
Choir Director,Teaching Instructional Support
Classroom Teacher,Teaching Instructional Support
Computer Science Teacher,Teaching Instructional Support
Cte Teacher,Teaching Instructional Support
Early Childhood Teacher,Teaching Instructional Support
Elementary Teacher,Teaching Instructional Support
Health Teacher,Teaching Instructional Support
High School Teacher,Teaching Instructional Support
Instructional Coach,Teaching Instructional Support
Instructional Fellow,Teaching Instructional Support
Literacy Coach,Teaching Instructional Support
Long Term Substitute,Teaching Instructional Support
Math Coach,Teaching Instructional Support
Math Interventionist,Teaching Instructional Support
Media Specialist,Teaching Instructional Support
Mentor Teacher,Teaching Instructional Support
Middle School Teacher,Teaching Instructional Support
Music Teacher,Teaching Instructional Support
Physical Education Teacher,Teaching Instructional Support
Reading Interventionist,Teaching Instructional Support
Student Teacher,Teaching Instructional Support
Substitute Teacher,Teaching Instructional Support
Teacher Librarian,Teaching Instructional Support
Teacher Resident,Teaching Instructional Support
Theater Teacher,Teaching Instructional Support
World Languages Teacher,Teaching Instructional Support
Activity Driver,Transportation
Bus Aide Monitor,Transportation
Bus Driver,Transportation
Crossing Guard,Transportation
Diesel Technician,Transportation
Director Of Transportation,Transportation
Dispatcher,Transportation
Fleet Manager,Transportation
Mechanic,Transportation
Routing Scheduling Coordinator,Transportation
Shop Foreman,Transportation
'''.format(
        rows="""{csv_rows}"""
    )

    # Build normalized rows list
    reader = csv.DictReader(StringIO(CSV_DATA))
    rows = [{"pos": (r.get("Position") or "").strip(), "dept": (r.get("Unit") or "").strip()} for r in reader]
    rows = [r for r in rows if r["pos"] and r["dept"]]

    if rows:
        def _chunks(iterable, size=500):
            for i in range(0, len(iterable), size):
                yield iterable[i:i + size]

        # Insert in chunks via a VALUES CTE (no temp tables)
        for batch in _chunks(rows, 500):
            values_sql = []
            params = {}
            for i, r in enumerate(batch):
                values_sql.append(f"(:pos_{i}, :dept_{i})")
                params[f"pos_{i}"] = r["pos"]
                params[f"dept_{i}"] = r["dept"]

            sql = f"""
                    WITH s(pos_title, dept_name) AS (
                        VALUES {", ".join(values_sql)}
                    )
                    INSERT INTO department_position_index (department_id, position_id)
                    SELECT d.id, p.id
                    FROM s
                    JOIN hr_positions p
                      ON trim(lower(p.title)) = trim(lower(s.pos_title))
                    JOIN departments d
                      ON trim(lower(d.name)) = trim(lower(s.dept_name))
                    ON CONFLICT (department_id, position_id) DO NOTHING
                """
            conn.execute(sa.text(sql), params)

def downgrade():
    # No-op (seeding only). If needed, delete by matching CSV contents.
    pass
