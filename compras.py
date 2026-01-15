import streamlit as st
import psycopg2
import pandas as pd
import plotly.express as px
from datetime import datetime
import time

# ==============================================================================
# 1. CONFIGURAÇÃO & DESIGN SYSTEM (PREMIUM)
# ==============================================================================
st.set_page_config(
    page_title="Portal Amâncio | SCM",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- PALETA DE CORES & ESTILO CSS ---
# Azul Navy: #0f172a | Fundo: #f1f5f9 | Branco: #ffffff | Dourado/Accent: #d97706
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        background-color: #f1f5f9;
        color: #1e293b;
    }
    
    /* REMOVER PADRÕES DO STREAMLIT */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* SIDEBAR PERSONALIZADA */
    [data-testid="stSidebar"] {
        background-color: #0f172a;
    }
    [data-testid="stSidebar"] * {
        color: #e2e8f0 !important;
    }
    .css-17lntkn { /* Títulos da sidebar */
        color: #94a3b8 !important;
        font-weight: 600;
    }

    /* CARDS DE KPI (FATOR UAU) */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        transition: transform 0.2s;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        border-color: #3b82f6;
    }
    [data-testid="stMetricLabel"] {
        color: #64748b;
        font-size: 0.9rem;
        font-weight: 600;
    }
    [data-testid="stMetricValue"] {
        color: #0f172a;
        font-weight: 700;
    }

    /* TABELAS */
    .stDataFrame {
        background-color: white;
        padding: 10px;
        border-radius: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }

    /* BOTÕES */
    .stButton>button {
        border-radius: 8px;
        font-weight: 600;
        border: none;
        transition: all 0.3s ease;
    }
    /* Botão Primário (Ações Fortes) */
    div.stButton > button:first-child {
        background-color: #ffffff; 
        color: #0f172a;
        border: 1px solid #cbd5e1;
    }
    div.stButton > button:first-child:hover {
        background-color: #f8fafc;
        border-color: #3b82f6;
        color: #3b82f6;
    }
    /* Botões dentro de forms (Submit) costumam ser diferentes, ajustamos via Python se precisar */

    /* TABS (ABAS) */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: transparent;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        background-color: #ffffff;
        border-radius: 8px;
        border: 1px solid #e2e8f0;
        color: #64748b;
        font-weight: 600;
        padding: 0 20px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #0f172a !important;
        color: #ffffff !important;
        border: none;
    }

    /* RODAPÉ ELEGANTE */
    .footer {
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background: linear-gradient(to right, #0f172a, #1e293b);
        color: #94a3b8;
        text-align: center;
        padding: 8px;
        font-size: 11px;
        letter-spacing: 1px;
        z-index: 999;
    }
    .block-container { padding-bottom: 80px; padding-top: 2rem; }
    
    /* LOGIN BOX */
    .login-box {
        background: white;
        padding: 2rem;
        border-radius: 15px;
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
        border: 1px solid #e2e8f0;
    }
    </style>
    
    <div class="footer">
        AMÂNCIO GESTÃO INTELIGENTE &copy; 2026 • DESENVOLVIDO POR CLAUDIO BONI
    </div>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. KERNEL DE DADOS (DB & Cache) - INTACTO
# ==============================================================================

@st.cache_resource
def get_db_connection():
    try:
        return psycopg2.connect(st.secrets["db_url"], connect_timeout=5)
    except Exception as e:
        st.error(f"❌ Falha de conexão Crítica: {e}")
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

# --- TELA DE LOGIN (COM DESIGN MELHORADO) ---
if not st.session_state["authenticated"]:
    # Espaçamento para centralizar
    st.write("")
    st.write("")
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        # Container Visual Branco
        st.markdown('<div class="login-box">', unsafe_allow_html=True)
        st.markdown("<h2 style='text-align: center; color: #0f172a; margin-bottom: 0px;'>🏗️ Portal Amâncio</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #64748b; font-size: 14px;'>Sistema Integrado de Gestão</p>", unsafe_allow_html=True)
        st.markdown("---")
        
        with st.form("login_form"):
            user = st.text_input("ID Usuário")
            pwd = st.text_input("Senha de Acesso", type="password")
            
            # Botão de Login Full Width
            submit = st.form_submit_button("🔒 ACESSAR SISTEMA", type="primary", use_container_width=True)
            
            if submit:
                if user == st.secrets["auth"]["username"] and pwd == st.secrets["auth"]["password"]:
                    st.session_state["authenticated"] = True
                    st.rerun()
                else:
                    st.error("Credenciais inválidas.")
        
        st.markdown("</div>", unsafe_allow_html=True) # Fim do box
        
        # Consulta Pública fora do box
        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("🔍 Consulta Pública (Acesso Visitante)"):
            df_public = processar_estoque()
            if not df_public.empty:
                busca_pub = st.text_input("O que você procura?", placeholder="Ex: Cimento, Areia...")
                if busca_pub:
                    df_public = df_public[df_public['Produto'].str.contains(busca_pub, case=False)]
                
                st.dataframe(
                    df_public[['Produto', 'Saldo', 'Unid', 'Status']],
                    hide_index=True,
                    use_container_width=True,
                    height=300
                )
            else:
                st.info("Sistema offline para consultas.")

# --- SISTEMA LOGADO ---
else:
    # Sidebar Profissional
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/1063/1063196.png", width=60)
        st.markdown("<h3 style='color: white;'>Amâncio Obras</h3>", unsafe_allow_html=True)
        st.markdown("<p style='color: #94a3b8; font-size: 12px;'>v2.5 Enterprise</p>", unsafe_allow_html=True)
        st.markdown("---")
        
        menu = st.radio(
            "NAVEGAÇÃO", 
            ["📊 Dashboard", "📦 Estoque Geral", "🔄 Central de Operações", "⚙️ Auditoria & Logs"],
        )
        
        st.markdown("---")
        c_logout = st.columns(1)[0]
        if c_logout.button("Sair do Sistema"):
            st.session_state["authenticated"] = False
            st.rerun()

    df_estoque = processar_estoque()
    
    # 1. DASHBOARD EXECUTIVO
    if menu == "📊 Dashboard":
        st.markdown("### 📊 Visão Executiva")
        st.markdown("Monitoramento em tempo real dos indicadores de obra.")
        
        if not df_estoque.empty:
            total_inv = df_estoque['valor_estoque'].sum()
            ruptura = len(df_estoque[df_estoque['Saldo'] <= 0])
            total_itens = len(df_estoque)
            
            # Cards KPI Estilizados
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Valor em Estoque", f"R$ {total_inv:,.2f}", delta="Atualizado agora")
            c2.metric("Itens Cadastrados", total_itens, delta="Mix de Produtos")
            c3.metric("Ruptura (Zerados)", rupture, delta="- Crítico" if rupture > 0 else "Estável", delta_color="inverse")
            c4.metric("Status do Sistema", "Online 🟢")
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Gráficos Lado a Lado
            g1, g2 = st.columns([2, 1])
            
            with g1:
                st.markdown("##### 📈 Curva ABC (Valor)")
                # Gráfico com cores personalizadas
                fig_bar = px.bar(
                    df_estoque.nlargest(8, 'valor_estoque'), 
                    x='Produto', y='valor_estoque', 
                    text_auto='.2s',
                    color='valor_estoque',
                    color_continuous_scale='Blues'
                )
                fig_bar.update_layout(xaxis_title=None, yaxis_title=None, height=350, margin=dict(l=0, r=0, t=0, b=0))
                st.plotly_chart(fig_bar, use_container_width=True)
                
            with g2:
                st.markdown("##### 🍩 Saúde do Estoque")
                fig_pie = px.pie(
                    df_estoque, 
                    names='Status', 
                    hole=0.6,
                    color='Status',
                    color_discrete_map={'🔴 Zerado':'#ef4444', '🟡 Baixo':'#eab308', '🟢 Normal':'#22c55e'}
                )
                fig_pie.update_layout(height=350, margin=dict(l=0, r=0, t=0, b=0), showlegend=True, legend=dict(orientation="h"))
                st.plotly_chart(fig_pie, use_container_width=True)

    # 2. ESTOQUE (Tabela Inteligente)
    elif menu == "📦 Estoque Geral":
        st.markdown("### 📦 Inventário Físico & Financeiro")
        
        if not df_estoque.empty:
            c_filtro, c_btn = st.columns([4, 1])
            with c_filtro:
                search = st.text_input("🔎 Pesquisar Material:", placeholder="Digite nome, código ou categoria...")
            with c_btn:
                st.markdown("<br>", unsafe_allow_html=True)
                st.download_button("📥 Baixar Excel", df_estoque.to_csv(index=False).encode('utf-8'), "estoque_amancio.csv", use_container_width=True)
            
            df_show = df_estoque[df_estoque['Produto'].str.contains(search, case=False)] if search else df_estoque
            
            # Tabela com Barra de Progresso Visual
            st.dataframe(
                df_show[['Cod', 'Produto', 'Status', 'Saldo', 'Unid', 'custo_medio', 'valor_estoque']],
                hide_index=True, 
                use_container_width=True, 
                height=600,
                column_config={
                    "Saldo": st.column_config.ProgressColumn(
                        "Nível de Estoque",
                        help="Visualização rápida do volume",
                        format="%.1f",
                        min_value=0,
                        max_value=df_estoque['Saldo'].max(),
                    ),
                    "custo_medio": st.column_config.NumberColumn("Custo Médio", format="R$ %.2f"),
                    "valor_estoque": st.column_config.NumberColumn("Total ($)", format="R$ %.2f"),
                    "Status": st.column_config.TextColumn("Status", width="small"),
                }
            )

    # 3. OPERAÇÕES (Abas Modernas)
    elif menu == "🔄 Central de Operações":
        st.markdown("### 🔄 Central de Movimentações")
        
        lista_prods = [f"{r['Cod']} - {r['Produto']}" for i, r in df_estoque.iterrows()] if not df_estoque.empty else []
        
        # Abas redesenhadas via CSS
        tab1, tab2, tab3, tab4 = st.tabs(["📥 RECEBIMENTO (Entrada)", "📤 EXPEDIÇÃO (Saída)", "🔧 AJUSTE DE BALANÇO", "✨ NOVO PRODUTO"])
        
        # --- ENTRADA ---
        with tab1:
            st.markdown("#### Registrar Compra / Entrada")
            c1, c2 = st.columns([1, 1.5], gap="large")
            
            with c1:
                st.markdown("**1. Adicionar Itens ao Romaneio**")
                with st.container(border=True):
                    ie = st.selectbox("Selecione o Material", lista_prods, key="ie")
                    col_q, col_v = st.columns(2)
                    qe = col_q.number_input("Quantidade", 0.01, key="qe")
                    ve = col_v.number_input("Custo Unit. (R$)", 0.0, key="ve")
                    
                    if st.button("➕ Adicionar à Lista", key="add_e", use_container_width=True):
                        if ie: 
                            st.session_state["carrinho_entrada"].append({
                                "cod": ie.split(" - ")[0], 
                                "desc": ie.split(" - ")[1], 
                                "qtd": qe, 
                                "custo": ve, 
                                "total": qe*ve
                            })
                            st.rerun()
            
            with c2:
                st.markdown("**2. Revisão & Finalização**")
                if st.session_state["carrinho_entrada"]:
                    df_carrinho = pd.DataFrame(st.session_state["carrinho_entrada"])
                    st.dataframe(
                        df_carrinho, 
                        hide_index=True, 
                        use_container_width=True,
                        column_config={"total": st.column_config.NumberColumn("Subtotal", format="R$ %.2f")}
                    )
                    
                    st.info(f"💰 Valor Total da Nota: **R$ {df_carrinho['total'].sum():,.2f}**")
                    nf = st.text_input("Número da Nota Fiscal / Fornecedor")
                    
                    if st.button("✅ Confirmar Entrada no Estoque", type="primary", use_container_width=True):
                        if nf:
                            for i in st.session_state["carrinho_entrada"]:
                                execute_action("INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, custo_unitario, referencia) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", 
                                               ("Entrada", datetime.now().date(), "CENTRAL", i['cod'], i['desc'], i['qtd'], i['custo'], nf))
                            st.session_state["carrinho_entrada"] = []
                            st.toast("Entrada realizada com sucesso!", icon="🚚")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.warning("Informe o Fornecedor ou NF para rastreio.")
                else: 
                    st.info("O carrinho está vazio. Adicione itens ao lado.")

        # --- SAÍDA ---
        with tab2:
            st.markdown("#### Registrar Uso / Saída para Obra")
            c1, c2 = st.columns([1, 1.5], gap="large")
            
            with c1:
                st.markdown("**1. Seleção de Materiais**")
                with st.container(border=True):
                    is_ = st.selectbox("Selecione o Material", lista_prods, key="is")
                    qs = st.number_input("Quantidade a retirar", 0.01, key="qs")
                    if st.button("➕ Adicionar à Lista", key="add_s", use_container_width=True):
                        if is_: 
                            st.session_state["carrinho_saida"].append({
                                "cod": is_.split(" - ")[0], 
                                "desc": is_.split(" - ")[1], 
                                "qtd": qs
                            })
                            st.rerun()
            with c2:
                st.markdown("**2. Destino**")
                if st.session_state["carrinho_saida"]:
                    st.dataframe(pd.DataFrame(st.session_state["carrinho_saida"]), hide_index=True, use_container_width=True)
                    ob = st.text_input("Qual Obra / Destino?")
                    
                    if st.button("📤 Confirmar Saída", type="primary", use_container_width=True):
                        if ob:
                            for i in st.session_state["carrinho_saida"]:
                                execute_action("INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, custo_unitario) VALUES (%s,%s,%s,%s,%s,%s,%s)", 
                                               ("Saída", datetime.now().date(), ob, i['cod'], i['desc'], i['qtd'], 0))
                            st.session_state["carrinho_saida"] = []
                            st.toast("Saída registrada!", icon="🏗️")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.warning("Informe para qual Obra o material vai.")
                else:
                    st.info("Lista de saída vazia.")

        # --- AJUSTE ---
        with tab3:
            st.markdown("#### 🔧 Correção de Estoque (Balanço)")
            st.warning("Utilize esta aba apenas para corrigir erros de contagem ou perdas.")
            
            with st.form("ajuste_form"):
                c_aj1, c_aj2 = st.columns(2)
                ia = c_aj1.selectbox("Produto para Ajuste", lista_prods)
                qa = c_aj2.number_input("Diferença encontrada (+ sobra, - falta)", step=1.0)
                ma = st.text_input("Motivo do Ajuste (Ex: Quebra, Contagem Cíclica)")
                
                if st.form_submit_button("⚖️ Processar Ajuste no Sistema", use_container_width=True):
                    if ia and qa != 0 and ma:
                        cod = ia.split(" - ")[0]
                        desc = ia.split(" - ")[1]
                        tipo = "Ajuste(+)" if qa > 0 else "Ajuste(-)"
                        execute_action("INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, custo_unitario, referencia) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", 
                                       (tipo, datetime.now().date(), "BALANÇO", cod, desc, abs(qa), 0, ma))
                        st.toast("Estoque corrigido com sucesso!", icon="✅")
                        time.sleep(1)
                        st.rerun()

        # --- CADASTRO ---
        with tab4:
            st.markdown("#### ✨ Novo Cadastro de Material")
            with st.container(border=True):
                with st.form("cad_form", clear_on_submit=True):
                    c_cad1, c_cad2, c_cad3 = st.columns([1, 2, 1])
                    nc = c_cad1.text_input("Código (Ex: CIM-01)").upper()
                    nd = c_cad2.text_input("Descrição Completa").title()
                    nu = c_cad3.selectbox("Unidade", ["UNID", "KG", "M", "M2", "M3", "SC", "CX", "L"])
                    
                    if st.form_submit_button("💾 Salvar Novo Produto", use_container_width=True):
                        execute_action("INSERT INTO produtos (codigo, descricao, unidade) VALUES (%s,%s,%s) ON CONFLICT (codigo) DO NOTHING", (nc, nd, nu))
                        st.toast("Produto cadastrado!", icon="✨")
                        time.sleep(1)
                        st.rerun()

    # 4. ADMIN
    elif menu == "⚙️ Auditoria & Logs":
        st.markdown("### ⚙️ Auditoria de Registros")
        
        df_logs = fetch_data("SELECT * FROM movimentacoes ORDER BY id DESC LIMIT 50")
        st.dataframe(df_logs, use_container_width=True, height=500)
        
        st.divider()
        st.markdown("#### Zona de Perigo")
        with st.expander("🗑️ Exclusão de Registros Incorretos"):
            c_del1, c_del2 = st.columns([3,1])
            id_del = c_del1.number_input("Digite o ID do movimento para excluir", min_value=0)
            if c_del2.button("❌ Excluir Definitivamente", type="primary"):
                if id_del > 0: 
                    execute_action("DELETE FROM movimentacoes WHERE id = %s", (id_del,))
                    st.rerun()
