-- Synthetic device/media snapshot. Not a numbered seed or migration.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';
LOCK TABLE location, mobile_device, offline_collection, mobile_media_upload IN EXCLUSIVE MODE;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM location) OR EXISTS (SELECT 1 FROM mobile_device)
       OR EXISTS (SELECT 1 FROM offline_collection) OR EXISTS (SELECT 1 FROM mobile_media_upload) THEN
        RAISE EXCEPTION 'Media fixture requires empty domain/device/media tables';
    END IF;
END $$;
INSERT INTO location (id,name,slug,country,region,timezone,metadata)
VALUES ('a0000000-0000-0000-0000-000000000001','Kokonut Adelphi','kokonut-adelphi',
    'Dominican Republic','Monte Plata','America/Santo_Domingo','{"synthetic_recovery_fixture":true}');
-- No bearer/device token is minted; this seed grants no device authority.
INSERT INTO mobile_device (id,device_id,device_name,location_id,user_id,metadata)
VALUES ('f0000000-0000-4000-8000-000000000010','kernel-recovery-adelphi-device',
    'Synthetic recovery device','a0000000-0000-0000-0000-000000000001',
    'synthetic-capture-operator','{"synthetic_recovery_fixture":true}');
INSERT INTO offline_collection
    (id,device_id,user_id,location_id,collection_type,client_id,payload,photo_refs,sync_status,metadata)
VALUES ('f0000000-0000-4000-8000-000000000013','kernel-recovery-adelphi-device',
    'synthetic-capture-operator','a0000000-0000-0000-0000-000000000001','photo',
    'kernel-recovery-attached-client','{"synthetic_recovery_fixture":true}',
    '["f0000000-0000-4000-8000-000000000012"]','synced','{"synthetic_recovery_fixture":true}');
INSERT INTO mobile_media_upload
    (media_id,device_id,user_id,collection_client_id,location_id,object_key,
     content_type,size_bytes,content_sha256,status,attached_collection_id)
SELECT media_id::uuid,'kernel-recovery-adelphi-device','synthetic-capture-operator',
    CASE WHEN status='attached' THEN 'kernel-recovery-attached-client' ELSE 'kernel-recovery-upload-client' END,
    'a0000000-0000-0000-0000-000000000001'::uuid,object_key,'image/jpeg',
    size_bytes,content_sha256,status,
    CASE WHEN status='attached' THEN 'f0000000-0000-4000-8000-000000000013'::uuid ELSE NULL END
FROM jsonb_to_recordset(:'media_records'::jsonb)
    AS records(media_id text,status text,object_key text,size_bytes integer,content_sha256 text);
COMMIT;
