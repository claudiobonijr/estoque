import streamlit as st
import psycopg2
import pandas as pd
import plotly.express as px
from datetime import datetime
import time

# ==============================================================================
# 1. CONFIGURAÇÃO & DESIGN SYSTEM
# ==============================================================================
st.set_page_config(
    page_title="Portal Amâncio | SCM",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS PROFISSIONAL + RODAPÉ PERSONALIZADO
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;700&display=swap');
    
    html, body, [class*="css"] { font-family: 'Roboto', sans-serif; }
    
    /* Remove Menu Padrão e Rodapé nativo */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Cards KPI */
    div[data-testid="metric-container"] {
        background-color: #f8f9fa;
        border-left: 5px solid #0f172a;
        padding: 15px;
        border-radius: 5px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    
    /* Tabelas */
    .stDataFrame { border: 1px solid #e0e0e0; border-radius: 5px; }
    
    /* Rodapé Fixo Personalizado */
    .footer {
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background-color: #f1f5f9;
        color: #475569;
        text-align: center;
        padding: 10px;
        font-size: 12px;
        border-top: 1px solid #e2e8f0;
        z-index: 999;
    }
    
    /* Espaço extra no final da página para o conteúdo não ficar atrás do rodapé */
    .block-container { padding-bottom: 60px; }
    </style>
    
    <div class="footer">
        DESENVOLVIDO POR CLAUDIO BONI JUNIOR / 2026
    </div>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. KERNEL DE DADOS (DB & Cache)
# ==============================================================================

@st.cache_resource
def get_db_connection():
    try:
        return psycopg2.connect(st.secrets["db_url"], connect_timeout=5)
    except Exception as e:
        st.error(f"❌ Falha de conexão: {e}")
        return None

@st.cache_data(ttl=60, show_spinner=False)
def fetch_data(query, params=None):
    conn = get_db_connection()
    if not conn: return pd.DataFrame()
    try:
        return pd.read_sql(query, conn, params=params)
    except Exception as e:
        st.error(f"Erro SQL: {e}")
        return pd.DataFrame()

def execute_action(query, params=None):
    conn = get_db_connection()
    if not conn: return False
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            conn.commit()
            fetch_data.clear() 
            return True
    except Exception as e:
        conn.rollback()
        st.toast(f"Erro ao salvar: {e}", icon="❌")
        return False

@st.cache_data(ttl=60)
def processar_estoque():
    df_prods = fetch_data("SELECT codigo, descricao, unidade FROM produtos ORDER BY descricao")
    df_movs = fetch_data("SELECT * FROM movimentacoes")
    
    if df_prods.empty: return pd.DataFrame()
    
    saldo_final = df_prods.copy()
    
    if not df_movs.empty:
        df_calc = df_movs.copy()
        # Define fator: Entrada/Ajuste(+) soma, Saída/Ajuste(-) subtrai
        df_calc['fator'] = df_calc['tipo'].apply(lambda x: 1 if x in ['Entrada', 'Ajuste(+)'] else -1)
        df_calc['qtd_real'] = df_calc['quantidade'] * df_calc['fator']
        
        saldos = df_calc.groupby('codigo')['qtd_real'].sum().reset_index()
        
        entradas = df_movs[df_movs['tipo'] == 'Entrada'].copy()
        custos = pd.DataFrame()
        if not entradas.empty:
            entradas['total_gasto'] = entradas['quantidade'] * entradas['custo_unitario']
            custos = entradas.groupby('codigo')[['quantidade', 'total_gasto']].sum().reset_index()
            custos['custo_medio'] = custos['total_gasto'] / custos['quantidade']
        
        saldo_final = pd.merge(saldo_final, saldos, on='codigo', how='left')
        if not custos.empty:
            saldo_final = pd.merge(saldo_final, custos[['codigo', 'custo_medio']], on='codigo', how='left')
            
    saldo_final = saldo_final.fillna(0)
    if 'qtd_real' not in saldo_final.columns: saldo_final['qtd_real'] = 0.0
    if 'custo_medio' not in saldo_final.columns: saldo_final['custo_medio'] = 0.0
    
    saldo_final['valor_estoque'] = saldo_final['qtd_real'] * saldo_final['custo_medio']
    
    def get_status(q):
        if q <= 0: return "🔴 Zerado"
        if q < 10: return "🟡 Baixo"
        return "🟢 Normal"
        
    saldo_final['Status'] = saldo_final['qtd_real'].apply(get_status)
    saldo_final.rename(columns={'qtd_real': 'Saldo', 'descricao': 'Produto', 'unidade': 'Unid', 'codigo': 'Cod'}, inplace=True)
    return saldo_final

# ==============================================================================
# 3. INTERFACE & NAVEGAÇÃO
# ==============================================================================

if "carrinho_entrada" not in st.session_state: st.session_state["carrinho_entrada"] = []
if "carrinho_saida" not in st.session_state: st.session_state["carrinho_saida"] = []
if "authenticated" not in st.session_state: st.session_state["authenticated"] = False

# --- TELA DE LOGIN & CONSULTA PÚBLICA ---
if not st.session_state["authenticated"]:
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        st.write(""); st.write("")
        st.markdown("<h1 style='text-align: center;'>🏗️ Portal Amâncio</h1>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            user = st.text_input("Usuário")
            pwd = st.text_input("Senha", type="password")
            if st.form_submit_button("🔒 Acessar Sistema", type="primary", use_container_width=True):
                if user == st.secrets["auth"]["username"] and pwd == st.secrets["auth"]["password"]:
                    st.session_state["authenticated"] = True
                    st.rerun()
                else:
                    st.error("Acesso Negado.")
        
        st.markdown("---")
        
        # [RESTAURADO] CONSULTA PÚBLICA DE ESTOQUE
        with st.expander("🔍 Consulta Pública de Estoque"):
            df_public = processar_estoque()
            if not df_public.empty:
                busca_pub = st.text_input("Buscar Material:", placeholder="Digite o nome...")
                if busca_pub:
                    df_public = df_public[df_public['Produto'].str.contains(busca_pub, case=False)]
                
                st.dataframe(
                    df_public[['Produto', 'Saldo', 'Unid', 'Status']],
                    hide_index=True,
                    use_container_width=True,
                    height=300
                )
            else:
                st.info("Sistema indisponível.")

# --- SISTEMA LOGADO ---
else:
    with st.sidebar:
        st.title("Menu")
        menu = st.radio("Navegação:", ["📊 Dashboard", "📦 Estoque", "🔄 Movimentações", "⚙️ Admin"], label_visibility="collapsed")
        st.markdown("---")
        st.caption(f"👤 {st.secrets['auth']['username'].upper()}")
        if st.button("Sair"):
            st.session_state["authenticated"] = False
            st.rerun()

    df_estoque = processar_estoque()
    
    # 1. DASHBOARD
    if menu == "📊 Dashboard":
        st.title("Visão Geral")
        if not df_estoque.empty:
            total_inv = df_estoque['valor_estoque'].sum()
            ruptura = len(df_estoque[df_estoque['Saldo'] <= 0])
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Valor Total", f"R$ {total_inv:,.2f}")
            c2.metric("Mix de Produtos", len(df_estoque))
            c3.metric("Ruptura", ruptura, delta_color="inverse", delta="- Crítico" if ruptura > 0 else "Ok")
            
            st.divider()
            g1, g2 = st.columns([2, 1])
            g1.plotly_chart(px.bar(df_estoque.nlargest(10, 'valor_estoque'), x='Produto', y='valor_estoque', title="Top 10 Valor"), use_container_width=True)
            g2.plotly_chart(px.pie(df_estoque, names='Status', title="Saúde do Estoque", color='Status', color_discrete_map={'🔴 Zerado':'red', '🟡 Baixo':'gold', '🟢 Normal':'green'}), use_container_width=True)

    # 2. ESTOQUE
    elif menu == "📦 Estoque":
        st.title("Controle de Estoque")
        if not df_estoque.empty:
            st.download_button("📥 Excel", df_estoque.to_csv(index=False).encode('utf-8'), "estoque.csv")
            search = st.text_input("Filtrar:", placeholder="Buscar item...")
            df_show = df_estoque[df_estoque['Produto'].str.contains(search, case=False)] if search else df_estoque
            
            st.dataframe(
                df_show[['Cod', 'Produto', 'Status', 'Saldo', 'Unid', 'custo_medio', 'valor_estoque']],
                hide_index=True, use_container_width=True, height=600,
                column_config={"custo_medio": st.column_config.NumberColumn(format="R$ %.2f"), "valor_estoque": st.column_config.NumberColumn(format="R$ %.2f")}
            )

    # 3. OPERAÇÕES (Entrada, Saída, Ajuste, Cadastro)
    elif menu == "🔄 Movimentações":
        st.title("Operações")
        lista_prods = [f"{r['Cod']} - {r['Produto']}" for i, r in df_estoque.iterrows()] if not df_estoque.empty else []
        
        # [RESTAURADO] ABA DE AJUSTE INCLUÍDA
        tab1, tab2, tab3, tab4 = st.tabs(["📥 Entrada", "📤 Saída", "🔧 Ajuste", "✨ Cadastro"])
        
        # --- ENTRADA ---
        with tab1:
            c1, c2 = st.columns([1, 2])
            with c1:
                st.caption("Adicionar ao Carrinho")
                ie = st.selectbox("Item", lista_prods, key="ie")
                qe = st.number_input("Qtd", 0.01, key="qe")
                ve = st.number_input("Custo R$", 0.0, key="ve")
                if st.button("➕ Add", key="add_e"):
                    if ie: st.session_state["carrinho_entrada"].append({"cod": ie.split(" - ")[0], "desc": ie.split(" - ")[1], "qtd": qe, "custo": ve, "total": qe*ve}); st.rerun()
            with c2:
                if st.session_state["carrinho_entrada"]:
                    st.dataframe(pd.DataFrame(st.session_state["carrinho_entrada"]), hide_index=True, use_container_width=True)
                    nf = st.text_input("Nota Fiscal / Fornecedor")
                    if st.button("✅ Finalizar Entrada", type="primary"):
                        if nf:
                            for i in st.session_state["carrinho_entrada"]:
                                execute_action("INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, custo_unitario, referencia) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", 
                                               ("Entrada", datetime.now().date(), "CENTRAL", i['cod'], i['desc'], i['qtd'], i['custo'], nf))
                            st.session_state["carrinho_entrada"] = []
                            st.toast("Sucesso!"); time.sleep(1); st.rerun()
                else: st.info("Carrinho vazio.")

        # --- SAÍDA ---
        with tab2:
            c1, c2 = st.columns([1, 2])
            with c1:
                st.caption("Romaneio de Saída")
                is_ = st.selectbox("Item", lista_prods, key="is")
                qs = st.number_input("Qtd", 0.01, key="qs")
                if st.button("➕ Add", key="add_s"):
                    if is_: st.session_state["carrinho_saida"].append({"cod": is_.split(" - ")[0], "desc": is_.split(" - ")[1], "qtd": qs}); st.rerun()
            with c2:
                if st.session_state["carrinho_saida"]:
                    st.dataframe(pd.DataFrame(st.session_state["carrinho_saida"]), hide_index=True, use_container_width=True)
                    ob = st.text_input("Obra / Destino")
                    if st.button("📤 Finalizar Saída", type="primary"):
                        if ob:
                            for i in st.session_state["carrinho_saida"]:
                                execute_action("INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, custo_unitario) VALUES (%s,%s,%s,%s,%s,%s,%s)", 
                                               ("Saída", datetime.now().date(), ob, i['cod'], i['desc'], i['qtd'], 0))
                            st.session_state["carrinho_saida"] = []
                            st.toast("Sucesso!"); time.sleep(1); st.rerun()
                else: st.info("Carrinho vazio.")

        # --- AJUSTE [RESTAURADO] ---
        with tab3:
            st.warning("⚠️ Use para Balanço ou Correção de Inventário")
            with st.form("ajuste_form"):
                ia = st.selectbox("Produto para Ajuste", lista_prods)
                qa = st.number_input("Diferença encontrada (+ sobra, - falta)", step=1.0)
                ma = st.text_input("Motivo (Ex: Contagem Cíclica)")
                
                if st.form_submit_button("⚖️ Processar Ajuste"):
                    if ia and qa != 0 and ma:
                        cod = ia.split(" - ")[0]
                        desc = ia.split(" - ")[1]
                        tipo = "Ajuste(+)" if qa > 0 else "Ajuste(-)"
                        execute_action("INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, custo_unitario, referencia) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", 
                                       (tipo, datetime.now().date(), "BALANÇO", cod, desc, abs(qa), 0, ma))
                        st.toast("Estoque corrigido!", icon="✅"); time.sleep(1); st.rerun()

        # --- CADASTRO ---
        with tab4:
            with st.form("cad_form"):
                nc = st.text_input("Código").upper()
                nd = st.text_input("Descrição").title()
                nu = st.selectbox("Unid", ["UNID", "KG", "M", "M2", "M3", "SC"])
                if st.form_submit_button("Salvar"):
                    execute_action("INSERT INTO produtos (codigo, descricao, unidade) VALUES (%s,%s,%s) ON CONFLICT (codigo) DO NOTHING", (nc, nd, nu))
                    st.toast("Cadastrado!"); time.sleep(1); st.rerun()

    # 4. ADMIN
    elif menu == "⚙️ Admin":
        st.title("Auditoria")
        df_logs = fetch_data("SELECT * FROM movimentacoes ORDER BY id DESC LIMIT 50")
        st.dataframe(df_logs, use_container_width=True)
        id_del = st.number_input("ID para excluir", min_value=0)
        if st.button("❌ Excluir Reg", type="primary"):
            if id_del > 0: execute_action("DELETE FROM movimentacoes WHERE id = %s", (id_del,)); st.rerun()
