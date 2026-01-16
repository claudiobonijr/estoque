import streamlit as st
import psycopg2
import pandas as pd
import plotly.express as px
from datetime import datetime
import time

# ==============================================================================
# 1. DESIGN SYSTEM & RESPONSIVIDADE (DARK MODE READY)
# ==============================================================================
st.set_page_config(page_title="Portal Amâncio | SCM", page_icon="🏗️", layout="wide")

st.markdown("""
    <style>
    /* Estilização Geral Adaptável */
    .main { background-color: transparent; }
    
    /* Cartões de KPI Estilo Glassmorphism */
    div[data-testid="metric-container"] {
        background-color: var(--secondary-background-color);
        border: 1px solid rgba(128, 128, 128, 0.2);
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    
    /* Tabelas e Dataframes */
    .stDataFrame { border-radius: 10px; overflow: hidden; }

    /* Ajustes Mobile */
    @media (max-width: 640px) {
        .block-container { padding: 1rem !important; }
        .stMetric { margin-bottom: 15px; }
    }
    
    .footer {
        position: fixed; left: 0; bottom: 0; width: 100%;
        background-color: var(--secondary-background-color);
        color: var(--text-color); text-align: center;
        padding: 5px; font-size: 0.7rem; z-index: 999;
        border-top: 1px solid rgba(128, 128, 128, 0.1);
    }
    </style>
    <div class="footer">AMÂNCIO GESTÃO INTELIGENTE &copy; 2026 • RESPONSIVE v3.0</div>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. ENGINE DE DADOS (POSTGRESQL)
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
        st.error(f"Erro na operação: {e}")
        return False

@st.cache_data(ttl=60)
def load_data(query):
    try:
        with get_conn() as conn:
            return pd.read_sql(query, conn)
    except: return pd.DataFrame()

def processar_estoque_full():
    df_p = load_data("SELECT * FROM produtos")
    df_m = load_data("SELECT * FROM movimentacoes")
    if df_p.empty: return pd.DataFrame()
    
    if not df_m.empty:
        df_m['fator'] = df_m['tipo'].apply(lambda x: 1 if x in ['Entrada', 'Ajuste(+)'] else -1)
        df_m['qtd_final'] = df_m['quantidade'] * df_m['fator']
        # Cálculo de custo médio simples para os gráficos
        entradas = df_m[df_m['tipo'] == 'Entrada']
        custos = entradas.groupby('codigo')['custo_unitario'].mean().reset_index()
        
        saldos = df_m.groupby('codigo')['qtd_final'].sum().reset_index()
        df_p = pd.merge(df_p, saldos, on='codigo', how='left')
        df_p = pd.merge(df_p, custos, on='codigo', how='left')
    else:
        df_p['qtd_final'] = 0.0
        df_p['custo_unitario'] = 0.0
        
    df_p = df_p.fillna(0)
    df_p['valor_total'] = df_p['qtd_final'] * df_p['custo_unitario']
    df_p['Status'] = df_p['qtd_final'].apply(lambda x: "🔴 Zerado" if x <= 0 else ("🟡 Baixo" if x < 5 else "🟢 OK"))
    return df_p

# ==============================================================================
# 3. INTERFACE DE NAVEGAÇÃO
# ==============================================================================
if "authenticated" not in st.session_state: st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.title("🏗️ Amâncio SCM")
        with st.form("login"):
            u = st.text_input("Usuário")
            p = st.text_input("Senha", type="password")
            if st.form_submit_button("Acessar", use_container_width=True):
                if u == st.secrets["auth"]["username"] and p == st.secrets["auth"]["password"]:
                    st.session_state["authenticated"] = True
                    st.rerun()
else:
    df_estoque = processar_estoque_full()
    df_cats = load_data("SELECT nome FROM categorias ORDER BY nome")
    
    menu = st.sidebar.radio("Navegação", ["📊 Dashboard", "📦 Inventário", "🔄 Movimentações", "⚙️ Configurações"])

    # --- 1. DASHBOARD INTELIGENTE ---
    if menu == "📊 Dashboard":
        st.title("📊 Painel de Controle")
        
        if not df_estoque.empty:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Itens no Estoque", len(df_estoque))
            c2.metric("Valor Total", f"R$ {df_estoque['valor_total'].sum():,.2f}")
            ruptura = len(df_estoque[df_estoque['qtd_final'] <= 0])
            c3.metric("Ruptura", ruptura, delta=f"{ruptura} itens zerados", delta_color="inverse")
            c4.metric("Categorias", len(df_cats))

            st.markdown("---")
            g1, g2 = st.columns(2)
            
            with g1:
                st.subheader("📦 Volume por Categoria")
                fig_cat = px.pie(df_estoque, names='categoria', values='qtd_final', hole=0.4, template="plotly_dark")
                fig_cat.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_cat, use_container_width=True)
                
            with g2:
                st.subheader("💰 Investimento por Categoria")
                df_val_cat = df_estoque.groupby('categoria')['valor_total'].sum().reset_index()
                fig_val = px.bar(df_val_cat, x='categoria', y='valor_total', color='categoria', template="plotly_dark")
                fig_val.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False)
                st.plotly_chart(fig_val, use_container_width=True)
        else:
            st.info("Aguardando dados para gerar gráficos.")

    # --- 2. INVENTÁRIO ---
    elif menu == "📦 Inventário":
        st.title("📦 Inventário Geral")
        filtro_cat = st.multiselect("Filtrar por Categoria", df_cats['nome'].tolist())
        
        df_view = df_estoque.copy()
        if filtro_cat:
            df_view = df_view[df_view['categoria'].isin(filtro_cat)]
            
        st.dataframe(
            df_view[['codigo', 'descricao', 'categoria', 'unidade', 'qtd_final', 'Status']],
            use_container_width=True, hide_index=True,
            column_config={
                "qtd_final": st.column_config.NumberColumn("Saldo Atual", format="%.2f"),
                "Status": st.column_config.TextColumn("Situação")
            }
        )

    # --- 3. MOVIMENTAÇÕES ---
    elif menu == "🔄 Movimentações":
        st.title("🔄 Registrar Movimento")
        with st.form("operacao"):
            col1, col2 = st.columns(2)
            tipo = col1.selectbox("Tipo", ["Entrada", "Saída", "Ajuste(+)"])
            if not df_estoque.empty:
                item = col2.selectbox("Produto", [f"{r['codigo']} | {r['descricao']}" for i,r in df_estoque.iterrows()])
            else:
                item = None
            
            qtd = st.number_input("Quantidade", min_value=0.01)
            custo = st.number_input("Custo Unitário (Apenas p/ Entradas)", min_value=0.0)
            ref = st.text_input("Referência (Nº Nota ou Nome da Obra)")
            
            if st.form_submit_button("Confirmar Lançamento", use_container_width=True):
                if item:
                    cod_sel = item.split(" | ")[0]
                    desc_sel = item.split(" | ")[1]
                    execute_sql("INSERT INTO movimentacoes (tipo, data, codigo, descricao, quantidade, custo_unitario, referencia) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                               (tipo, datetime.now().date(), cod_sel, desc_sel, qtd, custo, ref))
                    st.success("Lançamento realizado com sucesso!")
                    time.sleep(1)
                    st.rerun()

    # --- 4. CONFIGURAÇÕES (CADASTROS) ---
    elif menu == "⚙️ Configurações":
        st.title("⚙️ Gerenciamento do Sistema")
        
        t1, t2 = st.tabs(["✨ Cadastrar Produto", "📂 Gerenciar Categorias"])
        
        with t1:
            with st.form("novo_prod"):
                c1, c2 = st.columns(2)
                ncod = c1.text_input("Código do Produto").upper()
                ndesc = c2.text_input("Descrição / Nome")
                
                # SELEÇÃO DINÂMICA DE CATEGORIA
                ncat = st.selectbox("Categoria", df_cats['nome'].tolist() if not df_cats.empty else ["Cadastre uma categoria primeiro"])
                nunid = st.selectbox("Unidade", ["UNID", "KG", "M", "M2", "M3", "SC", "CX"])
                
                if st.form_submit_button("Salvar Produto"):
                    if ncod and ndesc and ncat:
                        execute_sql("INSERT INTO produtos (codigo, descricao, unidade, categoria) VALUES (%s,%s,%s,%s)",
                                   (ncod, ndesc, nunid, ncat))
                        st.success(f"Produto {ndesc} cadastrado!")
                        st.rerun()

        with t2:
            st.subheader("Categorias Existentes")
            st.write(", ".join(df_cats['nome'].tolist()) if not df_cats.empty else "Nenhuma categoria.")
            
            with st.form("nova_cat"):
                ncat_nome = st.text_input("Nome da Nova Categoria (Ex: Elétrica)")
                if st.form_submit_button("Adicionar Categoria"):
                    if ncat_nome:
                        execute_sql("INSERT INTO categorias (nome) VALUES (%s)", (ncat_nome.title(),))
                        st.success("Categoria adicionada!")
                        st.rerun()
