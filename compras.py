import streamlit as st
import psycopg2
import pandas as pd
from datetime import datetime

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Gestão de Estoque", page_icon="🏗️", layout="wide")

# 2. ESTILO E LOGO
logo_url = "https://media.discordapp.net/attachments/1287152284328919116/1459226633025224879/Design-sem-nome-1.png?ex=69628234&is=696130b4&hm=460d0214e433068507b61d26f3ae1957e36d7a9480bf97e899ef3ae70303f294&=&format=webp&quality=lossless&width=600&height=158"

st.markdown("""
    <style>
    div[data-testid="metric-container"] { background-color: rgba(151, 166, 195, 0.15); padding: 20px; border-radius: 12px; }
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; text-align: center; font-size: 12px; color: #888; background: white; padding: 5px; }
    section[data-testid="stSidebar"] { background-color: #1e293b; }
    section[data-testid="stSidebar"] * { color: white !important; }
    </style>
    """, unsafe_allow_html=True)

# 3. FUNÇÕES DE BANCO E LOGIN
def get_connection():
    return psycopg2.connect(st.secrets["db_url"])

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

# 4. SIDEBAR PERSONALIZADA
with st.sidebar:
    st.image(logo_url, width=200)
    st.title("Gestão de Estoque - Grupo Amâncio")
    st.markdown("---")
    
    # Se não estiver logado, mostra opção de Login
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
        
        # Menu Público
        menu = st.radio("Navegação:", ["📊 Saldo de Estoque"])
    
    else:
        # Menu de Administrador (você logado)
        st.success(f"Logado como: {st.secrets['auth']['username']}")
        menu = st.radio("Navegação:", ["📊 Saldo de Estoque", "📦 Cadastro", "📥 Entrada", "📤 Saída"])
        if st.button("Sair (Logoff)"):
            st.session_state["authenticated"] = False
            st.rerun()

    st.markdown("---")
    st.caption("Versão 2.2 | SQL Online")

# 5. LÓGICA DAS ABAS
if menu == "📊 Saldo de Estoque":
    st.title("📊 Saldo Geral (Público)")
    try:
        conn = get_connection()
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
            st.info("Nenhum dado para exibir.")
    except:
        st.error("Erro na conexão com o banco.")

# AS ABAS ABAIXO SÓ EXISTEM NO MENU SE VOCÊ ESTIVER LOGADO
elif menu == "📦 Cadastro":
    st.title("📦 Cadastro de Materiais")
    with st.form("f_cad", clear_on_submit=True):
        c1, c2 = st.columns(2)
        cod = c1.text_input("Código")
        des = c2.text_input("Descrição")
        if st.form_submit_button("Salvar"):
            conn = get_connection(); cur = conn.cursor()
            cur.execute("INSERT INTO produtos (codigo, descricao) VALUES (%s, %s) ON CONFLICT (codigo) DO NOTHING", (cod, des))
            conn.commit(); cur.close(); conn.close()
            st.success("Cadastrado!")

elif menu == "📥 Entrada":
    st.title("📥 Entrada de Material")
    conn = get_connection()
    prods = pd.read_sql("SELECT * FROM produtos ORDER BY descricao", conn)
    conn.close()
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

elif menu == "📤 Saída":
    st.title("📤 Saída de Material")
    conn = get_connection()
    prods = pd.read_sql("SELECT * FROM produtos ORDER BY descricao", conn)
    conn.close()
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

# RODAPÉ
st.markdown('<div class="footer">Desenvolvido por Claudio Boni Junior</div>', unsafe_allow_html=True)

