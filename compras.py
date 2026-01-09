import streamlit as st
import psycopg2
import pandas as pd
from datetime import datetime

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Gestão de Estoque", page_icon="🏗️", layout="wide")

# 2. PERSONALIZAÇÃO VISUAL
logo_url = "https://media.discordapp.net/attachments/1287152284328919116/1459226633025224879/Design-sem-nome-1.png?ex=69628234&is=696130b4&hm=460d0214e433068507b61d26f3ae1957e36d7a9480bf97e899ef3ae70303f294&=&format=webp&quality=lossless&width=600&height=158"

st.markdown("""
    <style>
    div[data-testid="metric-container"] { background-color: rgba(151, 166, 195, 0.15); padding: 20px; border-radius: 12px; }
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; text-align: center; font-size: 12px; color: #888; background: rgba(255,255,255,0.8); padding: 5px; }
    section[data-testid="stSidebar"] { background-color: #1e293b; }
    section[data-testid="stSidebar"] * { color: white !important; }
    </style>
    """, unsafe_allow_html=True)

# 3. CONEXÃO E CRIAÇÃO AUTOMÁTICA DE TABELAS
def get_connection():
    try:
        # Se db_url não estiver nos secrets, gera um erro amigável
        if "db_url" not in st.secrets:
            st.error("ERRO: A chave 'db_url' não foi encontrada nos Secrets do Streamlit.")
            return None
        return psycopg2.connect(st.secrets["db_url"])
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return None

def init_db():
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        # Cria as tabelas se elas não existirem
        cur.execute("""
            CREATE TABLE IF NOT EXISTS produtos (
                codigo TEXT PRIMARY KEY,
                descricao TEXT
            );
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

# Tenta inicializar o banco sempre que o app carregar
init_db()

# --- LÓGICA DE LOGIN ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

# 4. SIDEBAR
with st.sidebar:
    st.image(logo_url, width=250)
    st.title("Gestão de Estoque")
    st.markdown("---")
    
    if not st.session_state["authenticated"]:
        with st.expander("🔐 Área do Administrador"):
            u = st.text_input("Usuário")
            p = st.text_input("Senha", type="password")
            if st.button("Acessar"):
                if u == st.secrets["auth"]["username"] and p == st.secrets["auth"]["password"]:
                    st.session_state["authenticated"] = True
                    st.rerun()
                else:
                    st.error("Incorreto")
        menu = st.radio("Navegação:", ["📊 Saldo de Estoque"])
    else:
        st.success(f"Logado: {st.secrets['auth']['username']}")
        menu = st.radio("Navegação:", ["📊 Saldo de Estoque", "📦 Cadastro", "📥 Entrada", "📤 Saída"])
        if st.button("Sair (Logoff)"):
            st.session_state["authenticated"] = False
            st.rerun()

# 5. ABAS
if menu == "📊 Saldo de Estoque":
    st.title("📊 Saldo Geral (Público)")
    conn = get_connection()
    if conn:
        df_mov = pd.read_sql("SELECT * FROM movimentacoes", conn)
        conn.close()
        if not df_mov.empty:
            df_mov['val'] = df_mov.apply(lambda x: x['quantidade'] if x['tipo'] == 'Entrada' else -x['quantidade'], axis=1)
            saldo = df_mov.groupby(['codigo', 'descricao'])['val'].sum().reset_index()
            saldo.columns = ['Cód', 'Descrição', 'Saldo Atual']
            c1, c2 = st.columns(2); c1.metric("Itens", len(saldo)); c2.metric("Movimentações", len(df_mov))
            st.dataframe(saldo, use_container_width=True, hide_index=True)
        else:
            st.info("Aguardando lançamentos do administrador.")

elif menu == "📦 Cadastro":
    st.title("📦 Cadastro")
    with st.form("f_cad", clear_on_submit=True):
        c1 = st.text_input("Código"); c2 = st.text_input("Descrição")
        if st.form_submit_button("Salvar"):
            conn = get_connection()
            if conn:
                cur = conn.cursor()
                cur.execute("INSERT INTO produtos (codigo, descricao) VALUES (%s, %s) ON CONFLICT (codigo) DO NOTHING", (c1, c2))
                conn.commit(); cur.close(); conn.close(); st.success("Salvo!")

elif menu == "📥 Entrada":
    st.title("📥 Entrada")
    conn = get_connection()
    if conn:
        prods = pd.read_sql("SELECT * FROM produtos ORDER BY descricao", conn)
        conn.close()
        with st.form("f_ent", clear_on_submit=True):
            item = st.selectbox("Item", prods['codigo'] + " - " + prods['descricao']) if not prods.empty else "Nenhum"
            q = st.number_input("Qtd", min_value=0.01); ob = st.text_input("Obra")
            if st.form_submit_button("Confirmar"):
                conn = get_connection(); cur = conn.cursor()
                cur.execute("INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, referencia) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                           ("Entrada", datetime.now().date(), ob, item.split(" - ")[0], item.split(" - ")[1], q, "Entrada Direta"))
                conn.commit(); cur.close(); conn.close(); st.success("Registrado!")

elif menu == "📤 Saída":
    st.title("📤 Saída")
    conn = get_connection()
    if conn:
        prods = pd.read_sql("SELECT * FROM produtos ORDER BY descricao", conn)
        conn.close()
        with st.form("f_sai", clear_on_submit=True):
            item = st.selectbox("Item", prods['codigo'] + " - " + prods['descricao']) if not prods.empty else "Nenhum"
            q = st.number_input("Qtd", min_value=0.01); ob = st.text_input("Destino")
            if st.form_submit_button("Confirmar"):
                conn = get_connection(); cur = conn.cursor()
                cur.execute("INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, referencia) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                           ("Saída", datetime.now().date(), ob, item.split(" - ")[0], item.split(" - ")[1], q, "Baixa"))
                conn.commit(); cur.close(); conn.close(); st.warning("Saída registrada!")

st.markdown(f'<div class="footer">Desenvolvido por Claudio Boni Junior</div>', unsafe_allow_html=True)

