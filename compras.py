import streamlit as st
import psycopg2
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time

# -----------------------------------------------------------------------------
# 1. CONFIGURAÇÃO AVANÇADA DA PÁGINA
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Amâncio Gestão Pro",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -----------------------------------------------------------------------------
# 2. ESTILIZAÇÃO CSS PROFISSIONAL
# -----------------------------------------------------------------------------
st.markdown("""
    <style>
    /* Cores e Fontes Globais */
    :root {
        --primary-color: #2563eb;
        --background-light: #f8fafc;
        --text-dark: #1e293b;
    }
    
    /* Cards de Métricas */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    
    /* Botões Personalizados */
    .stButton>button {
        width: 100%;
        border-radius: 6px;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    /* Tabela de Dados */
    .stDataFrame {
        border: 1px solid #e2e8f0;
        border-radius: 8px;
    }
    
    /* Rodapé */
    .footer {
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background-color: #f1f5f9;
        color: #64748b;
        text-align: center;
        padding: 10px;
        font-size: 0.8rem;
        border-top: 1px solid #e2e8f0;
        z-index: 100;
    }
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 3. GERENCIAMENTO DE CONEXÃO (BLINDADO)
# -----------------------------------------------------------------------------
# Cache de conexão para performance (TTL = Time To Live de 10 segundos)
@st.cache_resource(ttl=10) 
def get_db_connection():
    """Conecta ao Supabase via Pooler ignorando erros de IPv6"""
    try:
        return psycopg2.connect(
            st.secrets["db_url"],
            connect_timeout=10,
            gssencmode="disable" # O Segredo do sucesso no plano Free
        )
    except Exception as e:
        st.error(f"🔌 Falha crítica de conexão: {e}")
        return None

def run_query(query, params=None, fetch_data=True):
    """Executa queries com tratamento de erro e fechamento seguro"""
    conn = get_db_connection()
    if conn:
        try:
            if fetch_data:
                df = pd.read_sql(query, conn, params=params)
                conn.close()
                return df
            else:
                cur = conn.cursor()
                cur.execute(query, params)
                conn.commit()
                cur.close()
                conn.close()
                return True
        except Exception as e:
            st.error(f"Erro SQL: {e}")
            if conn: conn.close()
            return None
    return None

# -----------------------------------------------------------------------------
# 4. AUTENTICAÇÃO
# -----------------------------------------------------------------------------
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

def login_screen():
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("<h2 style='text-align: center;'>🔐 Acesso Restrito</h2>", unsafe_allow_html=True)
        with st.form("login_form"):
            u = st.text_input("Usuário")
            p = st.text_input("Senha", type="password")
            if st.form_submit_button("Acessar Painel"):
                if u == st.secrets["auth"]["username"] and p == st.secrets["auth"]["password"]:
                    st.session_state["authenticated"] = True
                    st.toast("Login realizado com sucesso!", icon="✅")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Credenciais inválidas.")

# -----------------------------------------------------------------------------
# 5. SISTEMA PRINCIPAL
# -----------------------------------------------------------------------------
def main_system():
    # --- SIDEBAR ---
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/1063/1063196.png", width=70)
        st.markdown("### **Amâncio Obras**")
        st.caption(f"Usuário: {st.secrets['auth']['username'].upper()}")
        st.divider()
        
        menu = st.radio(
            "Navegação", 
            ["📊 Dashboard", "📦 Inventário", "🔄 Operações", "⚙️ Gerenciamento"],
            index=0
        )
        
        st.divider()
        if st.button("Sair do Sistema"):
            st.session_state["authenticated"] = False
            st.rerun()

    # --- DADOS GERAIS (Carregamento Único) ---
    df_prods = run_query("SELECT codigo, descricao, unidade FROM produtos ORDER BY descricao")
    df_movs = run_query("SELECT * FROM movimentacoes ORDER BY data DESC, id DESC")

    # Tratamento de dados para Saldos
    saldo_atual = pd.DataFrame()
    if df_prods is not None and not df_prods.empty:
        if df_movs is not None and not df_movs.empty:
            df_calc = df_movs.copy()
            # Lógica: Entrada/Ajuste(+) soma, Saída/Ajuste(-) subtrai
            df_calc['fator'] = df_calc['tipo'].apply(lambda x: 1 if x in ['Entrada', 'Ajuste(+)'] else -1)
            df_calc['qtd_real'] = df_calc['quantidade'] * df_calc['fator']
            
            saldos = df_calc.groupby('codigo')['qtd_real'].sum().reset_index()
            saldo_atual = pd.merge(df_prods, saldos, on='codigo', how='left').fillna(0)
        else:
            saldo_atual = df_prods.copy()
            saldo_atual['qtd_real'] = 0
            
        saldo_atual.rename(columns={'qtd_real': 'Saldo', 'descricao': 'Produto', 'unidade': 'Unid', 'codigo': 'Cod'}, inplace=True)

    # --- PÁGINA: DASHBOARD ---
    if menu == "📊 Dashboard":
        st.title("📊 Visão Geral da Obra")
        st.markdown("Resumo executivo de movimentações e estoque.")
        
        if not saldo_atual.empty:
            # 1. KPIs
            c1, c2, c3, c4 = st.columns(4)
            with c1: st.metric("Itens Cadastrados", len(df_prods))
            with c2: st.metric("Movimentações Totais", len(df_movs) if df_movs is not None else 0)
            with c3: st.metric("Itens Zerados", len(saldo_atual[saldo_atual['Saldo'] <= 0]), delta_color="inverse")
            with c4: st.metric("Última Atualização", datetime.now().strftime("%H:%M"))

            st.markdown("---")

            # 2. GRÁFICOS
            g1, g2 = st.columns([2, 1])
            
            with g1:
                st.subheader("📈 Top 10 Itens em Estoque")
                top_10 = saldo_atual.nlargest(10, 'Saldo')
                fig_bar = px.bar(top_10, x='Produto', y='Saldo', color='Saldo', 
                               text_auto=True, color_continuous_scale='Blues')
                fig_bar.update_layout(xaxis_title=None, height=350)
                st.plotly_chart(fig_bar, use_container_width=True)
            
            with g2:
                st.subheader("🍩 Composição")
                if df_movs is not None and not df_movs.empty:
                    mov_tipo = df_movs['tipo'].value_counts().reset_index()
                    fig_pie = px.pie(mov_tipo, values='count', names='tipo', hole=0.4, color_discrete_sequence=px.colors.sequential.RdBu)
                    fig_pie.update_layout(height=350)
                    st.plotly_chart(fig_pie, use_container_width=True)
                else:
                    st.info("Sem dados para gráfico.")

    # --- PÁGINA: INVENTÁRIO ---
    elif menu == "📦 Inventário":
        st.title("📦 Controle de Estoque")
        
        col_filtro, col_download = st.columns([3, 1])
        with col_filtro:
            busca = st.text_input("🔍 Buscar Material (Nome ou Código):", placeholder="Digite para filtrar...")
        
        if not saldo_atual.empty:
            df_show = saldo_atual.copy()
            
            # Filtro de busca
            if busca:
                df_show = df_show[
                    df_show['Produto'].str.contains(busca, case=False) | 
                    df_show['Cod'].str.contains(busca, case=False)
                ]
            
            # Estilização Condicional (Highlight em itens zerados)
            st.dataframe(
                df_show,
                use_container_width=True,
                column_config={
                    "Saldo": st.column_config.NumberColumn(
                        "Saldo Atual",
                        help="Quantidade física em estoque",
                        format="%.2f"
                    )
                },
                hide_index=True
            )
            
            with col_download:
                st.download_button(
                    "📥 Baixar Relatório (CSV)",
                    df_show.to_csv(index=False).encode('utf-8'),
                    "estoque_amancio.csv",
                    "text/csv"
                )
        else:
            st.info("Nenhum produto cadastrado.")

    # --- PÁGINA: OPERAÇÕES ---
    elif menu == "🔄 Operações":
        st.title("🔄 Movimentação de Materiais")
        
        tab1, tab2, tab3 = st.tabs(["📥 Entrada (Compra)", "📤 Saída (Obra)", "🆕 Novo Cadastro"])
        
        # ABA 1: ENTRADA
        with tab1:
            with st.form("form_entrada", clear_on_submit=True):
                c_sel, c_qtd = st.columns([3, 1])
                lista_prods = [f"{r['codigo']} - {r['descricao']} ({r['unidade']})" for i, r in df_prods.iterrows()] if not df_prods.empty else []
                item = c_sel.selectbox("Selecione o Material", lista_prods)
                qtd = c_qtd.number_input("Quantidade", min_value=0.01, step=1.0)
                
                c_det1, c_det2 = st.columns(2)
                forn = c_det1.text_input("Fornecedor / Origem")
                nf = c_det2.text_input("Nota Fiscal / Doc")
                obs = st.text_area("Observações")
                
                if st.form_submit_button("✅ Registrar Entrada"):
                    if item:
                        cod = item.split(" - ")[0]
                        desc = item.split(" - ")[1].split(" (")[0]
                        run_query(
                            "INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, referencia) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                            params=("Entrada", datetime.now().date(), "Estoque Central", cod, desc, qtd, f"Forn: {forn} | NF: {nf} | Obs: {obs}"),
                            fetch_data=False
                        )
                        st.success(f"Entrada de {qtd} para {desc} registrada!")
                        time.sleep(1)
                        st.rerun()

        # ABA 2: SAÍDA
        with tab2:
            with st.form("form_saida", clear_on_submit=True):
                c_sel, c_qtd = st.columns([3, 1])
                item_s = c_sel.selectbox("Material para Saída", lista_prods, key="sel_saida")
                qtd_s = c_qtd.number_input("Quantidade", min_value=0.01, step=1.0, key="qtd_saida")
                
                c_det1, c_det2 = st.columns(2)
                resp = c_det1.text_input("Responsável Retirada")
                dest = c_det2.text_input("Local de Aplicação (Obra)")
                
                if st.form_submit_button("📤 Registrar Saída"):
                    if item_s:
                        cod = item_s.split(" - ")[0]
                        desc = item_s.split(" - ")[1].split(" (")[0]
                        # Verificar saldo antes (Opcional, mas profissional)
                        saldo_item = saldo_atual.loc[saldo_atual['Cod'] == cod, 'Saldo'].values[0] if not saldo_atual.empty else 0
                        
                        if saldo_item >= qtd_s:
                            run_query(
                                "INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, referencia) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                                params=("Saída", datetime.now().date(), dest, cod, desc, qtd_s, f"Resp: {resp}"),
                                fetch_data=False
                            )
                            st.success(f"Saída de {qtd_s} registrada!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"Saldo insuficiente! Disponível: {saldo_item:.2f}")

        # ABA 3: CADASTRO
        with tab3:
            st.info("Cadastre novos materiais para que apareçam nas listas de entrada e saída.")
            with st.form("form_novo"):
                c1, c2, c3 = st.columns([1, 2, 1])
                new_cod = c1.text_input("Código (Ex: ELE-01)").upper()
                new_desc = c2.text_input("Descrição (Ex: Fio 6mm)").upper()
                new_unid = c3.selectbox("Unidade", ["UNID", "M", "KG", "L", "CX", "PCT", "M2", "M3"])
                
                if st.form_submit_button("💾 Salvar Novo Material"):
                    if new_cod and new_desc:
                        ok = run_query(
                            "INSERT INTO produtos (codigo, descricao, unidade) VALUES (%s, %s, %s) ON CONFLICT (codigo) DO NOTHING",
                            params=(new_cod, new_desc, new_unid),
                            fetch_data=False
                        )
                        if ok: 
                            st.toast("Material Cadastrado!", icon="🎉")
                            time.sleep(1)
                            st.rerun()
                    else:
                        st.warning("Preencha Código e Descrição.")

    # --- PÁGINA: GERENCIAMENTO ---
    elif menu == "⚙️ Gerenciamento":
        st.title("⚙️ Histórico e Ajustes")
        
        tabs = st.tabs(["📜 Histórico Completo", "🔧 Ajuste de Balanço"])
        
        with tabs[0]:
            if df_movs is not None:
                st.dataframe(df_movs, use_container_width=True, hide_index=True)
        
        with tabs[1]:
            st.warning("Use esta área apenas para correções de inventário (Balanço).")
            with st.form("form_ajuste"):
                lista_prods = [f"{r['codigo']} - {r['descricao']}" for i, r in df_prods.iterrows()] if not df_prods.empty else []
                item_aj = st.selectbox("Selecione Material", lista_prods)
                qtd_fisica = st.number_input("Quantidade REAL contada", min_value=0.0)
                motivo = st.text_input("Motivo da correção")
                
                if st.form_submit_button("⚠️ Ajustar Saldo"):
                    cod = item_aj.split(" - ")[0]
                    # Calc diferença
                    saldo_sistema = saldo_atual.loc[saldo_atual['Cod'] == cod, 'Saldo'].values[0]
                    diff = qtd_fisica - saldo_sistema
                    
                    if diff != 0:
                        tipo_aj = "Ajuste(+)" if diff > 0 else "Ajuste(-)"
                        run_query(
                            "INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, referencia) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                            params=(tipo_aj, datetime.now().date(), "BALANÇO", cod, item_aj.split(" - ")[1], abs(diff), motivo),
                            fetch_data=False
                        )
                        st.success("Estoque corrigido!")
                        time.sleep(1.5)
                        st.rerun()
                    else:
                        st.info("O saldo físico é igual ao do sistema. Nada a ajustar.")

    # Footer
    st.markdown('<div class="footer">Amâncio Obras • Sistema de Gestão Profissional v2.0</div>', unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 6. EXECUÇÃO
# -----------------------------------------------------------------------------
if st.session_state["authenticated"]:
    main_system()
else:
    login_screen()
