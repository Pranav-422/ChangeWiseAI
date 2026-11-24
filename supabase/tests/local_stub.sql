-- The parts of a Supabase project that the migrations rely on, for a plain PostgreSQL in tests and local
-- development. Never apply this to a Supabase project: the real objects are already there.
DO $$
DECLARE r TEXT;
BEGIN
    FOREACH r IN ARRAY ARRAY['anon', 'authenticated', 'service_role', 'supabase_auth_admin'] LOOP
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = r) THEN
            EXECUTE format('CREATE ROLE %I NOLOGIN', r);
        END IF;
    END LOOP;
END $$;
ALTER ROLE service_role BYPASSRLS;

CREATE SCHEMA auth;
CREATE TABLE auth.users (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email              TEXT UNIQUE,
    encrypted_password TEXT,
    raw_user_meta_data JSONB NOT NULL DEFAULT '{}'
);
CREATE FUNCTION auth.uid() RETURNS UUID LANGUAGE sql STABLE AS $$
    SELECT (nullif(current_setting('request.jwt.claims', true), '')::json ->> 'sub')::uuid
$$;
GRANT USAGE ON SCHEMA auth TO authenticated, anon, service_role;

CREATE SCHEMA storage;
CREATE TABLE storage.buckets (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, public BOOLEAN DEFAULT FALSE,
    file_size_limit BIGINT, allowed_mime_types TEXT[]
);
CREATE TABLE storage.objects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), bucket_id TEXT REFERENCES storage.buckets(id),
    name TEXT NOT NULL, owner UUID, UNIQUE (bucket_id, name)
);
ALTER TABLE storage.objects ENABLE ROW LEVEL SECURITY;
GRANT USAGE ON SCHEMA storage TO authenticated, anon, service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON storage.objects TO authenticated, anon;
