import streamlit as st
import psycopg2
import pandas as pd
from datetime import datetime
import plotly.express as px

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Amâncio Gestão Pro", page_icon="🏗️", layout="wide")

# 2. CSS RESPONSIVO E ADAPTATIVO
st.markdown("""
    <style>
    :root {
        --primary-bg: #ffffff; --secondary-bg: #f8fafc; --text-main: #1e293b;
        --card-bg: #ffffff; --border-color: #e2e8f0; --accent: #2563eb; --danger: #ef4444;
    }
    @media (prefers-color-scheme: dark) {
        :root {
            --primary-bg: #0e1117; --secondary-bg: #161b22; --text-main: #f0f6fc;
            --card-bg: #161b22; --border-color: #30363d; --accent: #58a6ff; --danger: #f85149;
        }
    }
    .stApp { background-color: var(--primary-bg); }
    div[data-testid="metric-container"] {
        background-color: var(--secondary-bg); border: 1px solid var(--border-color);
        padding: 20px; border-radius: 12px;
    }
    h1, h2, h3, p, span, label { color: var(--text-main) !important; }
    .stButton>button {
        width: 100%; border-radius: 8px; height: 3.5em;
        background: var(--accent); color: white !important; font-weight: bold; border: none;
    }
    /* Estilo para botão de excluir */
    .btn-excluir>button { background-color: var(--danger) !important; height: 2.5em !important; }
    </style>
    """, unsafe_allow_html=True)

# 3. CONEXÃO
def get_connection():
    try:
        return psycopg2.connect(st.secrets["db_url"])
    except Exception as e:
        st.error(f"Erro de Conexão: {e}")
        return None

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

# 4. SIDEBAR
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/1063/1063196.png", width=80)
    st.title("Amâncio Obras")
    
    if not st.session_state["authenticated"]:
        with st.expander("🔐 Admin"):
            u = st.text_input("Usuário")
            p = st.text_input("Senha", type="password")
            if st.button("Acessar"):
                if u == st.secrets["auth"]["username"] and p == st.secrets["auth"]["password"]:
                    st.session_state["authenticated"] = True
                    st.rerun()
        menu = st.radio("Ir para:", ["📊 Dashboard Público"])
    else:
        st.success("Administrador Logado")
        menu = st.radio("Navegação:", [
            "📊 Dashboard Público", 
            "📋 Inventário Geral", 
            "📥 Registrar Entrada", 
            "📤 Registrar Saída", 
            "🔧 Ajuste de Estoque",
            "🗑️ Gerenciar Lançamentos",
            "📦 Cadastrar Material"
        ])
        if st.button("Sair"):
            st.session_state["authenticated"] = False
            st.rerun()

conn = get_connection()

# 5. LÓGICA DAS TELAS (Resumo das funcionalidades principais)

if menu == "📊 Dashboard Público":
    st.title("📊 Status do Estoque")
    if conn:
        df_mov = pd.read_sql("SELECT * FROM movimentacoes", conn)
        if not df_mov.empty:
            df_mov['val'] = df_mov.apply(lambda x: x['quantidade'] if x['tipo'] in ['Entrada', 'Ajuste(+)'] else -x['quantidade'], axis=1)
            saldo = df_mov.groupby(['codigo', 'descricao'])['val'].sum().reset_index()
            saldo.columns = ['Cód', 'Descrição', 'Saldo']
            st.dataframe(saldo, use_container_width=True, hide_index=True)

elif menu == "🗑️ Gerenciar Lançamentos":
    st.title("🗑️ Gerenciar Lançamentos")
    st.info("Aqui você pode excluir entradas, saídas ou ajustes feitos por erro.")
    
    df_mov = pd.read_sql("SELECT * FROM movimentacoes ORDER BY id DESC LIMIT 100", conn)
    
    if not df_mov.empty:
        for index, row in df_mov.iterrows():
            with st.container():
                c1, c2, c3, c4 = st.columns([1, 3, 4, 1])
                c1.write(f"**{row['tipo']}**")
                c2.write(f"{row['descricao']} ({row['quantidade']} un)")
                c3.write(f"Ref: {row['referencia']}")
                
                # Botão de exclusão único para cada linha
                if c4.button("Excluir", key=f"del_{row['id']}"):
                    cur = conn.cursor()
                    cur.execute("DELETE FROM movimentacoes WHERE id = %s", (row['id'],))
                    conn.commit()
                    st.success(f"Lançamento {row['id']} removido!")
                    st.rerun()
                st.markdown("---")
    else:
        st.write("Nenhum lançamento encontrado.")

elif menu == "📥 Registrar Entrada":
    st.title("📥 Entrada Detalhada")
    prods = pd.read_sql("SELECT * FROM produtos ORDER BY descricao", conn)
    with st.form("ent_f", clear_on_submit=True):
        item = st.selectbox("Material", prods['codigo'] + " - " + prods['descricao'])
        qtd = st.number_input("Quantidade", min_value=0.01)
        nf = st.text_input("Nota Fiscal")
        forn = st.text_input("Fornecedor")
        if st.form_submit_button("SALVAR"):
            cur = conn.cursor()
            cur.execute("INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, referencia) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                       ("Entrada", datetime.now().date(), "Estoque", item.split(" - ")[0], item.split(" - ")[1], qtd, f"NF: {nf} | Forn: {forn}"))
            conn.commit(); st.success("OK!")

# (As outras abas seguem a lógica anterior de Saída, Cadastro e Ajuste)

if conn: conn.close()
