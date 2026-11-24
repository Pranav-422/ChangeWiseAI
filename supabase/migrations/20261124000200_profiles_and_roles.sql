-- User profiles linked to Supabase Auth. The role lives here and nowhere else.
CREATE SCHEMA IF NOT EXISTS app;

CREATE TABLE app.user_profiles (
    user_id    UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email      TEXT NOT NULL,
    full_name  TEXT NOT NULL DEFAULT '',
    role       TEXT NOT NULL DEFAULT 'VIEWER' CHECK (role IN
                 ('ADMIN','ENGINEERING','PURCHASING','PRODUCTION_PLANNER','QUALITY','VIEWER')),
    is_active  BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Every new account starts as VIEWER. Metadata sent by the client never sets the role.
CREATE FUNCTION app.handle_new_user() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
BEGIN
    INSERT INTO app.user_profiles (user_id, email, full_name)
    VALUES (NEW.id, coalesce(NEW.email, ''), left(coalesce(NEW.raw_user_meta_data ->> 'full_name', ''), 120))
    ON CONFLICT (user_id) DO NOTHING;
    RETURN NEW;
END $$;

CREATE TRIGGER on_auth_user_created AFTER INSERT ON auth.users
FOR EACH ROW EXECUTE FUNCTION app.handle_new_user();

-- Accounts that existed before this migration.
INSERT INTO app.user_profiles (user_id, email, full_name)
SELECT id, coalesce(email, ''), left(coalesce(raw_user_meta_data ->> 'full_name', ''), 120) FROM auth.users
ON CONFLICT (user_id) DO NOTHING;

-- Role of the calling user, or NULL when there is no active profile. Used by every RLS policy.
CREATE FUNCTION app.current_user_role() RETURNS TEXT
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
    SELECT role FROM app.user_profiles WHERE user_id = (SELECT auth.uid()) AND is_active
$$;

-- The backend announces the acting user once per transaction; column defaults and triggers read it.
CREATE FUNCTION app.acting_user() RETURNS UUID
LANGUAGE sql STABLE SET search_path = '' AS $$
    SELECT nullif(current_setting('app.user_id', true), '')::uuid
$$;
