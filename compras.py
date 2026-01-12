import streamlit as st
import psycopg2
import pandas as pd
import plotly.express as px
from datetime import datetime
import time

# -----------------------------------------------------------------------------
# 1. CONFIGURAÇÃO
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Amâncio Gestão Pro",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicializa as "Listas Temporárias" (Carrinhos) na memória
if "carrinho_entrada" not in st.session_state:
    st.session_state["carrinho_entrada"] = []
if "carrinho_saida" not in st.session_state:
    st.session_state["carrinho_saida"] = []

# -----------------------------------------------------------------------------
# 2. CONEXÃO (COM NOVA COLUNA DE CUSTO)
# -----------------------------------------------------------------------------
def run_query(query, params=None, fetch_data=True):
    conn = None
    try:
        conn = psycopg2.connect(
            st.secrets["db_url"],
            connect_timeout=10,
            gssencmode="disable"
        )
        if fetch_data:
            df = pd.read_sql(query, conn, params=params)
            return df
        else:
            with conn.cursor() as cur:
                cur.execute(query, params)
                conn.commit()
            return True
    except Exception as e:
        print(f"Erro SQL: {e}")
        if fetch_data: return pd.DataFrame()
        return False
    finally:
        if conn: conn.close()

# -----------------------------------------------------------------------------
# 3. AUTENTICAÇÃO
# -----------------------------------------------------------------------------
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

def login_screen():
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        st.markdown("<br><h1 style='text-align: center;'>🔐 Acesso Financeiro</h1>", unsafe_allow_html=True)
        with st.form("login_form"):
            u = st.text_input("Usuário")
            p = st.text_input("Senha", type="password")
            if st.form_submit_button("Acessar Sistema"):
                if u == st.secrets["auth"]["username"] and p == st.secrets["auth"]["password"]:
                    st.session_state["authenticated"] = True
                    st.rerun()
                else:
                    st.error("Acesso negado.")

# -----------------------------------------------------------------------------
# 4. SISTEMA PRINCIPAL
# -----------------------------------------------------------------------------
def main_system():
    # --- SIDEBAR ---
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/1063/1063196.png", width=60)
        st.markdown("### **Amâncio Obras**")
        st.caption("Versão Financeira 2.0")
        st.divider()
        menu = st.radio("Navegação:", ["📊 Dashboard Financeiro", "📦 Estoque & Preços", "🔄 Movimentações (Lote)", "⚙️ Histórico"])
        st.divider()
        if st.button("Sair"):
            st.session_state["authenticated"] = False
            st.rerun()

    # --- DADOS ---
    df_prods = run_query("SELECT codigo, descricao, unidade FROM produtos ORDER BY descricao")
    df_movs = run_query("SELECT * FROM movimentacoes ORDER BY data DESC, id DESC")

    # --- CÁLCULO DE SALDO E CUSTO MÉDIO ---
    saldo_atual = pd.DataFrame(columns=['Cod', 'Produto', 'Unid', 'Saldo', 'CustoMedio', 'ValorTotal'])
    
    if not df_prods.empty and not df_movs.empty:
        # 1. Calcular Saldo Físico
        df_calc = df_movs.copy()
        df_calc['fator'] = df_calc['tipo'].apply(lambda x: 1 if x in ['Entrada', 'Ajuste(+)'] else -1)
        df_calc['qtd_real'] = df_calc['quantidade'] * df_calc['fator']
        saldos = df_calc.groupby('codigo')['qtd_real'].sum().reset_index()

        # 2. Calcular Preço Médio (Baseado apenas nas Entradas)
        entradas = df_movs[df_movs['tipo'] == 'Entrada'].copy()
        entradas['total_gasto'] = entradas['quantidade'] * entradas['custo_unitario']
        
        # Agrupa gastos e quantidades compradas
        custos = entradas.groupby('codigo')[['quantidade', 'total_gasto']].sum().reset_index()
        custos['custo_medio'] = custos['total_gasto'] / custos['quantidade']
        
        # Junta tudo
        saldo_atual = pd.merge(df_prods, saldos, on='codigo', how='left').fillna(0)
        saldo_atual = pd.merge(saldo_atual, custos[['codigo', 'custo_medio']], on='codigo', how='left').fillna(0)
        
        # Calcula valor total em estoque
        saldo_atual['valor_estoque'] = saldo_atual['qtd_real'] * saldo_atual['custo_medio']
        
        # Renomeia
        saldo_atual.rename(columns={'qtd_real': 'Saldo', 'descricao': 'Produto', 'unidade': 'Unid', 'codigo': 'Cod'}, inplace=True)
    elif not df_prods.empty:
        saldo_atual = df_prods.copy()
        saldo_atual['Saldo'] = 0
        saldo_atual['custo_medio'] = 0
        saldo_atual['valor_estoque'] = 0
        saldo_atual.rename(columns={'descricao': 'Produto', 'unidade': 'Unid', 'codigo': 'Cod'}, inplace=True)

    # =========================================================================
    # TELA 1: DASHBOARD FINANCEIRO
    # =========================================================================
    if menu == "📊 Dashboard Financeiro":
        st.title("📊 Visão Financeira do Estoque")
        
        if not saldo_atual.empty:
            # MÉTRICAS
            total_itens = len(saldo_atual)
            valor_total = saldo_atual['valor_estoque'].sum()
            zerados = len(saldo_atual[saldo_atual['Saldo'] <= 0])
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Itens Cadastrados", total_itens)
            # Formatação de Moeda Brasileira
            c2.metric("💰 Valor em Estoque", f"R$ {valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            c3.metric("Estoque Zerado", zerados, delta_color="inverse")
            
            st.divider()
            
            col_g1, col_g2 = st.columns([2,1])
            with col_g1:
                st.subheader("💰 Onde está seu dinheiro? (Top 10)")
                if valor_total > 0:
                    top_val = saldo_atual.nlargest(10, 'valor_estoque')
                    fig = px.bar(top_val, x='valor_estoque', y='Produto', orientation='h', text_auto='.2s', color='valor_estoque', color_continuous_scale='Greens')
                    fig.update_layout(xaxis_title="Reais (R$)", yaxis_title=None)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Cadastre entradas com preços para ver os gráficos.")
            
            with col_g2:
                st.subheader("📋 Resumo Rápido")
                st.dataframe(
                    saldo_atual[['Produto', 'Saldo', 'valor_estoque']].sort_values('valor_estoque', ascending=False).head(10),
                    hide_index=True,
                    column_config={"valor_estoque": st.column_config.NumberColumn("Valor Total", format="R$ %.2f")}
                )

    # =========================================================================
    # TELA 2: ESTOQUE DETALHADO
    # =========================================================================
    elif menu == "📦 Estoque & Preços":
        st.title("📦 Tabela de Preços e Saldos")
        
        busca = st.text_input("🔍 Buscar:", placeholder="Nome do material...")
        
        if not saldo_atual.empty:
            df_show = saldo_atual.copy()
            if busca:
                df_show = df_show[df_show['Produto'].str.contains(busca, case=False)]
            
            st.dataframe(
                df_show[['Cod', 'Produto', 'Unid', 'Saldo', 'custo_medio', 'valor_estoque']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Saldo": st.column_config.NumberColumn("Qtd Física", format="%.2f"),
                    "custo_medio": st.column_config.NumberColumn("Custo Médio (Unit)", format="R$ %.2f"),
                    "valor_estoque": st.column_config.NumberColumn("Valor Total", format="R$ %.2f"),
                }
            )

    # =========================================================================
    # TELA 3: MOVIMENTAÇÕES EM LOTE (CARRINHO)
    # =========================================================================
    elif menu == "🔄 Movimentações (Lote)":
        st.title("🔄 Central de Operações")
        
        tab_ent, tab_sai, tab_cad = st.tabs(["📥 ENTRADA (Múltiplos Itens)", "📤 SAÍDA (Múltiplos Itens)", "🆕 CADASTRO"])
        
        # Lista para selects
        opcoes = []
        if not df_prods.empty:
            opcoes = [f"{r['codigo']} - {r['descricao']}" for i, r in df_prods.iterrows()]

        # --- ABA ENTRADA COM LISTA ---
        with tab_ent:
            c1, c2 = st.columns([1, 2])
            
            # Lado Esquerdo: Formulário de Adição
            with c1:
                st.markdown("##### 1. Adicionar Item na Lista")
                with st.form("add_ent_form", clear_on_submit=True):
                    item_e = st.selectbox("Material", opcoes)
                    qtd_e = st.number_input("Quantidade", min_value=0.01, step=1.0)
                    custo_e = st.number_input("Valor Unitário (R$)", min_value=0.0, step=0.10, format="%.2f")
                    
                    if st.form_submit_button("⬇️ Colocar na Lista"):
                        if item_e:
                            st.session_state["carrinho_entrada"].append({
                                "cod": item_e.split(" - ")[0],
                                "desc": item_e.split(" - ")[1],
                                "qtd": qtd_e,
                                "custo": custo_e,
                                "total": qtd_e * custo_e
                            })
                            st.rerun()

            # Lado Direito: A Lista e Finalização
            with c2:
                st.markdown("##### 2. Lista de Itens da Nota")
                if len(st.session_state["carrinho_entrada"]) > 0:
                    df_cart = pd.DataFrame(st.session_state["carrinho_entrada"])
                    st.dataframe(df_cart, hide_index=True, use_container_width=True,
                                column_config={"custo": st.column_config.NumberColumn("Unitário", format="R$ %.2f"),
                                               "total": st.column_config.NumberColumn("Total", format="R$ %.2f")})
                    
                    st.write(f"**Total da Nota: R$ {df_cart['total'].sum():,.2f}**")
                    
                    with st.form("finalizar_ent"):
                        nf = st.text_input("Número da NF / Fornecedor (Válido para todos os itens)")
                        if st.form_submit_button("✅ SALVAR TUDO NO ESTOQUE"):
                            if nf:
                                for item in st.session_state["carrinho_entrada"]:
                                    run_query(
                                        "INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, custo_unitario, referencia) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                                        ("Entrada", datetime.now().date(), "CENTRAL", item['cod'], item['desc'], item['qtd'], item['custo'], nf),
                                        fetch_data=False
                                    )
                                st.session_state["carrinho_entrada"] = [] # Limpa carrinho
                                st.success("Entrada em lote realizada!")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.warning("Preencha a NF/Fornecedor para finalizar.")
                    
                    if st.button("🗑️ Limpar Lista Entrada"):
                        st.session_state["carrinho_entrada"] = []
                        st.rerun()
                else:
                    st.info("Lista vazia. Adicione itens ao lado.")

        # --- ABA SAÍDA COM LISTA ---
        with tab_sai:
            c1, c2
