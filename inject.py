import sqlite3
from hashlib import sha256

# Conexão com o banco de dados
conn = sqlite3.connect("C:/Users/russo/Desktop/python/IA_system6/sistema_gestao.db")
cursor = conn.cursor()

# Função para hash de senha
def hash_senha(senha):
    return sha256(senha.encode()).hexdigest()

# Usuários a serem inseridos
usuarios = [
    {"usuario": "Henrique", "senha": "hbcr2005", "nivel_acesso": "master"},
    {"usuario": "Vhenrique", "senha": "hbcr2005", "nivel_acesso": "usuario"}
]

# Inserir usuários no banco
for user in usuarios:
    try:
        senha_hashed = hash_senha(user["senha"])
        cursor.execute(
            "INSERT INTO usuarios (usuario, senha, nivel_acesso) VALUES (?, ?, ?)",
            (user["usuario"], senha_hashed, user["nivel_acesso"])
        )
        print(f"Usuário {user['usuario']} inserido com sucesso!")
    except sqlite3.IntegrityError:
        print(f"Usuário {user['usuario']} já existe no banco!")

# Confirmar alterações e fechar conexão
conn.commit()
conn.close()
