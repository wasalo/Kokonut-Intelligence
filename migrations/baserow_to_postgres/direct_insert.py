#!/usr/bin/env python3
"""
Direct PostgreSQL insertion for Baserow migration.
This bypasses Directus API for tables that don't have collection metadata.
"""

import requests
import json
import time
import psycopg2
import sys
import os
from datetime import datetime

# Database connection - read from environment variables
DB_CONFIG = {
    'host': os.environ.get('PGHOST', 'localhost'),
    'port': int(os.environ.get('PGPORT', 5432)),
    'database': os.environ.get('PGDATABASE', 'kokonut_intelligence'),
    'user': os.environ.get('PGUSER', 'kokonut'),
    'password': os.environ.get('PGPASSWORD', '')
}

# Baserow API - read from environment variables
BASEROW_URL = os.environ.get('BASEROW_URL', 'https://api.baserow.io')
BASEROW_TOKEN = os.environ.get('BASEROW_TOKEN', '')
BASEROW_HEADERS = {'Authorization': f'Token {BASEROW_TOKEN}'}

# Get first location ID as default
def get_default_location_id():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT id FROM location LIMIT 1")
    result = cur.fetchone()
    cur.close()
    conn.close()
    return result[0] if result else None

# Get all locations for location mapping
def get_all_locations():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM location")
    locations = {row[1]: row[0] for row in cur.fetchall()}
    cur.close()
    conn.close()
    return locations

def fetch_baserow_rows(table_id):
    """Fetch all rows from a Baserow table."""
    all_rows = []
    page = 1
    while True:
        resp = requests.get(
            f'{BASEROW_URL}/api/database/rows/table/{table_id}/',
            headers=BASEROW_HEADERS,
            params={'user_field_names': 'true', 'page': page, 'size': 200}
        )
        resp.raise_for_status()
        data = resp.json()
        all_rows.extend(data.get('results', []))
        if not data.get('next'):
            break
        page += 1
        time.sleep(0.1)
    return all_rows

def insert_department(rows):
    """Insert departments."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    count = 0
    for row in rows:
        try:
            cur.execute("""
                INSERT INTO department (name, description)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
            """, (
                row.get('Name', ''),
                row.get('Description', '')
            ))
            count += 1
        except Exception as e:
            print(f"  Error inserting department: {e}")
    conn.commit()
    cur.close()
    conn.close()
    return count

def insert_job_role(rows):
    """Insert job roles."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # Get department IDs
    cur.execute("SELECT id, name FROM department")
    dept_map = {row[1]: row[0] for row in cur.fetchall()}
    
    count = 0
    for row in rows:
        try:
            dept_name = row.get('Department', '')
            # Handle link_row field (list of objects)
            if isinstance(dept_name, list) and dept_name:
                dept_name = dept_name[0].get('value', '') if isinstance(dept_name[0], dict) else str(dept_name[0])
            elif isinstance(dept_name, dict):
                dept_name = dept_name.get('value', '')
            dept_id = dept_map.get(dept_name)
            
            cur.execute("""
                INSERT INTO job_role (name, description, department_id)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (
                row.get('Name', ''),
                row.get('Description', ''),
                dept_id
            ))
            count += 1
        except Exception as e:
            print(f"  Error inserting job_role: {e}")
    conn.commit()
    cur.close()
    conn.close()
    return count

def insert_farm_task(rows):
    """Insert farm tasks."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    default_location = get_default_location_id()
    count = 0
    for row in rows:
        try:
            # Extract simple fields, skip link_row fields
            title = row.get('Title', '')
            description = row.get('Description', '')
            start_date = row.get('Start')
            end_date = row.get('Actual end date')
            duration_days = row.get('Duration in days')
            category = row.get('Category', '')
            quantity = row.get('Quantity')
            cost_per_unit = row.get('Quoted Cost per Unit')
            uuid_val = row.get('UUID', '')
            row_id = row.get('id', '')
            
            # Skip if title is empty or is a link_row
            if not title or isinstance(title, (list, dict)):
                continue
                
            cur.execute("""
                INSERT INTO farm_task (name, description, start_date, end_date, duration_days, 
                    category, quantity, cost_per_unit, status, location_id, slug, source_system, source_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (
                str(title),
                str(description) if description and not isinstance(description, (list, dict)) else '',
                start_date if not isinstance(start_date, (list, dict)) else None,
                end_date if not isinstance(end_date, (list, dict)) else None,
                duration_days if not isinstance(duration_days, (list, dict)) else None,
                str(category) if category and not isinstance(category, (list, dict)) else '',
                quantity if not isinstance(quantity, (list, dict)) else None,
                cost_per_unit if not isinstance(cost_per_unit, (list, dict)) else None,
                'pending',
                default_location,
                str(uuid_val) if uuid_val and not isinstance(uuid_val, (list, dict)) else '',
                'baserow',
                str(row_id) if row_id else ''
            ))
            count += 1
        except Exception as e:
            print(f"  Error inserting farm_task: {e}")
    conn.commit()
    cur.close()
    conn.close()
    return count

def insert_resource_input(rows):
    """Insert resource inputs."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    default_location = get_default_location_id()
    count = 0
    for row in rows:
        try:
            cur.execute("""
                INSERT INTO resource_input (name, description, is_active, location_id, slug, source_system, source_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (
                row.get('Name', ''),
                row.get('Notes', ''),
                row.get('Active', True),
                default_location,
                row.get('UUID', ''),
                'baserow',
                str(row.get('id', ''))
            ))
            count += 1
        except Exception as e:
            print(f"  Error inserting resource_input: {e}")
    conn.commit()
    cur.close()
    conn.close()
    return count

def insert_development_phase(rows):
    """Insert development phases."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    default_location = get_default_location_id()
    count = 0
    for row in rows:
        try:
            cur.execute("""
                INSERT INTO development_phase (name, description, location_id)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (
                row.get('Name', ''),
                row.get('Description', ''),
                default_location
            ))
            count += 1
        except Exception as e:
            print(f"  Error inserting development_phase: {e}")
    conn.commit()
    cur.close()
    conn.close()
    return count

def insert_framework_step(rows):
    """Insert framework steps."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    default_location = get_default_location_id()
    count = 0
    for row in rows:
        try:
            cur.execute("""
                INSERT INTO framework_step (name, description, duration_days, step_type, location_id)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (
                row.get('Title', ''),
                row.get('Description', ''),
                row.get('Duration in days'),
                row.get('Type', ''),
                default_location
            ))
            count += 1
        except Exception as e:
            print(f"  Error inserting framework_step: {e}")
    conn.commit()
    cur.close()
    conn.close()
    return count

def insert_weekly_plan(rows):
    """Insert weekly plans."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    default_location = get_default_location_id()
    count = 0
    for row in rows:
        try:
            cur.execute("""
                INSERT INTO weekly_plan (name, description, week_start, week_end, budget_forecast, location_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (
                row.get('Week', ''),
                row.get('Notes', ''),
                row.get('Date Start'),
                row.get('Date End'),
                row.get('Budget Forecast'),
                default_location
            ))
            count += 1
        except Exception as e:
            print(f"  Error inserting weekly_plan: {e}")
    conn.commit()
    cur.close()
    conn.close()
    return count

def insert_impact_dimension(rows):
    """Insert impact dimensions."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    count = 0
    for row in rows:
        try:
            cur.execute("""
                INSERT INTO impact_dimension (name, description, is_active)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (
                row.get('Name', ''),
                row.get('Description', ''),
                row.get('Active', True)
            ))
            count += 1
        except Exception as e:
            print(f"  Error inserting impact_dimension: {e}")
    conn.commit()
    cur.close()
    conn.close()
    return count

def insert_impact_framework(rows):
    """Insert impact frameworks."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    count = 0
    for row in rows:
        try:
            cur.execute("""
                INSERT INTO impact_framework (name, description, url)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (
                row.get('Name', ''),
                row.get('Description', ''),
                row.get('Source', '')
            ))
            count += 1
        except Exception as e:
            print(f"  Error inserting impact_framework: {e}")
    conn.commit()
    cur.close()
    conn.close()
    return count

def insert_form_of_capital(rows):
    """Insert forms of capital."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    count = 0
    for row in rows:
        try:
            cur.execute("""
                INSERT INTO form_of_capital (name, description, is_active)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (
                row.get('Name', ''),
                row.get('Notes', ''),
                row.get('Active', True)
            ))
            count += 1
        except Exception as e:
            print(f"  Error inserting form_of_capital: {e}")
    conn.commit()
    cur.close()
    conn.close()
    return count

def insert_sdg(rows):
    """Insert SDGs."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    count = 0
    for row in rows:
        try:
            cur.execute("""
                INSERT INTO sdg (name, description, is_active)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (
                row.get('Name', ''),
                row.get('Notes', ''),
                row.get('Active', True)
            ))
            count += 1
        except Exception as e:
            print(f"  Error inserting sdg: {e}")
    conn.commit()
    cur.close()
    conn.close()
    return count

def insert_objective(rows):
    """Insert objectives."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    default_location = get_default_location_id()
    count = 0
    for row in rows:
        try:
            cur.execute("""
                INSERT INTO objective (name, description, target_date, location_id)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (
                row.get('Title', ''),
                row.get('Description', ''),
                row.get('Date'),
                default_location
            ))
            count += 1
        except Exception as e:
            print(f"  Error inserting objective: {e}")
    conn.commit()
    cur.close()
    conn.close()
    return count

def insert_funding(rows):
    """Insert funding."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    count = 0
    for row in rows:
        try:
            cur.execute("""
                INSERT INTO funding (name, description, grant_amount, crowdfunding_amount, funding_date, slug, source_system, source_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (
                row.get('Program', ''),
                row.get('Overview', ''),
                row.get('Grant Amount'),
                row.get('Crowdfunding Amount'),
                row.get('Date'),
                row.get('UUID', ''),
                'baserow',
                str(row.get('id', ''))
            ))
            count += 1
        except Exception as e:
            print(f"  Error inserting funding: {e}")
    conn.commit()
    cur.close()
    conn.close()
    return count

def insert_funding_milestone(rows):
    """Insert funding milestones."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # Get funding IDs
    cur.execute("SELECT id, name FROM funding")
    funding_map = {row[1]: row[0] for row in cur.fetchall()}
    
    count = 0
    for row in rows:
        try:
            # Extract simple fields, skip link_row fields
            title = row.get('Title', '')
            description = row.get('Description', '')
            priority = row.get('Priority', '')
            start_date = row.get('Start Date')
            end_date = row.get('End Date')
            uuid_val = row.get('UUID', '')
            row_id = row.get('id', '')
            
            # Skip if title is empty or is a link_row
            if not title or isinstance(title, (list, dict)):
                continue
            
            # Handle link_row for funding
            funding_name = row.get('Source of Funding', '')
            if isinstance(funding_name, list) and funding_name:
                funding_name = funding_name[0].get('value', '') if isinstance(funding_name[0], dict) else str(funding_name[0])
            elif isinstance(funding_name, dict):
                funding_name = funding_name.get('value', '')
            funding_id = funding_map.get(str(funding_name) if funding_name else '')
            
            cur.execute("""
                INSERT INTO funding_milestone (name, description, priority, start_date, end_date, funding_id, slug, source_system, source_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (
                str(title),
                str(description) if description and not isinstance(description, (list, dict)) else '',
                str(priority) if priority and not isinstance(priority, (list, dict)) else '',
                start_date if not isinstance(start_date, (list, dict)) else None,
                end_date if not isinstance(end_date, (list, dict)) else None,
                funding_id,
                str(uuid_val) if uuid_val and not isinstance(uuid_val, (list, dict)) else '',
                'baserow',
                str(row_id) if row_id else ''
            ))
            count += 1
        except Exception as e:
            print(f"  Error inserting funding_milestone: {e}")
    conn.commit()
    cur.close()
    conn.close()
    return count

def insert_milestone_outcome(rows):
    """Insert milestone outcomes."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    count = 0
    for row in rows:
        try:
            cur.execute("""
                INSERT INTO milestone_outcome (name, description, proof_url, slug, source_system, source_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (
                row.get('Title', ''),
                row.get('Description', ''),
                row.get('Output Proof', ''),
                row.get('UUID', ''),
                'baserow',
                str(row.get('id', ''))
            ))
            count += 1
        except Exception as e:
            print(f"  Error inserting milestone_outcome: {e}")
    conn.commit()
    cur.close()
    conn.close()
    return count

def insert_impact_record(rows):
    """Insert impact records."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    default_location = get_default_location_id()
    count = 0
    for row in rows:
        try:
            cur.execute("""
                INSERT INTO impact_record (name, work_description, impact_description, work_start_date, work_end_date,
                    evidence_url, impact_url, verification_notes, impact_level, impact_score, location_id, slug, source_system, source_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (
                row.get('Name', ''),
                row.get('Work Description', ''),
                row.get('Impact Description', ''),
                row.get('Work Date Start'),
                row.get('Work Date End'),
                row.get('Impact Proof', ''),
                row.get('Impact URL', ''),
                row.get('Impact Verification', ''),
                row.get('Impact Level', ''),
                row.get('Impact Score'),
                default_location,
                row.get('UUID', ''),
                'baserow',
                str(row.get('id', ''))
            ))
            count += 1
        except Exception as e:
            print(f"  Error inserting impact_record: {e}")
    conn.commit()
    cur.close()
    conn.close()
    return count

def insert_ebf_record(rows):
    """Insert EBF records."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    count = 0
    for row in rows:
        try:
            cur.execute("""
                INSERT INTO ebf_record (name, description, is_active)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (
                row.get('Name', ''),
                row.get('Notes', ''),
                row.get('Active', True)
            ))
            count += 1
        except Exception as e:
            print(f"  Error inserting ebf_record: {e}")
    conn.commit()
    cur.close()
    conn.close()
    return count

def insert_ground_analytics_snapshot(rows):
    """Insert ground analytics snapshots."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    count = 0
    for row in rows:
        try:
            cur.execute("""
                INSERT INTO ground_analytics_snapshot (name, description, is_active)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (
                row.get('Name', ''),
                row.get('Notes', ''),
                row.get('Active', True)
            ))
            count += 1
        except Exception as e:
            print(f"  Error inserting ground_analytics_snapshot: {e}")
    conn.commit()
    cur.close()
    conn.close()
    return count

def insert_ecosystem_branch(rows):
    """Insert ecosystem branches."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    count = 0
    for row in rows:
        try:
            # Extract simple fields, skip link_row fields
            name = row.get('Name', '')
            notes = row.get('Notes', '')
            active = row.get('Active', True)
            
            # Skip if name is empty or is a link_row
            if not name or isinstance(name, (list, dict)):
                continue
                
            cur.execute("""
                INSERT INTO ecosystem_branch (name, description, is_active)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (
                str(name),
                str(notes) if notes and not isinstance(notes, (list, dict)) else '',
                active if not isinstance(active, (list, dict)) else True
            ))
            count += 1
        except Exception as e:
            print(f"  Error inserting ecosystem_branch: {e}")
    conn.commit()
    cur.close()
    conn.close()
    return count

def insert_dependency(rows):
    """Insert dependencies."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    count = 0
    for row in rows:
        try:
            cur.execute("""
                INSERT INTO dependency (name, description, url)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (
                row.get('Name', ''),
                row.get('Notes', ''),
                row.get('URL', '')
            ))
            count += 1
        except Exception as e:
            print(f"  Error inserting dependency: {e}")
    conn.commit()
    cur.close()
    conn.close()
    return count

def insert_equipment(rows):
    """Insert equipment as infrastructure_asset."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    default_location = get_default_location_id()
    count = 0
    for row in rows:
        try:
            cur.execute("""
                INSERT INTO infrastructure_asset (name, asset_type, description, location_id, status)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (
                row.get('Name', ''),
                'pump',
                row.get('Description', ''),
                default_location,
                'active'
            ))
            count += 1
        except Exception as e:
            print(f"  Error inserting equipment: {e}")
    conn.commit()
    cur.close()
    conn.close()
    return count

def insert_biofactory(rows):
    """Insert biofactory as infrastructure_asset."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    default_location = get_default_location_id()
    count = 0
    for row in rows:
        try:
            # Extract simple fields, skip link_row fields
            product = row.get('Product', '')
            notes = row.get('Notes', '')
            
            # Skip if product is empty or is a link_row
            if not product or isinstance(product, (list, dict)):
                continue
                
            cur.execute("""
                INSERT INTO infrastructure_asset (name, asset_type, description, location_id, status)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (
                str(product),
                'biofactory',
                str(notes) if notes and not isinstance(notes, (list, dict)) else '',
                default_location,
                'active'
            ))
            count += 1
        except Exception as e:
            print(f"  Error inserting biofactory: {e}")
    conn.commit()
    cur.close()
    conn.close()
    return count

def insert_ecosystem_infra(rows):
    """Insert ecosystem infra as infrastructure_asset."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    default_location = get_default_location_id()
    count = 0
    for row in rows:
        try:
            cur.execute("""
                INSERT INTO infrastructure_asset (name, asset_type, description, location_id, status)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (
                row.get('Name', ''),
                'greenhouse',
                row.get('Notes', ''),
                default_location,
                'active'
            ))
            count += 1
        except Exception as e:
            print(f"  Error inserting ecosystem_infra: {e}")
    conn.commit()
    cur.close()
    conn.close()
    return count

def main():
    print("=" * 60)
    print("Direct PostgreSQL Insertion for Baserow Migration")
    print("=" * 60)
    
    # Table ID to function mapping
    table_map = {
        305804: ('Departments', insert_department),
        305803: ('Job roles', insert_job_role),
        305801: ('Kokonut Farm Tasks', insert_farm_task),
        555496: ('F005 -- Resources Inputs', insert_resource_input),
        326753: ('Development Phases', insert_development_phase),
        331882: ('Framework Steps', insert_framework_step),
        415230: ('Weekly Planning', insert_weekly_plan),
        555533: ('Impact Dimensions', insert_impact_dimension),
        555534: ('Impact Frameworks', insert_impact_framework),
        487995: ('Forms of Capital', insert_form_of_capital),
        487994: ('SDGs', insert_sdg),
        554665: ('Objectives', insert_objective),
        554709: ('Funding', insert_funding),
        554723: ('Funding Milestones', insert_funding_milestone),
        554745: ('Milestones Outcomes', insert_milestone_outcome),
        554746: ('Impact', insert_impact_record),
        557322: ('EBF', insert_ebf_record),
        482436: ('Ground Analytics', insert_ground_analytics_snapshot),
        594558: ('Ecosystem Branches', insert_ecosystem_branch),
        594507: ('Kokonut Dependencies', insert_dependency),
        305807: ('Equipment', insert_equipment),
        417033: ('Biofactory', insert_biofactory),
        594514: ('Ecosystem Infra Stack', insert_ecosystem_infra),
    }
    
    total_inserted = 0
    
    for table_id, (table_name, insert_func) in table_map.items():
        print(f"\nMigrating: {table_name}")
        try:
            rows = fetch_baserow_rows(table_id)
            print(f"  Fetched {len(rows)} rows")
            
            if rows:
                count = insert_func(rows)
                print(f"  ✓ Inserted {count} rows")
                total_inserted += count
            else:
                print(f"  - No rows to insert")
                
        except Exception as e:
            print(f"  ✗ Error: {e}")
    
    print(f"\n{'=' * 60}")
    print(f"Migration complete! Total inserted: {total_inserted} rows")
    print(f"{'=' * 60}")

if __name__ == '__main__':
    main()
