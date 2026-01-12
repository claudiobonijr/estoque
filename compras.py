import streamlit as st
import psycopg2
import pandas as pd
from datetime import datetime
import plotly.express as px

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Amâncio Gestão Pro", page_icon="🏗️", layout="wide")

# 2. DESIGN ADAPTATIVO (CSS)
st.markdown("""
    <style>
    :root { --primary-bg: #ffffff; --text-main: #1e293b; --accent: #2563eb; }
    @media (prefers-color-scheme: dark) {
        :root { --primary-bg: #0e1117; --text-main: #f0f6fc; --accent: #58a6ff; }
    }
    .stApp { background-color: var(--primary-bg); }
    .stButton>button { width: 100%; border-radius: 8px; background: var(--accent); color: white !important; }
    </style>
    """, unsafe_allow_html=True)

# 3. FUNÇÃO DE CONEXÃO MELHORADA
def run_query(query, is_select=True, params=None):
    """Gerencia a abertura e fechamento da conexão automaticamente"""
    try:
        conn = psycopg2.connect(st.secrets["db_url"], connect_timeout=10)
        if is_select:
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
        st.error(f"Erro na operação: {e}")
        return None

# 4. CONTROLE DE ACESSO
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

# 5. SIDEBAR
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/1063/1063196.png", width=80)
    st.title("Amâncio Obras")
    
    if not st.session_state["authenticated"]:
        with st.expander("🔐 Login Admin", expanded=True):
            u = st.text_input("Usuário")
            p = st.text_input("Senha", type="password")
            if st.button("Entrar"):
                if u == st.secrets["auth"]["username"] and p == st.secrets["auth"]["password"]:
                    st.session_state["authenticated"] = True
                    st.rerun()
                else:
                    st.error("Incorreto")
        menu = "📊 Saldo Geral"
    else:
        st.success(f"Logado: {st.secrets['auth']['username']}")
        menu = st.radio("Navegação:", [
            "📊 Saldo Geral", "📋 Histórico", "📥 Entrada", "📤 Saída", "📦 Cadastrar Material"
        ])
        if st.button("Sair"):
            st.session_state["authenticated"] = False
            st.rerun()

# 6. LOGICA DAS TELAS (Só roda se estiver autenticado ou para ver saldo)
if menu == "📊 Saldo Geral":
    st.title("📊 Saldo em Estoque")
    df_produtos = run_query("SELECT codigo, descricao, unidade FROM produtos ORDER BY descricao")
    
    if df_produtos is not None and not df_produtos.empty:
        df_mov = run_query("SELECT codigo, tipo, quantidade FROM movimentacoes")
        
        if df_mov is not None and not df_mov.empty:
            df_mov['val'] = df_mov.apply(lambda x: x['quantidade'] if x['tipo'] in ['Entrada', 'Ajuste(+)'] else -x['quantidade'], axis=1)
            saldos_calc = df_mov.groupby('codigo')['val'].sum().reset_index()
            resultado = pd.merge(df_produtos, saldos_calc, on='codigo', how='left').fillna(0)
        else:
            resultado = df_produtos.copy()
            resultado['val'] = 0
        
        resultado.columns = ['Cód', 'Descrição', 'Und', 'Saldo Atual']
        st.dataframe(resultado, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum material cadastrado ou erro ao carregar.")

elif menu == "📦 Cadastrar Material" and st.session_state["authenticated"]:
    st.title("📦 Novo Produto")
    with st.form("form_cad", clear_on_submit=True):
        c1 = st.text_input("Código")
        c2 = st.text_input("Descrição")
        c3 = st.selectbox("Unidade", ["Unidade", "Kg", "Metro", "Saco", "Barra"])
        if st.form_submit_button("Salvar"):
            if c1 and c2:
                success = run_query("INSERT INTO produtos (codigo, descricao, unidade) VALUES (%s, %s, %s) ON CONFLICT (codigo) DO NOTHING", 
                                   is_select=False, params=(c1.upper(), c2.upper(), c3))
                if success: st.success("Cadastrado!")
            else: st.warning("Preencha tudo.")

elif menu == "📥 Entrada" and st.session_state["authenticated"]:
    st.title("📥 Entrada de Material")
    prods = run_query("SELECT codigo, descricao, unidade FROM produtos ORDER BY descricao")
    if prods is not None and not prods.empty:
        with st.form("form_ent"):
            item = st.selectbox("Material", prods['codigo'] + " - " + prods['descricao'])
            qtd = st.number_input("Quantidade", min_value=0.1)
            obra = st.text_input("Obra")
            if st.form_submit_button("Confirmar"):
                cod_sel = item.split(" - ")[0]
                des_sel = item.split(" - ")[1]
                run_query("INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade) VALUES (%s,%s,%s,%s,%s,%s)",
                          is_select=False, params=("Entrada", datetime.now().date(), obra, cod_sel, des_sel, qtd))
                st.success("Registrado!")
    else: st.warning("Cadastre produtos primeiro.")

elif menu == "📋 Histórico" and st.session_state["authenticated"]:
    st.title("📋 Histórico")
    df_hist = run_query("SELECT * FROM movimentacoes ORDER BY data DESC")
    if df_hist is not None:
        st.dataframe(df_hist, use_container_width=True)

st.markdown('<div style="text-align:center; color:grey; font-size:12px; margin-top:50px;">Claudio Boni Junior - Gestão de Obras</div>', unsafe_allow_html=True)
