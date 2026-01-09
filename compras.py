import streamlit as st
import psycopg2
import pandas as pd
from datetime import datetime

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Controle de Estoque Amâncio", page_icon="", layout="wide")

# 2. PERSONALIZAÇÃO DE LOGO E CORES
# COLOQUE O LINK DA SUA LOGO ABAIXO
logo_url = "https://github.com/claudiobonijr/estoque/blob/b844f6b03200868a1dfe94a1e0056c0f333c4f06/logo.png" 

st.markdown("""
    <style>
    [data-testid="stSidebar"] { background-color: #1e293b; color: white; }
    [data-testid="stSidebar"] * { color: white !important; }
    .stButton>button { border-radius: 8px; height: 3em; background-color: #3b82f6; color: white; font-weight: bold; border: none; }
    .stButton>button:hover { background-color: #2563eb; border: none; }
    .metric-card { background-color: #ffffff; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); border: 1px solid #e2e8f0; }
    </style>
    """, unsafe_allow_html=True)

# 3. FUNÇÕES DE BANCO DE DADOS
def get_connection():
    return psycopg2.connect(st.secrets["db_url"])

# 4. SIDEBAR COM SUA LOGO
with st.sidebar:
    st.image(logo_url, width=120)
    st.title("Gestão de Obras")
    st.markdown("---")
    menu = st.radio("Navegação Principal", ["📊 Painel de Controle", "📦 Cadastro de Insumos", "📥 Registrar Entrada", "📤 Registrar Saída"])
    st.markdown("---")
    st.caption("Versão 2.0 - Banco SQL")

# 5. LÓGICA DO SISTEMA
if menu == "📊 Painel de Controle":
    st.title("📊 Painel de Controle")
    
    try:
        conn = get_connection()
        df_mov = pd.read_sql("SELECT * FROM movimentacoes", conn)
        conn.close()

        if not df_mov.empty:
            # Cálculos de Saldo
            df_mov['val'] = df_mov.apply(lambda x: x['quantidade'] if x['tipo'] == 'Entrada' else -x['quantidade'], axis=1)
            resumo = df_mov.groupby(['codigo', 'descricao'])['val'].sum().reset_index()
            resumo.columns = ['Cód', 'Descrição', 'Saldo Atual']

            # Exibição de Métricas em Cards
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown(f'<div class="metric-card"><h3>📦 Itens</h3><h2>{len(resumo)}</h2></div>', unsafe_allow_html=True)
            with c2:
                total_mov = len(df_mov)
                st.markdown(f'<div class="metric-card"><h3>🔄 Movimentações</h3><h2>{total_mov}</h2></div>', unsafe_allow_html=True)
            with c3:
                baixo_estoque = len(resumo[resumo['Saldo Atual'] < 5])
                st.markdown(f'<div class="metric-card"><h3>⚠️ Alerta Crítico</h3><h2>{baixo_estoque}</h2></div>', unsafe_allow_html=True)

            st.markdown("### Detalhamento do Inventário")
            st.dataframe(resumo, use_container_width=True, hide_index=True)
        else:
            st.info("O estoque está vazio. Comece cadastrando produtos e registrando entradas.")
    except:
        st.error("Erro ao carregar dados. Verifique a conexão.")

elif menu == "📦 Cadastro de Insumos":
    st.title("📦 Cadastro de Insumos")
    col1, col2 = st.columns([1, 1])
    
    with col1:
        with st.form("cad", clear_on_submit=True):
            st.subheader("Novo Produto")
            c_cod = st.text_input("Código Único")
            c_des = st.text_input("Descrição do Material")
            if st.form_submit_button("Finalizar Cadastro"):
                if c_cod and c_des:
                    conn = get_connection()
                    cur = conn.cursor()
                    cur.execute("INSERT INTO produtos (codigo, descricao) VALUES (%s, %s) ON CONFLICT (codigo) DO NOTHING", (c_cod, c_des))
                    conn.commit()
                    cur.close()
                    conn.close()
                    st.success("Produto cadastrado!")
                else:
                    st.warning("Preencha todos os campos.")

elif menu == "📥 Registrar Entrada":
    st.title("📥 Registro de Entrada")
    conn = get_connection()
    prods = pd.read_sql("SELECT * FROM produtos ORDER BY descricao", conn)
    conn.close()

    if not prods.empty:
        with st.container():
            with st.form("ent", clear_on_submit=True):
                col1, col2 = st.columns(2)
                item = col1.selectbox("Selecione o Insumo", prods['codigo'] + " - " + prods['descricao'])
                qtd = col1.number_input("Quantidade", min_value=0.01)
                obra = col2.text_input("Obra Destino")
                ref = col2.text_input("NF ou Ordem de Compra")
                
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
        st.warning("Cadastre produtos antes de registrar movimentações.")

elif menu == "📤 Registrar Saída":
    st.title("📤 Registrar Saída")
    # Mesma lógica da entrada, apenas mudando o tipo para "Saída"
    # Adicionado campo de responsável ou destino específico
    conn = get_connection()
    prods = pd.read_sql("SELECT * FROM produtos ORDER BY descricao", conn)
    conn.close()

    if not prods.empty:
        with st.form("sai", clear_on_submit=True):
            col1, col2 = st.columns(2)
            item = col1.selectbox("Item Saindo", prods['codigo'] + " - " + prods['descricao'])
            qtd = col1.number_input("Qtd aplicada", min_value=0.01)
            obra = col2.text_input("Frente de Serviço")
            resp = col2.text_input("Encarregado/Responsável")
            
            if st.form_submit_button("Baixar Estoque"):
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, referencia) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                           ("Saída", datetime.now().date(), obra, item.split(" - ")[0], item.split(" - ")[1], qtd, f"Resp: {resp}"))
                conn.commit()
                cur.close()
                conn.close()
                st.info("Saída registrada com sucesso!")

