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
# Para o Pooler do Supabase (Porta 6543), NÃO devemos usar cache de conexão persistente.
# A melhor estratégia é: Abrir -> Usar -> Fechar imediatamente.

def run_query(query, params=None, fetch_data=True):
    conn = None
    try:
        # Conecta sempre do zero para evitar "Connection already closed"
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
        # Se der erro, não quebra o site. Retorna vazio.
        print(f"Erro BD: {e}") # Aparece no log do Streamlit
        if fetch_data:
            return pd.DataFrame() # Retorna tabela vazia para não travar loops
        return False
    finally:
        if conn:
            conn.close()

# -----------------------------------------------------------------------------
# 3. AUTENTICAÇÃO SIMPLES
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

    # --- CARREGAMENTO DE DADOS (COM PROTEÇÃO) ---
    # Se falhar, vem DataFrame vazio, mas não trava o site com tela preta
    df_prods = run_query("SELECT codigo, descricao, unidade FROM produtos ORDER BY descricao")
    df_movs = run_query("SELECT * FROM movimentacoes ORDER BY data DESC, id DESC")

    # Verifica se carregou
    if df_prods.empty and menu != "📦 Operações":
        st.warning("⚠️ Banco de dados conectou, mas não há produtos ou a conexão oscilou. Tente recarregar a página.")

    # --- LÓGICA DE SALDO ---
    saldo_atual = pd.DataFrame(columns=['Cod', 'Produto', 'Unid', 'Saldo'])
    if not df_prods.empty and not df_movs.empty:
        df_calc = df_movs.copy()
        # Ajuste positivo ou entrada = soma. Saída ou ajuste negativo = subtrai.
        df_calc['fator'] = df_calc['tipo'].apply(lambda x: 1 if x in ['Entrada', 'Ajuste(+)'] else -1)
        df_calc['qtd_real'] = df_calc['quantidade'] * df_calc['fator']
        
        saldos = df_calc.groupby('codigo')['qtd_real'].sum().reset_index()
        saldo_atual = pd.merge(df_prods, saldos, on='codigo', how='left').fillna(0)
        saldo_atual.rename(columns={'qtd_real': 'Saldo', 'descricao': 'Produto', 'unidade': 'Unid', 'codigo': 'Cod'}, inplace=True)
    elif not df_prods.empty:
        saldo_atual = df_prods.copy()
        saldo_atual.rename(columns={'descricao': 'Produto', 'unidade': 'Unid', 'codigo': 'Cod'}, inplace=True)
        saldo_atual['Saldo'] = 0

    # --- TELAS ---
    
    # 1. DASHBOARD
    if menu == "📊 Dashboard":
        st.header("📊 Visão Geral")
        if not saldo_atual.empty:
            c1, c2, c3 = st.columns(3)
            c1.metric("Total de Itens", len(saldo_atual))
            c2.metric("Movimentações",
