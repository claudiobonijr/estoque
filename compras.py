import streamlit as st
import psycopg2
import pandas as pd
import plotly.express as px
from datetime import datetime
import time

# -----------------------------------------------------------------------------
# 1. CONFIGURAÇÃO DA PÁGINA
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Amâncio Gestão",
    page_icon="🏗️",
    layout="wide"
)

# -----------------------------------------------------------------------------
# 2. CONEXÃO BLINDADA (SEM CACHE DE CONEXÃO)
# -----------------------------------------------------------------------------
def run_query(query, params=None, fetch_data=True):
    conn = None
    try:
        # Conecta sempre do zero para evitar quedas no Pooler do Supabase
        conn = psycopg2.connect(
            st.secrets["db_url"],
            connect_timeout=10,
            gssencmode="disable" 
        )
        
        if fetch_data:
            df = pd.read_sql(query, conn, params=params)
            return df
        else:
            with conn.cursor() as cur:
                cur.execute(query, params)
                conn.commit()
            return True
            
    except Exception as e:
        # Log do erro no console (invisível ao usuário comum) para debug
        print(f"Erro BD: {e}") 
        if fetch_data:
            return pd.DataFrame() # Retorna tabela vazia para não quebrar o site
        return False
    finally:
        if conn:
            conn.close()

# -----------------------------------------------------------------------------
# 3. AUTENTICAÇÃO
# -----------------------------------------------------------------------------
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

def login_screen():
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        st.title("🔐 Login")
        with st.form("login"):
            u = st.text_input("Usuário")
            p = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar"):
                if u == st.secrets["auth"]["username"] and p == st.secrets["auth"]["password"]:
                    st.session_state["authenticated"] = True
                    st.rerun()
                else:
                    st.error("Dados incorretos.")

# -----------------------------------------------------------------------------
# 4. SISTEMA PRINCIPAL
# -----------------------------------------------------------------------------
def main_system():
    # --- SIDEBAR ---
    with st.sidebar:
        st.title("Amâncio Obras")
        menu = st.radio("Menu", ["📊 Dashboard", "📦 Operações", "⚙️ Dados"])
        if st.button("Sair"):
            st.session_state["authenticated"] = False
            st.rerun()

    # --- CARREGAMENTO DE DADOS ---
    # Busca os dados no banco
    df_prods = run_query("SELECT codigo, descricao, unidade FROM produtos ORDER BY descricao")
    df_movs = run_query("SELECT * FROM movimentacoes ORDER BY data DESC, id DESC")

    # Verifica se carregou produtos
    if df_prods.empty and menu != "📦 Operações":
        st.warning("⚠️ O sistema conectou, mas não encontrou produtos. Vá em 'Operações' > 'Novo Produto' para começar.")

    # --- LÓGICA DE SALDO ---
    # Cria uma estrutura base de saldo
    saldo_atual
