import streamlit as st
import psycopg2
import pandas as pd
import plotly.express as px
from datetime import datetime
import time

# -----------------------------------------------------------------------------
# 1. CONFIGURAÇÃO AVANÇADA DA PÁGINA
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Amâncio Gestão Pro",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -----------------------------------------------------------------------------
# 2. ESTILIZAÇÃO CSS PROFISSIONAL
# -----------------------------------------------------------------------------
st.markdown("""
    <style>
    /* Cores e Fontes Globais */
    :root {
        --primary-color: #2563eb;
        --background-light: #f8fafc;
        --text-dark: #1e293b;
    }
    
    /* Cards de Métricas */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    
    /* Botões Personalizados */
    .stButton>button {
        width: 100%;
        border-radius: 6px;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    /* Tabela de Dados */
    .stDataFrame {
        border: 1px solid #e2e8f0;
        border-radius: 8px;
    }
    
    /* Rodapé */
    .footer {
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background-color: #f1f5f9;
        color: #64748b;
        text-align: center;
        padding: 10px;
        font-size: 0.8rem;
        border-top: 1px solid #e2e8f0;
        z-index: 100;
    }
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 3. GERENCIAMENTO DE CONEXÃO (BLINDADO)
# -----------------------------------------------------------------------------
@st.cache_resource(ttl=600)  # Mantém a conexão "quente" mas recria se necessário
def get_db_connection():
    """Conecta ao Supabase via Pooler ignorando erros de IPv6"""
    try:
        return psycopg2.connect(
            st.secrets["db_url"],
            connect_timeout=15,
            gssencmode="disable" # O Segredo do sucesso no plano Free
        )
    except Exception as e:
        return None

def run_query(query, params=None, fetch_data=True):
    """Executa queries com tratamento de erro e fechamento seguro"""
    try:
        # Forçamos uma nova conexão a cada query para garantir estabilidade no Pooler Session
        conn = psycopg2.connect(st.secrets["db_url"], connect_timeout=10, gssencmode="disable")
        
        if fetch_data:
            df = pd.read_sql(query, conn, params=params)
            conn.close()
            return df
        else:
            cur = conn.cursor()
            cur.execute(query, params)
            conn.commit()
            cur.close()
            conn.close()
            return True
    except Exception as e:
        st.error(f"Erro na operação de banco de dados: {e}")
        return None

# -----------------------------------------------------------------------------
# 4. AUTENTICAÇÃO
# -----------------------------------------------------------------------------
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

def login_screen():
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("<h2 style='text-align: center;'>🔐 Acesso Corporativo</h2>", unsafe_allow_html=True)
        with st.form("login_form"):
            u = st.text_input("ID Usuário")
            p = st.text_input("Senha de Acesso", type="password")
            if st.form_submit_button("Entrar no Sistema"):
                if u == st.secrets["auth"]["username"] and p == st.secrets["auth"]["password"]:
                    st.session_state["authenticated"] = True
                    st.toast("Login realizado com sucesso!", icon="✅")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Credenciais inválidas.")

# -----------------------------------------------------------------------------
# 5. SISTEMA PRINCIPAL
# -----------------------------------------------------------------------------
def main_system():
    # --- SIDEBAR ---
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/1063/1063196.png", width=70)
        st.markdown("### **Amâncio Obras**")
        st.caption(f"Logado como: {st.secrets['auth']['username'].upper()}")
        st.divider()
        
        menu = st.radio(
            "Navegação Principal", 
            ["📊 Dashboard Executivo", "📦 Inventário Geral", "🔄 Central de Operações", "⚙️ Ajustes & Histórico"],
            index=0
        )
        
        st.divider()
        if st.button("Encerrar Sessão"):
            st.session_state["authenticated"] = False
            st.rerun()

    # --- CARREGAMENTO DE DADOS (CACHEADO PARA PERFORMANCE) ---
    df_prods = run_query("SELECT codigo, descricao, unidade FROM produtos ORDER BY descricao")
    df_movs = run_query("SELECT * FROM movimentacoes ORDER BY data DESC, id DESC")

    # Cálculo de Saldos em Tempo Real
    saldo_atual = pd.DataFrame()
    if df_prods is not None and not df_prods.empty:
        if df_movs is not None and not df_movs.empty:
            df_calc = df_movs.copy()
            # Lógica: Entrada/Ajuste(+) soma, Saída/Ajuste(-) subtrai
            df_calc['fator'] = df
