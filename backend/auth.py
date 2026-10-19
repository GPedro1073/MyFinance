
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field
from pwdlib import PasswordHash
from psycopg import errors
import os
from datetime import datetime, timedelta, timezone

import jwt
from dotenv import load_dotenv
from database import get_connection
import os
from datetime import datetime, timedelta, timezone

import jwt
from dotenv import load_dotenv
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
load_dotenv()

JWT_SECRET_KEY = os.environ["JWT_SECRET_KEY"]
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_MINUTES = 60


def criar_token(usuario_id: int):
    agora = datetime.now(timezone.utc)

    payload = {
        "sub": str(usuario_id),
        "iat": agora,
        "exp": agora + timedelta(
            minutes=JWT_EXPIRATION_MINUTES
        )
    }

    return jwt.encode(
        payload,
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM
    )


# Validação do token JWT

seguranca = HTTPBearer(auto_error=False)


def obter_usuario_atual(
    credenciais: HTTPAuthorizationCredentials | None = Depends(seguranca)
):
    erro_autenticacao = HTTPException(
        status_code=401,
        detail="Token inválido ou expirado",
        headers={"WWW-Authenticate": "Bearer"}
    )

    if credenciais is None:
        raise erro_autenticacao

    try:
        payload = jwt.decode(
            credenciais.credentials,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM]
        )

        usuario_id = int(payload["sub"])

    except (jwt.InvalidTokenError, KeyError, ValueError, TypeError):
        raise erro_autenticacao

    with get_connection() as conn:
        usuario = conn.execute(
            """
            SELECT id, nome, email
            FROM usuarios
            WHERE id = %s AND ativo = TRUE
            """,
            (usuario_id,)
        ).fetchone()

    if usuario is None:
        raise erro_autenticacao

    return usuario


router = APIRouter(prefix="/auth", tags=["Autenticação"])

password_hash = PasswordHash.recommended()

load_dotenv()

JWT_SECRET_KEY = os.environ["JWT_SECRET_KEY"]
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_MINUTES = 60


def criar_token(usuario_id: int):
    agora = datetime.now(timezone.utc)

    payload = {
        "sub": str(usuario_id),
        "iat": agora,
        "exp": agora + timedelta(minutes=JWT_EXPIRATION_MINUTES)
    }

    return jwt.encode(
        payload,
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM
    )

class UsuarioCriar(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    email: EmailStr
    senha: str = Field(min_length=12, max_length=128)


@router.post("/cadastro", status_code=201)
def cadastrar_usuario(dados: UsuarioCriar):
    senha_protegida = password_hash.hash(dados.senha)

    try:
        with get_connection() as conn:
            usuario = conn.execute(
                """
                INSERT INTO usuarios (nome, email, senha_hash)
                VALUES (%s, %s, %s)
                RETURNING id, nome, email
                """,
                (
                    dados.nome.strip(),
                    str(dados.email).lower(),
                    senha_protegida
                )
            ).fetchone()

    except errors.UniqueViolation:
        raise HTTPException(
            status_code=409,
            detail="Não foi possível cadastrar este e-mail."
        )

    return usuario


# ==========================================
# LOGIN DE USUÁRIOS
# ==========================================

class UsuarioLogin(BaseModel):
    email: EmailStr
    senha: str


@router.post("/login")
def login_usuario(dados: UsuarioLogin):
    with get_connection() as conn:
        usuario = conn.execute(
            """
            SELECT id, nome, email, senha_hash, ativo
            FROM usuarios
            WHERE LOWER(email) = LOWER(%s)
            """,
            (str(dados.email),)
        ).fetchone()

    if (
        usuario is None
        or not usuario["ativo"]
        or not password_hash.verify(
            dados.senha, usuario["senha_hash"]
        )
    ):
        raise HTTPException(
            status_code=401,
            detail="E-mail ou senha inválidos"
        )

    
    token = criar_token(usuario["id"])

    return {
        "access_token": token,
        "token_type": "bearer",
        "usuario": {
            "id": usuario["id"],
            "nome": usuario["nome"],
            "email": usuario["email"]
        }
    }

@router.get("/me")
def consultar_meus_dados(
    usuario = Depends(obter_usuario_atual)
):
    return usuario