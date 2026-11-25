import os
import subprocess
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import jwt
from fastapi.testclient import TestClient
from psycopg import errors

BACKEND = Path(__file__).resolve().parents[1]
TEST_KEY = "myfinance-fictional-test-key-only-001"
TEST_PASSWORD = "fictional-test-password"
USER = {"id": 7, "nome": "Test User", "email": "tester@example.com"}


class BootstrapAndAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with (
            patch.dict(os.environ, {"JWT_SECRET_KEY": TEST_KEY}),
            patch.object(sys, "path", [str(BACKEND), *sys.path]),
            patch("dotenv.load_dotenv", return_value=False),
            patch("psycopg.connect", side_effect=AssertionError("Unexpected database access")),
        ):
            import auth
            from main import app

        cls.auth = auth
        cls.app = app

    def setUp(self):
        self.enterContext(
            patch("psycopg.connect", side_effect=AssertionError("Unexpected database access"))
        )
        self.client = self.enterContext(TestClient(self.app))

    def test_bootstrap_serves_health_frontend_and_openapi(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/app").status_code, 200)
        schema = self.client.get("/openapi.json")
        self.assertEqual(schema.status_code, 200)
        self.assertIn("/auth/login", schema.json()["paths"])

    def test_startup_rejects_missing_or_blank_jwt_key(self):
        environment = {"PYTHON_DOTENV_DISABLED": "1"}
        if os.name == "nt":
            environment["SystemRoot"] = os.environ["SystemRoot"]
        for value in (None, "", "   "):
            with self.subTest(value=value):
                env = environment.copy()
                if value is not None:
                    env["JWT_SECRET_KEY"] = value
                process = subprocess.run(
                    [sys.executable, "-c", "import main"],
                    cwd=BACKEND,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                self.assertNotEqual(process.returncode, 0)
                self.assertIn("JWT_SECRET_KEY must be set and non-blank", process.stderr)

    def test_registration_stores_argon2_hash(self):
        with patch.object(self.auth, "get_connection") as connect:
            execute = connect.return_value.__enter__.return_value.execute
            execute.return_value.fetchone.return_value = USER
            response = self.client.post(
                "/auth/cadastro", json={"nome": USER["nome"], "email": USER["email"], "senha": TEST_PASSWORD}
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), USER)
        stored_hash = execute.call_args.args[1][2]
        self.assertTrue(stored_hash.startswith("$argon2id$"))
        self.assertTrue(self.auth.password_hash.verify(TEST_PASSWORD, stored_hash))

    def test_duplicate_registration_returns_conflict(self):
        with patch.object(self.auth, "get_connection") as connect:
            execute = connect.return_value.__enter__.return_value.execute
            execute.side_effect = errors.UniqueViolation()
            response = self.client.post(
                "/auth/cadastro", json={"nome": USER["nome"], "email": USER["email"], "senha": TEST_PASSWORD}
            )
        self.assertEqual(response.status_code, 409)

    def test_login_and_authenticated_profile(self):
        stored_hash = self.auth.password_hash.hash(TEST_PASSWORD)
        with patch.object(self.auth, "get_connection") as connect:
            execute = connect.return_value.__enter__.return_value.execute
            execute.return_value.fetchone.return_value = {
                **USER, "ativo": True, "senha_hash": stored_hash
            }
            response = self.client.post(
                "/auth/login", json={"email": USER["email"], "senha": TEST_PASSWORD}
            )
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["usuario"], USER)
            self.assertEqual(data["token_type"], "bearer")
            token = data["access_token"]
            claims = jwt.decode(token, TEST_KEY, algorithms=["HS256"])
            self.assertEqual(claims["sub"], str(USER["id"]))
            self.assertEqual(claims["exp"] - claims["iat"], 60 * 60)

            execute.return_value.fetchone.return_value = USER
            me = self.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
            self.assertEqual(me.status_code, 200)
            self.assertEqual(me.json(), USER)
            self.assertEqual(execute.call_args.args[1], (USER["id"],))

    def test_login_rejects_wrong_password_and_inactive_user(self):
        stored_hash = self.auth.password_hash.hash(TEST_PASSWORD)
        with patch.object(self.auth, "get_connection") as connect:
            execute = connect.return_value.__enter__.return_value.execute
            for active, password in ((True, "incorrect"), (False, TEST_PASSWORD)):
                with self.subTest(active=active):
                    execute.return_value.fetchone.return_value = {
                        **USER, "ativo": active, "senha_hash": stored_hash
                    }
                    response = self.client.post(
                        "/auth/login", json={"email": USER["email"], "senha": password}
                    )
                    self.assertEqual(response.status_code, 401)

    def test_profile_rejects_missing_invalid_and_expired_tokens(self):
        expired = jwt.encode(
            {"sub": str(USER["id"]), "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
            TEST_KEY,
            algorithm="HS256",
        )
        for token in (None, "invalid", expired):
            with self.subTest(token_present=token is not None):
                headers = {"Authorization": f"Bearer {token}"} if token else {}
                response = self.client.get("/auth/me", headers=headers)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.headers["WWW-Authenticate"], "Bearer")
