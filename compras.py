import streamlit as st
import psycopg2
import pandas as pd
from datetime import datetime
import plotly.express as px

# --- CONFIGURAÇÃO DE TEMA ADAPTATIVO ---
st.markdown("""
    <style>
    /* 1. VARIÁVEIS DE CORES (Mudam conforme o tema) */
    :root {
        --bg-color: #ffffff;
        --text-color: #1e293b;
        --card-bg: rgba(0, 0, 0, 0.05);
        --border-color: rgba(0, 0, 0, 0.1);
        --accent-color: #2563eb;
    }

    @media (prefers-color-scheme: dark) {
        :root {
            --bg-color: #0e1117;
            --text-color: #f8fafc;
            --card-bg: rgba(255, 255, 255, 0.05);
            --border-color: rgba(255, 255, 255, 0.1);
            --accent-color: #38bdf8;
        }
    }

    /* 2. APLICAÇÃO NAS MÉTRICAS */
    div[data-testid="metric-container"] {
        background-color: var(--card-bg) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 12px;
        padding: 15px;
    }

    /* 3. TEXTOS ADAPTATIVOS */
    [data-testid="stMetricValue"], [data-testid="stMetricLabel"], h1, h2, h3, p {
        color: var(--text-color) !important;
    }

    /* 4. SIDEBAR RESPONSIVA */
    section[data-testid="stSidebar"] {
        border-right: 1px solid var(--border-color);
    }
    
    /* 5. TABELAS (Dataframes) */
    .stDataFrame {
        border: 1px solid var(--border-color);
        border-radius: 8px;
    }
    </style>
    """, unsafe_allow_html=True)

# 2. FUNÇÕES DE BANCO DE DADOS
def get_connection():
    try:
        return psycopg2.connect(st.secrets["db_url"])
    except Exception as e:
        st.error(f"Erro de Conexão: {e}")
        return None

# 3. CONTROLE DE ACESSO
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

# 4. SIDEBAR (Menu lateral)
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/1063/1063196.png", width=80)
    st.title("Amâncio Obras")
    st.markdown("---")
    
    if not st.session_state["authenticated"]:
        with st.expander("🔐 Acesso Administrador"):
            u = st.text_input("Usuário")
            p = st.text_input("Senha", type="password")
            if st.button("Entrar"):
                if u == st.secrets["auth"]["username"] and p == st.secrets["auth"]["password"]:
                    st.session_state["authenticated"] = True
                    st.rerun()
        menu = st.radio("Navegação:", ["📊 Dashboard Público"])
    else:
        st.success(f"Logado: {st.secrets['auth']['username']}")
        menu = st.radio("Navegação:", ["📊 Dashboard Público", "📋 Inventário Detalhado", "📦 Cadastro", "📥 Entrada", "📤 Saída", "🔧 Ajuste"])
        if st.button("Sair (Logoff)"):
            st.session_state["authenticated"] = False
            st.rerun()

# 5. LOGICA DAS TELAS
conn = get_connection()

if menu == "📊 Dashboard Público":
    st.title("📊 Painel de Controle de Estoque")
    if conn:
        df_mov = pd.read_sql("SELECT * FROM movimentacoes", conn)
        if not df_mov.empty:
            df_mov['val'] = df_mov.apply(lambda x: x['quantidade'] if x['tipo'] in ['Entrada', 'Ajuste(+)'] else -x['quantidade'], axis=1)
            saldo = df_mov.groupby(['codigo', 'descricao'])['val'].sum().reset_index()
            saldo.columns = ['Cód', 'Descrição', 'Saldo']

            # Métricas em Cards
            c1, c2, c3 = st.columns(3)
            c1.metric("Itens Cadastrados", len(saldo))
            c2.metric("Movimentações", len(df_mov))
            critico = len(saldo[saldo['Saldo'] < 10])
            c3.metric("Itens em Alerta", critico, delta="- Atenção", delta_color="inverse")

            # Gráfico de Consumo (Plotly)
            st.markdown("### 📈 Materiais mais Retirados")
            saidas = df_mov[df_mov['tipo'] == 'Saída'].groupby('descricao')['quantidade'].sum().reset_index().sort_values(by='quantidade', ascending=False).head(5)
            fig = px.bar(saidas, x='descricao', y='quantidade', color='quantidade', color_continuous_scale='Blues', template='plotly_dark')
            st.plotly_chart(fig, use_container_width=True)

            # Tabela com Pesquisa
            st.markdown("### 🔍 Consulta de Saldo")
            busca = st.text_input("Digite o nome do material para pesquisar:")
            if busca:
                saldo = saldo[saldo['Descrição'].str.contains(busca, case=False)]
            st.dataframe(saldo, use_container_width=True, hide_index=True)
        else:
            st.info("Sem dados para exibir.")

elif menu == "📋 Inventário Detalhado":
    st.title("📋 Inventário e Auditoria")
    df_mov = pd.read_sql("SELECT * FROM movimentacoes ORDER BY data DESC", conn)
    st.dataframe(df_mov, use_container_width=True)
    csv = df_mov.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Baixar Planilha Completa (Excel/CSV)", csv, "estoque_amancio.csv")

elif menu == "📦 Cadastro":
    st.title("📦 Cadastro de Novos Itens")
    with st.form("cad"):
        c1, c2 = st.columns(2)
        cod = c1.text_input("Código do Material")
        des = c2.text_input("Descrição (Nome)")
        if st.form_submit_button("Salvar Material"):
            cur = conn.cursor()
            cur.execute("INSERT INTO produtos (codigo, descricao) VALUES (%s, %s) ON CONFLICT DO NOTHING", (cod.upper(), des.upper()))
            conn.commit(); st.success("Cadastrado!")

elif menu == "📥 Entrada":
    st.title("📥 Registro de Entrada")
    prods = pd.read_sql("SELECT * FROM produtos ORDER BY descricao", conn)
    with st.form("ent"):
        item = st.selectbox("Material", prods['codigo'] + " - " + prods['descricao'])
        qtd = st.number_input("Qtd Recebida", min_value=0.1)
        obra = st.text_input("Obra/Destino")
        ref = st.text_input("NF / Fornecedor")
        if st.form_submit_button("Confirmar Recebimento"):
            cur = conn.cursor()
            cur.execute("INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, referencia) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                       ("Entrada", datetime.now().date(), obra, item.split(" - ")[0], item.split(" - ")[1], qtd, ref))
            conn.commit(); st.success("Estoque Alimentado!")

elif menu == "📤 Saída":
    st.title("📤 Registro de Saída")
    prods = pd.read_sql("SELECT * FROM produtos ORDER BY descricao", conn)
    with st.form("sai"):
        item = st.selectbox("Material Retirado", prods['codigo'] + " - " + prods['descricao'])
        qtd = st.number_input("Qtd Retirada", min_value=0.1)
        resp = st.text_input("Responsável pela Retirada")
        obra = st.text_input("Obra de Destino")
        if st.form_submit_button("Confirmar Baixa"):
            cur = conn.cursor()
            cur.execute("INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, referencia) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                       ("Saída", datetime.now().date(), obra, item.split(" - ")[0], item.split(" - ")[1], qtd, f"Resp: {resp}"))
            conn.commit(); st.warning("Saída Registrada!")

elif menu == "🔧 Ajuste":
    st.title("🔧 Ajuste Manual de Estoque")
    prods = pd.read_sql("SELECT * FROM produtos", conn)
    item = st.selectbox("Item para Ajustar", prods['codigo'] + " - " + prods['descricao'])
    novo_valor = st.number_input("Nova Quantidade Real", min_value=0.0)
    if st.button("Atualizar Saldo"):
        st.info("Ajuste realizado no sistema.") # Adicionar lógica de insert ajuste aqui

if conn: conn.close()
st.markdown('<div class="footer">© 2026 Amâncio Gestão de Obras - Claudio Boni Junior</div>', unsafe_allow_html=True)

