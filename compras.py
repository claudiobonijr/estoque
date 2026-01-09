import streamlit as st
import psycopg2
import pandas as pd
from datetime import datetime

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Gestão de Estoque Pro", page_icon="🏗️", layout="wide")

# 2. LOGO E PERSONALIZAÇÃO VISUAL
# Para trocar a logo, substitua o link abaixo pelo link da sua imagem
logo_url = "https://cdn-icons-png.flaticon.com/512/4222/4222961.png"

st.markdown("""
    <style>
    /* Estilização dos cards de métricas */
    div[data-testid="metric-container"] {
        background-color: rgba(151, 166, 195, 0.15);
        padding: 20px;
        border-radius: 12px;
        border: 1px solid rgba(151, 166, 195, 0.2);
    }
    /* Títulos das métricas */
    [data-testid="stMetricLabel"] {
        font-size: 1.1rem !important;
        font-weight: 600 !important;
    }
    /* Estilo do menu lateral */
    section[data-testid="stSidebar"] {
        background-color: #1e293b;
    }
    section[data-testid="stSidebar"] * {
        color: white !important;
    }
    /* Botões personalizados */
    .stButton>button {
        border-radius: 8px;
        background-color: #3b82f6;
        color: white;
        font-weight: bold;
        border: none;
        transition: 0.3s;
    }
    .stButton>button:hover {
        background-color: #2563eb;
        transform: translateY(-1px);
    }
    </style>
    """, unsafe_allow_html=True)

# 3. FUNÇÃO DE CONEXÃO COM O BANCO (RENDER)
def get_connection():
    return psycopg2.connect(st.secrets["db_url"])

# 4. SIDEBAR (MENU LATERAL)
with st.sidebar:
    st.image(logo_url, width=110)
    st.title("Sistema de Obras")
    st.markdown("---")
    menu = st.radio("Selecione uma Opção:", 
                    ["📊 Dashboard", "📦 Cadastro", "📥 Entrada", "📤 Saída"])
    st.markdown("---")
    st.caption("Versão 2.1 | Banco SQL Online")

# 5. LÓGICA DO DASHBOARD
if menu == "📊 Dashboard":
    st.title("📊 Painel de Controle")
    
    try:
        conn = get_connection()
        df_mov = pd.read_sql("SELECT * FROM movimentacoes", conn)
        conn.close()

        if not df_mov.empty:
            # Cálculo do Saldo Real
            df_mov['val_ajustada'] = df_mov.apply(lambda x: x['quantidade'] if x['tipo'] == 'Entrada' else -x['quantidade'], axis=1)
            saldo_df = df_mov.groupby(['codigo', 'descricao'])['val_ajustada'].sum().reset_index()
            saldo_df.columns = ['Cód', 'Descrição', 'Saldo Atual']

            # LINHA DE MÉTRICAS
            col1, col2, col3 = st.columns(3)
            col1.metric("Itens Cadastrados", len(saldo_df))
            col2.metric("Total de Movimentações", len(df_mov))
            col3.metric("Estoque Baixo (< 5)", len(saldo_df[saldo_df['Saldo Atual'] < 5]))

            st.markdown("---")
            st.subheader("📋 Inventário Detalhado")
            st.dataframe(saldo_df, use_container_width=True, hide_index=True)
            
        else:
            st.info("Nenhuma movimentação registrada no banco de dados.")
    except Exception as e:
        st.error(f"Erro ao conectar ao banco de dados: {e}")

# 6. LÓGICA DE CADASTRO
elif menu == "📦 Cadastro":
    st.title("📦 Cadastro de Materiais")
    with st.container():
        with st.form("form_cad", clear_on_submit=True):
            st.subheader("Informações do Insumo")
            col1, col2 = st.columns(2)
            c_cod = col1.text_input("Código do Material (Ex: 001)")
            c_des = col2.text_input("Descrição (Ex: Cimento CP-II)")
            
            if st.form_submit_button("Registrar no Banco"):
                if c_cod and c_des:
                    conn = get_connection()
                    cur = conn.cursor()
                    cur.execute("INSERT INTO produtos (codigo, descricao) VALUES (%s, %s) ON CONFLICT (codigo) DO NOTHING", (c_cod, c_des))
                    conn.commit()
                    cur.close()
                    conn.close()
                    st.success(f"O item '{c_des}' foi salvo com sucesso!")
                else:
                    st.warning("Preencha todos os campos obrigatórios.")

# 7. LÓGICA DE ENTRADA
elif menu == "📥 Entrada":
    st.title("📥 Registrar Entrada de Material")
    conn = get_connection()
    df_p = pd.read_sql("SELECT * FROM produtos ORDER BY descricao", conn)
    conn.close()

    if not df_p.empty:
        with st.form("form_ent", clear_on_submit=True):
            item = st.selectbox("Selecione o Insumo", df_p['codigo'] + " - " + df_p['descricao'])
            col1, col2 = st.columns(2)
            qtd = col1.number_input("Quantidade", min_value=0.01)
            obra = col1.text_input("Obra de Destino")
            ref = col2.text_input("Nº da Nota Fiscal / OC")
            
            if st.form_submit_button("Confirmar Entrada"):
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, referencia) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                           ("Entrada", datetime.now().date(), obra, item.split(" - ")[0], item.split(" - ")[1], qtd, ref))
                conn.commit()
                cur.close()
                conn.close()
                st.success("Estoque atualizado!")
    else:
        st.error("Nenhum produto cadastrado no sistema.")

# 8. LÓGICA DE SAÍDA
elif menu == "📤 Saída":
    st.title("📤 Registrar Saída / Aplicação")
    conn = get_connection()
    df_p = pd.read_sql("SELECT * FROM produtos ORDER BY descricao", conn)
    conn.close()

    if not df_p.empty:
        with st.form("form_sai", clear_on_submit=True):
            item = st.selectbox("Insumo Aplicado", df_p['codigo'] + " - " + df_p['descricao'])
            col1, col2 = st.columns(2)
            qtd = col1.number_input("Quantidade Utilizada", min_value=0.01)
            obra = col2.text_input("Frente de Serviço / Obra")
            resp = col2.text_input("Responsável pela Retirada")
            
            if st.form_submit_button("Dar Baixa no Estoque"):
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, referencia) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                           ("Saída", datetime.now().date(), obra, item.split(" - ")[0], item.split(" - ")[1], qtd, f"Resp: {resp}"))
                conn.commit()
                cur.close()
                conn.close()
                st.info("Saída registrada!")
    else:
        st.warning("Cadastre produtos para habilitar a saída.")
