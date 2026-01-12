import streamlit as st
import psycopg2
import pandas as pd
from datetime import datetime
import time

# -----------------------------------------------------------------------------
# 1. CONFIGURAÇÃO DA PÁGINA
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Amâncio Obras",
    page_icon="🏗️",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# -----------------------------------------------------------------------------
# 2. FUNÇÃO DE LOGO INTELIGENTE (DEFINIDA AQUI FORA)
# -----------------------------------------------------------------------------
def logo_dinamica(width=120):
    # --- ÁREA DE CONFIGURAÇÃO DAS LOGOS ---
    
    # 1. Logo ESCURA (Preta/Azul) -> Aparece quando o fundo do site é BRANCO
    url_logo_preta = "COLE_AQUI_O_LINK_DA_LOGO_PRETA.png" 
    
    # 2. Logo CLARA (Branca) -> Aparece quando o fundo do site é PRETO
    # (Usei o link que você mandou aqui, assumindo que ela seja a branca)
    url_logo_branca = "https://media.discordapp.net/attachments/1287152284328919116/1459226633025224879/Design-sem-nome-1.png?ex=696676b4&is=69652534&hm=c105a8bc947734040e988154ecef4e88f57da98dc697ec9337f1df86d58ddcdb&=&format=webp&quality=lossless&width=600&height=158"
    
    # O HTML Mágico que troca as imagens
    st.markdown(f"""
    <style>
    /* Configuração Padrão (Modo Claro) */
    .logo-light-mode {{ display: block; margin: 0 auto; }}
    .logo-dark-mode  {{ display: none; margin: 0 auto; }}

    /* Se o computador for Modo Escuro */
    @media (prefers-color-scheme: dark) {{
        .logo-light-mode {{ display: none; }}
        .logo-dark-mode  {{ display: block; }}
    }}
    </style>
    
    <div style="display: flex; justify-content: center; margin-bottom: 20px;">
        <img src="{url_logo_preta}" class="logo-light-mode" width="{width}">
        <img src="{url_logo_branca}" class="logo-dark-mode" width="{width}">
    </div>
    """, unsafe_allow_html=True)

# Inicializa Variáveis de Sessão
if "carrinho_entrada" not in st.session_state: st.session_state["carrinho_entrada"] = []
if "carrinho_saida" not in st.session_state: st.session_state["carrinho_saida"] = []
if "carrinho_ajuste" not in st.session_state: st.session_state["carrinho_ajuste"] = []
if "authenticated" not in st.session_state: st.session_state["authenticated"] = False

# -----------------------------------------------------------------------------
# 3. ESTILO CSS GERAL
# -----------------------------------------------------------------------------
st.markdown("""
    <style>
    /* Centraliza títulos e imagens */
    .stImage { display: flex; justify-content: center; }
    h1, h2, h3 { text-align: center; }
    
    /* Melhora o visual do Login */
    .login-box {
        padding: 30px;
        border-radius: 15px;
        background-color: #f0f2f6;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    /* Botões */
    .stButton>button { width: 100%; border-radius: 8px; }
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 4. CONEXÃO BLINDADA
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
        if fetch_data: return pd.DataFrame()
        return False
    finally:
        if conn: conn.close()

# -----------------------------------------------------------------------------
# 5. CARREGAMENTO DE DADOS
# -----------------------------------------------------------------------------
df_prods = run_query("SELECT codigo, descricao, unidade FROM produtos ORDER BY descricao")
df_movs = run_query("SELECT * FROM movimentacoes ORDER BY data DESC, id DESC")

# Cálculo de Saldo
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
        saldo_atual['qtd_real'] = 0; saldo_atual['custo_medio'] = 0; saldo_atual['valor_estoque'] = 0
    saldo_atual.rename(columns={'qtd_real': 'Saldo', 'descricao': 'Produto', 'unidade': 'Unid', 'codigo': 'Cod'}, inplace=True)

# -----------------------------------------------------------------------------
# 6. TELA DE LOGIN (CENTRALIZADA)
# -----------------------------------------------------------------------------
if not st.session_state["authenticated"]:
    st.write(""); st.write("") # Espaço topo
    
    c_vazio1, c_login, c_vazio2 = st.columns([1, 2, 1])
    
    with c_login:
        # --- AQUI CHAMA A LOGO DINÂMICA ---
        logo_dinamica(width=250)
        
        st.markdown("<h2 style='text-align: center;'>Portal Amâncio</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: grey;'>Gestão de Estoque Inteligente</p>", unsafe_allow_html=True)
        st.markdown("---")
        
        with st.form("login_center"):
            u = st.text_input("Usuário")
            p = st.text_input("Senha", type="password")
            
            if st.form_submit_button("🔒 ACESSAR SISTEMA"):
                if u == st.secrets["auth"]["username"] and p == st.secrets["auth"]["password"]:
                    st.session_state["authenticated"] = True
                    st.rerun()
                else:
                    st.error("Acesso Negado")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        with st.expander("👀 Consultar Estoque (Sem Senha)"):
             st.caption("Visão rápida para Engenheiros e Mestres")
             if not saldo_atual.empty:
                busca = st.text_input("Buscar material...", placeholder="Ex: Cimento")
                df_pub = saldo_atual[['Produto', 'Saldo', 'Unid']].copy()
                if busca: df_pub = df_pub[df_pub['Produto'].str.contains(busca, case=False)]
                st.dataframe(df_pub, hide_index=True, use_container_width=True)
             else:
                st.info("Estoque vazio.")

# -----------------------------------------------------------------------------
# 7. ÁREA DO SISTEMA (LOGADO)
# -----------------------------------------------------------------------------
else:
    with st.sidebar:
        # --- LOGO DINÂMICA NA LATERAL TAMBÉM ---
        logo_dinamica(width=180)
        
        st.write(f"👤 **{st.secrets['auth']['username'].upper()}**")
        st.divider()
        menu = st.radio("Navegação", 
                        ["📊 Dashboard", "🔄 Operações (Lote)", "🗑️ Exclusões", "⚙️ Histórico"])
        st.divider()
        if st.button("Sair"):
            st.session_state["authenticated"] = False
            st.rerun()

    # --- CONTEÚDO PRINCIPAL ---
    
    if menu == "📊 Dashboard":
        st.title("📊 Visão Geral")
        if not saldo_atual.empty:
            total_money = saldo_atual['valor_estoque'].sum()
            zerados = len(saldo_atual[saldo_atual['Saldo'] <= 0])
            
            col1, col2 = st.columns(2)
            col1.metric("Valor em Estoque", f"R$ {total_money:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            col2.metric("Itens Zerados", zerados, delta_color="inverse")
            
            st.divider()
            st.subheader("Estoque Financeiro")
            st.dataframe(
                saldo_atual[['Produto', 'Saldo', 'Unid', 'custo_medio', 'valor_estoque']].sort_values('valor_estoque', ascending=False),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "custo_medio": st.column_config.NumberColumn("Custo Médio", format="R$ %.2f"),
                    "valor_estoque": st.column_config.NumberColumn("Total", format="R$ %.2f")
                }
            )

    elif menu == "🔄 Operações (Lote)":
        st.title("🔄 Central de Operações")
        
        tab_ent, tab_sai, tab_aj, tab_cad = st.tabs(["📥 ENTRADA", "📤 SAÍDA", "🔧 AJUSTE", "🆕 NOVO"])
        opcoes = [f"{r['codigo']} - {r['descricao']}" for i, r in df_prods.iterrows()] if not df_prods.empty else []

        # 1. ENTRADA
        with tab_ent:
            st.info("📦 Adicionar Compras")
            with st.form("add_ent"):
                c1, c2 = st.columns([2, 1])
                ie = c1.selectbox("Material", opcoes)
                qe = c2.number_input("Qtd", 0.01)
                ve = st.number_input("Preço Unitário (R$)", 0.0)
                if st.form_submit_button("⬇️ Adicionar à Lista"):
                    if ie:
                        st.session_state["carrinho_entrada"].append({
                            "cod": ie.split(" - ")[0], "desc": ie.split(" - ")[1], 
                            "qtd": qe, "custo": ve, "total": qe*ve
                        })
                        st.rerun()
            
            if st.session_state["carrinho_entrada"]:
                st.write("📝 **Lista para Lançar:**")
                st.dataframe(pd.DataFrame(st.session_state["carrinho_entrada"]), hide_index=True)
                with st.form("save_ent"):
                    nf = st.text_input("Fornecedor / Nota Fiscal")
                    if st.form_submit_button("✅ SALVAR ENTRADA"):
                        if nf:
                            for i in st.session_state["carrinho_entrada"]:
                                run_query("INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, custo_unitario, referencia) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", 
                                          ("Entrada", datetime.now().date(), "CENTRAL", i['cod'], i['desc'], i['qtd'], i['custo'], nf), False)
                            st.session_state["carrinho_entrada"] = []
                            st.success("Salvo!"); time.sleep(1); st.rerun()
                if st.button("Limpar Lista", key="cls_ent"): st.session_state["carrinho_entrada"] = []; st.rerun()

        # 2. SAÍDA
        with tab_sai:
            st.warning("🚀 Enviar para Obra")
            with st.form("add_sai"):
                c1, c2 = st.columns([2, 1])
                is_ = c1.selectbox("Material", opcoes, key="s_i")
                qs = c2.number_input("Qtd", 0.01, key="s_q")
                if st.form_submit_button("⬇️ Adicionar à Lista"):
                    if is_:
                        st.session_state["carrinho_saida"].append({
                            "cod": is_.split(" - ")[0], "desc": is_.split(" - ")[1], "qtd": qs
                        })
                        st.rerun()
            
            if st.session_state["carrinho_saida"]:
                st.write("📝 **Lista de Saída:**")
                st.dataframe(pd.DataFrame(st.session_state["carrinho_saida"]), hide_index=True)
                with st.form("save_sai"):
                    ob = st.text_input("Qual Obra?")
                    if st.form_submit_button("📤 BAIXAR DO ESTOQUE"):
                        if ob:
                            for i in st.session_state["carrinho_saida"]:
                                run_query("INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, custo_unitario) VALUES (%s,%s,%s,%s,%s,%s,%s)", 
                                          ("Saída", datetime.now().date(), ob, i['cod'], i['desc'], i['qtd'], 0), False)
                            st.session_state["carrinho_saida"] = []
                            st.success("Baixado!"); time.sleep(1); st.rerun()
                if st.button("Limpar Lista", key="cls_sai"): st.session_state["carrinho_saida"] = []; st.rerun()

        # 3. AJUSTE
        with tab_aj:
            st.error("🔧 Correção de Inventário")
            with st.form("add_aj"):
                c1, c2 = st.columns([2, 1])
                ia = c1.selectbox("Material", opcoes, key="a_i")
                qa = c2.number_input("Diferença (+ Sobra / - Falta)", step=1.0)
                mot = st.text_input("Motivo")
                if st.form_submit_button("⬇️ Incluir no Balanço"):
                    if ia and qa != 0:
                        st.session_state["carrinho_ajuste"].append({
                            "cod": ia.split(" - ")[0], "desc": ia.split(" - ")[1], "qtd": qa, "motivo": mot
                        })
                        st.rerun()
            
            if st.session_state["carrinho_ajuste"]:
                st.write("📝 **Itens para Ajustar:**")
                st.dataframe(pd.DataFrame(st.session_state["carrinho_ajuste"]), hide_index=True)
                if st.button("⚖️ PROCESSAR AJUSTES"):
                    for i in st.session_state["carrinho_ajuste"]:
                        tipo = "Ajuste(+)" if i['qtd'] > 0 else "Ajuste(-)"
                        run_query("INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, custo_unitario, referencia) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", 
                                  (tipo, datetime.now().date(), "BALANÇO", i['cod'], i['desc'], abs(i['qtd']), 0, i['motivo']), False)
                    st.session_state["carrinho_ajuste"] = []
                    st.success("Estoque Corrigido!"); time.sleep(1); st.rerun()
                if st.button("Limpar Lista", key="cls_aj"): st.session_state["carrinho_ajuste"] = []; st.rerun()

        # 4. CADASTRO
        with tab_cad:
            st.success("✨ Novo Item")
            with st.form("cad_new"):
                cod = st.text_input("Código (Ex: CIM-01)").upper()
                des = st.text_input("Descrição").upper()
                und = st.selectbox("Unidade", ["UNID", "KG", "M", "M2", "M3", "SC", "CX"])
                if st.form_submit_button("Salvar"):
                    run_query("INSERT INTO produtos (codigo, descricao, unidade) VALUES (%s,%s,%s) ON CONFLICT (codigo) DO NOTHING", (cod, des, und), False)
                    st.success("Cadastrado!"); time.sleep(1); st.rerun()

    elif menu == "🗑️ Exclusões":
        st.title("🗑️ Gerenciar Lançamentos")
        st.warning("Apagar um registro corrige o saldo automaticamente.")
        
        if not df_movs.empty:
            filtro = st.text_input("Filtrar Histórico:", placeholder="Digite o nome do material...")
            df_del = df_movs.copy()
            if filtro:
                df_del = df_del[df_del['descricao'].str.contains(filtro, case=False)]
            st.dataframe(df_del, use_container_width=True, hide_index=True)
            
            c1, c2 = st.columns([1, 2])
            with c1:
                id_del = st.number_input("ID para Apagar:", min_value=0, step=1)
            with c2:
                st.write(""); st.write("")
                if st.button("❌ EXCLUIR AGORA"):
                    if id_del > 0:
                        run_query("DELETE FROM movimentacoes WHERE id = %s", (id_del,), False)
                        st.success("Apagado!"); time.sleep(1); st.rerun()

    elif menu == "⚙️ Histórico":
        st.title("📜 Histórico Completo")
        st.dataframe(df_movs, use_container_width=True)
