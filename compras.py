import streamlit as st
import psycopg2
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import time

# ==============================================================================
# 1. CONFIGURAÇÃO & DESIGN SYSTEM (A "Cara" da Empresa)
# ==============================================================================
st.set_page_config(
    page_title="Portal Amâncio | SCM",
    page_icon="🏗️", # Pode usar emoji ou caminho de arquivo
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS PROFISSIONAL - Remove elementos padrão e cria identidade visual
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;700&display=swap');
    
    html, body, [class*="css"] { font-family: 'Roboto', sans-serif; }
    
    /* Remove Menu Padrão do Streamlit (Hambúrguer superior direito) */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Cards de KPI estilo Dashboard Executivo */
    div[data-testid="metric-container"] {
        background-color: #f8f9fa;
        border-left: 5px solid #0f172a;
        padding: 15px;
        border-radius: 5px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    
    /* Ajuste de Tabelas */
    .stDataFrame { border: 1px solid #e0e0e0; border-radius: 5px; }
    
    /* Botões Premium */
    .stButton>button {
        border-radius: 4px;
        font-weight: bold;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. KERNEL DE DADOS (O "Cérebro" - Alta Performance)
# ==============================================================================

# CONEXÃO PERSISTENTE: Não reconecta a cada clique (Economiza 1-2 segundos)
@st.cache_resource
def get_db_connection():
    try:
        return psycopg2.connect(st.secrets["db_url"], connect_timeout=5)
    except Exception as e:
        st.error(f"❌ Falha crítica de conexão: {e}")
        return None

# LEITURA COM CACHE: Guarda o resultado por 60s (Ultra rápido)
@st.cache_data(ttl=60, show_spinner=False)
def fetch_data(query, params=None):
    conn = get_db_connection()
    if not conn: return pd.DataFrame()
    try:
        return pd.read_sql(query, conn, params=params)
    except Exception as e:
        st.error(f"Erro na consulta: {e}")
        return pd.DataFrame()

# ESCRITA (INSERT/UPDATE): Limpa o cache para atualizar a tela na hora
def execute_action(query, params=None):
    conn = get_db_connection()
    if not conn: return False
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            conn.commit()
            # IMPORTANTE: Limpa o cache de leitura para o usuário ver a mudança
            fetch_data.clear() 
            return True
    except Exception as e:
        conn.rollback()
        st.toast(f"Erro ao salvar: {e}", icon="❌")
        return False

# LÓGICA DE NEGÓCIO CENTRALIZADA (Evita refazer contas na interface)
@st.cache_data(ttl=60)
def processar_estoque():
    df_prods = fetch_data("SELECT codigo, descricao, unidade FROM produtos ORDER BY descricao")
    df_movs = fetch_data("SELECT * FROM movimentacoes")
    
    if df_prods.empty: return pd.DataFrame()
    
    # Base do relatório
    saldo_final = df_prods.copy()
    
    if not df_movs.empty:
        # 1. Calcula Saldos
        df_calc = df_movs.copy()
        df_calc['fator'] = df_calc['tipo'].apply(lambda x: 1 if x in ['Entrada', 'Ajuste(+)'] else -1)
        df_calc['qtd_real'] = df_calc['quantidade'] * df_calc['fator']
        saldos = df_calc.groupby('codigo')['qtd_real'].sum().reset_index()
        
        # 2. Calcula Custo Médio (Apenas entradas)
        entradas = df_movs[df_movs['tipo'] == 'Entrada'].copy()
        custos = pd.DataFrame()
        if not entradas.empty:
            entradas['total_gasto'] = entradas['quantidade'] * entradas['custo_unitario']
            custos = entradas.groupby('codigo')[['quantidade', 'total_gasto']].sum().reset_index()
            custos['custo_medio'] = custos['total_gasto'] / custos['quantidade']
        
        # 3. Mescla tudo
        saldo_final = pd.merge(saldo_final, saldos, on='codigo', how='left')
        if not custos.empty:
            saldo_final = pd.merge(saldo_final, custos[['codigo', 'custo_medio']], on='codigo', how='left')
            
    # Tratamento de Nulos
    saldo_final = saldo_final.fillna(0)
    if 'qtd_real' not in saldo_final.columns: saldo_final['qtd_real'] = 0.0
    if 'custo_medio' not in saldo_final.columns: saldo_final['custo_medio'] = 0.0
    
    saldo_final['valor_estoque'] = saldo_final['qtd_real'] * saldo_final['custo_medio']
    
    # Status Visual
    def get_status(q):
        if q <= 0: return "🔴 Zerado"
        if q < 10: return "🟡 Baixo"
        return "🟢 Normal"
        
    saldo_final['Status'] = saldo_final['qtd_real'].apply(get_status)
    saldo_final.rename(columns={'qtd_real': 'Saldo', 'descricao': 'Produto', 'unidade': 'Unid', 'codigo': 'Cod'}, inplace=True)
    
    return saldo_final

# ==============================================================================
# 3. COMPONENTES DE UI (Funções para limpar o código principal)
# ==============================================================================
def sidebar_user_info():
    st.sidebar.markdown("---")
    st.sidebar.caption(f"Logado como: **{st.secrets['auth']['username'].upper()}**")
    st.sidebar.caption(f"Ambiente: **Produção**")
    if st.sidebar.button("🔒 Sair do Sistema"):
        st.session_state["authenticated"] = False
        st.rerun()

# ==============================================================================
# 4. APLICAÇÃO PRINCIPAL (Fluxo de Telas)
# ==============================================================================

# Inicialização de Variáveis de Sessão
if "carrinho_entrada" not in st.session_state: st.session_state["carrinho_entrada"] = []
if "carrinho_saida" not in st.session_state: st.session_state["carrinho_saida"] = []
if "authenticated" not in st.session_state: st.session_state["authenticated"] = False

# --- TELA DE LOGIN ---
if not st.session_state["authenticated"]:
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        st.write(""); st.write("")
        st.markdown("<h1 style='text-align: center;'>🏗️ Portal Amâncio</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: gray;'>Supply Chain Management System</p>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            user = st.text_input("Usuário")
            pwd = st.text_input("Senha", type="password")
            submitted = st.form_submit_button("Acessar Painel", type="primary", use_container_width=True)
            
            if submitted:
                if user == st.secrets["auth"]["username"] and pwd == st.secrets["auth"]["password"]:
                    st.session_state["authenticated"] = True
                    st.toast("Autenticado com sucesso!", icon="✅")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("Credenciais inválidas.")

# --- SISTEMA LOGADO ---
else:
    # Menu Lateral
    with st.sidebar:
        st.title("Navegação")
        menu = st.radio(
            "Módulos:", 
            ["📊 Dashboard Executivo", "📦 Controle de Estoque", "🔄 Movimentações", "🛠️ Administração"],
            label_visibility="collapsed"
        )
        sidebar_user_info()

    # Carregamento de Dados (Cacheado)
    df_estoque = processar_estoque()
    
    # --- MÓDULO 1: DASHBOARD ---
    if menu == "📊 Dashboard Executivo":
        st.title("Visão Geral da Operação")
        st.markdown(f"*Data de Referência: {datetime.now().strftime('%d/%m/%Y')}*")
        
        if not df_estoque.empty:
            total_investido = df_estoque['valor_estoque'].sum()
            itens_zerados = len(df_estoque[df_estoque['Saldo'] <= 0])
            top_produto = df_estoque.sort_values('valor_estoque', ascending=False).iloc[0]['Produto'] if total_investido > 0 else "N/A"
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Valor em Estoque", f"R$ {total_investido:,.2f}", help="Custo Médio x Quantidade")
            c2.metric("Produto Curva A", top_produto, help="Item com maior valor alocado")
            c3.metric("Ruptura de Estoque", f"{itens_zerados} Itens", delta="- Crítico" if itens_zerados > 0 else "Ok", delta_color="inverse")
            
            st.divider()
            
            g1, g2 = st.columns([2, 1])
            with g1:
                st.subheader("Top 10 Itens (Valor)")
                fig_bar = px.bar(df_estoque.nlargest(10, 'valor_estoque'), x='Produto', y='valor_estoque', text_auto='.2s')
                fig_bar.update_layout(xaxis_title=None, yaxis_title="R$ Investido")
                st.plotly_chart(fig_bar, use_container_width=True)
            
            with g2:
                st.subheader("Disponibilidade")
                st.plotly_chart(px.pie(df_estoque, names='Status', color='Status', color_discrete_map={'🔴 Zerado':'red', '🟡 Baixo':'gold', '🟢 Normal':'green'}), use_container_width=True)
        else:
            st.warning("Aguardando dados para gerar indicadores.")

    # --- MÓDULO 2: TABELA DE ESTOQUE ---
    elif menu == "📦 Controle de Estoque":
        c1, c2 = st.columns([4, 1])
        c1.title("Posição de Estoque")
        
        if not df_estoque.empty:
            with c2:
                st.download_button("📥 Exportar Excel", df_estoque.to_csv(index=False).encode('utf-8'), "estoque.csv", "text/csv")
            
            search = st.text_input("🔎 Pesquisar item...", placeholder="Ex: Cimento, Tijolo...")
            df_view = df_estoque.copy()
            if search:
                df_view = df_view[df_view['Produto'].str.contains(search, case=False)]
            
            st.dataframe(
                df_view[['Cod', 'Produto', 'Status', 'Saldo', 'Unid', 'custo_medio', 'valor_estoque']],
                hide_index=True,
                use_container_width=True,
                height=600,
                column_config={
                    "custo_medio": st.column_config.NumberColumn("Custo Médio", format="R$ %.2f"),
                    "valor_estoque": st.column_config.NumberColumn("Total", format="R$ %.2f"),
                    "Status": st.column_config.TextColumn("Situação", width="small")
                }
            )
        else:
            st.info("Nenhum produto cadastrado.")

    # --- MÓDULO 3: OPERAÇÕES ---
    elif menu == "🔄 Movimentações":
        st.title("Central de Lançamentos")
        
        # Carrega lista de produtos para selects
        lista_prods = [f"{r['Cod']} - {r['Produto']}" for i, r in df_estoque.iterrows()] if not df_estoque.empty else []
        
        tab_ent, tab_sai, tab_cad = st.tabs(["📥 Entrada (Compras)", "📤 Saída (Obras)", "✨ Cadastro Novo"])
        
        # --- TAB ENTRADA ---
        with tab_ent:
            c_form, c_cart = st.columns([1, 2])
            with c_form:
                st.markdown("##### Adicionar ao Carrinho")
                sel_prod = st.selectbox("Produto", lista_prods, key="ent_prod")
                qtd_ent = st.number_input("Quantidade", min_value=0.01, format="%.2f", key="ent_qtd")
                val_ent = st.number_input("Custo Unitário (R$)", min_value=0.00, format="%.2f", key="ent_val")
                
                if st.button("⬇️ Incluir", key="btn_add_ent"):
                    if sel_prod:
                        cod = sel_prod.split(" - ")[0]
                        desc = sel_prod.split(" - ")[1]
                        st.session_state["carrinho_entrada"].append(
                            {"cod": cod, "desc": desc, "qtd": qtd_ent, "custo": val_ent, "total": qtd_ent*val_ent}
                        )
                        st.rerun()

            with c_cart:
                st.markdown("##### Espelho da Nota Fiscal")
                if st.session_state["carrinho_entrada"]:
                    df_cart = pd.DataFrame(st.session_state["carrinho_entrada"])
                    st.dataframe(df_cart, hide_index=True, use_container_width=True, column_config={"custo": st.column_config.NumberColumn(format="R$ %.2f"), "total": st.column_config.NumberColumn(format="R$ %.2f")})
                    
                    st.markdown(f"**Total da Nota: R$ {df_cart['total'].sum():,.2f}**")
                    
                    col_nf, col_btn = st.columns([2, 1])
                    nf_num = col_nf.text_input("Fornecedor / Nº Nota Fiscal")
                    
                    if col_btn.button("✅ Processar Entrada", type="primary", use_container_width=True):
                        if not nf_num:
                            st.warning("Preencha o número da NF.")
                        else:
                            sucesso = True
                            for item in st.session_state["carrinho_entrada"]:
                                res = execute_action(
                                    "INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, custo_unitario, referencia) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                                    ("Entrada", datetime.now().date(), "ALMOXARIFADO", item['cod'], item['desc'], item['qtd'], item['custo'], nf_num)
                                )
                                if not res: sucesso = False
                            
                            if sucesso:
                                st.session_state["carrinho_entrada"] = []
                                st.toast("Entrada processada com sucesso!", icon="🚀")
                                time.sleep(1)
                                st.rerun()
                    
                    if st.button("Limpar Carrinho"):
                        st.session_state["carrinho_entrada"] = []
                        st.rerun()
                else:
                    st.info("Carrinho vazio.")

        # --- TAB SAÍDA ---
        with tab_sai:
            st.info("ℹ️ As saídas baixam o estoque e são contabilizadas como custo zero na movimentação (custo absorvido pela obra).")
            # (Lógica similar à entrada, simplificada para brevidade no exemplo Enterprise)
            # Recomendo implementar igual à entrada, mas enviando type="Saída" e custo=0
            st.warning("Implementação segue o mesmo padrão da Entrada (Carrinho -> Processar).")

        # --- TAB CADASTRO ---
        with tab_cad:
            with st.form("new_prod"):
                c1, c2, c3 = st.columns([1, 2, 1])
                n_cod = c1.text_input("Código (SKU)").upper()
                n_desc = c2.text_input("Descrição").title()
                n_unid = c3.selectbox("Unidade", ["UNID", "KG", "M", "M2", "M3", "SC", "L"])
                
                if st.form_submit_button("💾 Cadastrar Produto"):
                    if n_cod and n_desc:
                        res = execute_action(
                            "INSERT INTO produtos (codigo, descricao, unidade) VALUES (%s,%s,%s) ON CONFLICT (codigo) DO NOTHING",
                            (n_cod, n_desc, n_unid)
                        )
                        if res: 
                            st.toast("Produto cadastrado!", icon="✨")
                            time.sleep(1)
                            st.rerun()
                    else:
                        st.error("Preencha todos os campos.")

    # --- MÓDULO 4: ADMIN ---
    elif menu == "🛠️ Administração":
        st.title("Log de Auditoria")
        df_logs = fetch_data("SELECT * FROM movimentacoes ORDER BY data DESC, id DESC LIMIT 100")
        st.dataframe(df_logs, use_container_width=True)
        
        st.divider()
        st.subheader("Zona de Perigo")
        id_del = st.number_input("ID do registro para estornar", min_value=0)
        if st.button("❌ Estornar Registro", type="primary"):
            if id_del > 0:
                execute_action("DELETE FROM movimentacoes WHERE id = %s", (id_del,))
                st.toast("Registro estornado.", icon="🗑️")
                time.sleep(1)
                st.rerun()
