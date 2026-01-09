import streamlit as st
import psycopg2
import pandas as pd
from datetime import datetime
import io

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Gestão de Estoque", page_icon="🏗️", layout="wide")

# 2. LOGO E CSS PERSONALIZADO
logo_url = "https://media.discordapp.net/attachments/1287152284328919116/1459226633025224879/Design-sem-nome-1.png?ex=69628234&is=696130b4&hm=460d0214e433068507b61d26f3ae1957e36d7a9480bf97e899ef3ae70303f294&=&format=webp&quality=lossless&width=600&height=158"

st.markdown("""
    <style>
    /* Cards de métricas com cores adaptáveis */
    div[data-testid="metric-container"] {
        background-color: rgba(151, 166, 195, 0.15);
        padding: 20px; border-radius: 12px; border: 1px solid rgba(151, 166, 195, 0.2);
    }
    /* Rodapé fixo */
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; text-align: center; font-size: 12px; color: #888; background: rgba(255,255,255,0.9); padding: 5px; z-index: 100; }
    /* Estilo Sidebar */
    section[data-testid="stSidebar"] { background-color: #1e293b; }
    section[data-testid="stSidebar"] * { color: white !important; }
    </style>
    """, unsafe_allow_html=True)

# 3. CONEXÃO COM O BANCO
def get_connection():
    try:
        return psycopg2.connect(st.secrets["db_url"])
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return None

# 4. LÓGICA DE LOGIN
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

# 5. SIDEBAR
with st.sidebar:
    st.image(logo_url, width=235)
    st.title("Controle Amâncio")
    st.markdown("---")
    
    if not st.session_state["authenticated"]:
        with st.expander("🔐 Acesso Restrito"):
            u = st.text_input("Usuário")
            p = st.text_input("Senha", type="password")
            if st.button("Entrar"):
                if u == st.secrets["auth"]["username"] and p == st.secrets["auth"]["password"]:
                    st.session_state["authenticated"] = True
                    st.rerun()
                else:
                    st.error("Dados inválidos")
        menu = st.radio("Menu:", ["📊 Painel de Saldos"])
    else:
        st.success(f"Olá, {st.secrets['auth']['username']}!")
        menu = st.radio("Menu:", ["📊 Painel de Saldos", "📦 Cadastrar Material", "📥 Registrar Entrada", "📤 Registrar Saída"])
        if st.button("Encerrar Sessão"):
            st.session_state["authenticated"] = False
            st.rerun()
    
    st.markdown("---")
    st.caption("v3.0 - Monitoramento Ativo")

# 6. ABAS DO SISTEMA
if menu == "📊 Painel de Saldos":
    st.title("📊 Painel de Controle de Estoque")
    
    conn = get_connection()
    if conn:
        df_mov = pd.read_sql("SELECT * FROM movimentacoes", conn)
        conn.close()
        
        if not df_mov.empty:
            # Cálculo de Saldo
            df_mov['calculo'] = df_mov.apply(lambda x: x['quantidade'] if x['tipo'] == 'Entrada' else -x['quantidade'], axis=1)
            saldo_df = df_mov.groupby(['codigo', 'descricao'])['calculo'].sum().reset_index()
            saldo_df.columns = ['Cód', 'Descrição', 'Saldo Atual']
            
            # Métricas em destaque
            m1, m2, m3 = st.columns(3)
            m1.metric("Itens Ativos", len(saldo_df))
            m2.metric("Movimentações (Mês)", len(df_mov))
            # Alerta Crítico
            criticos = len(saldo_df[saldo_df['Saldo Atual'] < 5])
            m3.metric("Itens Críticos (< 5 un)", criticos, delta=-criticos, delta_color="inverse")

            # Gráfico de Consumo (O que mais sai)
            st.markdown("### 📈 Materiais Mais Utilizados")
            saidas_df = df_mov[df_mov['tipo'] == 'Saída'].groupby('descricao')['quantidade'].sum().sort_values(ascending=False).head(5)
            st.bar_chart(saidas_df)

            # Tabela com Formatação Condicional
            st.markdown("### 📋 Inventário Atual")
            
            def highlight_low_stock(val):
                color = 'red' if val < 5 else 'none'
                return f'color: {color}; font-weight: bold' if val < 5 else ''

            st.dataframe(saldo_df.style.applymap(highlight_low_stock, subset=['Saldo Atual']), use_container_width=True, hide_index=True)

            # Botão de Exportação
            csv = saldo_df.to_csv(index=False).encode('utf-8')
            st.download_button(label="📥 Baixar Inventário (Excel/CSV)", data=csv, file_name=f'estoque_{datetime.now().strftime("%d_%m")}.csv', mime='text/csv')
        else:
            st.info("Nenhuma movimentação registrada no banco.")

elif menu == "📦 Cadastrar Material":
    st.header("📦 Novo Material")
    with st.form("cad"):
        c1, c2 = st.columns(2)
        cod = c1.text_input("Código do Item")
        des = c2.text_input("Descrição Completa")
        if st.form_submit_button("Salvar Cadastro"):
            if cod and des:
                conn = get_connection(); cur = conn.cursor()
                cur.execute("INSERT INTO produtos (codigo, descricao) VALUES (%s, %s) ON CONFLICT (codigo) DO NOTHING", (cod, des))
                conn.commit(); cur.close(); conn.close()
                st.success("Item cadastrado com sucesso!")

elif menu == "📥 Registrar Entrada":
    st.header("📥 Entrada de NF / Compra")
    conn = get_connection()
    prods = pd.read_sql("SELECT * FROM produtos ORDER BY descricao", conn)
    conn.close()
    
    with st.form("ent"):
        item = st.selectbox("Selecione o Insumo", prods['codigo'] + " - " + prods['descricao']) if not prods.empty else "Nenhum"
        c1, c2 = st.columns(2)
        qtd = c1.number_input("Quantidade Recebida", min_value=0.01)
        obra = c2.text_input("Obra / Fornecedor")
        ref = st.text_input("Número da NF ou Ordem de Compra")
        if st.form_submit_button("Confirmar Entrada"):
            conn = get_connection(); cur = conn.cursor()
            cur.execute("INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, referencia) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                       ("Entrada", datetime.now().date(), obra, item.split(" - ")[0], item.split(" - ")[1], qtd, ref))
            conn.commit(); cur.close(); conn.close()
            st.success("Estoque atualizado!")

elif menu == "📤 Registrar Saída":
    st.header("📤 Saída para Obra")
    conn = get_connection()
    prods = pd.read_sql("SELECT * FROM produtos ORDER BY descricao", conn)
    conn.close()
    
    with st.form("sai"):
        item = st.selectbox("Selecione o Insumo", prods['codigo'] + " - " + prods['descricao']) if not prods.empty else "Nenhum"
        c1, c2 = st.columns(2)
        qtd = c1.number_input("Quantidade Retirada", min_value=0.01)
        obra = c2.text_input("Destino (Frente de Obra)")
        resp = st.text_input("Quem retirou? (Responsável)")
        if st.form_submit_button("Registrar Saída"):
            conn = get_connection(); cur = conn.cursor()
            cur.execute("INSERT INTO movimentacoes (tipo, data, obra, codigo, descricao, quantidade, referencia) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                       ("Saída", datetime.now().date(), obra, item.split(" - ")[0], item.split(" - ")[1], qtd, f"Retirado por: {resp}"))
            conn.commit(); cur.close(); conn.close()
            st.warning(f"Saída de {qtd} registrada!")

# 7. RODAPÉ
st.markdown('<div class="footer">Desenvolvido por Claudio Boni Junior - Gestão Inteligente de Obras</div>', unsafe_allow_html=True)

