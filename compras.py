import streamlit as st
import psycopg2
import pandas as pd
import plotly.express as px
from datetime import datetime
import time

# ==============================================================================
# 1. DESIGN & RESPONSIVIDADE (DARK/LIGHT MODE ADAPTIVE)
# ==============================================================================
st.set_page_config(page_title="Portal Amâncio | SCM", page_icon="🏗️", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    /* Cartões de KPI Modernos */
    div[data-testid="metric-container"] {
        background-color: var(--secondary-background-color);
        border: 1px solid rgba(128, 128, 128, 0.2);
        padding: 20px; border-radius: 15px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    
    /* Tabelas */
    .stDataFrame { border: 1px solid rgba(128, 128, 128, 0.1); border-radius: 10px; }

    /* Rodapé */
    .footer {
        position: fixed; left: 0; bottom: 0; width: 100%;
        background-color: var(--secondary-background-color);
        color: var(--text-color); text-align: center;
        padding: 5px; font-size: 0.7rem; z-index: 999;
        border-top: 1px solid rgba(128, 128, 128, 0.1);
    }
    
    /* Estilo de Login */
    .login-box {
        padding: 2rem; border-radius: 15px;
        background-color: var(--secondary-background-color);
        border: 1px solid rgba(128, 128, 128, 0.2);
    }

    @media (max-width: 640px) { .block-container { padding: 1rem !important; } }
    </style>
    <div class="footer">AMÂNCIO GESTÃO INTELIGENTE &copy; 2026 • v4.0 PROFESSIONAL</div>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. CORE DE DADOS
# ==============================================================================
def get_conn():
    return psycopg2.connect(st.secrets["db_url"])

def execute_sql(query, params=None):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                conn.commit()
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro SQL: {e}")
        return False

@st.cache_data(ttl=30)
def load_data(query):
    try:
        with get_conn() as conn:
            return pd.read_sql(query, conn)
    except: return pd.DataFrame()

def processar_estoque():
    df_p = load_data("SELECT * FROM produtos")
    df_m = load_data("SELECT * FROM movimentacoes")
    if df_p.empty: return pd.DataFrame()
    
    if not df_m.empty:
        # Garante tipos numéricos
        df_m['quantidade'] = pd.to_numeric(df_m['quantidade'], errors='coerce').fillna(0)
        df_m['custo_unitario'] = pd.to_numeric(df_m['custo_unitario'], errors='coerce').fillna(0)
        
        df_m['fator'] = df_m['tipo'].apply(lambda x: 1 if x in ['Entrada', 'Ajuste(+)'] else -1)
        df_m['qtd_final'] = df_m['quantidade'] * df_m['fator']
        
        # Saldo e Custo Médio
        saldos = df_m.groupby('codigo')['qtd_final'].sum().reset_index()
        entradas = df_m[df_m['tipo'] == 'Entrada']
        custos = entradas.groupby('codigo')['custo_unitario'].mean().reset_index()
        
        df_p = pd.merge(df_p, saldos, on='codigo', how='left')
        df_p = pd.merge(df_p, custos, on='codigo', how='left')
    else:
        df_p['qtd_final'] = 0.0
        df_p['custo_unitario'] = 0.0

    df_p = df_p.fillna(0)
    df_p['valor_total'] = df_p['qtd_final'] * df_p['custo_unitario']
    df_p['Status'] = df_p['qtd_final'].apply(lambda x: "🔴 Zerado" if x <= 0 else ("🟡 Baixo" if x < 10 else "🟢 OK"))
    return df_p

# ==============================================================================
# 3. INTERFACE & LOGICA DE CARRINHO
# ==============================================================================
if "carrinho" not in st.session_state: st.session_state.carrinho = []
if "auth" not in st.session_state: st.session_state.auth = False

df_estoque = processar_estoque()

# --- TELA INICIAL (ENGENHEIROS / PÚBLICO) ---
if not st.session_state.auth:
    col_l, col_r = st.columns([2, 1])
    with col_l:
        st.title("🏗️ Portal Amâncio - Estoque Central")
        busca = st.text_input("🔍 Consultar Material (Engenheiros):", placeholder="Ex: Cimento, Tubo, Cabo...")
        
        df_pub = df_estoque.copy()
        if busca:
            df_pub = df_pub[df_pub['descricao'].str.contains(busca, case=False) | df_pub['codigo'].str.contains(busca, case=False)]
        
        st.dataframe(df_pub[['codigo', 'descricao', 'categoria', 'unidade', 'qtd_final', 'Status']], 
                     use_container_width=True, hide_index=True)
    
    with col_r:
        st.markdown('<div class="login-box">', unsafe_allow_html=True)
        st.subheader("🔐 Acesso Administrativo")
        u = st.text_input("ID")
        p = st.text_input("Senha", type="password")
        if st.button("ACESSAR SISTEMA", use_container_width=True, type="primary"):
            if u == st.secrets["auth"]["username"] and p == st.secrets["auth"]["password"]:
                st.session_state.auth = True
                st.rerun()
            else: st.error("Incorreto")
        st.markdown('</div>', unsafe_allow_html=True)

# --- SISTEMA ADMINISTRATIVO ---
else:
    with st.sidebar:
        st.title("Amâncio ADM")
        menu = st.radio("Menu", ["📊 Dashboard BI", "📦 Inventário", "🔄 Operações (Carrinho)", "⚙️ Cadastros"])
        if st.button("Sair"):
            st.session_state.auth = False
            st.rerun()

    # --- DASHBOARD / BI ---
    if menu == "📊 Dashboard BI":
        st.header("📊 Inteligência de Negócio")
        if not df_estoque.empty:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Itens Ativos", len(df_estoque))
            c2.metric("Valor em Estoque", f"R$ {df_estoque['valor_total'].sum():,.2f}")
            c3.metric("Rupturas", len(df_estoque[df_estoque['qtd_final'] <= 0]))
            c4.metric("Status", "ONLINE", delta="Sincronizado")
            
            st.divider()
            g1, g2 = st.columns(2)
            with g1:
                fig1 = px.pie(df_estoque, names='categoria', values='valor_total', title="Investimento por Categoria", hole=0.5, template="plotly_dark")
                st.plotly_chart(fig1, use_container_width=True)
            with g2:
                fig2 = px.bar(df_estoque.nlargest(10, 'valor_total'), x='descricao', y='valor_total', title="Top 10 Itens (R$)", template="plotly_dark")
                st.plotly_chart(fig2, use_container_width=True)

    # --- INVENTÁRIO ---
    elif menu == "📦 Inventário":
        st.header("📦 Controle de Saldo")
        cat_filter = st.multiselect("Filtrar Categorias", df_estoque['categoria'].unique())
        df_inv = df_estoque.copy()
        if cat_filter: df_inv = df_inv[df_inv['categoria'].isin(cat_filter)]
        st.dataframe(df_inv, use_container_width=True, hide_index=True)

    # --- OPERAÇÕES (CARRINHO MULTI-ITENS) ---
    elif menu == "🔄 Operações (Carrinho)":
        st.header("🔄 Movimentação em Lote")
        tipo_op = st.radio("Tipo de Operação", ["Entrada (NF)", "Saída (Obra)", "Ajuste de Estoque"], horizontal=True)
        
        with st.expander("➕ Adicionar Item ao Lote", expanded=True):
            col_a, col_b, col_c = st.columns([2, 1, 1])
            prod_sel = col_a.selectbox("Produto", [f"{r['codigo']} | {r['descricao']}" for i,r in df_estoque.iterrows()])
            qtd_op = col_b.number_input("Quantidade", min_value=0.0, step=1.0)
            v_unit = col_c.number_input("Valor Unit. (R$)", min_value=0.0) if tipo_op == "Entrada (NF)" else 0.0
            
            if st.button("Incluir no Carrinho"):
                st.session_state.carrinho.append({
                    "codigo": prod_sel.split(" | ")[0],
                    "descricao": prod_sel.split(" | ")[1],
                    "quantidade": qtd_op,
                    "valor": v_unit,
                    "total": qtd_op * v_unit
                })

        if st.session_state.carrinho:
            st.subheader("🛒 Itens Prontos para Processar")
            df_cart = pd.DataFrame(st.session_state.carrinho)
            st.table(df_cart)
            
            col_ref, col_btn = st.columns([2, 1])
            ref_final = col_ref.text_input("NF Fornecedor ou Nome da Obra:")
            
            if col_btn.button("✅ FINALIZAR TUDO", type="primary", use_container_width=True):
                if ref_final:
                    for item in st.session_state.carrinho:
                        tipo_db = "Entrada" if tipo_op == "Entrada (NF)" else ("Saída" if tipo_op == "Saída (Obra)" else "Ajuste(+)")
                        execute_sql("INSERT INTO movimentacoes (tipo, data, codigo, descricao, quantidade, custo_unitario, referencia) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                                   (tipo_db, datetime.now().date(), item['codigo'], item['descricao'], item['quantidade'], item['valor'], ref_final))
                    st.session_state.carrinho = []
                    st.success("Movimentação registrada!")
                    time.sleep(1)
                    st.rerun()
                else: st.warning("Informe a Referência (NF/Obra)")
            
            if st.button("Limpar Carrinho"): 
                st.session_state.carrinho = []
                st.rerun()

    # --- CADASTROS ---
    elif menu == "⚙️ Cadastros":
        tab1, tab2 = st.tabs(["Produtos", "Categorias"])
        with tab1:
            with st.form("f_prod"):
                c1, c2 = st.columns(2)
                cod = c1.text_input("Código").upper()
                des = c2.text_input("Descrição")
                cat = st.selectbox("Categoria", load_data("SELECT nome FROM categorias")['nome'].tolist())
                uni = st.selectbox("Unid", ["UNID", "KG", "M", "M3", "SC"])
                if st.form_submit_button("Salvar"):
                    execute_sql("INSERT INTO produtos (codigo, descricao, categoria, unidade) VALUES (%s,%s,%s,%s)", (cod, des, cat, uni))
                    st.rerun()
        with tab2:
            with st.form("f_cat"):
                n_cat = st.text_input("Nova Categoria")
                if st.form_submit_button("Cadastrar"):
                    execute_sql("INSERT INTO categorias (nome) VALUES (%s)", (n_cat.title(),))
                    st.rerun()
