-- Row Level Security. Browsers never write to these tables: every write goes through the FastAPI backend,
-- which checks the role again. RLS is the second lock, for anyone holding a user token.

GRANT USAGE ON SCHEMA core, app TO authenticated, service_role;
REVOKE ALL ON SCHEMA core, app FROM anon, PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA core, app FROM anon, authenticated, PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA app FROM anon, authenticated, PUBLIC;
GRANT EXECUTE ON FUNCTION app.current_user_role() TO authenticated;
GRANT EXECUTE ON FUNCTION app.acting_user() TO service_role;
GRANT EXECUTE ON FUNCTION app.handle_new_user() TO supabase_auth_admin;   -- the sign-up trigger runs as this role
GRANT SELECT ON ALL TABLES IN SCHEMA core, app TO authenticated;
GRANT SELECT ON ALL TABLES IN SCHEMA core, app TO service_role;

DO $$
DECLARE t RECORD;
BEGIN
    FOR t IN SELECT schemaname, tablename FROM pg_tables WHERE schemaname IN ('core', 'app') LOOP
        EXECUTE format('ALTER TABLE %I.%I ENABLE ROW LEVEL SECURITY', t.schemaname, t.tablename);
    END LOOP;
    -- Planning data: any active user may read it.
    FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'core' LOOP
        EXECUTE format('CREATE POLICY read_active ON core.%I FOR SELECT TO authenticated '
                       'USING ((SELECT app.current_user_role()) IS NOT NULL)', t.tablename);
    END LOOP;
    -- Workflow state that every role follows.
    FOR t IN SELECT unnest(ARRAY['planning_runs','what_if_requests','explanation_records',
                                 'explanation_verifications','approvals','action_items',
                                 'action_status_history']) AS tablename LOOP
        EXECUTE format('CREATE POLICY read_active ON app.%I FOR SELECT TO authenticated '
                       'USING ((SELECT app.current_user_role()) IS NOT NULL)', t.tablename);
    END LOOP;
    -- Engineering documents and their text.
    FOR t IN SELECT unnest(ARRAY['ecn_reviews','document_metadata']) AS tablename LOOP
        EXECUTE format('CREATE POLICY read_engineering ON app.%I FOR SELECT TO authenticated '
                       'USING ((SELECT app.current_user_role()) IN '
                       '(''ADMIN'',''ENGINEERING'',''PRODUCTION_PLANNER'',''QUALITY''))', t.tablename);
    END LOOP;
    -- Governance records.
    FOR t IN SELECT unnest(ARRAY['audit_log','legacy_audit_events','replay_records']) AS tablename LOOP
        EXECUTE format('CREATE POLICY read_governance ON app.%I FOR SELECT TO authenticated '
                       'USING ((SELECT app.current_user_role()) IN '
                       '(''ADMIN'',''ENGINEERING'',''PRODUCTION_PLANNER'',''QUALITY''))', t.tablename);
    END LOOP;
END $$;

CREATE POLICY read_own_profile ON app.user_profiles FOR SELECT TO authenticated
USING (user_id = (SELECT auth.uid()) OR (SELECT app.current_user_role()) = 'ADMIN');
-- No INSERT, UPDATE or DELETE policy and no such grant exists: users cannot change their own role.

-- Private document bucket. Objects are written and signed by the backend only.
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES ('ecn-documents', 'ecn-documents', FALSE, 10485760, ARRAY['application/pdf', 'text/plain'])
ON CONFLICT (id) DO UPDATE SET public = FALSE, file_size_limit = EXCLUDED.file_size_limit,
                               allowed_mime_types = EXCLUDED.allowed_mime_types;

CREATE POLICY ecn_documents_read ON storage.objects FOR SELECT TO authenticated
USING (bucket_id = 'ecn-documents' AND (SELECT app.current_user_role())
       IN ('ADMIN','ENGINEERING','PRODUCTION_PLANNER','QUALITY'));
