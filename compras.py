import streamlit as st
import psycopg2
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import time

# -----------------------------------------------------------------------------
# 1. CONFIGURAÇÃO PREMIUM
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Portal Amâncio",
    page_icon="favicon.png",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- CSS E DESIGN ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    
    /* Cards KPI */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    
    /* Status Badges */
    .status-badge {
        padding: 4px 8px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 600;
    }
    .status-ok { background-color: #dcfce7; color: #166534; }
    .status-warn { background-color: #fef9c3; color: #854d0e; }
    .status-crit { background-color: #fee2e2; color: #991b1b; }
    
    .stButton>button { border-radius: 8px; font-weight: 600; height: 45px; }
    .stImage { display: flex; justify-content: center; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. VARIÁVEIS E CONEXÃO
# -----------------------------------------------------------------------------
if "carrinho_entrada" not in st.session_state: st.session_state["carrinho_entrada"] = []
if "carrinho_saida" not in st.session_state: st.session_state["carrinho_saida"] = []
if "carrinho_ajuste" not in st.session_state: st.session_state["carrinho_ajuste"] = []
if "authenticated" not in st.session_state: st.session_state["authenticated"] = False

def run_query(query, params=None, fetch_data=True):
    conn = None
    try:
        conn = psycopg2.connect(st.secrets["db_url"], connect_timeout=10, gssencmode="disable")
        if fetch_data: return pd.read_sql(query, conn, params=params)
        else:
            with conn.cursor() as cur:
                cur.execute(query, params)
                conn.commit()
            return True
    except Exception: return pd.DataFrame() if fetch_data else False
    finally:
        if conn: conn.close()

def logo_dinamica(width=150):
    url_preta = "https://media.discordapp.net/attachments/1287152284328919116/1459226633025224879/Design-sem-nome-1.png?ex=696676b4&is=69652534&hm=c105a8bc947734040e988154ecef4e88f57da98dc697ec9337f1df86d58ddcdb&=&format=webp&quality=lossless&width=600&height=300"
    url_branca = "https://media.discordapp.net/attachments/1287152284328919116/1459226633025224879/Design-sem-nome-1.png?ex=696676b4&is=69652534&hm=c105a8bc947734040e988154ecef4e88f57da98dc697ec9337f1df86d58ddcdb&=&format=webp&quality=lossless&width=600&height=300"
    st.markdown(f"""
    <div style="display: flex; justify-content: center; margin-bottom: 15px;">
        <img src="{url_preta}" style="width: {width}px; filter: drop-shadow(0px 4px 6px rgba(0,0,0,0.1));">
    </div>""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 3. ENGINE DE DADOS
# -----------------------------------------------------------------------------
df_prods = run_query("SELECT codigo, descricao, unidade FROM produtos ORDER BY descricao")
df_movs = run_query("SELECT * FROM movimentacoes ORDER BY data DESC, id DESC")

saldo_atual = pd.DataFrame(columns=['Cod', 'Produto', 'Unid', 'Saldo', 'CustoMedio', 'ValorTotal', 'Status'])

if not df_prods.empty:
    if not df_movs.empty:
        df_calc = df_movs.copy()
        df_calc['fator'] = df_calc['tipo'].apply(lambda x: 1 if x in ['Entrada', 'Ajuste(+)'] else -1)
        df_calc['qtd_real'] = df_calc['quantidade'] * df_calc['fator']
        saldos = df_calc.groupby('codigo')['qtd_real'].sum().reset_index()

        entradas = df_movs[df_movs['tipo'] == 'Entrada'].copy()
        if not entradas.empty:
            entradas['total_gasto'] = entradas['quantidade'] * entradas['custo_unitario']
            custos = entradas.groupby('codigo')[['quantidade', 'total_gasto']].sum().reset_index()
            custos['custo_medio'] = custos['total_gasto'] / custos['quantidade']
            saldos = pd.merge(saldos, custos[['codigo', 'custo_medio']], on='codigo', how='left')
        
        saldo_atual = pd.merge(df_prods, saldos, on='codigo', how='left').fillna(0)
        if 'custo_medio' not in saldo_atual.columns: saldo_atual['custo_medio'] = 0
        saldo_atual['valor_estoque'] = saldo_atual['qtd_real'] * saldo_atual['custo_medio']
    else:
        saldo_atual = df_prods.copy()
        saldo_atual[['Saldo', 'custo_medio', 'valor_estoque']] = 0
    
    # Padronização de nomes (Title Case)
    saldo_atual['descricao'] = saldo_atual['descricao'].str.title()
    saldo_atual.rename(columns={'qtd_real': 'Saldo', 'descricao': 'Produto', 'unidade': 'Unid', 'codigo': 'Cod'}, inplace=True)
    
    # Lógica do Semáforo (Status)
    def definir_status(row):
        if row['Saldo'] <= 0: return "🔴 Zerado"
        elif row['Saldo'] < 10: return "🟡 Baixo" # Exemplo: menos de 10 é baixo
        else: return "🟢 Ok"
    
    saldo_atual['Status'] = saldo_atual.apply(definir_status, axis=1)

# -----------------------------------------------------------------------------
# 4. LOGIN
# -----------------------------------------------------------------------------
if not st.session_state["authenticated"]:
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        st.write(""); st.write("")
        logo_dinamica(width=150)
        st.markdown("<h1 style='text-align: center; color: #1e293b; font-size: 24px;'>Portal Amâncio</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #64748b; font-size: 14px;'>Gestão de Estoque Inteligente</p>", unsafe_allow_html=True)
        
        with st.form("login"):
            u = st.text_input("Login")
            p = st.text_input("Chave de Acesso", type="password")
            if st.form_submit_button("Autenticar", type="primary"):
                if u == st.secrets["auth"]["username"] and p == st.secrets["auth"]["password"]:
                    st.session_state["authenticated"] = True
                    st.rerun()
                else: st.error("Acesso Negado")
        
        st.markdown("---")
        with st.expander("🔍 Consulta Rápida (Estoque)"):
            if not saldo_atual.empty:
                busca = st.text_input("Material:", placeholder="Ex: Cimento")
                df_view = saldo_atual[['Produto', 'Saldo', 'Unid', 'Status']]
                if busca: df_view = df_view[df_view['Produto'].str.contains(busca, case=False)]
                st.dataframe(df_view, hide_index=True, use_container_width=True)
            else: st.info("Sem dados.")

# -----------------------------------------------------------------------------
# 5. SISTEMA (LOGADO)
# -----------------------------------------------------------------------------
else:
    with st.sidebar:
        logo_dinamica(width=300)
        st.markdown(f"<div style='text-align: center; color: gray; margin-bottom: 20px;'>Olá, {st.secrets['auth']['username'].title()}</div>", unsafe_allow_html=True)
        menu = st.radio("", ["📊 BI & Dashboard", "📦 Estoque (Semáforo)", "🔄 Operações", "⚙️ Auditoria"], label_visibility="collapsed")
        st.write(""); st.write("")
        if st.button("Sair"):
            st.session_state["authenticated"] = False
            st.rerun()

    # --- DASHBOARD ---
    if menu == "📊 BI & Dashboard":
        st.title("Business Intelligence")
        st.markdown(f"Posição do Estoque: *{datetime.now().strftime('%d/%m/%Y')}*")
        
        if not saldo_atual.empty:
            total_val = saldo_atual['valor_estoque'].sum()
            criticos = len(saldo_atual[saldo_atual['Saldo'] <= 0])
            top_item = saldo_atual.sort_values('valor_estoque', ascending=False).iloc[0]['Produto'] if total_val > 0 else "-"
            
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Capital Imobilizado", f"R$ {total_val:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), delta="Total Ativos")
            k2.metric("Mix de Produtos", len(saldo_atual))
            k3.metric("Item Curva A", top_item)
            k4.metric("Ruptura (Estoque 0)", criticos, delta="- Atenção", delta_color="inverse")
            st.write("")

            g1, g2 = st.columns([2, 1])
            with g1:
                st.subheader("Pareto Financeiro (Top 10)")
                if total_val > 0:
                    df_graf = saldo_atual.nlargest(10, 'valor_estoque')
                    fig = px.bar(df_graf, x='Produto', y='valor_estoque', text_auto='.2s', color='valor_estoque', color_continuous_scale='Blues')
                    fig.update_layout(xaxis_title="", yaxis_title="R$", plot_bgcolor="white")
                    st.plotly_chart(fig, use_container_width=True)
                else: st.info("Dados financeiros insuficientes.")
            
            with g2:
                st.subheader("Saúde do Estoque")
                status_counts = saldo_atual['Status'].value_counts()
                fig2 = px.pie(values=status_counts.values, names=status_counts.index, hole=0.5, color_discrete_sequence=['#ef4444', '#22c55e', '#eab308'])
                st.plotly_chart(fig2, use_container_width=True)

    # --- INVENTÁRIO (SEMÁFORO) ---
    elif menu == "📦 Estoque (Semáforo)":
        c1, c2 = st.columns([4, 1])
        with c1: st.title("Controle de Estoque")
        with c2: 
            if not saldo_atual.empty:
                csv = saldo_atual.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Excel / CSV", csv, "estoque_amancio.csv", "text/csv", type="primary")

        if not saldo_atual.empty:
            busca = st.text_input("Filtro rápido:", placeholder="Digite para buscar...")
            df_show = saldo_atual.copy()
            if busca: df_show = df_show[df_show['Produto'].str.contains(busca, case=False)]
            
            # Tabela com Coluna de Status Visual
            st.dataframe(
                df_show[['Cod', 'Produto', 'Status', 'Saldo', 'Unid', 'custo_medio', 'valor_estoque']],
                use_container_width=True,
                hide_index=True,
                height=600,
                column_config={
                    "Status": st.column_config.TextColumn("Status", width="small"),
                    "Saldo": st.column_config.NumberColumn("Qtd", format="%.2f"),
                    "custo_medio": st.column_config.NumberColumn("Custo Unit", format="R$ %.2f"),
                    "valor_estoque": st.column_config.NumberColumn("Total R$", format="R$ %.2f"),
                }
            )
        else: st.warning("Banco de dados vazio.")

    # --- OPERAÇÕES ---
    elif menu == "🔄 Operações":
        st.title("Central de Lançamentos")
        tab1, tab2, tab3, tab4 = st.tabs(["📥 COMPRAS", "📤 OBRAS", "🔧 AJUSTE", "🆕 CADASTRO"])
        opcoes = [f"{r['codigo']} - {r['descricao']}" for i, r in df_prods.iterrows()] if not df_prods.empty else []

        # ENTRADA
        with tab1:
            c1, c2 = st.columns([1, 2])
            with c1:
                st.info("Novo Item na Nota")
                with st.form("ae"):
                    ie = st.selectbox("Item", opcoes)
                    qe = st.number_input("Qtd", 0.01)
                    ve = st.number_input("Custo Unit. (R$)", 0.0)
                    if st.form_submit_button("⬇️ Adicionar"):
                        if ie: 
                            st.session_state["carrinho_entrada"].append({"cod": ie.split(" - ")[0], "desc": ie.split(" - ")[1].title(), "qtd": qe, "custo": ve, "total": qe*ve})
                            st.rerun()
            with c2:
                if st.session_state["carrinho_entrada"]:
                    df_c = pd.DataFrame(st.session_state["carrinho_entrada"])
                    st.dataframe(df_c, hide_index=True, use_container_width=True, column_config={"custo": st.column_config.NumberColumn("R$", format="%.2f")})
                    st.markdown(f"**Total NF: R$ {df_c['total'].sum():,.2f}**")
                    with st.form("fe"):
                        nf = st.text_input("Fornecedor / Nº Nota")
                        if st.form_submit_button("✅ Concluir Entrada", type="primary"):
                            if nf:
                                for i in st.session_state["carrinho_entrada"]:
                                    run_query("INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, custo_unitario, referencia) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", ("Entrada", datetime.now().date(), "CENTRAL", i['cod'], i['desc'], i['qtd'], i['custo'], nf), False)
                                st.session_state["carrinho_entrada"] = []
                                st.toast("Sucesso!", icon="🚀"); time.sleep(1); st.rerun()
                    if st.button("Limpar", key="cle"): st.session_state["carrinho_entrada"] = []; st.rerun()
                else: st.caption("Carrinho vazio.")

        # SAÍDA
        with tab2:
            c1, c2 = st.columns([1, 2])
            with c1:
                st.warning("Novo Item para Obra")
                with st.form("as_"):
                    is_ = st.selectbox("Item", opcoes, key="si")
                    qs = st.number_input("Qtd", 0.01, key="sq")
                    if st.form_submit_button("⬇️ Adicionar"):
                        if is_:
                            st.session_state["carrinho_saida"].append({"cod": is_.split(" - ")[0], "desc": is_.split(" - ")[1].title(), "qtd": qs})
                            st.rerun()
            with c2:
                if st.session_state["carrinho_saida"]:
                    st.dataframe(pd.DataFrame(st.session_state["carrinho_saida"]), hide_index=True, use_container_width=True)
                    with st.form("fs"):
                        ob = st.text_input("Obra de Destino")
                        if st.form_submit_button("📤 Concluir Saída", type="primary"):
                            if ob:
                                for i in st.session_state["carrinho_saida"]:
                                    run_query("INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, custo_unitario) VALUES (%s,%s,%s,%s,%s,%s,%s)", ("Saída", datetime.now().date(), ob, i['cod'], i['desc'], i['qtd'], 0), False)
                                st.session_state["carrinho_saida"] = []
                                st.toast("Sucesso!", icon="🚛"); time.sleep(1); st.rerun()
                    if st.button("Limpar", key="cls"): st.session_state["carrinho_saida"] = []; st.rerun()
                else: st.caption("Romaneio vazio.")

        # AJUSTE
        with tab3:
            c1, c2 = st.columns([1, 2])
            with c1:
                st.error("Item de Balanço")
                with st.form("aa"):
                    ia = st.selectbox("Item", opcoes, key="ai")
                    qa = st.number_input("Diferença (+/-)", step=1.0, key="aq")
                    ma = st.text_input("Motivo", key="am")
                    if st.form_submit_button("⬇️ Adicionar"):
                        if ia and qa != 0:
                            st.session_state["carrinho_ajuste"].append({"cod": ia.split(" - ")[0], "desc": ia.split(" - ")[1].title(), "qtd": qa, "motivo": ma})
                            st.rerun()
            with c2:
                if st.session_state["carrinho_ajuste"]:
                    st.dataframe(pd.DataFrame(st.session_state["carrinho_ajuste"]), hide_index=True, use_container_width=True)
                    if st.button("⚖️ Processar Balanço", type="primary"):
                        for i in st.session_state["carrinho_ajuste"]:
                            tipo = "Ajuste(+)" if i['qtd'] > 0 else "Ajuste(-)"
                            run_query("INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, custo_unitario, referencia) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", (tipo, datetime.now().date(), "BALANÇO", i['cod'], i['desc'], abs(i['qtd']), 0, i['motivo']), False)
                        st.session_state["carrinho_ajuste"] = []
                        st.toast("Ajustado!", icon="✅"); time.sleep(1); st.rerun()
                    if st.button("Limpar", key="cla"): st.session_state["carrinho_ajuste"] = []; st.rerun()
                else: st.caption("Nenhum ajuste.")

        # CADASTRO
        with tab4:
            st.markdown("##### Cadastro Master")
            with st.form("cn"):
                c1, c2, c3 = st.columns([1, 2, 1])
                cod = c1.text_input("Código (Ex: ELE-01)").upper()
                des = c2.text_input("Descrição").title()
                und = c3.selectbox("Und", ["UNID", "KG", "M", "M2", "M3", "SC", "CX", "L"])
                if st.form_submit_button("💾 Salvar no Sistema"):
                    run_query("INSERT INTO produtos (codigo, descricao, unidade) VALUES (%s,%s,%s) ON CONFLICT (codigo) DO NOTHING", (cod, des, und), False)
                    st.toast("Cadastrado!", icon="✨"); time.sleep(1); st.rerun()

    # --- AUDITORIA (HISTÓRICO) ---
    elif menu == "⚙️ Auditoria":
        st.title("Log de Auditoria")
        
        tab_log, tab_risk = st.tabs(["📜 Movimentações", "🗑️ Zona de Perigo"])
        
        with tab_log:
            # FILTRO DE DATA (A NOVIDADE)
            c1, c2 = st.columns(2)
            d_inicio = c1.date_input("De", datetime.now().date() - timedelta(days=30))
            d_fim = c2.date_input("Até", datetime.now().date())
            
            if not df_movs.empty:
                # Converte para data apenas se necessário e filtra
                mask = (df_movs['data'] >= d_inicio) & (df_movs['data'] <= d_fim)
                df_filtered = df_movs.loc[mask]
                st.dataframe(df_filtered, use_container_width=True, height=500)
            else: st.info("Sem registros.")

        with tab_risk:
            st.error("Ações Irreversíveis")
            id_del = st.number_input("ID do Registro", min_value=0)
            if st.button("❌ Excluir Registro (Admin)", type="primary"):
                if id_del > 0:
                    run_query("DELETE FROM movimentacoes WHERE id = %s", (id_del,), False)
                    st.toast("Registro removido.", icon="🗑️"); time.sleep(1); st.rerun()








