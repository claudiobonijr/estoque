import streamlit as st
import psycopg2
import pandas as pd
from datetime import datetime

# Configuração visual da página
st.set_page_config(page_title="Gestão de Estoque Pro", page_icon="🏗️", layout="wide")

# Estilo CSS para melhorar a interface
st.markdown("""
    <style>
    .main { background-color: #f0f2f6; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #007bff; color: white; }
    </style>
    """, unsafe_allow_html=True)

# Função para conectar ao banco de dados do Render usando a URL dos Secrets
def get_connection():
    return psycopg2.connect(st.secrets["db_url"])

# Função para criar as tabelas automaticamente (executa no início)
def init_db():
    try:
        conn = get_connection()
        cur = conn.cursor()
        # Cria tabela de produtos
        cur.execute("""
            CREATE TABLE IF NOT EXISTS produtos (
                codigo TEXT PRIMARY KEY,
                descricao TEXT
            );
        """)
        # Cria tabela de movimentações
        cur.execute("""
            CREATE TABLE IF NOT EXISTS movimentacoes (
                id SERIAL PRIMARY KEY,
                tipo TEXT,
                data DATE,
                obra TEXT,
                codigo TEXT,
                descricao TEXT,
                quantidade FLOAT,
                referencia TEXT
            );
        """)
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        st.error(f"Erro ao conectar ao banco: {e}")

# Inicializa o banco
init_db()

# --- MENU LATERAL ---
st.sidebar.title("🏗️ Controle de Estoque")
aba = st.sidebar.radio("Navegação", ["📊 Dashboard", "📦 Cadastro de Itens", "📥 Entrada", "📤 Saída"])

# --- ABA: DASHBOARD ---
if aba == "📊 Dashboard":
    st.title("📊 Saldo Geral de Estoque")
    try:
        conn = get_connection()
        df_mov = pd.read_sql("SELECT * FROM movimentacoes", conn)
        conn.close()

        if not df_mov.empty:
            # Calcula o saldo (Entrada soma, Saída subtrai)
            df_mov['qtd_calc'] = df_mov.apply(lambda x: x['quantidade'] if x['tipo'] == 'Entrada' else -x['quantidade'], axis=1)
            saldo = df_mov.groupby(['codigo', 'descricao'])['qtd_calc'].sum().reset_index()
            saldo.columns = ['Código', 'Descrição', 'Saldo Atual']
            
            st.dataframe(saldo, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma movimentação registrada até o momento.")
    except:
        st.warning("Aguardando dados...")

# --- ABA: CADASTRO ---
elif aba == "📦 Cadastro de Itens":
    st.title("📦 Cadastro de Novos Insumos")
    with st.form("form_cadastro"):
        cod = st.text_input("Código do Produto")
        desc = st.text_input("Descrição do Produto")
        if st.form_submit_button("Salvar Insumo"):
            if cod and desc:
                conn = get_connection()
                cur = conn.cursor()
                # Insere ou ignora se já existir
                cur.execute("INSERT INTO produtos (codigo, descricao) VALUES (%s, %s) ON CONFLICT (codigo) DO NOTHING", (cod, desc))
                conn.commit()
                cur.close()
                conn.close()
                st.success(f"Item {cod} cadastrado com sucesso!")
            else:
                st.error("Preencha todos os campos.")

# --- ABA: ENTRADA ---
elif aba == "📥 Entrada":
    st.title("📥 Registro de Entrada")
    conn = get_connection()
    df_p = pd.read_sql("SELECT * FROM produtos ORDER BY descricao", conn)
    conn.close()

    if not df_p.empty:
        with st.form("form_entrada"):
            opcoes = df_p['codigo'] + " - " + df_p['descricao']
            item_sel = st.selectbox("Selecione o Insumo", opcoes)
            qtd = st.number_input("Quantidade Recebida", min_value=0.01)
            obra = st.text_input("Obra de Destino")
            oc = st.text_input("Número da OC / NF")
            
            if st.form_submit_button("Confirmar Entrada"):
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, referencia)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, ("Entrada", datetime.now().date(), obra, item_sel.split(" - ")[0], item_sel.split(" - ")[1], qtd, oc))
                conn.commit()
                cur.close()
                conn.close()
                st.success("Entrada registrada no banco de dados!")
    else:
        st.warning("Cadastre produtos na aba de Cadastro antes de dar entrada.")

# --- ABA: SAÍDA ---
elif aba == "📤 Saída":
    st.title("📤 Registro de Saída / Aplicação")
    conn = get_connection()
    df_p = pd.read_sql("SELECT * FROM produtos ORDER BY descricao", conn)
    conn.close()

    if not df_p.empty:
        with st.form("form_saida"):
            opcoes = df_p['codigo'] + " - " + df_p['descricao']
            item_sel = st.selectbox("Selecione o Insumo", opcoes)
            qtd = st.number_input("Quantidade Utilizada", min_value=0.01)
            obra = st.text_input("Obra / Frente de Trabalho")
            
            if st.form_submit_button("Confirmar Saída"):
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, referencia)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, ("Saída", datetime.now().date(), obra, item_sel.split(" - ")[0], item_sel.split(" - ")[1], qtd, "Saída de Estoque"))
                conn.commit()
                cur.close()
                conn.close()
                st.warning("Saída registrada!")
    else:
        st.warning("Não há produtos cadastrados.")
