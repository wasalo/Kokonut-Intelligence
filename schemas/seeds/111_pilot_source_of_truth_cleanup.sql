-- Canonical Adelphi pilot cleanup.
-- The old labels are retained only as historical compatibility aliases in
-- 024_adelphi_alignment.sql; operational rows use Adelphi/ Dominican context.

UPDATE expense_event
SET vendor = CASE vendor
    WHEN 'Kisumu Water Co' THEN 'Adelphi Water Cooperative'
    WHEN 'Kisumu Agro Mechanics' THEN 'Adelphi Farm Services'
    WHEN 'Kisumu Transport Co' THEN 'Dominican Transport Cooperative'
    WHEN 'Kisumu County Land Board' THEN 'Adelphi Land Stewardship'
    WHEN 'Kisumu Agricultural Consultants' THEN 'Dominican Agronomy Advisors'
    WHEN 'AgroSupplies Kenya' THEN 'Adelphi Farm Services'
    WHEN 'Kenya Power' THEN 'Adelphi Renewable Utilities'
    ELSE vendor
END,
description = replace(description, 'Nairobi market', 'local market')
WHERE location_id = 'a0000000-0000-0000-0000-000000000001'
  AND (vendor IN (
      'Kisumu Water Co', 'Kisumu Agro Mechanics', 'Kisumu Transport Co',
      'Kisumu County Land Board', 'Kisumu Agricultural Consultants',
      'AgroSupplies Kenya', 'Kenya Power'
  ) OR description LIKE '%Nairobi market%');

UPDATE infrastructure_asset
SET description = replace(description, 'Kenya', 'Dominican Republic')
WHERE location_id = 'a0000000-0000-0000-0000-000000000001';
