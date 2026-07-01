-- Roll back only the team assignment table created by the paired migration.
-- Keep btree_gist because other database objects may depend on the extension.

DROP TABLE IF EXISTS public.crm_user_team_assignments;
