import streamlit as st
import psycopg2
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import time

# -----------------------------------------------------------------------------
# 1. CONFIGURAÇÃO PREMIUM
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Amâncio ERP",
    page_icon="🏗️",
    layout="wide", # Tela cheia para o Painel ficar bonito
    initial_sidebar_state="collapsed"
)

# --- CSS PROFISSIONAL (A MÁGICA VISUAL) ---
st.markdown("""
    <style>
    /* Importando fonte moderna */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* Cards de Métricas (KPIs) */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        transition: transform 0.2s;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.1);
        border-color: #2563eb;
    }

    /* Ajuste de Tabelas */
    .stDataFrame {
        border: 1px solid #f0f0f0;
        border-radius: 10px;
    }

    /* Botões */
    .stButton>button {
        border-radius: 8px;
        font-weight: 600;
        height: 45px;
    }
    
    /* Login Box Centralizado */
    .login-container {
        max-width: 400px;
        margin: 0 auto;
        padding: 40px;
        background: white;
        border-radius: 20px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.1);
        text-align: center;
    }
    
    /* Esconder menu padrão do Streamlit para parecer App Nativo */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Centralizar Imagens */
    .stImage { display: flex; justify-content: center; }
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. VARIÁVEIS DE SESSÃO & CONEXÃO
# -----------------------------------------------------------------------------
if "carrinho_entrada" not in st.session_state: st.session_state["carrinho_entrada"] = []
if "carrinho_saida" not in st.session_state: st.session_state["carrinho_saida"] = []
if "carrinho_ajuste" not in st.session_state: st.session_state["carrinho_ajuste"] = []
if "authenticated" not in st.session_state: st.session_state["authenticated"] = False

def run_query(query, params=None, fetch_data=True):
    conn = None
    try:
        conn = psycopg2.connect(st.secrets["db_url"], connect_timeout=10, gssencmode="disable")
        if fetch_data:
            df = pd.read_sql(query, conn, params=params)
            return df
        else:
            with conn.cursor() as cur:
                cur.execute(query, params)
                conn.commit()
            return True
    except Exception:
        return pd.DataFrame() if fetch_data else False
    finally:
        if conn: conn.close()

def logo_dinamica(width=150):
    # Insira aqui os links das suas logos reais
    url_preta = "https://cdn-icons-png.flaticon.com/512/1063/1063196.png" # Logo para fundo claro
    url_branca = "https://cdn-icons-png.flaticon.com/512/1063/1063196.png" # Logo para fundo escuro
    
    st.markdown(f"""
    <div style="display: flex; justify-content: center; margin-bottom: 15px;">
        <img src="{url_preta}" style="width: {width}px; filter: drop-shadow(0px 4px 6px rgba(0,0,0,0.1));">
    </div>
    """, unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 3. INTELIGÊNCIA DE DADOS (ENGINE)
# -----------------------------------------------------------------------------
df_prods = run_query("SELECT codigo, descricao, unidade FROM produtos ORDER BY descricao")
df_movs = run_query("SELECT * FROM movimentacoes ORDER BY data DESC, id DESC")

# Lógica Financeira Robusta
saldo_atual = pd.DataFrame(columns=['Cod', 'Produto', 'Unid', 'Saldo', 'CustoMedio', 'ValorTotal'])

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
    
    saldo_atual.rename(columns={'qtd_real': 'Saldo', 'descricao': 'Produto', 'unidade': 'Unid', 'codigo': 'Cod'}, inplace=True)
    # Reordenar colunas para visualização
    saldo_atual = saldo_atual[['Cod', 'Produto', 'Unid', 'Saldo', 'custo_medio', 'valor_estoque']]

# -----------------------------------------------------------------------------
# 4. TELA DE LOGIN (Clean & Minimalista)
# -----------------------------------------------------------------------------
if not st.session_state["authenticated"]:
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        st.write(""); st.write(""); st.write("") # Espaçamento
        logo_dinamica(width=120)
        st.markdown("<h1 style='text-align: center; color: #1e293b; font-size: 24px;'>Portal Amâncio</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #64748b; font-size: 14px;'>Acesso Administrativo Seguro</p>", unsafe_allow_html=True)
        
        with st.form("login"):
            u = st.text_input("Usuário", placeholder="ID Corporativo")
            p = st.text_input("Senha", type="password", placeholder="••••••••")
            
            if st.form_submit_button("Entrar", type="primary"):
                if u == st.secrets["auth"]["username"] and p == st.secrets["auth"]["password"]:
                    st.session_state["authenticated"] = True
                    st.rerun()
                else:
                    st.error("Credenciais Inválidas")
        
        st.markdown("---")
        with st.expander("🔍 Consulta Pública (Engenharia)"):
            if not saldo_atual.empty:
                busca = st.text_input("Buscar Item:", placeholder="Digite o nome...")
                df_view = saldo_atual[['Produto', 'Saldo', 'Unid']]
                if busca: df_view = df_view[df_view['Produto'].str.contains(busca, case=False)]
                st.dataframe(df_view, hide_index=True, use_container_width=True)
            else:
                st.info("Sistema aguardando dados.")

# -----------------------------------------------------------------------------
# 5. DASHBOARD EXECUTIVO (A Visão do Diretor)
# -----------------------------------------------------------------------------
else:
    # --- SIDEBAR PROFISSIONAL ---
    with st.sidebar:
        logo_dinamica(width=100)
        st.markdown(f"<div style='text-align: center; color: gray; margin-bottom: 20px;'>Olá, {st.secrets['auth']['username'].title()}</div>", unsafe_allow_html=True)
        
        menu = st.radio("", ["📊 Dashboard", "📦 Inventário", "🔄 Operações", "⚙️ Gerenciamento"], label_visibility="collapsed")
        
        st.write(""); st.write("") # Spacer
        if st.button("Sair do Sistema"):
            st.session_state["authenticated"] = False
            st.rerun()

    # --- PÁGINA: DASHBOARD ---
    if menu == "📊 Dashboard":
        st.title("Visão Geral da Obra")
        st.markdown(f"Atualizado em: *{datetime.now().strftime('%d/%m/%Y às %H:%M')}*")
        st.write("")

        if not saldo_atual.empty:
            # 1. CARDS DE KPI (RENTABILIDADE)
            total_val = saldo_atual['valor_estoque'].sum()
            criticos = len(saldo_atual[saldo_atual['Saldo'] <= 0])
            top_item = saldo_atual.sort_values('valor_estoque', ascending=False).iloc[0]['Produto'] if total_val > 0 else "-"
            
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Valor em Estoque", f"R$ {total_val:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), delta="Capital Imobilizado")
            k2.metric("Itens Cadastrados", len(saldo_atual), delta="Mix de Produtos")
            k3.metric("Item Mais Valioso", top_item)
            k4.metric("Estoque Crítico", criticos, delta="- Reposição Necessária", delta_color="inverse")

            st.write("") # Spacer

            # 2. GRÁFICOS LADO A LADO
            g1, g2 = st.columns([2, 1])
            
            with g1:
                st.subheader("💰 Curva ABC (Onde está o dinheiro)")
                if total_val > 0:
                    df_graf = saldo_atual.nlargest(8, 'valor_estoque')
                    fig = px.bar(df_graf, x='Produto', y='valor_estoque', text_auto='.2s', 
                                 color='valor_estoque', color_continuous_scale='Blues')
                    fig.update_layout(xaxis_title="", yaxis_title="Reais (R$)", plot_bgcolor="white")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Registre entradas com valor para ver o gráfico financeiro.")
            
            with g2:
                st.subheader("📦 Movimentação Recente")
                if not df_movs.empty:
                    mov_counts = df_movs['tipo'].value_counts()
                    fig2 = px.pie(values=mov_counts.values, names=mov_counts.index, hole=0.6, 
                                  color_discrete_sequence=px.colors.qualitative.Pastel)
                    fig2.update_layout(showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                    st.plotly_chart(fig2, use_container_width=True)
                else:
                    st.info("Sem dados.")

    # --- PÁGINA: INVENTÁRIO (TABELA INTELIGENTE) ---
    elif menu == "📦 Inventário":
        c1, c2 = st.columns([4, 1])
        with c1: st.title("Estoque & Custos")
        with c2: 
            # Botão de Exportação para o Diretor
            if not saldo_atual.empty:
                csv = saldo_atual.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Baixar Relatório", csv, "estoque_amancio.csv", "text/csv", type="primary")

        if not saldo_atual.empty:
            busca = st.text_input("🔍 Filtrar material...", placeholder="Ex: Cimento, Areia, Tubo...")
            df_show = saldo_atual.copy()
            if busca: df_show = df_show[df_show['Produto'].str.contains(busca, case=False)]
            
            st.dataframe(
                df_show,
                use_container_width=True,
                hide_index=True,
                height=600,
                column_config={
                    "Saldo": st.column_config.NumberColumn("Qtd Física", format="%.2f"),
                    "custo_medio": st.column_config.NumberColumn("Custo Médio", format="R$ %.2f"),
                    "valor_estoque": st.column_config.NumberColumn("Valor Total", format="R$ %.2f"),
                    "Cod": st.column_config.TextColumn("Código", width="small"),
                    "Unid": st.column_config.TextColumn("Und", width="small"),
                }
            )
        else:
            st.warning("Nenhum dado encontrado.")

    # --- PÁGINA: OPERAÇÕES (CAIXA RÁPIDO) ---
    elif menu == "🔄 Operações":
        st.title("Central de Operações")
        
        tab1, tab2, tab3, tab4 = st.tabs(["📥 ENTRADA (Compra)", "📤 SAÍDA (Obra)", "🔧 AJUSTE (Balanço)", "🆕 CADASTRO"])
        opcoes = [f"{r['codigo']} - {r['descricao']}" for i, r in df_prods.iterrows()] if not df_prods.empty else []

        # -- ENTRADA --
        with tab1:
            col_form, col_list = st.columns([1, 2])
            with col_form:
                st.markdown("##### Novo Item")
                with st.form("add_e"):
                    ie = st.selectbox("Material", opcoes)
                    qe = st.number_input("Quantidade", 0.01)
                    ve = st.number_input("Preço Unit. (R$)", 0.0)
                    if st.form_submit_button("⬇️ Adicionar"):
                        if ie:
                            st.session_state["carrinho_entrada"].append({
                                "cod": ie.split(" - ")[0], "desc": ie.split(" - ")[1], "qtd": qe, "custo": ve, "total": qe*ve
                            })
                            st.rerun()
            with col_list:
                st.markdown("##### 🛒 Carrinho de Entrada")
                if st.session_state["carrinho_entrada"]:
                    df_c = pd.DataFrame(st.session_state["carrinho_entrada"])
                    st.dataframe(df_c, hide_index=True, use_container_width=True, column_config={"custo": st.column_config.NumberColumn("R$", format="%.2f")})
                    st.markdown(f"**Total da Nota: R$ {df_c['total'].sum():,.2f}**")
                    
                    with st.form("save_e"):
                        nf = st.text_input("Número NF / Fornecedor")
                        if st.form_submit_button("✅ Processar Entrada", type="primary"):
                            if nf:
                                for i in st.session_state["carrinho_entrada"]:
                                    run_query("INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, custo_unitario, referencia) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", 
                                              ("Entrada", datetime.now().date(), "CENTRAL", i['cod'], i['desc'], i['qtd'], i['custo'], nf), False)
                                st.session_state["carrinho_entrada"] = []
                                st.toast("Entrada registrada com sucesso!", icon="🎉")
                                time.sleep(1); st.rerun()
                    if st.button("Limpar", key="cl1"): st.session_state["carrinho_entrada"] = []; st.rerun()
                else: st.info("Adicione itens à esquerda.")

        # -- SAÍDA --
        with tab2:
            col_form, col_list = st.columns([1, 2])
            with col_form:
                st.markdown("##### Novo Item")
                with st.form("add_s"):
                    is_ = st.selectbox("Material", opcoes, key="si")
                    qs = st.number_input("Quantidade", 0.01, key="sq")
                    if st.form_submit_button("⬇️ Adicionar"):
                        if is_:
                            st.session_state["carrinho_saida"].append({"cod": is_.split(" - ")[0], "desc": is_.split(" - ")[1], "qtd": qs})
                            st.rerun()
            with col_list:
                st.markdown("##### 🚛 Romaneio de Saída")
                if st.session_state["carrinho_saida"]:
                    st.dataframe(pd.DataFrame(st.session_state["carrinho_saida"]), hide_index=True, use_container_width=True)
                    with st.form("save_s"):
                        ob = st.text_input("Obra / Destino")
                        if st.form_submit_button("📤 Processar Saída", type="primary"):
                            if ob:
                                for i in st.session_state["carrinho_saida"]:
                                    run_query("INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, custo_unitario) VALUES (%s,%s,%s,%s,%s,%s,%s)", 
                                              ("Saída", datetime.now().date(), ob, i['cod'], i['desc'], i['qtd'], 0), False)
                                st.session_state["carrinho_saida"] = []
                                st.toast("Saída registrada!", icon="🚛")
                                time.sleep(1); st.rerun()
                    if st.button("Limpar", key="cl2"): st.session_state["carrinho_saida"] = []; st.rerun()
                else: st.info("Adicione itens à esquerda.")

        # -- AJUSTE --
        with tab3:
            col_form, col_list = st.columns([1, 2])
            with col_form:
                st.markdown("##### Correção")
                with st.form("add_a"):
                    ia = st.selectbox("Material", opcoes, key="ai")
                    qa = st.number_input("Diferença (+/-)", step=1.0, key="aq")
                    ma = st.text_input("Motivo", key="am")
                    if st.form_submit_button("⬇️ Adicionar"):
                        if ia and qa != 0:
                            st.session_state["carrinho_ajuste"].append({"cod": ia.split(" - ")[0], "desc": ia.split(" - ")[1], "qtd": qa, "motivo": ma})
                            st.rerun()
            with col_list:
                st.markdown("##### ⚖️ Itens de Balanço")
                if st.session_state["carrinho_ajuste"]:
                    st.dataframe(pd.DataFrame(st.session_state["carrinho_ajuste"]), hide_index=True, use_container_width=True)
                    if st.button("✅ Confirmar Ajustes", type="primary"):
                        for i in st.session_state["carrinho_ajuste"]:
                            tipo = "Ajuste(+)" if i['qtd'] > 0 else "Ajuste(-)"
                            run_query("INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, custo_unitario, referencia) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", 
                                      (tipo, datetime.now().date(), "BALANÇO", i['cod'], i['desc'], abs(i['qtd']), 0, i['motivo']), False)
                        st.session_state["carrinho_ajuste"] = []
                        st.toast("Estoque corrigido!", icon="✅"); time.sleep(1); st.rerun()
                    if st.button("Limpar", key="cl3"): st.session_state["carrinho_ajuste"] = []; st.rerun()
        
        # -- CADASTRO --
        with tab4:
            st.markdown("##### Novo Produto")
            with st.form("cad_n"):
                c1, c2, c3 = st.columns([1, 2, 1])
                cod = c1.text_input("Código (Ex: CIM-01)").upper()
                des = c2.text_input("Descrição").upper()
                und = c3.selectbox("Und", ["UNID", "KG", "M", "M2", "M3", "SC", "CX", "L"])
                if st.form_submit_button("💾 Salvar Produto"):
                    run_query("INSERT INTO produtos (codigo, descricao, unidade) VALUES (%s,%s,%s) ON CONFLICT (codigo) DO NOTHING", (cod, des, und), False)
                    st.toast("Produto Cadastrado!", icon="✨"); time.sleep(1); st.rerun()

    # --- PÁGINA: GERENCIAMENTO (HISTÓRICO) ---
    elif menu == "⚙️ Gerenciamento":
        st.title("Histórico & Auditoria")
        
        tab_h, tab_del = st.tabs(["📜 Histórico Completo", "🗑️ Exclusão (Admin)"])
        
        with tab_h:
            if not df_movs.empty:
                st.dataframe(df_movs, use_container_width=True, height=500)
            else: st.info("Sem histórico.")
            
        with tab_del:
            st.warning("⚠️ Área de Risco: Excluir um registro recalcula todo o saldo imediatamente.")
            col_del1, col_del2 = st.columns([1, 2])
            with col_del1:
                id_del = st.number_input("ID do Registro para Excluir", min_value=0)
                if st.button("❌ Excluir Definitivamente", type="primary"):
                    if id_del > 0:
                        run_query("DELETE FROM movimentacoes WHERE id = %s", (id_del,), False)
                        st.toast("Registro Apagado.", icon="🗑️"); time.sleep(1); st.rerun()
