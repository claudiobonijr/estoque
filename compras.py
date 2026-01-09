import streamlit as st
import psycopg2
import pandas as pd
from datetime import datetime
import plotly.express as px

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Amâncio Gestão Pro", page_icon="🏗️", layout="wide")

# 2. CSS RESPONSIVO E ADAPTATIVO (AUTO LIGHT/DARK)
st.markdown("""
    <style>
    /* Variáveis de Cores Adaptativas */
    :root {
        --primary-bg: #ffffff;
        --secondary-bg: #f8fafc;
        --text-main: #1e293b;
        --card-bg: #ffffff;
        --border-color: #e2e8f0;
        --accent: #2563eb;
    }

    @media (prefers-color-scheme: dark) {
        :root {
            --primary-bg: #0e1117;
            --secondary-bg: #161b22;
            --text-main: #f0f6fc;
            --card-bg: #161b22;
            --border-color: #30363d;
            --accent: #58a6ff;
        }
    }

    /* Aplicação dos Estilos */
    .stApp { background-color: var(--primary-bg); }
    
    div[data-testid="metric-container"] {
        background-color: var(--secondary-bg);
        border: 1px solid var(--border-color);
        padding: 20px;
        border-radius: 12px;
    }

    h1, h2, h3, p, span, label { color: var(--text-main) !important; }

    .footer { 
        position: fixed; left: 0; bottom: 0; width: 100%; 
        text-align: center; padding: 10px; font-size: 12px; 
        color: #8b949e; background: var(--secondary-bg); 
        border-top: 1px solid var(--border-color); z-index: 100;
    }
    
    /* Botão mais largo e visível no mobile */
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        height: 3.5em;
        background: var(--accent);
        color: white !important;
        font-weight: bold;
        border: none;
    }
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
        menu = st.radio("Navegação:", ["📊 Dashboard Público", "📋 Inventário Geral", "📥 Registrar Entrada", "📤 Registrar Saída", "📦 Cadastrar Material", "🔧 Ajuste"])
        if st.button("Sair"):
            st.session_state["authenticated"] = False
            st.rerun()

# 5. LÓGICA DAS TELAS
conn = get_connection()

if menu == "📊 Dashboard Público":
    st.title("📊 Status do Estoque")
    if conn:
        df_mov = pd.read_sql("SELECT * FROM movimentacoes", conn)
        if not df_mov.empty:
            df_mov['val'] = df_mov.apply(lambda x: x['quantidade'] if x['tipo'] in ['Entrada', 'Ajuste(+)'] else -x['quantidade'], axis=1)
            saldo = df_mov.groupby(['codigo', 'descricao'])['val'].sum().reset_index()
            saldo.columns = ['Cód', 'Descrição', 'Saldo']

            # Gráfico de Consumo
            saidas = df_mov[df_mov['tipo'] == 'Saída'].groupby('descricao')['quantidade'].sum().reset_index().sort_values(by='quantidade', ascending=False).head(5)
            fig = px.bar(saidas, x='descricao', y='quantidade', title="Top 5 Materiais Mais Usados", template="plotly_white" if st.get_option("theme.base") == "light" else "plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

            busca = st.text_input("🔍 Pesquisar material:")
            if busca:
                saldo = saldo[saldo['Descrição'].str.contains(busca, case=False)]
            st.dataframe(saldo, use_container_width=True, hide_index=True)

# --- TELAS DETALHADAS (SOMENTE LOGADO) ---
elif menu == "📥 Registrar Entrada":
    st.title("📥 Entrada de Material (Detalhada)")
    prods = pd.read_sql("SELECT * FROM produtos ORDER BY descricao", conn)
    
    with st.form("entrada_full", clear_on_submit=True):
        col1, col2 = st.columns(2)
        item = col1.selectbox("Selecione o Material", prods['codigo'] + " - " + prods['descricao'])
        qtd = col2.number_input("Quantidade Recebida", min_value=0.01)
        
        col3, col4 = st.columns(2)
        nf = col3.text_input("Nota Fiscal (Número)")
        forn = col4.text_input("Fornecedor / Loja")
        
        obra = st.text_input("Obra de Destino")
        obs = st.text_area("Observações (Ex: Estado do material, marca...)")
        data_e = st.date_input("Data", datetime.now())

        if st.form_submit_button("✅ SALVAR ENTRADA NO BANCO"):
            cur = conn.cursor()
            ref = f"NF: {nf} | Forn: {forn} | Obs: {obs}"
            cur.execute("INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, referencia) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                       ("Entrada", data_e, obra, item.split(" - ")[0], item.split(" - ")[1], qtd, ref))
            conn.commit(); st.success("Entrada registrada com sucesso!")

elif menu == "📤 Registrar Saída":
    st.title("📤 Saída de Material (Rastreável)")
    prods = pd.read_sql("SELECT * FROM produtos ORDER BY descricao", conn)
    
    with st.form("saida_full", clear_on_submit=True):
        col1, col2 = st.columns(2)
        item = col1.selectbox("Material Retirado", prods['codigo'] + " - " + prods['descricao'])
        qtd = col2.number_input("Quantidade Saindo", min_value=0.01)
        
        col3, col4 = st.columns(2)
        resp = col3.text_input("Quem retirou? (Responsável)")
        dest = col4.text_input("Frente de Serviço / Destino")
        
        obs_s = st.text_area("Motivo ou Notas Adicionais")
        data_s = st.date_input("Data", datetime.now())

        if st.form_submit_button("🚨 CONFIRMAR BAIXA DE ESTOQUE"):
            cur = conn.cursor()
            ref = f"Resp: {resp} | Dest: {dest} | Notas: {obs_s}"
            cur.execute("INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, referencia) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                       ("Saída", data_s, "Estoque Central", item.split(" - ")[0], item.split(" - ")[1], qtd, ref))
            conn.commit(); st.warning("Baixa de material concluída!")

elif menu == "📋 Inventário Geral":
    st.title("📋 Inventário e Histórico")
    df_mov = pd.read_sql("SELECT * FROM movimentacoes ORDER BY data DESC", conn)
    st.dataframe(df_mov, use_container_width=True)

elif menu == "📦 Cadastrar Material":
    st.title("📦 Novo Cadastro")
    with st.form("cad_p"):
        c1, c2 = st.columns(2)
        cod = c1.text_input("Código")
        des = c2.text_input("Nome/Descrição")
        if st.form_submit_button("Salvar"):
            cur = conn.cursor()
            cur.execute("INSERT INTO produtos (codigo, descricao) VALUES (%s, %s) ON CONFLICT DO NOTHING", (cod.upper(), des.upper()))
            conn.commit(); st.success("Cadastrado!")

if conn: conn.close()
st.markdown('<div class="footer">Claudio Boni Junior - Gestão Inteligente de Obras</div>', unsafe_allow_html=True)
