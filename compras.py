import streamlit as st
import psycopg2
import pandas as pd
import plotly.express as px
from datetime import datetime
import time

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Portal Amâncio | SCM", page_icon="🏗️", layout="wide")

# CSS para Dark Mode e Responsividade
st.markdown("""
    <style>
    div[data-testid="metric-container"] {
        background-color: var(--secondary-background-color);
        border: 1px solid rgba(128, 128, 128, 0.2);
        padding: 20px; border-radius: 15px;
    }
    @media (max-width: 640px) { .block-container { padding: 1rem !important; } }
    </style>
""", unsafe_allow_html=True)

# --- FUNÇÕES DE BANCO ---
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

@st.cache_data(ttl=60)
def load_data(query):
    try:
        with get_conn() as conn:
            return pd.read_sql(query, conn)
    except Exception as e:
        # Retorna dataframe vazio se a tabela não existir ou der erro
        return pd.DataFrame()

# --- PROCESSAMENTO ---
def processar_estoque():
    df_p = load_data("SELECT * FROM produtos")
    df_m = load_data("SELECT * FROM movimentacoes")
    
    # Se produtos estiver vazio, retorna vazio estruturado
    if df_p.empty:
        return pd.DataFrame(columns=['codigo', 'descricao', 'categoria', 'unidade', 'qtd_final', 'valor_total', 'Status'])
    
    if not df_m.empty:
        df_m['fator'] = df_m['tipo'].apply(lambda x: 1 if x in ['Entrada', 'Ajuste(+)'] else -1)
        df_m['qtd_calc'] = df_m['quantidade'] * df_m['fator']
        saldos = df_m.groupby('codigo')['qtd_calc'].sum().reset_index()
        df_p = pd.merge(df_p, saldos, on='codigo', how='left').fillna(0)
        df_p.rename(columns={'qtd_calc': 'qtd_final'}, inplace=True)
    else:
        df_p['qtd_final'] = 0.0

    # Garantir que a coluna custo_unitario exista (mesmo que 0)
    if 'custo_unitario' not in df_p.columns: df_p['custo_unitario'] = 0.0
    
    df_p['valor_total'] = df_p['qtd_final'] * df_p['custo_unitario']
    df_p['Status'] = df_p['qtd_final'].apply(lambda x: "🔴 Zerado" if x <= 0 else "🟢 OK")
    return df_p

# --- INTERFACE ---
if "authenticated" not in st.session_state: st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.title("🏗️ Amâncio SCM")
    u = st.text_input("Usuário")
    p = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if u == st.secrets["auth"]["username"] and p == st.secrets["auth"]["password"]:
            st.session_state["authenticated"] = True
            st.rerun()
else:
    df_estoque = processar_estoque()
    df_cats = load_data("SELECT nome FROM categorias ORDER BY nome")
    
    menu = st.sidebar.radio("Navegação", ["📊 Dashboard", "📦 Inventário", "🔄 Movimentar", "⚙️ Cadastros"])

    if menu == "📊 Dashboard":
        st.header("Resumo da Obra")
        if df_estoque.empty or df_estoque['qtd_final'].sum() == 0:
            st.info("Nenhum dado de movimentação para gerar gráficos ainda.")
        else:
            c1, c2 = st.columns(2)
            fig1 = px.pie(df_estoque, names='categoria', values='qtd_final', title="Volume por Categoria", template="plotly_dark")
            c1.plotly_chart(fig1, use_container_width=True)
            
            fig2 = px.bar(df_estoque, x='categoria', y='qtd_final', title="Saldo por Categoria", template="plotly_dark")
            c2.plotly_chart(fig2, use_container_width=True)

    elif menu == "📦 Inventário":
        st.header("Estoque Atual")
        st.dataframe(df_estoque, use_container_width=True, hide_index=True)

    elif menu == "🔄 Movimentar":
        st.header("Lançar Movimentação")
        with st.form("mov"):
            t = st.selectbox("Tipo", ["Entrada", "Saída"])
            # Só mostra produtos se existirem
            prods = [f"{r['codigo']} | {r['descricao']}" for i,r in df_estoque.iterrows()] if not df_estoque.empty else ["Nenhum produto cadastrado"]
            p_sel = st.selectbox("Produto", prods)
            q = st.number_input("Qtd", min_value=0.1)
            if st.form_submit_button("Confirmar"):
                if "Nenhum" not in p_sel:
                    c = p_sel.split(" | ")[0]
                    d = p_sel.split(" | ")[1]
                    execute_sql("INSERT INTO movimentacoes (tipo, data, codigo, descricao, quantidade) VALUES (%s,%s,%s,%s,%s)", (t, datetime.now().date(), c, d, q))
                    st.success("Feito!")
                    st.rerun()

    elif menu == "⚙️ Cadastros":
        st.subheader("Novas Categorias")
        with st.form("f_cat"):
            n_c = st.text_input("Nome da Categoria")
            if st.form_submit_button("Adicionar"):
                execute_sql("INSERT INTO categorias (nome) VALUES (%s)", (n_c.title(),))
                st.rerun()
        
        st.divider()
        st.subheader("Novo Produto")
        with st.form("f_prod"):
            c = st.text_input("Código")
            d = st.text_input("Descrição")
            cat = st.selectbox("Categoria", df_cats['nome'].tolist() if not df_cats.empty else ["Padrão"])
            if st.form_submit_button("Cadastrar"):
                execute_sql("INSERT INTO produtos (codigo, descricao, categoria) VALUES (%s,%s,%s)", (c, d, cat))
                st.success("Produto cadastrado!")
                st.rerun()
