-- KIPAWA PLATFORM — DATABASE CLEANUP
-- Deletes all farm-related data, preserves admin users only
-- Run: docker exec -i plotra-postgres psql -U postgres -d plotra_db < clean_farms.sql

BEGIN;

-- Delete in order respecting foreign key constraints
DELETE FROM eudr_submissions;
DELETE FROM batches;
DELETE FROM deliveries;
DELETE FROM land_parcels;
DELETE FROM farms;
-- Cooperative members reference users & cooperatives
DELETE FROM cooperative_members;
-- Cooperatives reference users (primary_officer_id)
DELETE FROM cooperatives;
-- Now delete non-admin users (farmers, coop officers, reviewers)
DELETE FROM users WHERE role NOT IN ('plotra_admin');

COMMIT;

-- Show counts after cleanup
SELECT 'Remaining users:' AS info, COUNT(*) FROM users;
SELECT 'Remaining farms:' AS info, COUNT(*) FROM farms;
SELECT 'Remaining parcels:' AS info, COUNT(*) FROM land_parcels;
SELECT 'Remaining cooperatives:' AS info, COUNT(*) FROM cooperatives;

