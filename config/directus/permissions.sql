-- ============================================================
-- Directus Permissions — Milestone 2: Staff-managed operations
-- Creates roles, policies, access rules, and per-collection permissions
-- ============================================================

-- ============================================================
-- 1. CREATE ROLES (skip if already exist by name)
-- ============================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM directus_roles WHERE name = 'Field Worker') THEN
        INSERT INTO directus_roles (id, name, icon, description) VALUES
            ('a1000000-0000-0000-0000-000000000001', 'Field Worker', 'agriculture', 'Field data entry staff — can create and read own location records');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM directus_roles WHERE name = 'Supervisor') THEN
        INSERT INTO directus_roles (id, name, icon, description) VALUES
            ('a1000000-0000-0000-0000-000000000002', 'Supervisor', 'supervisor_account', 'Field supervisors — can read all, submit field data for approval');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM directus_roles WHERE name = 'Manager') THEN
        INSERT INTO directus_roles (id, name, icon, description) VALUES
            ('a1000000-0000-0000-0000-000000000003', 'Manager', 'supervised_user_circle', 'Farm/location managers — can approve operational records');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM directus_roles WHERE name = 'Finance') THEN
        INSERT INTO directus_roles (id, name, icon, description) VALUES
            ('a1000000-0000-0000-0000-000000000004', 'Finance', 'account_balance', 'Finance/accounting staff — can approve expenses and verify sales');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM directus_roles WHERE name = 'Analyst') THEN
        INSERT INTO directus_roles (id, name, icon, description) VALUES
            ('a1000000-0000-0000-0000-000000000005', 'Analyst', 'analytics', 'Data analysts — read-only access to verified/published data');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM directus_roles WHERE name = 'Auditor') THEN
        INSERT INTO directus_roles (id, name, icon, description) VALUES
            ('a1000000-0000-0000-0000-000000000009', 'Auditor', 'verified', 'Compliance/audit — read-only access to all statuses for forensic review');
    END IF;
END $$;

-- ============================================================
-- 2. CREATE POLICIES (skip if already exist by name)
-- ============================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM directus_policies WHERE name = 'Field Worker Policy') THEN
        INSERT INTO directus_policies (id, name, icon, admin_access, app_access, description) VALUES
            ('b1000000-0000-0000-0000-000000000001', 'Field Worker Policy', 'agriculture', false, true, 'Policy for field data entry staff');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM directus_policies WHERE name = 'Supervisor Policy') THEN
        INSERT INTO directus_policies (id, name, icon, admin_access, app_access, description) VALUES
            ('b1000000-0000-0000-0000-000000000002', 'Supervisor Policy', 'supervisor_account', false, true, 'Policy for field supervisors');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM directus_policies WHERE name = 'Manager Policy') THEN
        INSERT INTO directus_policies (id, name, icon, admin_access, app_access, description) VALUES
            ('b1000000-0000-0000-0000-000000000003', 'Manager Policy', 'supervised_user_circle', false, true, 'Policy for farm/location managers');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM directus_policies WHERE name = 'Finance Policy') THEN
        INSERT INTO directus_policies (id, name, icon, admin_access, app_access, description) VALUES
            ('b1000000-0000-0000-0000-000000000004', 'Finance Policy', 'account_balance', false, true, 'Policy for finance/accounting staff');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM directus_policies WHERE name = 'Analyst Policy') THEN
        INSERT INTO directus_policies (id, name, icon, admin_access, app_access, description) VALUES
            ('b1000000-0000-0000-0000-000000000005', 'Analyst Policy', 'analytics', false, true, 'Policy for data analysts');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM directus_policies WHERE name = 'Auditor Policy') THEN
        INSERT INTO directus_policies (id, name, icon, admin_access, app_access, description) VALUES
            ('b1000000-0000-0000-0000-000000000009', 'Auditor Policy', 'verified', false, true, 'Policy for compliance/audit — read-only to all statuses');
    END IF;
END $$;

-- ============================================================
-- 3. LINK ROLES TO POLICIES (access table)
-- ============================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM directus_access WHERE role = 'a1000000-0000-0000-0000-000000000001') THEN
        INSERT INTO directus_access (id, role, policy, sort) VALUES
            ('c1000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000001', 'b1000000-0000-0000-0000-000000000001', 1);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM directus_access WHERE role = 'a1000000-0000-0000-0000-000000000002') THEN
        INSERT INTO directus_access (id, role, policy, sort) VALUES
            ('c1000000-0000-0000-0000-000000000002', 'a1000000-0000-0000-0000-000000000002', 'b1000000-0000-0000-0000-000000000002', 1);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM directus_access WHERE role = 'a1000000-0000-0000-0000-000000000003') THEN
        INSERT INTO directus_access (id, role, policy, sort) VALUES
            ('c1000000-0000-0000-0000-000000000003', 'a1000000-0000-0000-0000-000000000003', 'b1000000-0000-0000-0000-000000000003', 1);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM directus_access WHERE role = 'a1000000-0000-0000-0000-000000000004') THEN
        INSERT INTO directus_access (id, role, policy, sort) VALUES
            ('c1000000-0000-0000-0000-000000000004', 'a1000000-0000-0000-0000-000000000004', 'b1000000-0000-0000-0000-000000000004', 1);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM directus_access WHERE role = 'a1000000-0000-0000-0000-000000000005') THEN
        INSERT INTO directus_access (id, role, policy, sort) VALUES
            ('c1000000-0000-0000-0000-000000000005', 'a1000000-0000-0000-0000-000000000005', 'b1000000-0000-0000-0000-000000000005', 1);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM directus_access WHERE role = 'a1000000-0000-0000-0000-000000000009') THEN
        INSERT INTO directus_access (id, role, policy, sort) VALUES
            ('c1000000-0000-0000-0000-000000000009', 'a1000000-0000-0000-0000-000000000009', 'b1000000-0000-0000-0000-000000000009', 1);
    END IF;
END $$;

-- ============================================================
-- 4. PERMISSION RULES — skip if policy already has permissions
-- ============================================================

-- Field Worker Policy permissions
DO $$ BEGIN
IF NOT EXISTS (SELECT 1 FROM directus_permissions WHERE policy = 'b1000000-0000-0000-0000-000000000001' AND collection = 'farm_activity' AND action = 'create') THEN
    INSERT INTO directus_permissions (collection, action, permissions, validation, fields, policy) VALUES
        ('farm_activity', 'create', '{}', '{}', 'activity_type,activity_date,description,labor_hours,labor_cost,materials_used,evidence_urls,notes,plot_id,crop_cycle_id,location_id,source_system,source_id,source_raw', 'b1000000-0000-0000-0000-000000000001');
END IF;
END $$;

DO $$ BEGIN
IF NOT EXISTS (SELECT 1 FROM directus_permissions WHERE policy = 'b1000000-0000-0000-0000-000000000001' AND collection = 'farm_activity' AND action = 'read') THEN
    INSERT INTO directus_permissions (collection, action, permissions, validation, fields, policy) VALUES
        ('farm_activity', 'read', '{"_and":[{"location_id":{"_eq":"$CURRENT_USER.location_id"}}]}', '{}', '*', 'b1000000-0000-0000-0000-000000000001');
END IF;
END $$;

DO $$ BEGIN
IF NOT EXISTS (SELECT 1 FROM directus_permissions WHERE policy = 'b1000000-0000-0000-0000-000000000001' AND collection = 'farm_activity' AND action = 'update') THEN
    INSERT INTO directus_permissions (collection, action, permissions, validation, fields, policy) VALUES
        ('farm_activity', 'update', '{"_and":[{"location_id":{"_eq":"$CURRENT_USER.location_id"}},{"status":{"_eq":"draft"}}]}', '{}', 'activity_type,activity_date,description,labor_hours,labor_cost,materials_used,evidence_urls,notes,plot_id,crop_cycle_id', 'b1000000-0000-0000-0000-000000000001');
END IF;
END $$;

-- harvest_event
DO $$ BEGIN
IF NOT EXISTS (SELECT 1 FROM directus_permissions WHERE policy = 'b1000000-0000-0000-0000-000000000001' AND collection = 'harvest_event' AND action = 'create') THEN
    INSERT INTO directus_permissions (collection, action, permissions, validation, fields, policy) VALUES
        ('harvest_event', 'create', '{}', '{}', 'harvest_date,quantity,unit,quality_grade,destination,loss_amount,loss_unit,loss_reason,loss_estimated_value,evidence_urls,notes,plot_id,crop_cycle_id,location_id,source_system,source_id,source_raw', 'b1000000-0000-0000-0000-000000000001');
END IF;
END $$;

DO $$ BEGIN
IF NOT EXISTS (SELECT 1 FROM directus_permissions WHERE policy = 'b1000000-0000-0000-0000-000000000001' AND collection = 'harvest_event' AND action = 'read') THEN
    INSERT INTO directus_permissions (collection, action, permissions, validation, fields, policy) VALUES
        ('harvest_event', 'read', '{"_and":[{"location_id":{"_eq":"$CURRENT_USER.location_id"}}]}', '{}', '*', 'b1000000-0000-0000-0000-000000000001');
END IF;
END $$;

DO $$ BEGIN
IF NOT EXISTS (SELECT 1 FROM directus_permissions WHERE policy = 'b1000000-0000-0000-0000-000000000001' AND collection = 'harvest_event' AND action = 'update') THEN
    INSERT INTO directus_permissions (collection, action, permissions, validation, fields, policy) VALUES
        ('harvest_event', 'update', '{"_and":[{"location_id":{"_eq":"$CURRENT_USER.location_id"}},{"status":{"_eq":"draft"}}]}', '{}', 'harvest_date,quantity,unit,quality_grade,destination,loss_amount,loss_unit,loss_reason,loss_estimated_value,evidence_urls,notes,plot_id,crop_cycle_id', 'b1000000-0000-0000-0000-000000000001');
END IF;
END $$;

-- expense_event
DO $$ BEGIN
IF NOT EXISTS (SELECT 1 FROM directus_permissions WHERE policy = 'b1000000-0000-0000-0000-000000000001' AND collection = 'expense_event' AND action = 'create') THEN
    INSERT INTO directus_permissions (collection, action, permissions, validation, fields, policy) VALUES
        ('expense_event', 'create', '{}', '{}', 'expense_date,category,subcategory,description,vendor,amount,currency,is_capex,allocation_method,allocation_weight,evidence_urls,invoice_number,notes,plot_id,crop_cycle_id,location_id,source_system,source_id,source_raw', 'b1000000-0000-0000-0000-000000000001');
END IF;
END $$;

DO $$ BEGIN
IF NOT EXISTS (SELECT 1 FROM directus_permissions WHERE policy = 'b1000000-0000-0000-0000-000000000001' AND collection = 'expense_event' AND action = 'read') THEN
    INSERT INTO directus_permissions (collection, action, permissions, validation, fields, policy) VALUES
        ('expense_event', 'read', '{"_and":[{"location_id":{"_eq":"$CURRENT_USER.location_id"}}]}', '{}', '*', 'b1000000-0000-0000-0000-000000000001');
END IF;
END $$;

DO $$ BEGIN
IF NOT EXISTS (SELECT 1 FROM directus_permissions WHERE policy = 'b1000000-0000-0000-0000-000000000001' AND collection = 'expense_event' AND action = 'update') THEN
    INSERT INTO directus_permissions (collection, action, permissions, validation, fields, policy) VALUES
        ('expense_event', 'update', '{"_and":[{"location_id":{"_eq":"$CURRENT_USER.location_id"}},{"status":{"_eq":"draft"}}]}', '{}', 'expense_date,category,subcategory,description,vendor,amount,currency,is_capex,allocation_method,allocation_weight,evidence_urls,invoice_number,notes,plot_id,crop_cycle_id', 'b1000000-0000-0000-0000-000000000001');
END IF;
END $$;

-- sales_event
DO $$ BEGIN
IF NOT EXISTS (SELECT 1 FROM directus_permissions WHERE policy = 'b1000000-0000-0000-0000-000000000001' AND collection = 'sales_event' AND action = 'create') THEN
    INSERT INTO directus_permissions (collection, action, permissions, validation, fields, policy) VALUES
        ('sales_event', 'create', '{}', '{}', 'sale_date,buyer,buyer_type,quantity,unit,price_per_unit,total_amount,currency,payment_status,payment_date,payment_method,invoice_number,return_amount,discount_amount,evidence_urls,notes,harvest_id,crop_cycle_id,partner_id,location_id,source_system,source_id,source_raw', 'b1000000-0000-0000-0000-000000000001');
END IF;
END $$;

DO $$ BEGIN
IF NOT EXISTS (SELECT 1 FROM directus_permissions WHERE policy = 'b1000000-0000-0000-0000-000000000001' AND collection = 'sales_event' AND action = 'read') THEN
    INSERT INTO directus_permissions (collection, action, permissions, validation, fields, policy) VALUES
        ('sales_event', 'read', '{"_and":[{"location_id":{"_eq":"$CURRENT_USER.location_id"}}]}', '{}', '*', 'b1000000-0000-0000-0000-000000000001');
END IF;
END $$;

DO $$ BEGIN
IF NOT EXISTS (SELECT 1 FROM directus_permissions WHERE policy = 'b1000000-0000-0000-0000-000000000001' AND collection = 'sales_event' AND action = 'update') THEN
    INSERT INTO directus_permissions (collection, action, permissions, validation, fields, policy) VALUES
        ('sales_event', 'update', '{"_and":[{"location_id":{"_eq":"$CURRENT_USER.location_id"}},{"status":{"_eq":"draft"}}]}', '{}', 'sale_date,buyer,buyer_type,quantity,unit,price_per_unit,total_amount,currency,payment_status,payment_date,payment_method,invoice_number,return_amount,discount_amount,evidence_urls,notes,harvest_id,crop_cycle_id,partner_id', 'b1000000-0000-0000-0000-000000000001');
END IF;
END $$;

-- loss_event
DO $$ BEGIN
IF NOT EXISTS (SELECT 1 FROM directus_permissions WHERE policy = 'b1000000-0000-0000-0000-000000000001' AND collection = 'loss_event' AND action = 'create') THEN
    INSERT INTO directus_permissions (collection, action, permissions, validation, fields, policy) VALUES
        ('loss_event', 'create', '{}', '{}', 'loss_date,loss_type,quantity,unit,estimated_value,cause,impact_description,mitigation,severity,evidence_urls,notes,crop_cycle_id,harvest_id,plot_id,location_id,source_system,source_id,source_raw', 'b1000000-0000-0000-0000-000000000001');
END IF;
END $$;

DO $$ BEGIN
IF NOT EXISTS (SELECT 1 FROM directus_permissions WHERE policy = 'b1000000-0000-0000-0000-000000000001' AND collection = 'loss_event' AND action = 'read') THEN
    INSERT INTO directus_permissions (collection, action, permissions, validation, fields, policy) VALUES
        ('loss_event', 'read', '{"_and":[{"location_id":{"_eq":"$CURRENT_USER.location_id"}}]}', '{}', '*', 'b1000000-0000-0000-0000-000000000001');
END IF;
END $$;

DO $$ BEGIN
IF NOT EXISTS (SELECT 1 FROM directus_permissions WHERE policy = 'b1000000-0000-0000-0000-000000000001' AND collection = 'loss_event' AND action = 'update') THEN
    INSERT INTO directus_permissions (collection, action, permissions, validation, fields, policy) VALUES
        ('loss_event', 'update', '{"_and":[{"location_id":{"_eq":"$CURRENT_USER.location_id"}},{"status":{"_eq":"draft"}}]}', '{}', 'loss_date,loss_type,quantity,unit,estimated_value,cause,impact_description,mitigation,severity,evidence_urls,notes,crop_cycle_id,harvest_id,plot_id', 'b1000000-0000-0000-0000-000000000001');
END IF;
END $$;

-- labor_event
DO $$ BEGIN
IF NOT EXISTS (SELECT 1 FROM directus_permissions WHERE policy = 'b1000000-0000-0000-0000-000000000001' AND collection = 'labor_event' AND action = 'create') THEN
    INSERT INTO directus_permissions (collection, action, permissions, validation, fields, policy) VALUES
        ('labor_event', 'create', '{}', '{}', 'staff_id,worker_name,work_date,hours_worked,hourly_rate,total_cost,role,activity_description,notes,plot_id,crop_cycle_id,location_id,source_system,source_id,source_raw', 'b1000000-0000-0000-0000-000000000001');
END IF;
END $$;

DO $$ BEGIN
IF NOT EXISTS (SELECT 1 FROM directus_permissions WHERE policy = 'b1000000-0000-0000-0000-000000000001' AND collection = 'labor_event' AND action = 'read') THEN
    INSERT INTO directus_permissions (collection, action, permissions, validation, fields, policy) VALUES
        ('labor_event', 'read', '{"_and":[{"location_id":{"_eq":"$CURRENT_USER.location_id"}}]}', '{}', '*', 'b1000000-0000-0000-0000-000000000001');
END IF;
END $$;

DO $$ BEGIN
IF NOT EXISTS (SELECT 1 FROM directus_permissions WHERE policy = 'b1000000-0000-0000-0000-000000000001' AND collection = 'labor_event' AND action = 'update') THEN
    INSERT INTO directus_permissions (collection, action, permissions, validation, fields, policy) VALUES
        ('labor_event', 'update', '{"_and":[{"location_id":{"_eq":"$CURRENT_USER.location_id"}},{"status":{"_eq":"draft"}}]}', '{}', 'staff_id,worker_name,work_date,hours_worked,hourly_rate,total_cost,role,activity_description,notes,plot_id,crop_cycle_id', 'b1000000-0000-0000-0000-000000000001');
END IF;
END $$;

-- field_note
DO $$ BEGIN
IF NOT EXISTS (SELECT 1 FROM directus_permissions WHERE policy = 'b1000000-0000-0000-0000-000000000001' AND collection = 'field_note' AND action = 'create') THEN
    INSERT INTO directus_permissions (collection, action, permissions, validation, fields, policy) VALUES
        ('field_note', 'create', '{}', '{}', 'note_date,note_type,title,content,images,tags,plot_id,crop_cycle_id,location_id,source_system,source_id,source_raw', 'b1000000-0000-0000-0000-000000000001');
END IF;
END $$;

DO $$ BEGIN
IF NOT EXISTS (SELECT 1 FROM directus_permissions WHERE policy = 'b1000000-0000-0000-0000-000000000001' AND collection = 'field_note' AND action = 'read') THEN
    INSERT INTO directus_permissions (collection, action, permissions, validation, fields, policy) VALUES
        ('field_note', 'read', '{"_and":[{"location_id":{"_eq":"$CURRENT_USER.location_id"}}]}', '{}', '*', 'b1000000-0000-0000-0000-000000000001');
END IF;
END $$;

DO $$ BEGIN
IF NOT EXISTS (SELECT 1 FROM directus_permissions WHERE policy = 'b1000000-0000-0000-0000-000000000001' AND collection = 'field_note' AND action = 'update') THEN
    INSERT INTO directus_permissions (collection, action, permissions, validation, fields, policy) VALUES
        ('field_note', 'update', '{"_and":[{"location_id":{"_eq":"$CURRENT_USER.location_id"}},{"status":{"_eq":"draft"}}]}', '{}', 'note_date,note_type,title,content,images,tags,plot_id,crop_cycle_id,source_system,source_id,source_raw', 'b1000000-0000-0000-0000-000000000001');
END IF;
END $$;

-- file_upload, workflow_history, approval, expense_category for field worker
DO $$ BEGIN
IF NOT EXISTS (SELECT 1 FROM directus_permissions WHERE policy = 'b1000000-0000-0000-0000-000000000001' AND collection = 'file_upload' AND action = 'create') THEN
    INSERT INTO directus_permissions (collection, action, permissions, validation, fields, policy) VALUES
        ('file_upload', 'create', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000001'),
        ('file_upload', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000001'),
        ('workflow_history', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000001'),
        ('approval', 'create', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000001'),
        ('approval', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000001'),
        ('expense_category', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000001');
END IF;
END $$;

-- ============================================================
-- 5. Supervisor Policy permissions
-- ============================================================

DO $$ BEGIN
IF NOT EXISTS (SELECT 1 FROM directus_permissions WHERE policy = 'b1000000-0000-0000-0000-000000000002' AND collection = 'farm_activity') THEN
    INSERT INTO directus_permissions (collection, action, permissions, validation, fields, policy) VALUES
        ('farm_activity', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000002'),
        ('farm_activity', 'update', '{}', '{}', 'status', 'b1000000-0000-0000-0000-000000000002'),
        ('harvest_event', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000002'),
        ('harvest_event', 'update', '{}', '{}', 'status', 'b1000000-0000-0000-0000-000000000002'),
        ('expense_event', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000002'),
        ('expense_event', 'update', '{}', '{}', 'status', 'b1000000-0000-0000-0000-000000000002'),
        ('sales_event', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000002'),
        ('sales_event', 'update', '{}', '{}', 'status', 'b1000000-0000-0000-0000-000000000002'),
        ('loss_event', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000002'),
        ('loss_event', 'update', '{}', '{}', 'status', 'b1000000-0000-0000-0000-000000000002'),
        ('labor_event', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000002'),
        ('labor_event', 'update', '{}', '{}', 'status', 'b1000000-0000-0000-0000-000000000002'),
        ('field_note', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000002'),
        ('workflow_history', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000002'),
        ('approval', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000002'),
        ('expense_category', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000002');
END IF;
END $$;

-- ============================================================
-- 6. Manager Policy permissions
-- ============================================================

DO $$ BEGIN
IF NOT EXISTS (SELECT 1 FROM directus_permissions WHERE policy = 'b1000000-0000-0000-0000-000000000003' AND collection = 'farm_activity') THEN
    INSERT INTO directus_permissions (collection, action, permissions, validation, fields, policy) VALUES
        ('farm_activity', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000003'),
        ('farm_activity', 'update', '{}', '{}', 'status,rejection_reason', 'b1000000-0000-0000-0000-000000000003'),
        ('harvest_event', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000003'),
        ('harvest_event', 'update', '{}', '{}', 'status,rejection_reason', 'b1000000-0000-0000-0000-000000000003'),
        ('expense_event', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000003'),
        ('expense_event', 'update', '{}', '{}', 'status,rejection_reason', 'b1000000-0000-0000-0000-000000000003'),
        ('sales_event', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000003'),
        ('revenue_event', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000003'),
        ('revenue_event', 'update', '{}', '{}', 'status,rejection_reason', 'b1000000-0000-0000-0000-000000000003'),
        ('loss_event', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000003'),
        ('loss_event', 'update', '{}', '{}', 'status,rejection_reason', 'b1000000-0000-0000-0000-000000000003'),
        ('labor_event', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000003'),
        ('labor_event', 'update', '{}', '{}', 'status', 'b1000000-0000-0000-0000-000000000003'),
        ('field_note', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000003'),
        ('field_note', 'update', '{}', '{}', 'status', 'b1000000-0000-0000-0000-000000000003'),
        ('workflow_history', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000003'),
        ('approval', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000003'),
        ('expense_category', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000003');
END IF;
END $$;

-- ============================================================
-- 7. Finance Policy permissions
-- ============================================================

DO $$ BEGIN
IF NOT EXISTS (SELECT 1 FROM directus_permissions WHERE policy = 'b1000000-0000-0000-0000-000000000004' AND collection = 'expense_event') THEN
    INSERT INTO directus_permissions (collection, action, permissions, validation, fields, policy) VALUES
        ('expense_event', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000004'),
        ('expense_event', 'update', '{}', '{}', 'status,rejection_reason', 'b1000000-0000-0000-0000-000000000004'),
        ('sales_event', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000004'),
        ('sales_event', 'update', '{}', '{}', 'status,rejection_reason', 'b1000000-0000-0000-0000-000000000004'),
        ('revenue_event', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000004'),
        ('revenue_event', 'update', '{}', '{}', 'status,rejection_reason', 'b1000000-0000-0000-0000-000000000004'),
        ('farm_activity', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000004'),
        ('harvest_event', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000004'),
        ('loss_event', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000004'),
        ('labor_event', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000004'),
        ('field_note', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000004'),
        ('workflow_history', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000004'),
        ('approval', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000004'),
        ('expense_category', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000004'),
        ('noi_snapshot', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000004');
END IF;
END $$;

-- ============================================================
-- 8. Analyst Policy permissions
-- ============================================================

DO $$ BEGIN
IF NOT EXISTS (SELECT 1 FROM directus_permissions WHERE policy = 'b1000000-0000-0000-0000-000000000005' AND collection = 'farm_activity') THEN
    INSERT INTO directus_permissions (collection, action, permissions, validation, fields, policy) VALUES
        ('farm_activity', 'read', '{"status":{"_in":["verified","published"]}}', '{}', '*', 'b1000000-0000-0000-0000-000000000005'),
        ('harvest_event', 'read', '{"status":{"_in":["verified","published"]}}', '{}', '*', 'b1000000-0000-0000-0000-000000000005'),
        ('expense_event', 'read', '{"status":{"_in":["verified","published"]}}', '{}', '*', 'b1000000-0000-0000-0000-000000000005'),
        ('sales_event', 'read', '{"status":{"_in":["verified","published"]}}', '{}', '*', 'b1000000-0000-0000-0000-000000000005'),
        ('loss_event', 'read', '{"status":{"_in":["verified","published"]}}', '{}', '*', 'b1000000-0000-0000-0000-000000000005'),
        ('labor_event', 'read', '{"status":{"_in":["verified","published"]}}', '{}', '*', 'b1000000-0000-0000-0000-000000000005'),
        ('field_note', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000005'),
        ('noi_snapshot', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000005'),
        ('metric_definition', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000005'),
        ('workflow_history', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000005'),
        ('approval', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000005'),
        ('expense_category', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000005');
END IF;
END $$;

-- ============================================================
-- 9. AUDITOR POLICY permissions — read-only, ALL statuses
-- ============================================================

DO $$ BEGIN
IF NOT EXISTS (SELECT 1 FROM directus_permissions WHERE policy = 'b1000000-0000-0000-0000-000000000009' AND collection = 'farm_activity') THEN
    INSERT INTO directus_permissions (collection, action, permissions, validation, fields, policy) VALUES
        ('farm_activity', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000009'),
        ('harvest_event', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000009'),
        ('expense_event', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000009'),
        ('sales_event', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000009'),
        ('loss_event', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000009'),
        ('labor_event', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000009'),
        ('field_note', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000009'),
        ('noi_snapshot', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000009'),
        ('metric_definition', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000009'),
        ('metric_value', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000009'),
        ('workflow_history', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000009'),
        ('approval', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000009'),
        ('expense_category', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000009'),
        ('attestation_record', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000009'),
        ('mrv_claim', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000009'),
        ('dashboard_dataset', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000009'),
        ('report_snapshot', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000009'),
        ('forecast_scenario', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000009'),
        ('forecast_output', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000009'),
        ('revenue_event', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000009'),
        ('water_access', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000009'),
        ('capex_breakdown', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000009'),
        ('attestation_plan', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000009'),
        ('agent_identity', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000009'),
        ('agent_task', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000009'),
        ('agent_action_log', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000009'),
        ('digital_lego_usage', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000009'),
        ('capital_source', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000009');
END IF;
END $$;

-- ============================================================
-- 10. AGENT ROLES — Scoped roles for AI agent access
-- ============================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM directus_roles WHERE name = 'Agent Read-Only') THEN
        INSERT INTO directus_roles (id, name, icon, description) VALUES
            ('a1000000-0000-0000-0000-000000000006', 'Agent Read-Only', 'smart_toy', 'AI agent — read-only access to verified/published data');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM directus_roles WHERE name = 'Agent Write') THEN
        INSERT INTO directus_roles (id, name, icon, description) VALUES
            ('a1000000-0000-0000-0000-000000000007', 'Agent Write', 'smart_toy', 'AI agent — can create draft records, submit for review');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM directus_roles WHERE name = 'Agent Full') THEN
        INSERT INTO directus_roles (id, name, icon, description) VALUES
            ('a1000000-0000-0000-0000-000000000008', 'Agent Full', 'smart_toy', 'AI agent — full access (requires human approval for high-risk ops)');
    END IF;
END $$;

-- Agent policies
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM directus_policies WHERE name = 'Agent Read-Only Policy') THEN
        INSERT INTO directus_policies (id, name, icon, admin_access, app_access, description) VALUES
            ('b1000000-0000-0000-0000-000000000006', 'Agent Read-Only Policy', 'smart_toy', false, true, 'Policy for AI agents — read-only');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM directus_policies WHERE name = 'Agent Write Policy') THEN
        INSERT INTO directus_policies (id, name, icon, admin_access, app_access, description) VALUES
            ('b1000000-0000-0000-0000-000000000007', 'Agent Write Policy', 'smart_toy', false, true, 'Policy for AI agents — can create drafts');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM directus_policies WHERE name = 'Agent Full Policy') THEN
        INSERT INTO directus_policies (id, name, icon, admin_access, app_access, description) VALUES
            ('b1000000-0000-0000-0000-000000000008', 'Agent Full Policy', 'smart_toy', false, true, 'Policy for AI agents — full access with approval gates');
    END IF;
END $$;

-- Link agent roles to policies
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM directus_access WHERE role = 'a1000000-0000-0000-0000-000000000006') THEN
        INSERT INTO directus_access (id, role, policy, sort) VALUES
            ('c1000000-0000-0000-0000-000000000006', 'a1000000-0000-0000-0000-000000000006', 'b1000000-0000-0000-0000-000000000006', 1);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM directus_access WHERE role = 'a1000000-0000-0000-0000-000000000007') THEN
        INSERT INTO directus_access (id, role, policy, sort) VALUES
            ('c1000000-0000-0000-0000-000000000007', 'a1000000-0000-0000-0000-000000000007', 'b1000000-0000-0000-0000-000000000007', 1);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM directus_access WHERE role = 'a1000000-0000-0000-0000-000000000008') THEN
        INSERT INTO directus_access (id, role, policy, sort) VALUES
            ('c1000000-0000-0000-0000-000000000008', 'a1000000-0000-0000-0000-000000000008', 'b1000000-0000-0000-0000-000000000008', 1);
    END IF;
END $$;

-- Agent Read-Only permissions (read verified/published data + agent tables)
DO $$ BEGIN
IF NOT EXISTS (SELECT 1 FROM directus_permissions WHERE policy = 'b1000000-0000-0000-0000-000000000006' AND collection = 'farm_activity') THEN
    INSERT INTO directus_permissions (collection, action, permissions, validation, fields, policy) VALUES
        ('farm_activity', 'read', '{"status":{"_in":["verified","published"]}}', '{}', '*', 'b1000000-0000-0000-0000-000000000006'),
        ('harvest_event', 'read', '{"status":{"_in":["verified","published"]}}', '{}', '*', 'b1000000-0000-0000-0000-000000000006'),
        ('expense_event', 'read', '{"status":{"_in":["verified","published"]}}', '{}', '*', 'b1000000-0000-0000-0000-000000000006'),
        ('sales_event', 'read', '{"status":{"_in":["verified","published"]}}', '{}', '*', 'b1000000-0000-0000-0000-000000000006'),
        ('loss_event', 'read', '{"status":{"_in":["verified","published"]}}', '{}', '*', 'b1000000-0000-0000-0000-000000000006'),
        ('labor_event', 'read', '{"status":{"_in":["verified","published"]}}', '{}', '*', 'b1000000-0000-0000-0000-000000000006'),
        ('field_note', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000006'),
        ('mrv_claim', 'read', '{"status":{"_in":["verified","published"]}}', '{}', '*', 'b1000000-0000-0000-0000-000000000006'),
        ('attestation_record', 'read', '{"status":{"_in":["verified","published"]}}', '{}', '*', 'b1000000-0000-0000-0000-000000000006'),
        ('agent_identity', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000006'),
        ('agent_task', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000006'),
        ('ai_summary', 'read', '{"status":{"_in":["verified","published"]}}', '{}', '*', 'b1000000-0000-0000-0000-000000000006'),
        ('metric_definition', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000006'),
        ('forecast_scenario', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000006'),
        ('forecast_output', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000006');
END IF;
END $$;

-- Agent Write permissions (create draft records + agent tables)
DO $$ BEGIN
IF NOT EXISTS (SELECT 1 FROM directus_permissions WHERE policy = 'b1000000-0000-0000-0000-000000000007' AND collection = 'farm_activity') THEN
    INSERT INTO directus_permissions (collection, action, permissions, validation, fields, policy) VALUES
        ('mrv_claim', 'create', '{}', '{}', 'claim_type,claim_date,claim_data,source_record_ids,evidence_urls,location_id,plot_id', 'b1000000-0000-0000-0000-000000000007'),
        ('mrv_claim', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000007'),
        ('field_note', 'create', '{}', '{}', 'note_date,note_type,title,content,images,tags,plot_id,crop_cycle_id,location_id', 'b1000000-0000-0000-0000-000000000007'),
        ('field_note', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000007'),
        ('agent_identity', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000007'),
        ('agent_identity', 'create', '{}', '{}', 'name,agent_type,description,capabilities,wallet_address', 'b1000000-0000-0000-0000-000000000007'),
        ('agent_task', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000007'),
        ('agent_task', 'create', '{}', '{}', 'task_type,input_data,location_id', 'b1000000-0000-0000-0000-000000000007'),
        ('agent_task', 'update', '{}', '{}', 'execution_status,execution_result,error_message', 'b1000000-0000-0000-0000-000000000007'),
        ('agent_action_log', 'create', '{}', '{}', 'task_id,action,collection,record_id,payload_hash,action_result,metadata', 'b1000000-0000-0000-0000-000000000007'),
        ('agent_action_log', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000007'),
        ('ai_summary', 'create', '{}', '{}', 'subject_type,subject_id,summary_type,content,source_record_ids,source_tables,model_version,confidence', 'b1000000-0000-0000-0000-000000000007'),
        ('ai_summary', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000007'),
        ('metric_definition', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000007'),
        ('forecast_scenario', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000007'),
        ('forecast_output', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000007'),
        ('harvest_event', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000007'),
        ('expense_event', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000007'),
        ('sales_event', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000007');
END IF;
END $$;

-- Agent Full permissions (read all, create, update — no publish)
DO $$ BEGIN
IF NOT EXISTS (SELECT 1 FROM directus_permissions WHERE policy = 'b1000000-0000-0000-0000-000000000008' AND collection = 'farm_activity') THEN
    INSERT INTO directus_permissions (collection, action, permissions, validation, fields, policy) VALUES
        ('farm_activity', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000008'),
        ('farm_activity', 'create', '{}', '{}', 'activity_type,activity_date,description,labor_hours,labor_cost,materials_used,evidence_urls,notes,plot_id,crop_cycle_id,location_id', 'b1000000-0000-0000-0000-000000000008'),
        ('harvest_event', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000008'),
        ('harvest_event', 'create', '{}', '{}', 'harvest_date,quantity,unit,quality_grade,destination,loss_amount,loss_unit,loss_reason,loss_estimated_value,evidence_urls,notes,plot_id,crop_cycle_id,location_id', 'b1000000-0000-0000-0000-000000000008'),
        ('expense_event', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000008'),
        ('expense_event', 'create', '{}', '{}', 'expense_date,category,subcategory,description,vendor,amount,currency,is_capex,allocation_method,allocation_weight,evidence_urls,invoice_number,notes,plot_id,crop_cycle_id,location_id', 'b1000000-0000-0000-0000-000000000008'),
        ('mrv_claim', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000008'),
        ('mrv_claim', 'create', '{}', '{}', 'claim_type,claim_date,claim_data,source_record_ids,evidence_urls,location_id,plot_id', 'b1000000-0000-0000-0000-000000000008'),
        ('mrv_claim', 'update', '{}', '{}', 'status,review_notes', 'b1000000-0000-0000-0000-000000000008'),
        ('field_note', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000008'),
        ('field_note', 'create', '{}', '{}', 'note_date,note_type,title,content,images,tags,plot_id,crop_cycle_id,location_id', 'b1000000-0000-0000-0000-000000000008'),
        ('agent_identity', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000008'),
        ('agent_identity', 'create', '{}', '{}', 'name,agent_type,description,capabilities,wallet_address', 'b1000000-0000-0000-0000-000000000008'),
        ('agent_task', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000008'),
        ('agent_task', 'create', '{}', '{}', 'task_type,input_data,location_id', 'b1000000-0000-0000-0000-000000000008'),
        ('agent_task', 'update', '{}', '{}', 'execution_status,execution_result,error_message', 'b1000000-0000-0000-0000-000000000008'),
        ('agent_action_log', 'create', '{}', '{}', 'task_id,action,collection,record_id,payload_hash,action_result,metadata', 'b1000000-0000-0000-0000-000000000008'),
        ('agent_action_log', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000008'),
        ('ai_summary', 'create', '{}', '{}', 'subject_type,subject_id,summary_type,content,source_record_ids,source_tables,model_version,confidence', 'b1000000-0000-0000-0000-000000000008'),
        ('ai_summary', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000008'),
        ('metric_definition', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000008'),
        ('forecast_scenario', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000008'),
        ('forecast_output', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000008'),
        ('attestation_record', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000008'),
        ('attestation_request', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000008'),
        ('attestation_request', 'create', '{}', '{}', 'subject_type,subject_id,event_type,location_id', 'b1000000-0000-0000-0000-000000000008'),
        ('workflow_history', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000008'),
        ('expense_category', 'read', '{}', '{}', '*', 'b1000000-0000-0000-0000-000000000008');
END IF;
END $$;
