"""Local stand-in for Supabase Auth and Storage: development and tests only, never deployed.

It implements the few calls this project makes, issues ES256 tokens and keeps files in memory. CI also runs the
same end-to-end tests against the real Supabase stack (`supabase start`).
"""
import base64
import hashlib
import secrets
import time
import uuid

import jwt
import psycopg
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse


def create(base_url, database_url):
    key, kid = ec.generate_private_key(ec.SECP256R1()), "local-dev"
    refresh, recovery, files = {}, {}, {}
    app = FastAPI()
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], expose_headers=["*"])

    def query(sql, *values):
        with psycopg.connect(database_url, autocommit=True) as conn:
            cursor = conn.execute(sql, values)
            return cursor.fetchone() if cursor.description else None

    def hashed(password):
        return hashlib.sha256(password.encode()).hexdigest()

    def user_json(user_id, email):
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        return {"id": str(user_id), "aud": "authenticated", "role": "authenticated", "email": email, "app_metadata": {},
                "user_metadata": {}, "identities": [], "created_at": now, "updated_at": now, "email_confirmed_at": now}

    def session(user_id, email):
        now = int(time.time())
        token = jwt.encode({"sub": str(user_id), "email": email, "aud": "authenticated", "role": "authenticated",
                            "iss": f"{base_url}/auth/v1", "iat": now, "exp": now + 3600, "session_id": str(uuid.uuid4())},
                           key, algorithm="ES256", headers={"kid": kid})
        renew = secrets.token_hex(12)
        refresh[renew] = (user_id, email)
        return {"access_token": token, "token_type": "bearer", "expires_in": 3600, "expires_at": now + 3600,
                "refresh_token": renew, "user": user_json(user_id, email)}

    def fail(status, code, message):
        return JSONResponse({"code": status, "error_code": code, "msg": message}, status)

    def caller(request):
        token = request.headers.get("authorization", "").removeprefix("Bearer ")
        return jwt.decode(token, key.public_key(), algorithms=["ES256"], audience="authenticated")

    @app.get("/auth/v1/.well-known/jwks.json")
    def jwks():
        numbers = key.public_key().public_numbers()

        def encode(n):
            return base64.urlsafe_b64encode(n.to_bytes(32, "big")).rstrip(b"=").decode()
        return {"keys": [{"kty": "EC", "crv": "P-256", "x": encode(numbers.x), "y": encode(numbers.y), "kid": kid,
                          "alg": "ES256", "use": "sig", "key_ops": ["verify"], "ext": True}]}

    @app.post("/auth/v1/signup")
    async def signup(request: Request):
        body = await request.json()
        if len(body.get("password", "")) < 8:
            return fail(422, "weak_password", "Password should be at least 8 characters.")
        if query("SELECT 1 FROM auth.users WHERE email = %s", body["email"]):
            return fail(422, "user_already_exists", "User already registered")
        name = (body.get("data") or {}).get("full_name", "")
        user_id = query("INSERT INTO auth.users (email, encrypted_password, raw_user_meta_data) VALUES (%s, %s, "
                        "jsonb_build_object('full_name', %s::text)) RETURNING id", body["email"], hashed(body["password"]), name)[0]
        return session(user_id, body["email"])

    @app.post("/auth/v1/token")
    async def token(request: Request, grant_type: str):
        body = await request.json()
        if grant_type == "password":
            row = query("SELECT id, email FROM auth.users WHERE email = %s AND encrypted_password = %s",
                        body.get("email"), hashed(body.get("password", "")))
            return session(*row) if row else fail(400, "invalid_credentials", "Invalid login credentials")
        known = refresh.pop(body.get("refresh_token"), None)
        return session(*known) if known else fail(400, "refresh_token_not_found", "Invalid Refresh Token")

    @app.get("/auth/v1/user")
    def get_user(request: Request):
        claims = caller(request)
        return user_json(claims["sub"], claims["email"])

    @app.put("/auth/v1/user")
    async def update_user(request: Request):
        claims, body = caller(request), await request.json()
        if body.get("password"):
            query("UPDATE auth.users SET encrypted_password = %s WHERE id = %s", hashed(body["password"]), claims["sub"])
        return user_json(claims["sub"], claims["email"])

    @app.post("/auth/v1/logout")
    def logout():
        return Response(status_code=204)

    @app.post("/auth/v1/recover")
    async def recover(request: Request):
        body = await request.json()
        row = query("SELECT id, email FROM auth.users WHERE email = %s", body["email"])
        if row:
            recovery[body["email"]] = secrets.token_hex(16)
        return {}

    @app.post("/auth/v1/verify")
    async def verify(request: Request):
        body = await request.json()
        email = next((e for e, t in recovery.items() if t == body.get("token_hash")), None)
        if body.get("type") != "recovery" or email is None:
            return fail(403, "otp_expired", "Email link is invalid or has expired")
        del recovery[email]
        return session(*query("SELECT id, email FROM auth.users WHERE email = %s", email))

    @app.get("/dev/recovery-token")  # what the e-mail would carry
    def recovery_token(email: str):
        return {"token_hash": recovery.get(email)}

    @app.post("/storage/v1/object/sign/{path:path}")
    def sign(path: str):
        return {"signedURL": f"/object/sign/{path}?token=local"} if path in files else fail(404, "not_found", "Object not found")

    @app.get("/storage/v1/object/{kind}/{path:path}")
    def download(kind: str, path: str):
        if path not in files:
            return fail(404, "not_found", "Object not found")
        content, mime = files[path]
        return Response(content, media_type=mime)

    @app.post("/storage/v1/object/{path:path}")
    async def upload(path: str, request: Request):
        files[path] = (await request.body(), request.headers.get("content-type", "application/octet-stream"))
        return {"Key": path}

    return app
