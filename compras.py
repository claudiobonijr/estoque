import streamlit as st
import psycopg2
import pandas as pd
from datetime import datetime

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Estoque Obras", page_icon="🏗️", layout="wide")

# 2. ESTILO E LOGO
logo_url = "https://cdn-icons-png.flaticon.com/512/4222/4222961.png"

st.markdown("""
    <style>
    div[data-testid="metric-container"] { background-color: rgba(151, 166, 195, 0.15); padding: 20px; border-radius: 12px; }
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; text-align: center; font-size: 12px; color: #888; background: rgba(255,255,255,0.8); padding: 5px; }
    section[data-testid="stSidebar"] { background-color: #1e293b; }
    section[data-testid="stSidebar"] * { color: white !important; }
    </style>
    """, unsafe_allow_html=True)

# 3. FUNÇÃO DE CONEXÃO COM TRATAMENTO DE ERRO
def get_connection():
    try:
        # Tenta conectar usando a URL do Secrets
        conn = psycopg2.connect(st.secrets["db_url"])
        return conn
    except Exception as e:
        # Se falhar, mostra o erro técnico para facilitar o ajuste
        st.error(f"⚠️ Erro técnico de conexão: {e}")
        return None

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

# 4. SIDEBAR PERSONALIZADA
with st.sidebar:
    st.image(logo_url, width=100)
    st.title("Sistema de Obras")
    st.markdown("---")
    
    if not st.session_state["authenticated"]:
        with st.expander("🔐 Área do Administrador"):
            user = st.text_input("Usuário")
            pw = st.text_input("Senha", type="password")
            if st.button("Acessar"):
                if user == st.secrets["auth"]["username"] and pw == st.secrets["auth"]["password"]:
                    st.session_state["authenticated"] = True
                    st.rerun()
                else:
                    st.error("Incorreto")
        menu = st.radio("Navegação:", ["📊 Saldo de Estoque"])
    else:
        st.success(f"Logado como: {st.secrets['auth']['username']}")
        menu = st.radio("Navegação:", ["📊 Saldo de Estoque", "📦 Cadastro", "📥 Entrada", "📤 Saída"])
        if st.button("Sair (Logoff)"):
            st.session_state["authenticated"] = False
            st.rerun()

# 5. LÓGICA DAS ABAS
if menu == "📊 Saldo de Estoque":
    st.title("📊 Saldo Geral (Público)")
    conn = get_connection()
    
    if conn:
        try:
            df_mov = pd.read_sql("SELECT * FROM movimentacoes", conn)
            conn.close()
            if not df_mov.empty:
                df_mov['val'] = df_mov.apply(lambda x: x['quantidade'] if x['tipo'] == 'Entrada' else -x['quantidade'], axis=1)
                saldo = df_mov.groupby(['codigo', 'descricao'])['val'].sum().reset_index()
                saldo.columns = ['Cód', 'Descrição', 'Saldo Atual']
                
                c1, c2 = st.columns(2)
                c1.metric("Itens Ativos", len(saldo))
                c2.metric("Total Movimentações", len(df_mov))
                
                st.dataframe(saldo, use_container_width=True, hide_index=True)
            else:
                st.info("Nenhuma movimentação registrada. O administrador precisa lançar as entradas.")
        except:
            st.warning("As tabelas ainda não foram criadas ou o banco está vazio.")
    else:
        st.warning("Verifique se o IP 0.0.0.0/0 está liberado no Render e se a URL no Secrets termina com ?sslmode=require")

# ABAS DE EDIÇÃO (ADMIN)
elif menu == "📦 Cadastro":
    st.title("📦 Cadastro de Materiais")
    with st.form("f_cad", clear_on_submit=True):
        c1, c2 = st.columns(2)
        cod = c1.text_input("Código")
        des = c2.text_input("Descrição")
        if st.form_submit_button("Salvar"):
            conn = get_connection()
            if conn:
                cur = conn.cursor()
                cur.execute("INSERT INTO produtos (codigo, descricao) VALUES (%s, %s) ON CONFLICT (codigo) DO NOTHING", (cod, des))
                conn.commit(); cur.close(); conn.close()
                st.success("Cadastrado com sucesso!")

elif menu == "📥 Entrada":
    st.title("📥 Entrada de Material")
    conn = get_connection()
    if conn:
        prods = pd.read_sql("SELECT * FROM produtos ORDER BY descricao", conn)
        conn.close()
        if not prods.empty:
            with st.form("f_ent", clear_on_submit=True):
                item = st.selectbox("Selecione", prods['codigo'] + " - " + prods['descricao'])
                q = st.number_input("Qtd", min_value=0.01)
                ob = st.text_input("Obra")
                if st.form_submit_button("Confirmar Entrada"):
                    conn = get_connection(); cur = conn.cursor()
                    cur.execute("INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, referencia) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                               ("Entrada", datetime.now().date(), ob, item.split(" - ")[0], item.split(" - ")[1], q, "Entrada Direta"))
                    conn.commit(); cur.close(); conn.close()
                    st.success("Entrada salva!")
        else:
            st.warning("Cadastre o produto primeiro.")

elif menu == "📤 Saída":
    st.title("📤 Saída de Material")
    conn = get_connection()
    if conn:
        prods = pd.read_sql("SELECT * FROM produtos ORDER BY descricao", conn)
        conn.close()
        if not prods.empty:
            with st.form("f_sai", clear_on_submit=True):
                item = st.selectbox("Selecione", prods['codigo'] + " - " + prods['descricao'])
                q = st.number_input("Qtd", min_value=0.01)
                ob = st.text_input("Destino")
                if st.form_submit_button("Confirmar Saída"):
                    conn = get_connection(); cur = conn.cursor()
                    cur.execute("INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, referencia) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                               ("Saída", datetime.now().date(), ob, item.split(" - ")[0], item.split(" - ")[1], q, "Baixa"))
                    conn.commit(); cur.close(); conn.close()
                    st.warning("Saída salva!")

# RODAPÉ FIXO
st.markdown('<div class="footer">Desenvolvido por Claudio Boni Junior</div>', unsafe_allow_html=True)
