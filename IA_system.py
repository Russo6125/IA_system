import streamlit as st
import sqlite3
from hashlib import sha256
from barcode import Code128
from barcode.writer import ImageWriter
from io import BytesIO
from PIL import Image
import pandas as pd
from datetime import datetime
import plotly.express as px
from fpdf import FPDF
import pytz
import json

st.set_page_config(page_title="TecnoKohler management", page_icon="C:/Users/russo/Desktop/python/IA_system4/favicon.png", layout="wide")

# Inicializar chaves no st.session_state se não existirem
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if "nivel_acesso" not in st.session_state:
    st.session_state["nivel_acesso"] = None

if "usuario_logado" not in st.session_state:
    st.session_state["usuario_logado"] = None

# Função para hash de senha
def hash_senha(senha):
    return sha256(senha.encode()).hexdigest()

# Configuração do banco de dados SQLite
conn = sqlite3.connect("sistema_gestao.db")
cursor = conn.cursor()

# Criação da tabela de usuários para controle de acesso
cursor.execute('''
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario TEXT UNIQUE NOT NULL,
    senha TEXT NOT NULL,
    nivel_acesso TEXT NOT NULL
)
''')

cursor.execute("""
CREATE TABLE IF NOT EXISTS vendas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente TEXT,
    propriedade TEXT,
    prazo TEXT,
    forma_pagamento TEXT,
    descricao_pagamento TEXT,
    produtos TEXT,
    total REAL,
    status INTEGER
)
""")

# Criação das tabelas existentes
cursor.execute('''
CREATE TABLE IF NOT EXISTS clientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT,
    endereco TEXT,
    telefone TEXT,
    whatsapp INTEGER,
    cidade TEXT,
    estado TEXT,
    observacoes TEXT,
    ativo INTEGER,
    documento TEXT,
    contrato INTEGER              
)
''')

# Criação das tabelas existentes
cursor.execute('''
CREATE TABLE IF NOT EXISTS propriedades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT,
    quantidade_tanques INTEGER,
    area_tanques INTEGER,
    endereco TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS fornecedores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT,
    cnpj TEXT,
    telefone TEXT,
    whatsapp INTEGER,
    endereco TEXT,
    cidade TEXT,
    estado TEXT,
    observacoes TEXT,
    ativo INTEGER,
    contato_vendedor TEXT,
    site TEXT,
    cep TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS componentes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT,
    tipo TEXT,
    fornecedor TEXT,
    preco_base REAL,
    quantidade_minima INTEGER,
    imagem BLOB NOT NULL,
    quantidade INTEGER, 
    marca TEXT, 
    cor TEXT,
    observacoes TEXT,
    unidade TEXT,
    pedido_minimo INTEGER,
    data_ultimo_pedido
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS produtos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT,
    observacoes TEXT,
    quantidade_minima INTEGER,
    id_serial TEXT,
    preco_venda REAL
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS estoque (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    serial TEXT,
    tipo_produto TEXT,
    status INTEGER,
    deveui TEXT,
    appkey TEXT,
    cliente TEXT,
    propriedade TEXT, 
    data_confeccao TEXT,
    data_venda TEXT,
    historico TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS produtos_componentes (
    produto_id INTEGER,
    componente_nome TEXT,
    quantidade INTEGER,
    FOREIGN KEY(produto_id) REFERENCES produtos(id)
)
''')

# Criação das tabelas existentes
cursor.execute('''
CREATE TABLE IF NOT EXISTS Estoque (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT,
    endereco TEXT,
    telefone TEXT,
    whatsapp INTEGER,
    cidade TEXT,
    estado TEXT,
    observacoes TEXT,
    ativo INTEGER,
    documento TEXT,
    contrato INTEGER              
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    user TEXT NOT NULL,
    action TEXT NOT NULL
);
''')

cursor.execute("""
CREATE TABLE IF NOT EXISTS vendas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente TEXT,
    propriedade TEXT,
    prazo TEXT,
    forma_pagamento TEXT,
    descricao_pagamento TEXT,
    produtos TEXT,
    total REAL,
    status INTEGER
)
""")

cursor.execute('''
CREATE TABLE IF NOT EXISTS backups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ultimo_backup TEXT
);
''')

conn.commit()

# Função para autenticar usuários
def autenticar(usuario, senha):
    senha_hashed = hash_senha(senha)
    cursor.execute("SELECT * FROM usuarios WHERE usuario = ? AND senha = ?", (usuario, senha_hashed))
    return cursor.fetchone()

# Adicionando sessão do usuário logado
if "usuario_logado" not in st.session_state:
    st.session_state["autenticado"] = False
    st.session_state["usuario_logado"] = None

# Função para deslogar
def deslogar():
    st.session_state["autenticado"] = False
    st.session_state["nivel_acesso"] = None
    st.session_state["usuario_logado"] = None
    st.rerun()

def log_action(user, action):
    cursor.execute(
        "INSERT INTO logs (user, action) VALUES (?, ?)",
        (user, action)
    )

    conn.commit()

def get_logs():
    cursor.execute("SELECT * FROM logs")
    logs = cursor.fetchall()

    return logs

def get_filtered_logs(start_date=None, end_date=None, user=None):
    query = "SELECT * FROM logs WHERE 1=1"
    params = []

    # Ajustar o timezone para UTC-3 ao buscar registros
    local_tz = pytz.timezone("America/Sao_Paulo")
    
    # Configurar os filtros com horários explícitos
    if start_date:
        start_datetime = datetime.combine(start_date, datetime.min.time())
        start_utc = start_datetime.astimezone(pytz.utc).strftime("%Y-%m-%d %H:%M:%S")
        query += " AND timestamp >= ?"
        params.append(start_utc)

    if end_date:
        end_datetime = datetime.combine(end_date, datetime.max.time())
        end_utc = end_datetime.astimezone(pytz.utc).strftime("%Y-%m-%d %H:%M:%S")
        query += " AND timestamp <= ?"
        params.append(end_utc)

    if user:
        query += " AND user LIKE ?"
        params.append(f"%{user}%")

    # Ordenar os logs em ordem decrescente (mais recentes primeiro)
    query += " ORDER BY timestamp DESC"

    # Gerenciador de contexto para a conexão
    with sqlite3.connect("sistema_gestao.db") as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        logs = cursor.fetchall()

    # Ajustar os horários para UTC-3 e formatar para o padrão brasileiro
    adjusted_logs = []
    for log in logs:
        try:
            timestamp_str = log[1]  # Supondo que timestamp seja o segundo campo
            timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=pytz.utc)
            local_time = timestamp.astimezone(local_tz)
            formatted_time = local_time.strftime("%d/%m/%Y %H:%M:%S")
            adjusted_logs.append((formatted_time, log[2], log[3]))
        except (ValueError, TypeError) as e:
            # Ignorar registros com timestamp inválido
            print(f"Erro ao processar registro {log}: {e}")
            continue

    return adjusted_logs

def obter_produtos():
    """Retorna a lista de produtos do banco de dados."""
    cursor.execute("SELECT nome, preco_venda FROM produtos")
    produtos = cursor.fetchall()
    return produtos

def obter_estoque(produto):
    """Retorna o número de itens em estoque de um produto específico."""
    cursor.execute("SELECT COUNT(*) FROM estoque WHERE tipo_produto = ? AND status = 0", (produto,))
    estoque = cursor.fetchone()[0]
    return estoque

def atualizar_status_venda(venda_id, novo_status):
    """Atualiza o status de uma venda no banco de dados."""
    cursor.execute("UPDATE vendas SET status = ? WHERE id = ?", (novo_status, venda_id))
    conn.commit()

def carregar_pendencias():
    """Carrega todas as vendas pendentes do banco de dados ordenadas pela data mais próxima."""
    cursor.execute("SELECT id, cliente, propriedade, prazo, total, produtos FROM vendas WHERE status = 0 ORDER BY prazo ASC")
    pendencias = cursor.fetchall()
    return pendencias

def formatar_data(data_iso):
    """Formata a data de ISO para o formato dd/mm/yyyy."""
    return datetime.strptime(data_iso, "%Y-%m-%d").strftime("%d/%m/%Y")

def formatar_historico(historico):
    if historico:
        return "\n".join(historico.splitlines())
    return "Sem histórico disponível"

def ordenar_historico(historico):
    if historico:
        linhas = historico.splitlines()
        linhas_ordenadas = sorted(linhas, key=lambda x: x.split('] ')[0][1:], reverse=True)
        return "\n".join(linhas_ordenadas)
    return "Sem histórico disponível"

# Função para exportar logs filtrados para PDF
def export_to_pdf(dataframe):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    # Cabeçalho
    pdf.cell(200, 10, txt="Relatório de Logs", ln=True, align="C")

    # Adicionar os dados
    for index, row in dataframe.iterrows():
        pdf.cell(200, 10, txt=f"{row['Timestamp']} | {row['Usuário']} | {row['Ação']}", ln=True)

    # Salvar o PDF em um buffer
    buffer = BytesIO()
    buffer.write(pdf.output(dest='S').encode('latin1'))  # Salvar no buffer
    buffer.seek(0)  # Reseta o cursor do buffer para o início
    return buffer

# Tela de login
if not st.session_state["autenticado"]:
    st.title("Login")
    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")

    if st.button("Entrar"):
        usuario_db = autenticar(usuario, senha)
        if usuario_db:
            st.session_state["autenticado"] = True
            st.session_state["nivel_acesso"] = usuario_db[3]  # Pega o nível de acesso do banco
            st.session_state["usuario_logado"] = usuario  # Armazena o nome do usuário logado
            #st.rerun()
        else:
            st.error("Usuário ou senha inválidos.")

# Interface principal
else:
    st.title("Sistema de gerenciamento TecnoKohler")
    # Cabeçalho com informações do usuário logado
    col1, col2 = st.columns([8, 1])
    with col1:
        st.markdown(f"**Usuário Logado:** {st.session_state['usuario_logado']}")
    with col2:
        if st.button("Sair"):
            deslogar()

    # Interface para Master
    if st.session_state["nivel_acesso"] == "master":

        # Lista usuários cadastrados
        st.subheader("Usuários cadastrados")
        usuarios = cursor.execute("SELECT id, usuario, nivel_acesso FROM usuarios").fetchall()
        for usuario_id, nome, nivel in usuarios:
            col1, col2, col3 = st.columns([4, 3, 2])
            with col1:
                st.text(f"{nome} ({nivel})")
            with col3:
                if st.button("Excluir", key=f"excluir_{usuario_id}"):
                    cursor.execute("DELETE FROM usuarios WHERE id = ?", (usuario_id,))
                    conn.commit()
                    st.session_state["mensagem"] = "Usuário excluído com sucesso!"
                    st.rerun()

        if "mensagem" in st.session_state:
            st.success(st.session_state["mensagem"])
            del st.session_state["mensagem"]

        # Adicionar novo usuário
        st.subheader("Adicionar Novo Usuário")
        novo_usuario = st.text_input("Novo Usuário", key="novo_usuario")
        nova_senha = st.text_input("Senha", type="password", key="nova_senha")
        if st.checkbox("Definir como Master?", key="Master_checkbox"):
            nivel_acesso = "master"
        else:
            nivel_acesso = "usuario"

        if "usuario_salvo" not in st.session_state:
            st.session_state.usuario_salvo = True

        if st.button("Salvar Usuário"):
            try:
                cursor.execute(
                    "INSERT INTO usuarios (usuario, senha, nivel_acesso) VALUES (?, ?, ?)",
                    (novo_usuario, hash_senha(nova_senha), nivel_acesso)
                )
                conn.commit()
                st.session_state["mensagem"] = "Usuário criado com sucesso!"
                st.rerun()
            except sqlite3.IntegrityError:
                st.session_state["mensagem"] = "Erro: Usuário já existe!"

        if "mensagem" in st.session_state:
            if "Erro" in st.session_state["mensagem"]:
                st.error(st.session_state["mensagem"])
            else:
                st.success(st.session_state["mensagem"])
            del st.session_state["mensagem"]


    # Interface para Usuários
    else:
        aba = st.tabs(["Vendas","Propriedades","Clientes", "Fornecedores", "Componentes", "Produtos", "Estoque", "Histórico","Pendências","Estatísticas", "Backup"])

        # Função para buscar registros
        def search_records(search_text, table_name):
            query = f"SELECT * FROM {table_name} WHERE nome LIKE ?"
            cursor.execute(query, (f"%{search_text}%",))
            return cursor.fetchall()

        def excluir_registro(table_name, id, registro_id):
            try:
                cursor.execute("DELETE FROM " + table_name + " WHERE " + id + " = ?", (registro_id,))
                conn.commit()

            except sqlite3.OperationalError as e:
                st.error(f"Erro de bloqueio no banco de dados: {e}")
            except Exception as e:
                st.error(f"Erro ao excluir registro: {e}")

        # Função para converter imagem em blob
        def imagem_para_blob(imagem):
            buffer = BytesIO()
            imagem.save(buffer, format="PNG")
            buffer.seek(0)
            return buffer.getvalue()
        
        def gerar_codigo_barras(nome):
            # Gerar código de barras
            buffer = BytesIO()
            barcode = Code128(nome, writer=ImageWriter())
            barcode.write(buffer)
            
            # Abrir e redimensionar a imagem
            buffer.seek(0)
            img = Image.open(buffer)
            img_redimensionada = img.resize((max(1, 330), max(1, 150)))
            
            # Converter para blob e salvar
            return imagem_para_blob(img_redimensionada)
        
        def construir_id(codigo_base, n_serial):
            if n_serial > 1000:
                return f"{codigo_base}{n_serial}"
            elif n_serial > 99:
                return f"{codigo_base}0{n_serial}"
            elif n_serial > 9:
                return f"{codigo_base}00{n_serial}"
            else:
                return f"{codigo_base}000{n_serial}"
        
        with aba[0]:
            st.header("Vendas")

            clientes_disponiveis = [c[1] for c in search_records("", "clientes")]
            cliente_selecionado = st.selectbox("Cliente:", [""] + clientes_disponiveis, key="select_clientes_venda")

            propriedades_disponiveis = [c[1] for c in search_records("", "propriedades")]
            propriedade_selecionado = st.selectbox("Propriedade:", [""] + propriedades_disponiveis, key="select_propriedades_venda")

            prazo = st.date_input("Prazo de Entrega")

            produtos = obter_produtos()
            produto_opcoes = [produto[0] for produto in produtos]

            if "venda" not in st.session_state:
                st.session_state.venda = []

            col1, col2 = st.columns(2)
            with col1:
                produto_selecionado = st.selectbox("Selecione o produto", produto_opcoes)
            with col2:
                quantidade = st.number_input("Quantidade", min_value=1, step=1)

            if st.button("Adicionar à Lista"):
                preco_unitario = next(preco for nome, preco in produtos if nome == produto_selecionado)
                estoque_disponivel = obter_estoque(produto_selecionado)

                item_existente = next((item for item in st.session_state.venda if item["produto"] == produto_selecionado), None)

                if item_existente:
                    item_existente["quantidade"] += quantidade
                else:
                    st.session_state.venda.append({
                        "produto": produto_selecionado,
                        "quantidade": quantidade,
                        "estoque_disponivel": estoque_disponivel,
                        "preco_unitario": preco_unitario
                    })

            if st.session_state.venda:
                st.write("### Lista de Vendas")
                
                # Criação de colunas para cabeçalho
                col1, col2, col3, col4, col5, col6 = st.columns([3, 2, 2, 2, 2, 1])
                with col1:
                    st.write("**Produto**")
                with col2:
                    st.write("**Quantidade**")
                with col3:
                    st.write("**Preço Unitário**")
                with col4:
                    st.write("**Total**")
                with col5:
                    st.write("**Estoque Disponível**")
                with col6:
                    st.write("**Ações**")
                
                # Iteração para exibir itens
                for i, item in enumerate(st.session_state.venda):
                    col1, col2, col3, col4, col5, col6 = st.columns([3, 2, 2, 2, 2, 1])
                    with col1:
                        st.write(item["produto"])
                    with col2:
                        st.write(f'{item["quantidade"]}')
                    with col3:
                        st.write(f'R${item["preco_unitario"]:.2f}')
                    with col4:
                        st.write(f'R${item["quantidade"] * item["preco_unitario"]:.2f}')
                    with col5:
                        st.write(f'{item["estoque_disponivel"]}')
                    with col6:
                        if st.button("Excluir", key=f"excluir_{i}"):
                            st.session_state.venda.pop(i)
                            st.rerun()  # Atualiza a página para refletir a mudança

                # Cálculo e exibição do total geral
                total_geral = sum(item["quantidade"] * item["preco_unitario"] for item in st.session_state.venda)
                st.write(f"**Total Geral: R${total_geral:.2f}**")

                desconto = st.number_input("Valor de desconto", min_value=0.0, max_value=float(total_geral), step=0.01)
                total_com_desconto = total_geral - desconto
                st.write(f"### Total com desconto: R${total_com_desconto:.2f}")

                st.write("### Forma de Pagamento")
                forma_pagamento = st.selectbox("Selecione a forma de pagamento", ["PIX", "Boleto", "Cartão", "Outro"])
                descricao_pagamento = ""

                if forma_pagamento == "Cartão":
                    tipo_cartao = st.selectbox("Tipo de Cartão", ["Débito", "Crédito"])
                    if tipo_cartao == "Crédito":
                        parcelas = st.number_input("Número de parcelas", min_value=1, step=1)
                        descricao_pagamento = f"Crédito - {parcelas}x"
                    else:
                        descricao_pagamento = "Débito"
                elif forma_pagamento == "Outro":
                    descricao_pagamento = st.text_input("Descrição do pagamento")

                if st.button("Realizar Venda"):
                    produtos_json = json.dumps(st.session_state.venda)
                    status = 0  # Status inicial: pendente
                    log_action(st.session_state['usuario_logado'], f"Realizou uma venda para {cliente_selecionado}")
                    cursor.execute(
                        '''
                        INSERT INTO vendas (cliente, propriedade, prazo, forma_pagamento, descricao_pagamento, produtos, total, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ''',
                        (cliente_selecionado, propriedade_selecionado, prazo, forma_pagamento, descricao_pagamento, produtos_json, total_com_desconto, status)
                    )

                    conn.commit()

                    st.balloons()



        # Aba de Clientes
        with aba[1]:
            st.header("Propriedades")
            st.subheader("Pesquisar Propriedades")

            propriedades_disponiveis= [c[1] for c in search_records("", "propriedades")]
            propriedade_selecionado = st.selectbox(" ", [""] + propriedades_disponiveis, key="select_propriedades")

            if(propriedade_selecionado != ""):

                quantidade_tanques = [c[2] for c in search_records(propriedade_selecionado, "propriedades")][0]
                area_tanques = [c[3] for c in search_records(propriedade_selecionado, "propriedades")][0]
                endereco_propriedade = [c[4] for c in search_records(propriedade_selecionado, "propriedades")][0]

                with st.expander(f"📋 {propriedade_selecionado}"):
                    st.markdown(f"**Quantidade de Tanques:** {quantidade_tanques}")
                    st.markdown(f"**area_tanques:** {area_tanques}")
                    st.markdown(f"**endereco:** {endereco_propriedade}")

            if st.button("Deletar Propriedade") and propriedade_selecionado != "":
                excluir_registro("propriedades", "nome", propriedade_selecionado)
                log_action(st.session_state['usuario_logado'], f"Excluiu a propriedade {propriedade_selecionado}")
                st.rerun()

            st.subheader("Registrar Propriedade")

            nome_propriedade = st.text_input("Nome da Propriedade", key="propriedade_nome")

            endereco_propriedade = st.text_input("Endereço da Propriedade", key="propriedade_endereco")

            quantidade_tanques = st.number_input(
                "Quantidade de Tanques", min_value=1, key="quantidade_tanques"
            )

            area_tanques = st.number_input(
                "Área dos Tanques", min_value=100, key="area_tanques"
            )

            if st.button("Salvar Propriedade") :
                if nome_propriedade != "":
                    bool = False
                    for c in propriedades_disponiveis:
                        if (nome_propriedade == c):
                            bool = True

                    if(not bool):
                        log_action(st.session_state['usuario_logado'], f"Registrou a propriedade {nome_propriedade}")
                        cursor.execute(
                        '''
                        INSERT INTO propriedades (nome, quantidade_tanques, area_tanques, endereco)
                        VALUES (?, ?, ?, ?)
                        ''',
                        (nome_propriedade, quantidade_tanques, area_tanques, endereco_propriedade)
                        )
                        conn.commit()
                        st.rerun()

                    else:
                        st.error("Já existe uma Propriedade com esse nome!")
                        bool = False
                else:
                    st.error("É necessário Preencher os Campos para Salvar!")

        with aba[2]:
            st.header("Clientes")
            st.subheader("Pesquisar Clientes")

            clientes_disponiveis= [c[1] for c in search_records("", "clientes")]
            cliente_selecionado = st.selectbox(" ", [""] + clientes_disponiveis, key="select_clientes")

            if(cliente_selecionado != ""):
                records = search_records(cliente_selecionado, "clientes")
                print(records)
                id_cliente = [c[0] for c in search_records(cliente_selecionado, "clientes")][0]
                endereco_cliente = [c[2] for c in search_records(cliente_selecionado, "clientes")][0]
                telefone_cliente = [c[3] for c in search_records(cliente_selecionado, "clientes")][0]
                whatsapp_cliente = [c[4] for c in search_records(cliente_selecionado, "clientes")][0]
                cidade_cliente =  [c[5] for c in search_records(cliente_selecionado, "clientes")][0]
                estado_cliente = [c[6] for c in search_records(cliente_selecionado, "clientes")][0]
                observacoes_cliente = [c[7] for c in search_records(cliente_selecionado, "clientes")][0]
                ativo_cliente =  [c[8] for c in search_records(cliente_selecionado, "clientes")][0]
                documento_cliente = [c[9] for c in search_records(cliente_selecionado, "clientes")][0]
                contrato_cliente =  [c[10] for c in search_records(cliente_selecionado, "clientes")][0]

                with st.expander(f"📋 {cliente_selecionado}"):
                    st.markdown(f"**Endereço:** {endereco_cliente}")
                    st.markdown(f"**Telefone:** {telefone_cliente}")
                    st.markdown(f"**WhatsApp:** {'Sim' if whatsapp_cliente else 'Não'}")
                    st.markdown(f"**Cidade:** {cidade_cliente}")
                    st.markdown(f"**Estado:** {estado_cliente}")

                    if contrato_cliente:
                        st.markdown(f"**CNPJ:** {documento_cliente}")
                    else:
                        st.markdown(f"**CPF:** {documento_cliente}")

                    st.markdown(f"**Pessoa:** {'Júridica' if contrato_cliente else 'Física'}")
                    st.markdown(f"**Observações:** {observacoes_cliente}")
                    st.markdown(f"**Ativo:** {'Sim' if ativo_cliente else 'Não'}")

                if ativo_cliente:
                    btt_pass = "Desativar"
                else:
                    btt_pass = "Ativar"

                if st.button(btt_pass + " Cliente") and cliente_selecionado != "":
                    if not ativo_cliente == 1:
                        log_action(st.session_state['usuario_logado'], f"Ativou o cliente {cliente_selecionado}")
                    else:
                        log_action(st.session_state['usuario_logado'], f"Desativou o cliente {cliente_selecionado}")
                    cursor.execute(
                    '''
                    UPDATE clientes SET ativo = ? WHERE id = ?;
                    ''',
                    (not ativo_cliente, id_cliente)
                    )
                    conn.commit()
                    st.rerun()    

            st.subheader("Registrar Cliente")
            nome_cliente = st.text_input("Nome", key="cliente_nome")
            endereco_cliente = st.text_input("Endereço", key="cliente_endereco")
            cidade_cliente = st.text_input("Cidade", key="cliente_cidade")
            estado_cliente = st.text_input("Estado", key="cliente_estado")
            telefone_cliente = st.text_input("Telefone", key="cliente_telefone")
            whatsapp_cliente = st.checkbox("É WhatsApp?", key="cliente_whatsapp")
            documento_cliente = st.text_input("CPF / CNPJ", key="cliente_documentos")
            contrato_cliente = st.selectbox("Pessoa", ["Física" , "Jurítica"], key="contrato_pessoa")
            observacoes_cliente = st.text_area("Observações", key="cliente_observacoes")
            ativo_cliente = st.checkbox("Está ativo?", key="cliente_ativo")

            if contrato_cliente == "Física":
                contrato_cliente = 0
            else:
                contrato_cliente = 1

            if st.button("Salvar Cliente") and nome_cliente != "":
                if nome_cliente != "":
                    bool = False
                    for c in clientes_disponiveis:
                        if (nome_cliente == c):
                            bool = True           

                    if(not bool):
                        log_action(st.session_state['usuario_logado'], f"Registrou o cliente {nome_cliente}")
                        cursor.execute(
                            '''
                            INSERT INTO clientes (nome, endereco, telefone, whatsapp, cidade, estado, observacoes, ativo, documento, contrato)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''',
                            (nome_cliente, endereco_cliente, telefone_cliente, whatsapp_cliente,
                            cidade_cliente, estado_cliente, observacoes_cliente, ativo_cliente, documento_cliente, contrato_cliente)
                        )
                        conn.commit()
                        st.rerun()  

                    else:
                        st.error("Já existe um Cliente registrado com esse nome!")
                        bool = False

                else:
                    st.error("É necessário Preencher os Campos para Salvar!")

        # Aba de Fornecedores
        with aba[3]:
            st.header("Fornecedores")
            st.subheader("Pesquisar Fornecedores")

            fornececedores_disponiveis= [c[1] for c in search_records("", "fornecedores")]
            fornecedor_selecionado = st.selectbox(" ", [""] + fornececedores_disponiveis, key="select_fornecedores")

            if(fornecedor_selecionado != ""):
                id_fornecedores = [c[0] for c in search_records(fornecedor_selecionado, "fornecedores")][0]
                cnpj_fornecedor = [c[2] for c in search_records(fornecedor_selecionado, "fornecedores")][0]
                telefone_fornecedor = [c[3] for c in search_records(fornecedor_selecionado, "fornecedores")][0]
                whatsapp_fornecedor = [c[4] for c in search_records(fornecedor_selecionado, "fornecedores")][0]
                endereco_fornecedor = [c[5] for c in search_records(fornecedor_selecionado, "fornecedores")][0]
                cidade_fornecedor =  [c[6] for c in search_records(fornecedor_selecionado, "fornecedores")][0]
                estado_fornecedor = [c[7] for c in search_records(fornecedor_selecionado, "fornecedores")][0]
                observacoes_fornecedor = [c[8] for c in search_records(fornecedor_selecionado, "fornecedores")][0]
                ativo_fornecedor =  [c[9] for c in search_records(fornecedor_selecionado, "fornecedores")][0]
                contato_vendedor =  [c[10] for c in search_records(fornecedor_selecionado, "fornecedores")][0]
                site_fornecedor = [c[11] for c in search_records(fornecedor_selecionado, "fornecedores")][0]
                cep_fornecedor = [c[12] for c in search_records(fornecedor_selecionado, "fornecedores")][0]

                with st.expander(f"📋 {fornecedor_selecionado}"):
                    st.markdown(f"**CNPJ:** {cnpj_fornecedor}")
                    st.markdown(f"**Contato Vendedor:** {contato_vendedor}")
                    st.markdown(f"**Telefone:** {telefone_fornecedor}")
                    st.markdown(f"**WhatsApp:** {'Sim' if whatsapp_fornecedor else 'Não'}")
                    st.markdown(f"**Endereço:** {endereco_fornecedor}")
                    st.markdown(f"**Cidade:** {cidade_fornecedor}")
                    st.markdown(f"**Estado:** {estado_fornecedor}")
                    st.markdown(f"**CEP:** {cep_fornecedor}")
                    st.markdown(f"**Site ou Mídia Social:** {site_fornecedor}")
                    st.markdown(f"**Observações:** {observacoes_fornecedor}")
                    st.markdown(f"**Ativo:** {'Sim' if ativo_fornecedor else 'Não'}")

                if ativo_fornecedor:
                    btt_pass = "Desativar"
                else:
                    btt_pass = "Ativar"

                if st.button(btt_pass + " Fornecedor") and fornecedor_selecionado != "":
                    if not ativo_fornecedor == 1:
                        log_action(st.session_state['usuario_logado'], f"Ativou o fornecedor {fornecedor_selecionado}")
                    else:
                        log_action(st.session_state['usuario_logado'], f"Desativou o fornecedor {fornecedor_selecionado}")
                    cursor.execute(
                    '''
                    UPDATE fornecedores SET nome = ?, cnpj = ?, telefone = ?, whatsapp = ?, endereco = ?, cidade = ?, estado = ?, observacoes = ?, ativo = ? WHERE id = ?;
                    ''',
                    (fornecedor_selecionado, cnpj_fornecedor, telefone_fornecedor, whatsapp_fornecedor,
                    endereco_fornecedor, cidade_fornecedor, estado_fornecedor, observacoes_fornecedor, not ativo_fornecedor, id_fornecedores)
                    )
                    conn.commit()
                    st.rerun()

            st.subheader("Registrar Fornecedor")
            nome_fornecedor = st.text_input("Nome / Razão Social", key="fornecedor_nome")
            cnpj_fornecedor = st.text_input("CPF / CNPJ", key="fornecedor_cnpj")
            contato_vendedor = st.text_input("Contato Vendedor", key="fornecedor_contato_vendedor")
            telefone_fornecedor = st.text_input("Telefone", key="fornecedor_telefone")
            whatsapp_fornecedor = st.checkbox("É WhatsApp?", key="fornecedor_whatsapp")
            endereco_fornecedor = st.text_input("Endereço", key="fornecedor_endereco")
            cidade_fornecedor = st.text_input("Cidade", key="fornecedor_cidade")
            estado_fornecedor = st.text_input("Estado", key="fornecedor_estado")
            cep_fornecedor = st.text_input("CEP", key="fornecedor_cep")
            site_fornecedor = st.text_input("Site", key="fornecedor_site")
            observacoes_fornecedor = st.text_area("Observações", key="fornecedor_observacoes")
            ativo_fornecedor = st.checkbox("Está ativo?", key="fornecedor_ativo")

            if st.button("Salvar Fornecedor") and nome_fornecedor != "":
                if nome_fornecedor != "":
                    bool = False
                    for c in fornececedores_disponiveis:
                        if (nome_fornecedor == c):
                            bool = True

                    if(not bool):
                        log_action(st.session_state['usuario_logado'], f"Registrou o fornecedor {nome_fornecedor}")
                        cursor.execute(
                            '''
                            INSERT INTO fornecedores (nome, cnpj, telefone, whatsapp, endereco, cidade, estado, observacoes, ativo, contato_vendedor, site, cep)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''',
                            (nome_fornecedor, cnpj_fornecedor, telefone_fornecedor, whatsapp_fornecedor,
                            endereco_fornecedor, cidade_fornecedor, estado_fornecedor, observacoes_fornecedor, ativo_fornecedor, 
                            contato_vendedor, site_fornecedor, cep_fornecedor)
                        )
                        conn.commit()
                        st.rerun()
                        
                    else:
                        st.error("Já existe um Fornecedor registrado com esse nome!")
                        bool = False

                else:
                    st.error("É necessário Preencher os Campos para Salvar!")

        # Aba de Componentes
        with aba[4]:
            st.header("Componentes")
            st.subheader("Pesquisar Componentes")

            componentes_disponiveis = [c[1] for c in search_records("", "componentes")]
            componente_selecionado = st.selectbox(" ", [""] + componentes_disponiveis, key="select_componente")

            if(componente_selecionado != ""):

                tipo_componente = [c[2] for c in search_records(componente_selecionado, "componentes")][0]
                fornecedor_componente = [c[3] for c in search_records(componente_selecionado, "componentes")][0]
                preco_base_componente = [c[4] for c in search_records(componente_selecionado, "componentes")][0]
                quantidade_minima_componente = [c[5] for c in search_records(componente_selecionado, "componentes")][0]
                codigo_barras_componente = [c[6] for c in search_records(componente_selecionado, "componentes")][0]
                quantidade_estoque = [c[7] for c in search_records(componente_selecionado, "componentes")][0]
                marca_componente = [c[8] for c in search_records(componente_selecionado, "componentes")][0]
                cor_componente = [c[9] for c in search_records(componente_selecionado, "componentes")][0]
                observacoes_componente = [c[10] for c in search_records(componente_selecionado, "componentes")][0]
                unidade = [c[11] for c in search_records(componente_selecionado, "componentes")][0]
                pedido_minimo = [c[12] for c in search_records(componente_selecionado, "componentes")][0]
                data_componente = [c[13] for c in search_records(componente_selecionado, "componentes")][0]

                with st.expander(f"📋 {componente_selecionado}"):
                    st.markdown(f"**Tipo:** {tipo_componente}")
                    if marca_componente != None: st.markdown(f"**Marca:** {marca_componente}")
                    if cor_componente != None: st.markdown(f"**Cor:** {cor_componente}")
                    if unidade != None: st.markdown(f"**Unidade:** {unidade}")
                    st.markdown(f"**Fornecedor:** {fornecedor_componente}")
                    st.markdown(f"**Preço:** R$ {preco_base_componente}")
                    st.markdown(f"**Quantidade em Estoque:** {quantidade_estoque}")
                    st.markdown(f"**Quantidade Mínima em Estoque:** {quantidade_minima_componente}")
                    if pedido_minimo != None: st.markdown(f"**Pedido Mínimo:** {pedido_minimo}")
                    if observacoes_componente != None: st.markdown(f"**Observações:** {observacoes_componente}")
                    if data_componente != None: st.markdown(f"**Data do ultimo Pedido:** {data_componente}")
                    st.image(codigo_barras_componente, caption=f"Código de Barras para {componente_selecionado}", use_column_width=False)

            if st.button("Deletar Componente") and componente_selecionado != "":
                excluir_registro("componentes", "nome", componente_selecionado)
                log_action(st.session_state['usuario_logado'], f"Excluiu o Componente {componente_selecionado}")
                st.rerun()

            st.subheader("Registrar Componente")
            nome_componente = st.text_input("Nome do Componente", key="componente_nome")
            tipo_componente = st.selectbox(
                "Tipo", ["Componente", "Sonda", "Microcontrolador", "PCB", "Cabo", "Caixa Hermética", "Conector", "Outro"], key="componente_tipo"
            )

            fornecedores_nomes = [f[1] for f in search_records("", "fornecedores")]
            fornecedores_ativos = [f[9] for f in search_records("", "fornecedores")]

            nomes_ativos = [""]
            for i in range(len(fornecedores_nomes)):
                if fornecedores_ativos[i] == 1:  # Verifica se a pessoa está ativa
                    nomes_ativos.append(fornecedores_nomes[i])

            marca_componente = st.text_input("Marca", key="componente_marca")

            fornecedor_componente = st.selectbox(
                "Fornecedor", nomes_ativos, key="componente_fornecedor"
            )
            preco_base_componente = st.number_input(
                "Preço", min_value=0.0, format="%.2f", key="componente_preco_base"
            )
            quantidade_minima_componente = st.number_input(
                "Quantidade Mínima em Estoque", min_value=0, key="componente_quantidade_minima"
            )

            pedido_minimo = st.number_input(
                "Pedido mínimo", min_value=0, key="componente_pedido_minimo"
            )

            cor_componente = st.text_input("Cor", key="componente_cor")

            unidade = st.text_input("Unidade", key="componente_unidade")

            observacoes_componente = st.text_area("Observações", key="componente_observacoes")

            col1, col2 = st.columns(2)
            with col1:
                btt = st.button("Salvar Componente")
            with col2:
                cdd = st.button("Código de Barras Componente")

            if cdd:
                if nome_componente != "":
                    codigo_de_barras = gerar_codigo_barras(nome_componente)
                    st.image(codigo_de_barras, caption=f"Código de Barras para {nome_componente}", use_column_width=False)
                else:
                    st.error("É necessário Preencher o Campo Nome d Componente para Gerar!")

            if btt:
                if nome_componente != "":
                    bool = False
                    for c in componentes_disponiveis:
                        if (nome_componente == c):
                            bool = True

                    codigo_de_barras = gerar_codigo_barras(nome_componente)

                    if(not bool):   
                        log_action(st.session_state['usuario_logado'], f"Registrou o componente {nome_componente}")                
                        cursor.execute(
                        '''
                        INSERT INTO componentes (nome, tipo, fornecedor, preco_base, quantidade_minima, imagem, quantidade, marca, cor, observacoes, unidade, pedido_minimo)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''',
                        (nome_componente, tipo_componente, fornecedor_componente,
                        preco_base_componente, quantidade_minima_componente, codigo_de_barras, 0, marca_componente, cor_componente,
                        observacoes_componente, unidade, pedido_minimo)
                        )
                        conn.commit()
                        st.rerun()

                    else:
                        st.error("Já existe um componente com esse nome!")
                        bool = False

                else:
                    st.error("É necessário Preencher os Campos para Salvar!")

        # Aba de Produtos
        with aba[5]:
            st.header("Produtos")

            st.subheader("Pesquisar Produtos")

            produtos_disponiveis = [c[1] for c in search_records("", "produtos")]
            produto_selecionado = st.selectbox(" ", [""] + produtos_disponiveis, key="select_Produtos")

            if(produto_selecionado != ""):

                id_produtos = [c[0] for c in search_records(produto_selecionado, "produtos")][0]
                observacoes_produto = [c[2] for c in search_records(produto_selecionado, "produtos")][0]
                quantidade_minima_produtos = [c[3] for c in search_records(produto_selecionado, "produtos")][0]
                id_serial = [c[4] for c in search_records(produto_selecionado, "produtos")][0]
                preco_venda = [c[5] for c in search_records(produto_selecionado, "produtos")][0]

                cursor.execute('''SELECT COUNT(*) FROM estoque WHERE status = 0 AND tipo_produto = ?''', (produto_selecionado,))
                quantidade_estoque = cursor.fetchone()[0]

                with st.expander(f"📋 {produto_selecionado}"):
                    st.markdown(f"**Quantidade em Estoque:** {quantidade_estoque}")
                    st.markdown(f"**Quantidade Mínima em Estoque:** {quantidade_minima_produtos}")
                    st.markdown(f"**Código Serial Base:** {id_serial}")
                    st.markdown(f"**Observações:** {observacoes_produto}")
                    cursor.execute(
                        "SELECT componente_nome, quantidade FROM produtos_componentes WHERE produto_id = ?", (id_produtos,)
                    )
                    componentes = cursor.fetchall()
                    total_preco = 0
                    st.markdown("**Componentes Utilizados:**")
                    for componente in componentes:
                        total_preco += [c[4] for c in search_records(componente[0], "componentes")][0]
                        st.markdown(f"- {componente[0]} (Quantidade: {componente[1]})")   

                    st.markdown(f"**Custo unitário de Confecção:** {round(total_preco, 2)}R$")
                    st.markdown(f"**Preço unitário de Venda:** {round(preco_venda, 2)}R$")
                        

            if st.button("Deletar Produto") and produto_selecionado != "":
                excluir_registro("produtos", "nome", produto_selecionado)
                log_action(st.session_state['usuario_logado'], f"excluiu o produto {produto_selecionado}")
                excluir_registro("produtos_componentes", "produto_id", id_produtos)
                st.rerun()

            st.subheader("Registrar Produto")

            if "componentes_produto" not in st.session_state:
                st.session_state.componentes_produto = {}

            nome_produto = st.text_input("Nome do Produto", key="produto_nome")

            quantidade_minima_produtos = st.number_input(
                "Quantidade Mínima em Estoque", min_value=0, key="produto_quantidade_minima"
            )
            id_serial = st.text_input("Código Serial Base", key="id_serial_produtos")

            observacoes_produto = st.text_area("Observações", key="produto_observacoes")
            componentes_disponiveis = [c[1] for c in search_records("", "componentes")]

            preco_base_produto = st.number_input(
                "Preço de Venda", min_value=0.0, format="%.2f", key="produtos_preco_base"
            )

            componente_selecionado = st.selectbox("Selecionar Componentes", ["Selecione"] + componentes_disponiveis, key="select_componentes_produtos")
            if st.button("Adicionar Componente"):
                if componente_selecionado != "Selecione" and componente_selecionado not in st.session_state.componentes_produto:
                    st.session_state.componentes_produto[componente_selecionado] = 1

            if st.session_state.componentes_produto:
                st.subheader("Componentes Selecionados")
                for componente, quantidade in list(st.session_state.componentes_produto.items()):
                    col1, col2, col3 = st.columns([5, 3, 1])
                    with col1:
                        st.markdown(f"**{componente}**")
                    with col2:
                        st.session_state.componentes_produto[componente] = st.number_input(f"Quantidade", value=quantidade, key=f"quantidade_{componente}")
                    with col3:
                        if st.button("❌", key=f"excluir_{componente}"):
                            del st.session_state.componentes_produto[componente]

            if st.button("Salvar Produto"):
                if nome_produto != "" and id_serial != "":
                    bool = False
                    for c in produtos_disponiveis:
                        if (nome_produto == c):
                            bool = True

                    if nome_produto and st.session_state.componentes_produto and bool == False:
                        log_action(st.session_state['usuario_logado'], f"Registrou o Produto {nome_produto}")
                        cursor.execute('INSERT INTO produtos (nome, observacoes, quantidade_minima, id_serial, preco_venda) VALUES (?, ?, ?, ?, ?)', (nome_produto, observacoes_produto, quantidade_minima_produtos, id_serial, preco_base_produto))
                        produto_id = cursor.lastrowid
                        for componente, quantidade in st.session_state.componentes_produto.items():
                            cursor.execute(
                                '''
                                INSERT INTO produtos_componentes (produto_id, componente_nome, quantidade)
                                VALUES (?, ?, ?)
                                ''',
                                (produto_id, componente, quantidade)
                            )
                        conn.commit()
                        st.success("Produto salvo com sucesso!")
                        st.session_state.componentes_produto = {}
                        st.rerun()
                    elif not nome_produto or not st.session_state.componentes_produto:
                        st.error("Preencha todos os campos!")
                    else:
                        bool = False
                        st.error("Já existe um Produto com esse nome!")
                else:
                    st.error("É necessário Preencher os Campos para Salvar!")

        with aba[6]:
            st.header("Estoque")

            st.subheader("Pesquisar Origem de Produtos")

            cursor.execute(f"SELECT serial FROM estoque")
            seriais_estoque = [linha[0] for linha in cursor.fetchall()]

            produto_ = st.selectbox(" ", [""] + seriais_estoque[::-1], key="select_estoque")
           
            if(produto_ != ""):

                cursor.execute("SELECT tipo_produto FROM estoque WHERE serial = ?", (produto_,))
                tipo_estoque = cursor.fetchone()[0]

                cursor.execute("SELECT status FROM estoque WHERE serial = ?", (produto_,))
                status = cursor.fetchone()[0]

                cursor.execute("SELECT deveui FROM estoque WHERE serial = ?", (produto_,))
                deveui = cursor.fetchone()[0]

                cursor.execute("SELECT appkey FROM estoque WHERE serial = ?", (produto_,))
                appkey = cursor.fetchone()[0]

                cursor.execute("SELECT cliente FROM estoque WHERE serial = ?", (produto_,))
                cliente = cursor.fetchone()[0]

                cursor.execute("SELECT propriedade FROM estoque WHERE serial = ?", (produto_,))
                propriedade = cursor.fetchone()[0]

                cursor.execute("SELECT data_confeccao FROM estoque WHERE serial = ?", (produto_,))
                confeccao = cursor.fetchone()[0]

                cursor.execute("SELECT data_venda FROM estoque WHERE serial = ?", (produto_,))
                venda = cursor.fetchone()[0]

                if status == 0:
                    status = "Em Estoque"
                elif status == 1:
                    status = "Em Campo"
                elif status == 2:
                    status = "Em Manutenção"
                elif status == 3:
                    status = "Inativo"
                elif status == 4:
                    status = "Em Fabricação"
                else:
                    status = "Reservado"

                if cliente == None: cliente = "Não designado"
                if propriedade == None: propriedade = "Não designada"

                cursor.execute("SELECT historico FROM estoque WHERE serial = ?", (produto_,))
                historico = cursor.fetchone()[0]
                historico_ordenado = ordenar_historico(historico)

                with st.expander(f"📋 {produto_}"):
                    st.markdown(f"**Tipo de Produto:** {tipo_estoque}")
                    st.markdown(f"**status do Produto:** {status}")
                    st.markdown(f"**deveui:** {deveui}")
                    st.markdown(f"**appkey:** {appkey}")
                    st.markdown(f"**Cliente:** {cliente}")
                    st.markdown(f"**Propriedade:** {propriedade}")
                    st.markdown(f"Data de Produção: {confeccao}")
                    if status != "Em estoque":
                        st.markdown(f"Data de Venda:{venda}")
                    codigo_de_barras = gerar_codigo_barras(produto_)
                    st.image(codigo_de_barras, caption=f"Código de Barras para {produto_}", use_column_width=False)

                    col1, col2 = st.columns(2)

                    with col1: btt = st.button("Exportar Histórico para PDF")

                    if btt:
                        pdf = FPDF()
                        pdf.set_auto_page_break(auto=True, margin=15)
                        pdf.add_page()
                        pdf.set_font("Arial", size=12)

                        pdf.cell(200, 10, txt=f"Histórico do Produto: {produto_}", ln=True, align="C")
                        pdf.ln(10)

                        pdf.set_font("Arial", size=12)
                        linhas_historico = historico_ordenado.splitlines()
                        for linha in linhas_historico:
                            pdf.multi_cell(0, 10, txt=linha)

                        pdf_path = f"historico_{produto_}.pdf"
                        pdf.output(pdf_path)

                        with open(pdf_path, "rb") as pdf_file:
                            with col2:
                                st.download_button("Baixar PDF", data=pdf_file, file_name=f"historico_{produto_}.pdf")

            st.subheader("Repor Estoque de Componentes")
            
            componentes_disponiveis = [c[1] for c in search_records("", "componentes")]
            componente_selecionado = st.selectbox("Componente", [""] + componentes_disponiveis, key="select_Componentes_Estoque")

            if componente_selecionado != "":

                quantidade_reposicao = st.number_input(
                    "Quantidade a ser Reposta", min_value=1, key="componentes_quantidade_Estoque"
                )

                fornecedores_nomes = [f[1] for f in search_records("", "fornecedores")]
                fornecedores_ativos = [f[9] for f in search_records("", "fornecedores")]

                nomes_ativos = [""]
                for i in range(len(fornecedores_nomes)):
                    if fornecedores_ativos[i] == 1:  # Verifica se a pessoa está ativa
                        nomes_ativos.append(fornecedores_nomes[i])

                fornecedor_componente = st.selectbox(
                    "Fornecedor do Lote", nomes_ativos, key="componente_fornecedor_disponiveis"
                )

                preco_componente = st.number_input(
                    "Preço por Unidade", min_value=0.1, format="%.2f", key="componente_preco"
                )

                if st.button("Injetar Reposição"):
                    if componente_selecionado != "" and fornecedor_componente != "":
                        log_action(st.session_state['usuario_logado'], f"Repôs {quantidade_reposicao} {componente_selecionado} em estoque")
                        cursor.execute('''UPDATE componentes SET fornecedor = ?, preco_base = ?, quantidade = quantidade + ? WHERE nome = ?''', (fornecedor_componente, preco_componente, quantidade_reposicao, componente_selecionado))
                        conn.commit()
                        st.rerun()

            st.subheader("Atualizar Produtos")

            cursor.execute(f"SELECT serial FROM estoque")
            seriais_estoque = [linha[0] for linha in cursor.fetchall()]
            produto_ = st.selectbox(" ", [""] + seriais_estoque[::-1], key="select_estoque_update")

            if produto_ != "":

                cursor.execute("SELECT tipo_produto FROM estoque WHERE serial = ?", (produto_,))
                tipo_produto = cursor.fetchone()[0]

                                
                cursor.execute("SELECT status FROM estoque WHERE serial = ?", (produto_,))
                status_bd = cursor.fetchone()[0]

                if status_bd == 0:
                    status_bd = "Em Estoque"
                elif status_bd == 1:
                    status_bd = "Em Campo"
                elif status_bd == 2:
                    status_bd = "Em Manutenção"
                elif status_bd == 3:
                    status_bd = "Inativo"
                elif status_bd == 4:
                    status_bd = "Em Fabricação"
                else:
                    status_bd = "Reservado"

                status_opcoes = ["Em Estoque", "Em Campo", "Em Manutenção", "Inativo", "Reservado"]

                if status_bd in status_opcoes:
                    status_opcoes.remove(status_bd)
                status_opcoes.insert(0, status_bd)

                status = st.selectbox("Status", status_opcoes, key="select_status_update")


                cursor.execute("SELECT deveui FROM estoque WHERE serial = ?", (produto_,))
                deveui_bd = cursor.fetchone()[0]
                deveui = st.text_input(f"devEui {produto_}", value=deveui_bd, key=f"deveui_{i}")

                cursor.execute("SELECT appkey FROM estoque WHERE serial = ?", (produto_,))
                appkey_bd = cursor.fetchone()[0]
                appkey = st.text_input(f"appKey {produto_} ", value=appkey_bd, key=f"appkey_{i}")

                cursor.execute("SELECT cliente FROM estoque WHERE serial = ?", (produto_,))
                cliente = cursor.fetchone()[0]
                if cliente == None: cliente = ""

                cursor.execute("SELECT propriedade FROM estoque WHERE serial = ?", (produto_,))
                propriedade = cursor.fetchone()[0]
                if propriedade == None: propriedade = ""

                cursor.execute("SELECT cliente FROM estoque WHERE serial = ?", (produto_,))
                cliente = cursor.fetchone()[0]

                clientes_disponiveis = [c[1] for c in search_records("", "clientes")]

                if cliente in clientes_disponiveis:
                    clientes_disponiveis.remove(cliente) 
                clientes_disponiveis.insert(0, cliente)  

                cliente_selecionado = st.selectbox("Cliente", clientes_disponiveis, key="select_clientes_estoque")

                cursor.execute("SELECT propriedade FROM estoque WHERE serial = ?", (produto_,))
                propriedade = cursor.fetchone()[0]

                propriedades_disponiveis = [c[1] for c in search_records("", "propriedades")]

                if propriedade in propriedades_disponiveis:
                    propriedades_disponiveis.remove(propriedade) 
                propriedades_disponiveis.insert(0, propriedade)  
                
                propriedade_selecionado = st.selectbox("Propriedade", propriedades_disponiveis, key="select_propriedades_estoque")

                cursor.execute("SELECT tipo_produto, status, historico FROM estoque WHERE serial = ?", (produto_,))
                tipo_produto, status_bd, historico_bd = cursor.fetchone()
                
                if status_bd == 0:
                    status_bd = "Em Estoque"
                elif status_bd == 1:
                    status_bd = "Em Campo"
                elif status_bd == 2:
                    status_bd = "Em Manutenção"
                elif status_bd == 3:
                    status_bd = "Inativo"
                else:
                    status_bd = "Reservado"

                historico_novo = st.text_input("Adicionar ao Histórico", key=f"historico_novo_{produto_}")

                if st.button("Atualizar") and produto_ != "":

                    if status == "Em Estoque":
                        status = 0
                    elif status == "Em Campo":
                        status = 1
                    elif status == "Em Manutenção":
                        status = 2
                    elif status == "Inativo":
                        status = 3
                    elif status == "Em Fabricação":
                        status = 4
                    else:
                        status = 5
                        
                    log_action(st.session_state['usuario_logado'], f"Atualizou um {tipo_produto} de serial {produto_}")

                    cursor.execute(
                    '''
                    UPDATE estoque SET status = ?, deveui = ?, appkey = ?, cliente = ?, propriedade = ? WHERE serial = ?;
                    ''',
                    (status, deveui, appkey, cliente_selecionado, propriedade_selecionado, produto_))
                    conn.commit()

                    #if historico_novo != "":
                    data_atual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    historico_atualizado = (historico_bd or "") + f"\n[{data_atual}] {historico_novo}" if historico_novo else historico_bd
                    cursor.execute("UPDATE estoque SET historico = ? WHERE serial = ?", (historico_atualizado, produto_))
                    conn.commit()

                    st.rerun()

            st.subheader("Registrar Confecção")

            produtos_disponiveis = [c[1] for c in search_records("", "produtos")]
            produto_selecionado = st.selectbox("Produto", [""] + produtos_disponiveis, key="select_Produtos_Estoque")

            quantidade_confeccionada = st.number_input(
                "Quantidade a ser Confeccionada", min_value=1, key="produto_quantidade_Estoque"
            )

            if produto_selecionado != "":
                id_produtos = [c[0] for c in search_records(produto_selecionado, "produtos")][0]

                cursor.execute(
                            "SELECT componente_nome, quantidade FROM produtos_componentes WHERE produto_id = ?", (id_produtos,)
                        )
                componentes = cursor.fetchall()

                tipo_componente = []
                quantidade_componente = []
                quantidade_producao = []
                precos_componentes = []
                total_quantidade1 = 0
                total_quantidade2 = 0
                total_preco = 0

                for componente in componentes:
                    preco_componente = [c[4] for c in search_records(componente[0], "componentes")][0]

                    tipo_componente.append(componente[0])
                    quantidade_componente.append(componente[1])
                    quantidade_producao.append(round(componente[1]*quantidade_confeccionada, 2))
                    precos_componentes.append(round(preco_componente*quantidade_confeccionada, 2))

                    total_quantidade1 += componente[1]
                    total_quantidade2 += componente[1]*quantidade_confeccionada
                    total_preco += preco_componente*quantidade_confeccionada

                tipo_componente.append("Total:")
                quantidade_componente.append(total_quantidade1)
                quantidade_producao.append(total_quantidade2)
                precos_componentes.append(round(total_preco, 2))

                data = {
                    "Componentes": tipo_componente,
                    "Quantidade unitária": quantidade_componente,
                    "Quantidade para Produção": quantidade_producao,
                    "Preço de Produção (R$)": precos_componentes
                }

                df = pd.DataFrame(data)  

                st.dataframe(df, use_container_width=True) 
            
            chaves = []
            if quantidade_confeccionada and produto_selecionado != "":
                st.write(f"Preencha os campos para cada {produto_selecionado}:")
                for i in range(quantidade_confeccionada):
                    st.subheader(f"{produto_selecionado} {i + 1}")
                    deveui = st.text_input(f"devEui {produto_selecionado} {i + 1}", key=f"deveui__{i}")
                    appkey = st.text_input(f"appKey {produto_selecionado} {i + 1}", key=f"appkey__{i}")
                    chaves.append({"devEui": deveui, "appKey": appkey})


            col1, col2 = st.columns(2)
            with col1:
                btt = st.button("Salvar Confecção")
            with col2:
                cdd = st.button("Código de Barras")

            if cdd:
                bool = False
                for c in produtos_disponiveis:
                    if (produto_selecionado == c):
                        bool = True

                if produto_selecionado != "" and bool:
                    codigo_serial = [c[4] for c in search_records(produto_selecionado, "produtos")][0]

                    cursor.execute("SELECT MAX(id) FROM estoque")
                    ultimo_id = cursor.fetchone()[0]

                    if ultimo_id == None: ultimo_id = 0

                    for c in range(quantidade_confeccionada):
                        codigo_gerado = construir_id(codigo_serial, ultimo_id+c)
                        imagem_codigo_barras = gerar_codigo_barras(codigo_gerado)
                        st.image(imagem_codigo_barras, caption=f"Código de Barras para {produto_selecionado}: {codigo_gerado}", use_column_width=False)
                else:
                    st.error("É necessário Preencher o Campo Produto ou preenche-lo com um produto listado para Gerar!")

            if btt:
                if produto_selecionado != "":
                    bool = False
                    for c in produtos_disponiveis:
                        if (produto_selecionado == c):
                            bool = True

                    ftt = True
                    componentes_faltantes = []
                    for c in range(len(tipo_componente)-1):
                        quantidade_componente = [c[7] for c in search_records(tipo_componente[c], "componentes")][0]
                        if quantidade_componente < quantidade_producao[c]:
                            componentes_faltantes.append(f"{(quantidade_componente - quantidade_producao[c])*-1} {tipo_componente[c]}")
                            ftt = False

                    if ftt:
                        for c in range(len(tipo_componente)-1):
                            cursor.execute('''UPDATE componentes SET quantidade = quantidade - ? WHERE nome = ?''', (quantidade_producao[c], tipo_componente[c]))
                            conn.commit()
                    
                    else:
                        message_error = "Está faltando componentes para essa confeccção. São eles:"
                        for i in componentes_faltantes:
                            message_error += f" {i} /"

                        st.error(message_error)

                    if(bool and ftt):
                        codigo_serial = [c[4] for c in search_records(produto_selecionado, "produtos")][0]

                        cursor.execute("SELECT MAX(id) FROM estoque")
                        ultimo_id = cursor.fetchone()[0]

                        if ultimo_id == None: ultimo_id = 0

                        log_action(st.session_state['usuario_logado'], f"Registrou a Confecção de {quantidade_confeccionada} {produto_selecionado}")

                        devEuis = [chave["devEui"] for chave in chaves]
                        appKeys = [chave["appKey"] for chave in chaves]

                        if len(devEuis) != len(set(devEuis)) or len(appKeys) != len(set(appKeys)) or set(devEuis) & set(appKeys):
                            st.error("As chaves estão inconsistentes")

                        else:
                            for c in range(quantidade_confeccionada):
                                codigo_gerado = construir_id(codigo_serial, ultimo_id+c)

                                deveui = chaves[c]["devEui"]
                                appkey = chaves[c]["appKey"]

                                data_atual = datetime.now().strftime('%d/%m/%Y')

                                cursor.execute(
                                    '''
                                    INSERT INTO estoque (serial, tipo_produto, status, deveui, appkey, data_confeccao)
                                    VALUES (?, ?, ?, ?, ?, ?)
                                    ''',
                                    (codigo_gerado, produto_selecionado, 4, deveui, appkey, data_atual)
                                )
                                conn.commit()

                            st.rerun()


                else:
                    st.error("É necessário Preencher os Campos para Salvar!")

        with aba[7]:
            st.header("Histórico")

            col1, col2, col3 = st.columns(3)
            with col1:
                start_date = st.date_input("Data de início", value=None)
            with col2:
                end_date = st.date_input("Data de fim", value=None)
            with col3:
                user = st.text_input("Usuário")

            # Obter a data atual se não houver filtros
            if not start_date and not end_date:
                today = datetime.now().date()  # Retorna um objeto datetime.date
                logs = get_filtered_logs(start_date=today, end_date=today)
            else:
                logs = get_filtered_logs(
                    start_date=start_date if start_date else None,
                    end_date=end_date if end_date else None,
                    user=user
                )


            # Exibir os resultados
            if logs:
                df = pd.DataFrame(logs, columns=["Timestamp", "Usuário", "Ação"])
                pdf_buffer = export_to_pdf(df)
                st.download_button(
                    label="Baixar PDF",
                    data=pdf_buffer,
                    file_name="relatorio_logs.pdf",
                    mime="application/pdf",
                )

                st.dataframe(df, use_container_width=True)


            else:
                st.warning("Nenhum log encontrado para os filtros selecionados.")

        with aba[8]:
            st.header("Pendências")

            st.subheader("Lista de Compras de Componentes")

            cursor.execute('''
            SELECT nome, tipo, fornecedor, preco_base, quantidade, quantidade_minima 
            FROM componentes 
            WHERE quantidade < quantidade_minima
            ''')
            dados = cursor.fetchall() 

            diferencas = []
            for linha in dados:
                quantidade_minima = linha[5] 
                quantidade = linha[4] 
                diferenca = quantidade_minima - quantidade
                diferencas.append(diferenca)

            precos_estimados = [
                linha[3] * diferenca for linha, diferenca in zip(dados, diferencas)
            ]

            data = {
                "Componentes": [linha[0] for linha in dados],
                "Tipo": [linha[1] for linha in dados],
                "Fornecedor": [linha[2] for linha in dados],
                "Preço Unitário (R$)": [linha[3] for linha in dados],
                "Quantidade Mínima": diferencas,
                "Preço Estimado de Reposição (R$)": precos_estimados,
            }

            df = pd.DataFrame(data)

            total_diferencas = sum(diferencas)
            total_precos = sum(precos_estimados)

            linha_resumo = {
                "Componentes": "TOTAL",
                "Tipo": "",
                "Fornecedor": "",
                "Preço Unitário (R$)": "",
                "Quantidade Mínima": total_diferencas,
                "Preço Estimado de Reposição (R$)": total_precos,
            }

            df = pd.concat([df, pd.DataFrame([linha_resumo])], ignore_index=True)

            st.dataframe(df, use_container_width=True)

            cursor.execute('''
            SELECT tipo_produto, COUNT(*) as quantidade_status_0
            FROM estoque
            WHERE status = 0
            GROUP BY tipo_produto
            ''')
            status_data = cursor.fetchall()

            status_df = pd.DataFrame(status_data, columns=["tipo_produto", "quantidade_status_0"])

            cursor.execute('''SELECT nome, quantidade_minima FROM produtos''')
            produtos_data = cursor.fetchall()

            produtos_df = pd.DataFrame(produtos_data, columns=["nome", "quantidade_minima"])
            result_df = pd.merge(produtos_df, status_df, left_on="nome", right_on="tipo_produto", how="left")
            result_df["quantidade_status_0"] = result_df["quantidade_status_0"].fillna(0).astype(int)
            result_df["quantidade_minima_a_confeccionar"] = result_df["quantidade_minima"] - result_df["quantidade_status_0"]
            faltantes_df = result_df[result_df["quantidade_minima_a_confeccionar"] > 0]
            st.subheader("Lista de Produtos para Fabricar")
            if not faltantes_df.empty:
                st.dataframe(faltantes_df[["nome", "quantidade_minima_a_confeccionar"]] , use_container_width=True)
            else:
                st.success("Todos os produtos estão dentro da quantidade mínima!")

            cursor.execute('''
            SELECT serial, tipo_produto
            FROM estoque
            WHERE status = 2
            ''')
            reparar_data = cursor.fetchall()

            reparar_df = pd.DataFrame(reparar_data, columns=["Serial", "Tipo de Produto"])

            st.subheader("Lista de Produtos para Reparar")
            if not reparar_df.empty:
                st.dataframe(reparar_df , use_container_width=True)
            else:
                st.success("Não há produtos para reparar no momento!")

            st.subheader("Lista de Produtos para Venda")

            pendencias = carregar_pendencias()
            if pendencias:
                for pendencia in pendencias:
                    venda_id, cliente, propriedade, prazo, total, produtos = pendencia
                    produtos_venda = json.loads(produtos)

                    prazo_formatado = formatar_data(prazo)

                    col1, col2 = st.columns(2)

                    with col1:
                        st.write(f"### Venda {venda_id}")
                        st.write(f"**Cliente:** {cliente} | **Propriedade:** {propriedade} | **Prazo:** {prazo_formatado} | **Total:** R${total:.2f}")

                    with col2:
                        if st.button("Concluir", key=f"concluir_{venda_id}"):
                            atualizar_status_venda(venda_id, 1)

                    df_produtos = pd.DataFrame(produtos_venda)
                    st.dataframe(df_produtos, use_container_width=True)


        with aba[9]:
            st.header("Estatísticas")
            
            # Obter dados do banco
            cursor.execute("SELECT status FROM estoque")
            dados = cursor.fetchall()
            df = pd.DataFrame(dados, columns=["status"])

            # Mapeamento de status
            status_mapping = {
                0: "Estoque",
                1: "Campo",
                2: "Manutenção",
                3: "Inativo", 
                4: "Fabricação",
                5: "Reservado"
            }

            df["status_nome"] = df["status"].map(status_mapping)

            # Ordem desejada
            order = ["Estoque", "Manutenção", "Fabricação", "Campo", "Reservado", "Inativo"]
            df["status_nome"] = pd.Categorical(df["status_nome"], categories=order, ordered=True)

            # Frequências
            frequencias = df["status_nome"].value_counts().reindex(order).reset_index()
            frequencias.columns = ["Status", "Quantidade"]

            # Cores consistentes
            colors = px.colors.sequential.Agsunset  # Cores do gráfico
            color_mapping = {status: colors[i % len(colors)] for i, status in enumerate(order)}

            # Gráfico de pizza
            fig = px.pie(
                frequencias, 
                names="Status", 
                values="Quantidade", 
                title="Distribuição de Status",
                color="Status", 
                color_discrete_map=color_mapping  # Mapeamento de cores consistente
            )

            col1, col2 = st.columns(2)

            with col1:
                st.header("Detalhes por Status")
                
                # Retângulos com cores consistentes
                for i, row in frequencias.iterrows():
                    color = color_mapping[row['Status']]  # Cor baseada no status
                    st.markdown(
                        f"""
                        <div style='
                            background-color: {color};
                            padding: 10px;
                            border-radius: 10px;
                            margin-bottom: 10px;
                            color: white;
                            width: 600px; /* Define a largura */
                            height: 50px; /* Define a altura */
                            display: flex;
                            flex-direction: column;
                            justify-content: center; /* Centraliza o conteúdo verticalmente */
                            align-items: center; /* Centraliza o conteúdo horizontalmente */
                        '>
                            <h3 style='margin: 0;'>{row['Status']}</h3>
                            <p style='margin: 0;'>Quantidade: {row['Quantidade']}</p>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

            with col2:
                st.header("Gráfico de Status")
                st.plotly_chart(fig, use_container_width=True)

        with aba[10]:
            st.header("Backup")

            col1, col2, col3 = st.columns(3)

            with col1:
                st.write("### Download do Banco de Dados:")

            with col2:
                btt = st.button("Dados bd")

            if btt:
                with col3:
                    with open("sistema_gestao.db", "rb") as f:
                        db_file = f.read()
                        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                        st.download_button(
                            label="Baixar Banco de Dados (.db)",
                            data=db_file,
                            file_name= f"sistema_gestao {now} .db",
                            mime="application/octet-stream"
                        )
                        cursor.execute(
                            '''
                            INSERT INTO backups (ultimo_backup)
                            VALUES (?)
                            ''',
                            (now,)
                        )
                        conn.commit()
                        log_action(st.session_state['usuario_logado'], f"Fez Backup do Banco de Dados")

            cursor.execute("SELECT ultimo_backup FROM backups ORDER BY id DESC LIMIT 1")
            result = cursor.fetchone()[0]
            if not result: result =  "Nenhum Backup Realizado Ainda"
            st.write(f"Ultimo Backup em: {result}")

