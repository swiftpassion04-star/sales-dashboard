-- This migration creates assignment table only.
-- It does not seed users.
-- It does not change crm_user_roles.
-- It does not change manual order/follow-up/import write paths.
-- Team membership is effective-dated.

CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE IF NOT EXISTS public.crm_user_team_assignments (
  id bigserial PRIMARY KEY,
  user_email text NOT NULL,
  team_code text NOT NULL,
  team_name text GENERATED ALWAYS AS (
    CASE team_code
      WHEN 'CRM_TEAM' THEN 'CRM Team'
      WHEN 'UPSELL_TEAM' THEN 'Upsell Team'
    END
  ) STORED,
  effective_from timestamptz NOT NULL,
  effective_to timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  created_by text,
  updated_at timestamptz NOT NULL DEFAULT now(),
  updated_by text,
  CONSTRAINT chk_team_code
    CHECK (team_code IN ('CRM_TEAM', 'UPSELL_TEAM')),
  CONSTRAINT chk_normalized_user_email
    CHECK (user_email <> '' AND user_email = lower(btrim(user_email))),
  CONSTRAINT chk_assignment_period
    CHECK (effective_to IS NULL OR effective_to > effective_from),
  CONSTRAINT ex_assignment_period
    EXCLUDE USING gist (
      user_email WITH =,
      tstzrange(effective_from, effective_to, '[)') WITH &&
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_team_assignment_current_user
  ON public.crm_user_team_assignments (user_email)
  WHERE effective_to IS NULL;

CREATE INDEX IF NOT EXISTS idx_team_assignment_user_period
  ON public.crm_user_team_assignments (user_email, effective_from DESC);

CREATE INDEX IF NOT EXISTS idx_team_assignment_team_period
  ON public.crm_user_team_assignments
  (team_code, effective_from, effective_to);
