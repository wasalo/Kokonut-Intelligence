-- Correct the Data Post schema UID after its Celo mainnet registration.
UPDATE attestation_schema
SET schema_uid = '0xf0de37f5c4a441aedb794d5585201c6ef150543dc53f894e1212f7e330205045',
    resolver_address = '0x6E1502c7a14b45aba5FC420dC92C1E3b38BD79Ad',
    active = TRUE
WHERE id = 'a0000000-0000-0000-0000-0000000001e6'
  AND name = 'Kokonut Data Post'
  AND chain = 'celo';
