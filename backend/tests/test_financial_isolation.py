import os
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock, patch

import jwt
from fastapi.testclient import TestClient
from psycopg import errors

BACKEND = Path(__file__).resolve().parents[1]
TEST_KEY = "myfinance-fictional-financial-tests-only"
USERS = {
    11: {"id": 11, "nome": "User A", "email": "a@example.com"},
    22: {"id": 22, "nome": "User B", "email": "b@example.com"},
}
MOVEMENT = {
    "descricao": "Test movement",
    "valor": "12.50",
    "tipo": "despesa",
    "data_transacao": "2024-02-20",
    "categoria_id": 1,
}
BILL = {
    "descricao": "Test bill",
    "valor": "12.50",
    "dia_vencimento": 31,
    "categoria_id": 1,
}
PAYMENT = {"data_pagamento": "2024-02-20"}
PERIOD = "?ano=2024&mes=2"
FEB = date(2024, 2, 1)
MAR = date(2024, 3, 1)
DUE = "/pagamentos/vencimentos"


class FinancialIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with (
            patch.dict(os.environ, {"JWT_SECRET_KEY": TEST_KEY}),
            patch.object(sys, "path", [str(BACKEND), *sys.path]),
            patch("dotenv.load_dotenv", return_value=False),
            patch("psycopg.connect", side_effect=AssertionError("Unexpected database access")),
        ):
            import auth
            import main
            import pagamentos

        cls.auth, cls.main, cls.pagamentos = auth, main, pagamentos

    def setUp(self):
        self.enterContext(
            patch("psycopg.connect", side_effect=AssertionError("Unexpected database access"))
        )
        auth_conn = self.enterContext(patch.object(self.auth, "get_connection"))
        lookup = auth_conn.return_value.__enter__.return_value.execute

        def lookup_active_user(sql, params):
            self.assertIn("ativo = TRUE", sql)
            return Mock(**{"fetchone.return_value": USERS.get(params[0])})

        lookup.side_effect = lookup_active_user
        self.lookup = lookup
        self.financial = Mock()
        self.financial.return_value.__enter__ = Mock(return_value=Mock())
        self.financial.return_value.__exit__ = Mock(return_value=False)
        self.sql = self.financial.return_value.__enter__.return_value.execute
        self.enterContext(patch.object(self.main, "get_connection", self.financial))
        self.enterContext(patch.object(self.pagamentos, "get_connection", self.financial))
        self.client = self.enterContext(TestClient(self.main.app))

    def request(self, method, path, payload=None, user_id=None, token=None):
        if user_id is not None:
            token = self.auth.criar_token(user_id)
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return self.client.request(method, path, headers=headers, json=payload)

    def assert_queries(self, expected):
        self.assertEqual(self.sql.call_count, len(expected))
        for call, (fragments, params) in zip(self.sql.call_args_list, expected, strict=True):
            for fragment in fragments:
                self.assertIn(fragment, " ".join(call.args[0].split()))
            self.assertEqual(call.args[1:], (params,) if params is not None else ())

    def query_results(self, *results):
        self.sql.reset_mock()
        self.sql.side_effect = results

    def test_all_financial_routes_require_authentication(self):
        cases = [
            ("GET", "/categorias", None),
            ("GET", "/transacoes", None),
            ("POST", "/transacoes", MOVEMENT),
            ("GET", "/transacoes/1", None),
            ("PUT", "/transacoes/1", MOVEMENT),
            ("DELETE", "/transacoes/1", None),
            ("GET", "/contas-fixas", None),
            ("POST", "/contas-fixas", BILL),
            ("GET", "/contas-fixas/1", None),
            ("PUT", "/contas-fixas/1", BILL),
            ("DELETE", "/contas-fixas/1", None),
            ("GET", "/relatorios/mensal" + PERIOD, None),
            ("GET", DUE + PERIOD, None),
            ("POST", DUE + "/1/pagar", PAYMENT),
            ("POST", DUE + "/1/estornar", None),
        ]
        for method, path, payload in cases:
            with self.subTest(method=method, path=path):
                response = self.request(method, path, payload)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.headers["WWW-Authenticate"], "Bearer")
        self.lookup.assert_not_called()
        self.financial.assert_not_called()

    def test_invalid_expired_and_inactive_tokens_never_open_financial_connection(self):
        expired = jwt.encode(
            {"sub": "11", "exp": datetime.now(timezone.utc) - timedelta(seconds=1)},
            self.auth.JWT_SECRET_KEY,
            algorithm="HS256",
        )
        for token in ("invalid", expired, self.auth.criar_token(33)):
            with self.subTest():
                self.assertEqual(self.request("GET", "/transacoes", token=token).status_code, 401)
        self.lookup.assert_called_once()
        self.financial.assert_not_called()

    def test_authenticated_categories_are_global_and_read_only(self):
        self.query_results(Mock(**{"fetchall.return_value": [{"id": 1, "nome": "Test"}]}))
        self.assertEqual(self.request("GET", "/categorias", user_id=11).status_code, 200)
        self.assert_queries([(("SELECT id, nome FROM categorias",), None)])
        self.assertEqual(self.request("POST", "/categorias", {}, user_id=11).status_code, 405)

    def test_two_users_get_separate_movements_and_bills(self):
        for user_id in USERS:
            for path, table, record in (
                ("/transacoes", "transacoes", MOVEMENT),
                ("/contas-fixas", "contas_fixas", BILL),
            ):
                with self.subTest(user=user_id, path=path):
                    row = {**record, "id": user_id * 10, "descricao": f"User {user_id}"}
                    self.query_results(Mock(**{"fetchall.return_value": [row]}))
                    # A query string cannot override the authenticated scope.
                    response = self.request("GET", path + "?usuario_id=999", user_id=user_id)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual([item["id"] for item in response.json()], [row["id"]])
                    self.assert_queries([((f"FROM {table} WHERE usuario_id = %s",), (user_id,))])

    def test_creation_uses_owner_from_session(self):
        for user_id in USERS:
            for path, payload, table, params in (
                ("/transacoes", MOVEMENT, "transacoes",
                 ("Test movement", Decimal("12.50"), "despesa", date(2024, 2, 20), 1, None)),
                ("/contas-fixas", BILL, "contas_fixas", ("Test bill", Decimal("12.50"), 31, 1, True)),
            ):
                with self.subTest(path=path, user=user_id):
                    self.query_results(Mock(**{"fetchone.return_value": {**payload, "id": 101}}))
                    response = self.request("POST", path, payload, user_id=user_id)
                    self.assertEqual(response.status_code, 201)
                    self.assert_queries([
                        ((f"INSERT INTO {table}", "usuario_id ) VALUES"), (*params, user_id)),
                    ])

    def test_payload_cannot_set_or_change_owner(self):
        for method, path, payload in (
            ("POST", "/transacoes", MOVEMENT),
            ("PUT", "/transacoes/1", MOVEMENT),
            ("POST", "/contas-fixas", BILL),
            ("PUT", "/contas-fixas/1", BILL),
            ("POST", DUE + "/1/pagar", PAYMENT),
        ):
            with self.subTest(method=method, path=path):
                response = self.request(method, path, {**payload, "usuario_id": 22}, user_id=11)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json()["detail"][0]["loc"], ["body", "usuario_id"])
        self.financial.assert_not_called()

    def test_cross_owner_and_ownerless_movement_access_returns_404(self):
        for record_id in (220, 300):
            for method, payload, result in (
                ("GET", None, "FROM transacoes WHERE"),
                ("PUT", MOVEMENT, "UPDATE transacoes"),
                ("DELETE", None, "DELETE FROM transacoes WHERE"),
            ):
                with self.subTest(method=method, record_id=record_id):
                    absent = Mock(**{"fetchone.return_value": None})
                    linked = [] if method == "GET" else [
                        (("WHERE t.id = %s AND t.usuario_id = %s",), (record_id, 11))
                    ]
                    self.query_results(*([absent] * (len(linked) + 1)))
                    response = self.request(
                        method, f"/transacoes/{record_id}", payload, user_id=11
                    )
                    self.assertEqual(response.status_code, 404)
                    params = (record_id, 11)
                    if method == "PUT":
                        params = ("Test movement", Decimal("12.50"), "despesa",
                                  date(2024, 2, 20), 1, None, *params)
                    self.assert_queries([
                        *linked,
                        ((result, "WHERE id = %s AND usuario_id = %s"), params),
                    ])

    def test_cross_owner_and_ownerless_bill_access_returns_404(self):
        for record_id in (220, 300):
            for method, payload in (("GET", None), ("PUT", BILL), ("DELETE", None)):
                with self.subTest(method=method, record_id=record_id):
                    self.query_results(Mock(**{"fetchone.return_value": None}))
                    response = self.request(method, f"/contas-fixas/{record_id}", payload, user_id=11)
                    self.assertEqual(response.status_code, 404)
                    fragments = ("FROM contas_fixas", "WHERE id = %s AND usuario_id = %s")
                    params = (record_id, 11)
                    if method == "PUT":
                        fragments = ("UPDATE contas_fixas", "WHERE id = %s AND usuario_id = %s")
                        params = ("Test bill", Decimal("12.50"), 31, 1, True, *params)
                    if method == "DELETE":
                        fragments += ("FOR UPDATE",)
                    self.assert_queries([(fragments, params)])

    def test_monthly_report_filters_each_component(self):
        for user_id in USERS:
            with self.subTest(user=user_id):
                self.query_results(
                    Mock(**{"fetchone.return_value": {"receitas": Decimal(user_id), "despesas": Decimal(2)}}),
                    Mock(**{"fetchall.return_value": [{"categoria": f"Group {user_id}", "total": Decimal(2)}]}),
                    Mock(**{"fetchall.return_value": [
                        {**BILL, "id": user_id, "valor": Decimal("12.50")}
                    ]}),
                )
                response = self.request("GET", "/relatorios/mensal" + PERIOD, user_id=user_id)
                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertEqual(data["saldo"], str(user_id - 2))
                self.assertEqual(data["despesas_por_categoria"][0]["categoria"], f"Group {user_id}")
                self.assertEqual(data["contas_fixas_previstas"][0]["id"], user_id)
                self.assert_queries([
                    (("FROM transacoes WHERE usuario_id = %s",), (user_id, FEB, MAR)),
                    (("WHERE t.usuario_id = %s",), (user_id, FEB, MAR)),
                    (("FROM contas_fixas WHERE usuario_id = %s AND ativa = TRUE",), (user_id,)),
                ])

    def test_due_generation_and_listing_use_only_owned_bills(self):
        for user_id in USERS:
            with self.subTest(user=user_id):
                bill = {**BILL, "id": user_id * 10, "valor": Decimal("12.50")}
                self.query_results(
                    Mock(**{"fetchall.return_value": [bill]}),
                    Mock(),
                    Mock(**{"fetchall.return_value": [{"id": user_id, "conta_fixa_id": bill["id"]}]}),
                )
                response = self.request("GET", DUE + PERIOD, user_id=user_id)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()[0]["conta_fixa_id"], bill["id"])
                self.assert_queries([
                    (("WHERE usuario_id = %s AND ativa = TRUE", "FOR SHARE"), (user_id,)),
                    (("INSERT INTO vencimentos", "ON CONFLICT"),
                     (bill["id"], FEB, date(2024, 2, 29), bill["descricao"], bill["valor"], 1)),
                    (("WHERE v.competencia = %s AND c.usuario_id = %s",
                      "t.usuario_id = c.usuario_id", "v.transacao_id IS NULL OR t.id IS NOT NULL"),
                     (FEB, user_id)),
                ])

    def test_cross_owner_payment_and_reversal_do_not_write(self):
        for action, payload in (("pagar", PAYMENT), ("estornar", None)):
            with self.subTest(action=action):
                self.query_results(Mock(**{"fetchone.return_value": None}))
                response = self.request("POST", DUE + "/220/" + action, payload, user_id=11)
                self.assertEqual(response.status_code, 404)
                self.assert_queries([
                    (("WHERE v.id = %s AND c.usuario_id = %s",
                      "t.usuario_id = c.usuario_id", "FOR UPDATE OF v"), (220, 11)),
                ])

    def test_own_payment_and_reversal_use_one_transaction_per_request(self):
        due = {**BILL, "valor": Decimal("12.50"), "transacao_id": None}
        self.query_results(Mock(**{"fetchone.return_value": due}),
                           Mock(**{"fetchone.return_value": {"id": 81}}), Mock())
        response = self.request("POST", DUE + "/110/pagar", PAYMENT, user_id=11)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["transacao_id"], 81)
        self.financial.assert_called_once()
        self.financial.return_value.__exit__.assert_called_once_with(None, None, None)
        self.assert_queries([
            (("c.usuario_id = %s", "FOR UPDATE OF v"), (110, 11)),
            (("INSERT INTO transacoes", "usuario_id ) VALUES"),
             ("Test bill", Decimal("12.50"), date(2024, 2, 20), 1, "Pagamento de conta fixa", 11)),
            (("UPDATE vencimentos", "AND c.usuario_id = %s"), (81, 110, 11)),
        ])

        self.financial.reset_mock()
        self.query_results(Mock(**{"fetchone.return_value": {**due, "transacao_id": 81}}),
                           Mock(), Mock(**{"fetchone.return_value": {"id": 81}}))
        response = self.request("POST", DUE + "/110/estornar", user_id=11)
        self.assertEqual(response.status_code, 200)
        self.financial.assert_called_once()
        self.financial.return_value.__exit__.assert_called_once_with(None, None, None)
        self.assert_queries([
            (("c.usuario_id = %s", "FOR UPDATE OF v"), (110, 11)),
            (("SET transacao_id = NULL", "AND c.usuario_id = %s"), (110, 11)),
            (("DELETE FROM transacoes WHERE id = %s AND usuario_id = %s",), (81, 11)),
        ])

    def test_failed_payment_link_exits_connection_with_exception(self):
        due = {**BILL, "valor": Decimal("12.50"), "transacao_id": None}
        self.query_results(Mock(**{"fetchone.return_value": due}),
                           Mock(**{"fetchone.return_value": {"id": 81}}),
                           errors.ForeignKeyViolation())
        with self.assertRaises(errors.ForeignKeyViolation):
            self.request("POST", DUE + "/110/pagar", PAYMENT, user_id=11)
        self.assertIs(self.financial.return_value.__exit__.call_args.args[0], errors.ForeignKeyViolation)

    def test_reversal_with_unavailable_linked_transaction_signals_rollback(self):
        due = {"transacao_id": 81}
        self.query_results(
            Mock(**{"fetchone.return_value": due}),
            Mock(),
            Mock(**{"fetchone.return_value": None}),
        )
        response = self.request("POST", DUE + "/110/estornar", user_id=11)
        self.assertEqual(response.status_code, 404)
        self.assert_queries([
            (("FOR UPDATE OF v",), (110, 11)),
            (("SET transacao_id = NULL", "AND c.usuario_id = %s"), (110, 11)),
            (("DELETE FROM transacoes WHERE id = %s AND usuario_id = %s",), (81, 11)),
        ])
        self.assertEqual(self.financial.return_value.__exit__.call_args.args[1].status_code, 404)
